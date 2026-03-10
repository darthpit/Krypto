"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  REINFORCEMENT LEARNING AGENT (FAZA 4)                                       ║
║  PPO (Proximal Policy Optimization) Trading Environment                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Ten moduł implementuje kompletne środowisko RL do treningu bota tradingowego.

ARCHITEKTURA:
─────────────────────────────────────────────────────────────────────────────
1. TradingEnv (Gymnasium Environment)
   - Symuluje giełdę MEXC z prowizjami, spreadem, funding fees
   - Przetwarza dane historyczne jako "planszę do gry"
   - Oblicza nagrody/kary na podstawie PnL i zarządzania ryzykiem

2. PPOAgent (Wrapper dla Stable-Baselines3)
   - Implementuje algorytm PPO
   - Trenuje na milionach epizodów
   - Zapisuje/ładuje modele

3. Reward Function (Kluczowa logika)
   - +100: Zysk > 2% (dobry trade)
   - +10: Zysk 0-2% (ok trade)
   - -50: Strata > 2% (zły trade)
   - -10: Strata 0-2% (ok, stop loss działa)
   - -100: Drawdown > 20% (katastrofa!)
   - -1: Za każdy krok z otwartą pozycją (kara za trzymanie w nieskończoność)

WORKFLOW:
─────────────────────────────────────────────────────────────────────────────
TRENING:
1. Załaduj 6 miesięcy danych historycznych (OHLCV + indicators)
2. Stwórz TradingEnv z tymi danymi
3. Uruchom PPO training (100k-1M steps)
4. Agent rozgrywa miliony wirtualnych transakcji
5. Zapisz wytrenowany model

VALIDATION:
1. Załaduj nowe dane (kolejny miesiąc)
2. Uruchom wytrenowanego agenta (bez uczenia)
3. Sprawdź performance (PnL, Sharpe Ratio, Max Drawdown)

PRODUKCJA:
1. Agent dostaje obecny stan rynku
2. Zwraca decyzję: HOLD/LONG/SHORT
3. process_trader.py wykonuje akcję
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback

from ..utils.logger import log


# ═══════════════════════════════════════════════════════════════════════════
# 1. TRADING ENVIRONMENT (Gym/Gymnasium)
# ═══════════════════════════════════════════════════════════════════════════

class TradingEnv(gym.Env):
    """
    Środowisko giełdowe zgodne z Gymnasium API.
    
    OBSERVATION SPACE (State):
    ─────────────────────────────────────────────────────────────────────────
    - Technical Indicators: RSI, MACD, ATR, Volume, etc. (19 features)
    - LSTM Prediction: Prawdopodobieństwo wzrostu (0-1)
    - LSTM Confidence: Pewność predykcji (0-1)
    - Portfolio State:
      * Position: -1 (SHORT), 0 (NEUTRAL), +1 (LONG)
      * Entry Price: Cena wejścia w pozycję
      * Position Size: Wielkość pozycji w USDT
      * Current PnL: % zysku/straty
      * Balance: Aktualny kapitał
      * Drawdown: % spadku od szczytu
    
    ACTION SPACE:
    ─────────────────────────────────────────────────────────────────────────
    - 0: HOLD (Trzymaj obecną pozycję lub czekaj)
    - 1: OPEN_LONG (Kup)
    - 2: OPEN_SHORT (Sprzedaj)
    - 3: CLOSE (Zamknij pozycję)
    
    REWARD FUNCTION (NOWA ZDROWA LOGIKA):
    ─────────────────────────────────────────────────────────────────────────
    FILOZOFIA: Model ma budżet podzielony na 10 części (każda transakcja = 10% budżetu).
    Przy skuteczności 55% LSTM, agent powinien zarabiać. Cel: 90% skuteczności.
    
    NAGRODY I KARY:
    
    1. OTWARCIE POZYCJI (action=1 lub 2):
       - Samo otwarcie: 0 punktów (brak nagrody/kary)
       
    2. NATYCHMIASTOWY KIERUNEK (pierwszy krok po otwarciu):
       - Jeśli PnL > 0 (od razu w zyskownym kierunku): +10 punktów ✅
       - Jeśli PnL ≤ 0 (nie idzie w zyskownym kierunku): -5 punktów ⚠️
       
    3. ZAMKNIĘCIE POZYCJI (action=3):
       a) Zysk > +2.5%: +150 punktów (DUŻA NAGRODA! 💰)
       b) Zysk 0% do +2.5%: 0 punktów (za mały zysk, brak nagrody)
       c) Strata (< 0%): KARA proporcjonalna do straty:
          - Strata 0% do -2%: -30 punktów
          - Strata -2% do -5%: -80 punktów
          - Strata > -5%: -150 punktów (DUŻA KARA!)
       
    4. KARY ZA DRAWDOWN (ochrona kapitału):
       - Drawdown > 40%: -2.0 per step (bardzo źle!)
       - Drawdown > 30%: -1.0 per step (źle!)
       - Drawdown > 20%: -0.3 per step (uwaga!)
       - Drawdown > 10%: -0.05 per step (lekkie ostrzeżenie)
       
    5. BANKRUPTCY (balance ≤ 0):
       - Natychmiastowe zakończenie epizodu
       - Kara: -200 punktów (GAME OVER!)
       
    6. BONUS ZA NOWY SZCZYT KAPITAŁU:
       - Każdy nowy peak balance: +2.0 punktów (motywacja do wzrostu!)
       
    DLACZEGO TA LOGIKA DZIAŁA:
    - Motywuje do zyskownych transakcji (>2.5% = +150 pkt)
    - Karze za straty proporcjonalnie
    - Nie karze za samo otwieranie/zamykanie
    - Nagroda za natychmiastowy dobry kierunek (+10 pkt)
    - Kara za zły timing (-5 pkt)
    - Przy 55% accuracy LSTM + dobry PPO timing = rentowność
    - Cel: 90% accuracy = wysokie zyski
    """
    
    metadata = {'render.modes': ['human']}
    
    def __init__(
        self,
        df: pd.DataFrame,
        initial_balance: float = 1000.0,
        leverage: int = 20,
        trading_fee: float = 0.0006,  # 0.06% (maker+taker MEXC)
        spread: float = 0.0002,  # 0.02% spread
        funding_rate_hourly: float = 0.0001,  # 0.01% per hour
        lstm_predictions: Optional[pd.Series] = None,
        lstm_confidences: Optional[pd.Series] = None,
        max_episode_steps: Optional[int] = None,
    ):
        """
        Args:
            df: DataFrame z danymi historycznymi (OHLCV + indicators)
            initial_balance: Początkowy kapitał (USDT)
            leverage: Dźwignia (20x dla MEXC Futures)
            trading_fee: Prowizja za otwarcie/zamknięcie (0.06%)
            spread: Spread bid-ask (0.02%)
            funding_rate_hourly: Funding rate per hour (0.01%)
            lstm_predictions: Predykcje z obecnego modelu LSTM (optional)
            lstm_confidences: Confidence scores z LSTM (optional)
            max_episode_steps: Max kroków w epizodzie (None = całe dane)
        """
        super(TradingEnv, self).__init__()
        
        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.trading_fee = trading_fee
        self.spread = spread
        self.funding_rate_hourly = funding_rate_hourly
        self.max_episode_steps = max_episode_steps
        
        # LSTM predictions (jeśli dostępne)
        self.lstm_predictions = lstm_predictions
        self.lstm_confidences = lstm_confidences
        
        # Feature columns (19 technical indicators)
        self.feature_cols = [
            'rsi', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
            'market_correlation', 'bulls_bears_ratio', 'market_strength',
            'volume_sma_ratio', 'obv_ratio', 'mfi',
            'atr_pct', 'bb_width',
            'roc', 'stoch_k', 'stoch_d',
            'funding_rate', 'funding_rate_trend',
            'price_change_pct', 'volatility'
        ]
        
        # Ensure all features exist
        for col in self.feature_cols:
            if col not in self.df.columns:
                self.df[col] = 0.0
        
        # --- FEATURE SCALING (StandardScaler Manual Implementation) ---
        # Calculate mean/std for normalization to prevent gradient explosion
        # and ensure consistent input scaling for the neural network
        self.feature_stats = {}
        for col in self.feature_cols:
            self.feature_stats[col] = {
                'mean': self.df[col].mean(),
                'std': self.df[col].std() + 1e-8  # Avoid division by zero
            }

        # State dimensions
        n_features = len(self.feature_cols)
        n_lstm_features = 2 if lstm_predictions is not None else 0
        n_portfolio_features = 7  # position, entry, size, pnl, balance, drawdown, steps_in_pos
        state_dim = n_features + n_lstm_features + n_portfolio_features
        
        # Observation space: [features, lstm, portfolio]
        # Using -1 to 1 range implies we should use Tanh activation or ensure inputs are scaled
        self.observation_space = spaces.Box(
            low=-5.0, # Soft bounds for normalized data
            high=5.0,
            shape=(state_dim,),
            dtype=np.float32
        )
        
        # Action space: 0=HOLD, 1=LONG, 2=SHORT, 3=CLOSE
        self.action_space = spaces.Discrete(4)
        
        # Episode tracking
        self.current_step = 0
        self.max_steps = len(df) - 1
        
        # Portfolio state
        self.balance = initial_balance
        self.peak_balance = initial_balance
        self.position = 0  # -1=SHORT, 0=NEUTRAL, +1=LONG
        self.entry_price = 0.0
        self.position_size = 0.0  # USDT value
        self.steps_in_position = 0
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0  # NEW: Track losing trades
        self.total_pnl = 0.0
        self.episode_history = []
        self.trade_history = []  # NEW: Track all trades for analysis
        
    def reset(self, seed=None, options=None):
        """Reset environment to początkowego stanu."""
        super().reset(seed=seed)
        
        # Determine start step
        if self.max_episode_steps and len(self.df) > self.max_episode_steps:
            # Random start for training diversity
            max_start = len(self.df) - self.max_episode_steps - 1
            if max_start > 0:
                self.current_step = np.random.randint(0, max_start)
            else:
                self.current_step = 0
        else:
            # Full sequence for validation
            self.current_step = 0
            
        self.start_step = self.current_step
        self.steps_in_episode = 0
        
        self.balance = self.initial_balance
        self.peak_balance = self.initial_balance
        self.position = 0
        self.entry_price = 0.0
        self.position_size = 0.0
        self.steps_in_position = 0
        
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.trade_history = []
        
        # DEBUG: Log episode start
        if not hasattr(self, '_episode_count'):
            self._episode_count = 0
        self._episode_count += 1
        
        # Log every 100th episode to avoid spam
        if self._episode_count % 100 == 0:
            log(f"🔄 PPO Episode #{self._episode_count} started | "
                f"Dataset: {len(self.df)} candles | "
                f"Max Episode Steps: {self.max_episode_steps if self.max_episode_steps else 'None (full dataset)'}", 
                "INFO", ppo_only=True)
        
        return self._get_observation(), {}
    
    def step(self, action: int):
        """
        Wykonuje akcję i zwraca (observation, reward, done, truncated, info).
        
        Args:
            action: 0=HOLD, 1=LONG, 2=SHORT, 3=CLOSE
            
        Returns:
            observation: Nowy stan środowiska
            reward: Nagroda za akcję
            terminated: Czy epizod się zakończył (bankructwo)
            truncated: Czy osiągnięto max steps
            info: Dodatkowe informacje
        """
        current_price = self.df.loc[self.current_step, 'close']
        reward = 0.0
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 1: Aktualizuj PnL dla otwartej pozycji
        # ═══════════════════════════════════════════════════════════════════
        if self.position != 0:
            pnl_pct = self._calculate_pnl_pct(current_price)
            
            # Funding fee cost (co 8 godzin = 480 świeczek 1min)
            if self.steps_in_position > 0 and self.steps_in_position % 480 == 0:
                funding_cost = self.position_size * self.funding_rate_hourly * 8
                self.balance -= funding_cost
            
            # ═══════════════════════════════════════════════════════════════════
            # IMMEDIATE DIRECTION REWARD (ONLY ON FIRST STEP AFTER OPENING)
            # ═══════════════════════════════════════════════════════════════
            # "Jeżeli wejdzie i od razu transakcja leci w zyskownym kierunku... +10 punktów"
            # "Jeżeli nie idzie w zyskownym kierunku po otwarciu to -5 puntków"
            if self.steps_in_position == 1:  # FIXED: Check on step 1 (right after opening)
                if pnl_pct > 0:
                    reward += 10.0  # ✅ Going in profitable direction
                else:
                    reward -= 5.0   # ⚠️ Not going in profitable direction
            
            # AI Alignment Bonus (Reward for following the Ensemble Model)
            if self.lstm_predictions is not None:
                try:
                    current_pred = self.lstm_predictions.iloc[self.current_step] if self.current_step < len(self.lstm_predictions) else 0.5
                    # If Strong UP signal (>0.7) and we are LONG -> Bonus
                    if current_pred > 0.7 and self.position == 1:
                        reward += 0.05
                    # If Strong DOWN signal (<0.3) and we are SHORT -> Bonus
                    elif current_pred < 0.3 and self.position == -1:
                        reward += 0.05
                except:
                    pass

            self.steps_in_position += 1
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 2: Wykonaj akcję
        # ═══════════════════════════════════════════════════════════════════
        if action == 0:  # HOLD
            pass  # Nie rób nic
            
        elif action == 1:  # OPEN LONG
            if self.position == 0:  # Tylko jeśli nie ma pozycji
                reward += self._open_position(current_price, "LONG")
            # No penalty for trying to open when already in position (agent learning)
                
        elif action == 2:  # OPEN SHORT
            if self.position == 0:
                reward += self._open_position(current_price, "SHORT")
            # No penalty for trying to open when already in position (agent learning)
                
        elif action == 3:  # CLOSE
            if self.position != 0:
                reward += self._close_position(current_price)
            # No penalty for trying to close when no position (agent learning)
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 3: Sprawdź drawdown i warunki zakończenia
        # ═══════════════════════════════════════════════════════════════════
        drawdown_pct = ((self.peak_balance - self.balance) / self.peak_balance) * 100
        
        # ═══════════════════════════════════════════════════════════════════
        # DRAWDOWN PENALTIES (NOWA LOGIKA - Proporcjonalna kara)
        # ═══════════════════════════════════════════════════════════════════
        if drawdown_pct > 40:
            reward -= 2.0  # Bardzo źle! (risk of bankruptcy)
        elif drawdown_pct > 30:
            reward -= 1.0  # Źle! (high risk)
        elif drawdown_pct > 20:
            reward -= 0.3  # Uwaga! (moderate risk)
        elif drawdown_pct > 10:
            reward -= 0.05  # Lekkie ostrzeżenie
        
        # ═══════════════════════════════════════════════════════════════════
        # BONUS ZA NOWY SZCZYT KAPITAŁU (Motywacja do wzrostu!)
        # ═══════════════════════════════════════════════════════════════════
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
            reward += 2.0  # 🎉 Nowy szczyt! Motywacja do dalszego wzrostu
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 4: Sprawdź warunki zakończenia epizodu
        # ═══════════════════════════════════════════════════════════════════
        self.current_step += 1
        self.steps_in_episode += 1
        
        terminated = False  # Bankructwo
        truncated = False   # Koniec danych / limit kroków
        
        # ═══════════════════════════════════════════════════════════════════
        # BANKRUPTCY CHECK (Balance ≤ 0 = GAME OVER)
        # ═══════════════════════════════════════════════════════════════════
        if self.balance <= 0:  # Bankruptcy: 0 kapitału lub mniej
            terminated = True
            reward -= 200  # ❌ DUŻA KARA za bankructwo (GAME OVER!)
            log(f"💀 RL Episode TERMINATED: Bankructwo! Balance={self.balance:.2f}", "ERROR")
        
        # Koniec danych lub limit kroków epizodu
        data_ended = self.current_step >= len(self.df) - 1
        episode_limit_reached = (self.max_episode_steps is not None) and (self.steps_in_episode >= self.max_episode_steps)
        
        if data_ended or episode_limit_reached:
            truncated = True
            # Zamknij otwarte pozycje
            if self.position != 0:
                reward += self._close_position(current_price, forced=True)
            
            # DEBUG: Log episode end every 100 episodes
            if hasattr(self, '_episode_count') and self._episode_count % 100 == 0:
                reason = "data_ended" if data_ended else "step_limit_reached"
                log(f"🏁 PPO Episode #{self._episode_count} ended ({reason}) | "
                    f"Steps: {self.steps_in_episode} | "
                    f"Trades: {self.total_trades} (W:{self.winning_trades}, L:{self.losing_trades}) | "
                    f"Balance: ${self.balance:.2f} | "
                    f"Total Reward: {reward:.2f}", 
                    "INFO", ppo_only=True)
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 5: Zwróć wyniki
        # ═══════════════════════════════════════════════════════════════════
        observation = self._get_observation()
        info = {
            'balance': self.balance,
            'position': self.position,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,  # NEW: Losing trades stat
            'win_rate': self.winning_trades / max(self.total_trades, 1),
            'loss_rate': self.losing_trades / max(self.total_trades, 1),  # NEW: Loss rate
            'total_pnl': self.total_pnl,
            'drawdown_pct': drawdown_pct,
        }
        
        return observation, reward, terminated, truncated, info
    
    def _get_observation(self) -> np.ndarray:
        """Zwraca obecny stan środowiska jako observation vector (Normalized)."""
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1
        
        # 1. Technical indicators (19 features) - NORMALIZED
        raw_features = self.df.loc[self.current_step, self.feature_cols].values.astype(np.float32)
        features = []

        # Apply normalization (Z-score scaling)
        for i, col in enumerate(self.feature_cols):
            val = raw_features[i]
            mean = self.feature_stats[col]['mean']
            std = self.feature_stats[col]['std']
            norm_val = (val - mean) / std
            # Clip to range [-5, 5] to avoid outliers breaking the model
            norm_val = np.clip(norm_val, -5.0, 5.0)
            features.append(norm_val)
        
        features = np.array(features, dtype=np.float32)
        
        # 2. LSTM predictions (if available) - already 0-1 range
        lstm_features = []
        if self.lstm_predictions is not None:
            pred = self.lstm_predictions.iloc[self.current_step] if self.current_step < len(self.lstm_predictions) else 0.5
            conf = self.lstm_confidences.iloc[self.current_step] if self.lstm_confidences is not None and self.current_step < len(self.lstm_confidences) else 0.5

            # Normalize to -1 to 1 range for better NN performance
            pred_norm = (pred - 0.5) * 2.0  # 0..1 -> -1..1
            conf_norm = (conf - 0.5) * 2.0  # 0..1 -> -1..1
            lstm_features = [pred_norm, conf_norm]
        else:
            # Consistent dimension if no LSTM
            lstm_features = [0.0, 0.0]
        
        # 3. Portfolio state (7 features) - FIXED NORMALIZATION
        current_price = self.df.loc[self.current_step, 'close']
        pnl_pct = self._calculate_pnl_pct(current_price) if self.position != 0 else 0.0
        drawdown_pct = ((self.peak_balance - self.balance) / self.peak_balance) * 100
        
        # Robust Normalization
        # Entry price: relative distance from current price (0 if no position)
        entry_price_norm = 0.0
        if self.position != 0 and self.entry_price > 0:
             # Log-distance is better for prices
             entry_price_norm = np.log(current_price / self.entry_price) * 100 # ~ percentage diff

        # Balance: normalized log scale relative to initial
        balance_norm = np.log(self.balance / self.initial_balance)

        # Position Size: normalized by current balance * leverage (0.0 to 1.0 usage)
        size_norm = 0.0
        if self.balance > 0:
            size_norm = self.position_size / (self.balance * self.leverage)

        portfolio_features = [
            float(self.position),          # -1, 0, +1
            entry_price_norm,              # Normalized price distance
            size_norm,                     # Normalized size usage
            pnl_pct / 10.0,                # Normalized PnL (scale down: 10% -> 1.0)
            balance_norm,                  # Normalized balance
            drawdown_pct / 20.0,           # Normalized drawdown (20% -> 1.0)
            np.log1p(self.steps_in_position) / 3.0 # Log scale steps (0-3 range roughly)
        ]
        
        # Combine all features
        observation = np.concatenate([features, lstm_features, portfolio_features]).astype(np.float32)
        
        # Final safety check for NaN/Inf
        observation = np.nan_to_num(observation, nan=0.0, posinf=5.0, neginf=-5.0)

        return observation
    
    def _open_position(self, price: float, side: str) -> float:
        """
        Otwiera pozycję LONG lub SHORT.
        
        Returns:
            reward: Nagroda za otwarcie (domyślnie 0, ale może być bonus)
        """
        # Position sizing: 10% balance z leverage
        risk_amount = self.balance * 0.10  # 10% na trade
        self.position_size = risk_amount * self.leverage
        
        # Trading fee
        fee = self.position_size * self.trading_fee
        self.balance -= fee
        
        # Spread cost
        spread_cost = self.position_size * self.spread
        self.balance -= spread_cost
        
        # Set position
        self.position = 1 if side == "LONG" else -1
        self.entry_price = price
        self.steps_in_position = 0
        
        # FIXED: No reward/penalty for just opening
        return 0.0
    
    def _close_position(self, price: float, forced: bool = False) -> float:
        """
        Zamyka otwartą pozycję i oblicza reward.
        
        Args:
            price: Cena zamknięcia
            forced: Czy zamknięcie wymuszone (koniec epizodu)
            
        Returns:
            reward: Nagroda za trade
        """
        # Calculate PnL
        pnl_pct = self._calculate_pnl_pct(price)
        pnl_usdt = (self.position_size * pnl_pct) / 100.0
        
        # Trading fee
        fee = self.position_size * self.trading_fee
        spread_cost = self.position_size * self.spread
        total_cost = fee + spread_cost
        
        # Net PnL
        net_pnl = pnl_usdt - total_cost
        self.balance += net_pnl
        self.total_pnl += net_pnl
        
        # Update stats
        self.total_trades += 1
        if net_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1  # NEW: Track losses
        
        # NEW: Record trade details for analysis
        trade_record = {
            'step': self.current_step,
            'position_type': 'LONG' if self.position == 1 else 'SHORT',
            'entry_price': self.entry_price,
            'exit_price': price,
            'pnl_pct': pnl_pct,
            'pnl_usdt': net_pnl,
            'duration_steps': self.steps_in_position,
            'is_winner': net_pnl > 0,
            'forced_close': forced
        }
        self.trade_history.append(trade_record)
        
        # ═══════════════════════════════════════════════════════════════════
        # REWARD CALCULATION (NAPRAWA LOGIKI - BRAK MARTWYCH STREF)
        # ═══════════════════════════════════════════════════════════════════
        # Nowa logika: Nagroda jest ciągła i proporcjonalna do PnL.
        # Eliminujemy "martwą strefę" 0-2.5%, która zabijała scalping.

        reward = 0.0
        
        # 1. Base PnL Reward (Continuous)
        # Example: 1% gain = +10 pts, 2.5% gain = +25 pts
        reward = pnl_pct * 10.0
        
        # 2. Bonus for "Home Runs" (Big Wins)
        if pnl_pct > 2.5:
            reward += 50.0  # Extra bonus for hitting the big target

        # 3. Penalty Multiplier for Losses (Asymmetry: Losses hurt more)
        if pnl_pct < 0:
            reward = pnl_pct * 15.0 # Losses hurt 1.5x more than gains feel good

        # 4. Strict Stop Loss Penalty (if stopped out hard)
        if forced and pnl_pct < -2.0:
            reward -= 50.0 # Extra penalty for hitting hard stop or liquidation

        # 5. Time Penalty (slight decay to encourage efficiency)
        # Handled in step() function via -0.01 per step, no need to add here
        
        # Reset position
        self.position = 0
        self.entry_price = 0.0
        self.position_size = 0.0
        self.steps_in_position = 0
        
        return reward
    
    def _calculate_pnl_pct(self, current_price: float) -> float:
        """Oblicza % PnL dla otwartej pozycji."""
        if self.position == 0:
            return 0.0
        
        if self.position == 1:  # LONG
            return ((current_price - self.entry_price) / self.entry_price) * 100 * self.leverage
        else:  # SHORT
            return ((self.entry_price - current_price) / self.entry_price) * 100 * self.leverage
    
    def render(self, mode='human'):
        """Renderuje stan środowiska (opcjonalne)."""
        current_price = self.df.loc[self.current_step, 'close']
        pnl_pct = self._calculate_pnl_pct(current_price) if self.position != 0 else 0.0
        
        print(f"\n{'='*60}")
        print(f"Step: {self.current_step}/{self.max_steps}")
        print(f"Price: ${current_price:.2f}")
        print(f"Balance: ${self.balance:.2f} (Peak: ${self.peak_balance:.2f})")
        print(f"Position: {['SHORT', 'NEUTRAL', 'LONG'][self.position + 1]}")
        if self.position != 0:
            print(f"Entry: ${self.entry_price:.2f}")
            print(f"Size: ${self.position_size:.2f}")
            print(f"PnL: {pnl_pct:+.2f}%")
        print(f"Trades: {self.total_trades} (Win: {self.winning_trades}, Loss: {self.losing_trades})")
        print(f"Win Rate: {self.winning_trades / max(self.total_trades, 1) * 100:.1f}%")
        print(f"Total PnL: ${self.total_pnl:+.2f}")
        print(f"{'='*60}\n")
    
    def get_losing_trades_summary(self) -> Dict:
        """
        NEW: Returns detailed summary of losing trades for analysis.
        
        Returns:
            Dict with losing trade statistics
        """
        if not self.trade_history:
            return {'total_trades': 0, 'losing_trades': 0, 'message': 'No trades yet'}
        
        losing_trades = [t for t in self.trade_history if not t['is_winner']]
        
        if not losing_trades:
            return {
                'total_trades': len(self.trade_history),
                'losing_trades': 0,
                'message': 'No losing trades! 🎉'
            }
        
        # Analyze losing trades
        avg_loss_pct = np.mean([t['pnl_pct'] for t in losing_trades])
        avg_loss_usdt = np.mean([t['pnl_usdt'] for t in losing_trades])
        max_loss_pct = min([t['pnl_pct'] for t in losing_trades])
        avg_duration = np.mean([t['duration_steps'] for t in losing_trades])
        
        # Count by position type
        losing_longs = sum(1 for t in losing_trades if t['position_type'] == 'LONG')
        losing_shorts = sum(1 for t in losing_trades if t['position_type'] == 'SHORT')
        
        return {
            'total_trades': len(self.trade_history),
            'losing_trades': len(losing_trades),
            'loss_rate': len(losing_trades) / len(self.trade_history) * 100,
            'avg_loss_pct': avg_loss_pct,
            'avg_loss_usdt': avg_loss_usdt,
            'max_loss_pct': max_loss_pct,
            'avg_duration_steps': avg_duration,
            'losing_longs': losing_longs,
            'losing_shorts': losing_shorts,
            'recent_5_losses': losing_trades[-5:] if len(losing_trades) >= 5 else losing_trades
        }


# ═══════════════════════════════════════════════════════════════════════════
# 2. PPO AGENT WRAPPER
# ═══════════════════════════════════════════════════════════════════════════

class PPOTradingAgent:
    """
    Wrapper dla Stable-Baselines3 PPO Agent.
    
    Upraszcza trening, zapisywanie i ładowanie modelu.
    """
    
    def __init__(
        self,
        env: TradingEnv,
        model_path: str = "models/ppo_trading_agent",
        tensorboard_log: str = "./logs/tensorboard/"
    ):
        """
        Args:
            env: Trading environment
            model_path: Ścieżka do zapisu modelu
            tensorboard_log: Ścieżka do logów TensorBoard
        """
        self.env = DummyVecEnv([lambda: env])
        self.model_path = model_path
        self.tensorboard_log = tensorboard_log
        
        # Initialize PPO model
        self.model = PPO(
            "MlpPolicy",
            self.env,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            verbose=1,
            tensorboard_log=tensorboard_log
        )
    
    def train(self, total_timesteps: int = 100000, callback=None):
        """
        Trenuje agenta przez N timesteps.
        
        Args:
            total_timesteps: Liczba kroków treningowych (100k-1M recommended)
            callback: Opcjonalny callback dla monitoringu
        """
        log(f"🚀 Starting PPO training for {total_timesteps} timesteps...", "INFO")
        self.model.learn(total_timesteps=total_timesteps, callback=callback)
        log(f"✅ Training complete!", "SUCCESS")
    
    def save(self):
        """Zapisuje wytrenowany model."""
        self.model.save(self.model_path)
        log(f"💾 Model saved to {self.model_path}", "SUCCESS")
    
    def load(self):
        """Ładuje wytrenowany model."""
        self.model = PPO.load(self.model_path, env=self.env)
        log(f"📂 Model loaded from {self.model_path}", "SUCCESS")
    
    def predict(self, observation):
        """
        Zwraca akcję dla danego stanu.
        
        Args:
            observation: Stan środowiska
            
        Returns:
            action: 0=HOLD, 1=LONG, 2=SHORT, 3=CLOSE
        """
        action, _states = self.model.predict(observation, deterministic=True)
        return action


# ═══════════════════════════════════════════════════════════════════════════
# 3. TRAINING CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

class TradingCallback(BaseCallback):
    """
    Custom callback do monitoringu treningu PPO.
    
    Loguje szczegółowe informacje o treningu:
    - Episode reward, length
    - Win rate, accuracy
    - Total PnL, Balance
    - Training progress %
    - Timesteps completed
    - AUTO-CHECKPOINT: Zapisuje model co X epizodów
    """
    
    def __init__(
        self, 
        total_timesteps: int = 100000, 
        checkpoint_interval: int = 10000,
        checkpoint_dir: str = "./models/checkpoints",
        verbose=0
    ):
        super(TradingCallback, self).__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
        self.total_timesteps = total_timesteps
        self.last_log_step = 0
        self.log_interval = 2048  # Log every 2048 steps (1 rollout in PPO)
        self._training_env = None  # Will be set in _init_callback (use _ prefix to avoid property conflict)
        
        # Tracking metrics
        self.winning_episodes = 0
        self.losing_episodes = 0  # NEW: Track losing episodes
        self.total_episodes = 0
        self.cumulative_pnl = 0.0
        self.total_trades = 0  # NEW: Track total trades
        self.winning_trades = 0  # NEW: Track winning trades
        self.losing_trades = 0  # NEW: Track losing trades
        
        # Checkpoint settings
        self.checkpoint_interval = checkpoint_interval
        self.checkpoint_dir = checkpoint_dir
        self.last_checkpoint_step = 0
        
        # Create checkpoint directory
        import os
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        log(f"🎯 PPO Training Target: {total_timesteps} timesteps", "INFO", ppo_only=True)
        log(f"💾 Auto-checkpoint enabled: Every {checkpoint_interval} steps → {self.checkpoint_dir}", "INFO", ppo_only=True)
    
    def _init_callback(self) -> None:
        """Called when callback is initialized (access to model/env)."""
        super()._init_callback()
        self._training_env = self.model.get_env()  # Store reference to environment
    
    def _on_step(self) -> bool:
        """Called after each step."""
        # Log progress periodically
        if self.num_timesteps - self.last_log_step >= self.log_interval:
            self._log_training_progress()
            self.last_log_step = self.num_timesteps
        
        # Auto-checkpoint: Save model at intervals
        if self.num_timesteps - self.last_checkpoint_step >= self.checkpoint_interval:
            self._save_checkpoint()
            self.last_checkpoint_step = self.num_timesteps
        
        return True
    
    def _on_rollout_end(self) -> None:
        """Called at the end of a rollout (every 2048 steps for PPO)."""
        # DEBUG: Log ep_info_buffer status
        buffer_size = len(self.model.ep_info_buffer) if hasattr(self.model, 'ep_info_buffer') else 0
        
        # Log every 10 rollouts to diagnose Episodes=0 bug
        if (self.num_timesteps // self.log_interval) % 10 == 0:
            log(f"🔍 DEBUG: ep_info_buffer size = {buffer_size} (should be >0 if episodes completed)", 
                "WARNING" if buffer_size == 0 else "INFO", ppo_only=True)
            
            if buffer_size == 0:
                log(f"⚠️ PROBLEM DETECTED: No episodes completed in this rollout!", "ERROR", ppo_only=True)
                log(f"   Possible causes:", "WARNING", ppo_only=True)
                log(f"   1. max_episode_steps might be too large (current: {self.model.get_env().envs[0].unwrapped.max_episode_steps if hasattr(self.model.get_env().envs[0], 'unwrapped') else 'unknown'})", "INFO", ppo_only=True)
                log(f"   2. Dataset might be too small", "INFO", ppo_only=True)
                log(f"   3. Episodes taking longer than 2048 steps (n_steps)", "INFO", ppo_only=True)
        
        # Log training metrics
        if len(self.model.ep_info_buffer) > 0:
            mean_reward = np.mean([ep_info['r'] for ep_info in self.model.ep_info_buffer])
            mean_length = np.mean([ep_info['l'] for ep_info in self.model.ep_info_buffer])
            
            # Update metrics
            for ep_info in self.model.ep_info_buffer:
                self.total_episodes += 1
                episode_reward = ep_info['r']
                
                if episode_reward > 0:
                    self.winning_episodes += 1
                else:
                    self.losing_episodes += 1  # NEW: Track losses
                
                self.cumulative_pnl += episode_reward
            
            # Calculate win rate and loss rate
            win_rate = (self.winning_episodes / self.total_episodes * 100) if self.total_episodes > 0 else 0.0
            loss_rate = (self.losing_episodes / self.total_episodes * 100) if self.total_episodes > 0 else 0.0
            
            # Log to PPO.log (with NEW METRICS)
            log(f"📊 PPO Rollout #{self.num_timesteps//self.log_interval}: "
                f"Mean Reward={mean_reward:.2f}, "
                f"Mean Length={mean_length:.0f}, "
                f"Win Rate={win_rate:.1f}%, "
                f"Loss Rate={loss_rate:.1f}%, "  # NEW: Show loss rate
                f"Episodes={self.total_episodes} (W:{self.winning_episodes}, L:{self.losing_episodes})", 
                "INFO", ppo_only=True)
            
            # NEW: Log losing trades analysis every 10 rollouts
            if (self.num_timesteps // self.log_interval) % 10 == 0:
                try:
                    if hasattr(self._training_env, 'envs') and len(self._training_env.envs) > 0:
                        env = self._training_env.envs[0]
                        if hasattr(env, 'unwrapped'):
                            env = env.unwrapped
                        if hasattr(env, 'get_losing_trades_summary'):
                            summary = env.get_losing_trades_summary()
                            log(f"📉 Losing Trades Analysis:", "WARNING", ppo_only=True)
                            log(f"   Total Trades: {summary.get('total_trades', 0)}", "INFO", ppo_only=True)
                            log(f"   Losing Trades: {summary.get('losing_trades', 0)} ({summary.get('loss_rate', 0):.1f}%)", "WARNING", ppo_only=True)
                            log(f"   Avg Loss: {summary.get('avg_loss_pct', 0):.2f}% (${summary.get('avg_loss_usdt', 0):.2f})", "WARNING", ppo_only=True)
                            log(f"   Max Loss: {summary.get('max_loss_pct', 0):.2f}%", "ERROR", ppo_only=True)
                            log(f"   Losing LONG: {summary.get('losing_longs', 0)}, Losing SHORT: {summary.get('losing_shorts', 0)}", "INFO", ppo_only=True)
                except Exception as e:
                    pass  # Silently ignore if environment doesn't support this
    
    def _log_training_progress(self):
        """Logs detailed training progress to PPO.log."""
        progress_pct = (self.num_timesteps / self.total_timesteps) * 100
        
        # Calculate current win rate and loss rate
        win_rate = (self.winning_episodes / self.total_episodes * 100) if self.total_episodes > 0 else 0.0
        loss_rate = (self.losing_episodes / self.total_episodes * 100) if self.total_episodes > 0 else 0.0
        
        # Estimate accuracy (win rate is a proxy for accuracy in RL)
        accuracy_pct = win_rate
        
        # NEW: Access trade-level stats from environment (if available)
        trade_stats = ""
        try:
            if hasattr(self._training_env, 'envs') and len(self._training_env.envs) > 0:
                env = self._training_env.envs[0]
                if hasattr(env, 'unwrapped'):
                    env = env.unwrapped
                total_trades = getattr(env, 'total_trades', 0)
                winning_trades = getattr(env, 'winning_trades', 0)
                losing_trades = getattr(env, 'losing_trades', 0)
                trade_win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
                trade_stats = f" | Trades: {total_trades} (W:{winning_trades}, L:{losing_trades}, WR:{trade_win_rate:.1f}%)"
        except:
            pass
        
        log(f"🎯 PPO Progress: {self.num_timesteps}/{self.total_timesteps} steps ({progress_pct:.1f}%) | "
            f"Episodes: {self.total_episodes} (W:{self.winning_episodes}, L:{self.losing_episodes}) | "
            f"Episode Win Rate: {win_rate:.1f}% | "
            f"Accuracy: {accuracy_pct:.1f}%{trade_stats} | "
            f"Cumulative Reward: {self.cumulative_pnl:.2f}", 
            "SUCCESS", ppo_only=True)
    
    def _save_checkpoint(self):
        """Saves model checkpoint with metadata."""
        import os
        import json
        from datetime import datetime
        
        try:
            # Calculate current metrics
            win_rate = (self.winning_episodes / self.total_episodes * 100) if self.total_episodes > 0 else 0.0
            progress_pct = (self.num_timesteps / self.total_timesteps) * 100
            
            # Checkpoint filename with timesteps
            checkpoint_name = f"ppo_checkpoint_{self.num_timesteps}"
            checkpoint_path = os.path.join(self.checkpoint_dir, checkpoint_name)
            
            # Save model
            self.model.save(checkpoint_path)
            
            # Save metadata
            metadata = {
                'timesteps': self.num_timesteps,
                'total_timesteps': self.total_timesteps,
                'progress_pct': progress_pct,
                'episodes': self.total_episodes,
                'winning_episodes': self.winning_episodes,
                'win_rate': win_rate,
                'cumulative_reward': self.cumulative_pnl,
                'saved_at': datetime.now().isoformat(),
                'checkpoint_file': checkpoint_name + '.zip'
            }
            
            metadata_path = checkpoint_path + '_metadata.json'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            log(f"💾 Checkpoint saved: {checkpoint_name}.zip | "
                f"Steps: {self.num_timesteps}/{self.total_timesteps} ({progress_pct:.1f}%) | "
                f"Win Rate: {win_rate:.1f}%", 
                "SUCCESS", ppo_only=True)
            
        except Exception as e:
            log(f"❌ Failed to save checkpoint: {e}", "ERROR", ppo_only=True)


# ═══════════════════════════════════════════════════════════════════════════
# 4. UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def create_env_from_data(
    df: pd.DataFrame,
    lstm_predictions: Optional[pd.Series] = None,
    lstm_confidences: Optional[pd.Series] = None,
    initial_balance: float = 1000.0,
    **kwargs
) -> TradingEnv:
    """
    Helper function do tworzenia TradingEnv z danych.
    
    Args:
        df: DataFrame z danymi OHLCV + indicators
        lstm_predictions: Predykcje z LSTM
        lstm_confidences: Confidence scores
        initial_balance: Początkowy kapitał
        **kwargs: Dodatkowe argumenty dla TradingEnv (np. max_episode_steps)
        
    Returns:
        TradingEnv: Gotowe środowisko
    """
    return TradingEnv(
        df=df,
        initial_balance=initial_balance,
        lstm_predictions=lstm_predictions,
        lstm_confidences=lstm_confidences,
        **kwargs
    )


def backtest_agent(
    agent: PPOTradingAgent,
    test_df: pd.DataFrame,
    lstm_predictions: Optional[pd.Series] = None,
    lstm_confidences: Optional[pd.Series] = None,
    initial_balance: float = 1000.0,
    render: bool = False
) -> Dict:
    """
    Przeprowadza backtest wytrenowanego agenta na nowych danych.
    
    Args:
        agent: Wytrenowany PPOTradingAgent
        test_df: DataFrame z danymi testowymi
        lstm_predictions: Predykcje LSTM dla test_df
        lstm_confidences: Confidence scores
        initial_balance: Początkowy kapitał
        render: Czy renderować każdy krok
        
    Returns:
        Dict: Wyniki backtestingu (PnL, Win Rate, Sharpe, Max DD)
    """
    env = create_env_from_data(test_df, lstm_predictions, lstm_confidences, initial_balance)
    obs, _ = env.reset()
    
    total_reward = 0
    done = False
    
    log(f"🔬 Starting backtest on {len(test_df)} candles...", "INFO")
    
    while not done:
        action = agent.predict(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        done = terminated or truncated
        
        if render and env.current_step % 100 == 0:
            env.render()
    
    # Final results
    final_balance = info['balance']
    total_return_pct = ((final_balance - initial_balance) / initial_balance) * 100
    win_rate = info['win_rate'] * 100
    
    log(f"✅ Backtest Complete!", "SUCCESS")
    log(f"   Initial Balance: ${initial_balance:.2f}", "INFO")
    log(f"   Final Balance: ${final_balance:.2f}", "INFO")
    log(f"   Total Return: {total_return_pct:+.2f}%", "SUCCESS" if total_return_pct > 0 else "ERROR")
    log(f"   Total Trades: {info['total_trades']}", "INFO")
    log(f"   Win Rate: {win_rate:.1f}%", "INFO")
    log(f"   Max Drawdown: {info['drawdown_pct']:.2f}%", "WARNING")
    
    return {
        'initial_balance': initial_balance,
        'final_balance': final_balance,
        'total_return_pct': total_return_pct,
        'total_trades': info['total_trades'],
        'winning_trades': info['winning_trades'],
        'win_rate': win_rate,
        'total_pnl': info['total_pnl'],
        'max_drawdown_pct': info['drawdown_pct'],
        'total_reward': total_reward,
    }
