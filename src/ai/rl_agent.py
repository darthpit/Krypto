"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  REINFORCEMENT LEARNING AGENT — ARCHITEKTURA "SPARTAN+TITAN" v3.0           ║
║  PPO (Proximal Policy Optimization) Trading Environment                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

ARCHITEKTURA REWARD FUNCTION — "SPARTAN ENVIRONMENT":
─────────────────────────────────────────────────────────────────────────────
Filozofia: Środowisko tak surowe i zgodne z prawami rynku, że jedyną drogą
do przetrwania jest profesjonalny trading. Brak darmowych okruchów.

WSZYSTKIE NAGRODY W SKALI [-10, +10] (hard clip na końcu step())
Chroni gradient przed dominacją jednej kary.

1. BLOOD TOLL (Bariera wejścia):
   - Każde OPEN i CLOSE kosztuje: fee (0.04%) + slippage (0.02%) z position_size
   - Pozycja startuje z PnL -0.12% (przy 20x: -2.4%). Scalping +0.05% = samobójstwo.

2. DELTA PnL (Serce systemu — płatność za jazdę z trendem):
   - Per krok: reward += (current_unrealized_pnl - prev_unrealized_pnl) * 0.5
   - Rynek idzie z tobą → mikropłatność. Rynek zawraca → mikroodliczenie.
   - Agent SAM uczy się kiedy wychodzić. Żadnych sztywnych SL/TP.

3. ASYMETRYCZNA KARA ZA STRATY (Eksponencjalny ból):
   - Zysk: reward += pnl_pct * 8.0 (liniowy)
   - Strata: reward -= |pnl_pct|^1.5 * 6.0 (eksponencjalny)
   - Przykład: -1% = -6 pkt, -3% = -31 pkt, -5% = -67 pkt → ucina straty szybko

4. FUNDING RATE (Koszt martwej pozycji):
   - reward -= 0.003 per krok w pozycji
   - 100 kroków bez ruchu = -0.3 pkt → wymusza zamknięcie martwych pozycji

5. INTELIGENTNY SOFT LIQUIDATION (-8% od szczytu epizodu):
   - Jeśli balance > initial * 1.3: tolerancja rośnie do -12% (nie karz za korektę po hossie)
   - Kara za soft liq: -200 pkt (nie -1000 — nie dominuje nad gradient)
   - max_episode_steps = 4096 (2.8 dni danych 1-min)

6. REWARD CLIP:
   - Na końcu step(): reward = max(min(reward, 10.0), -10.0)
   - Chroni przed fat tails kryptowalut (15% świeca = -67 pkt bez clipa)

BRAK:
   - ❌ +10 za natychmiastowy kierunek (było źródłem reward hacking)
   - ❌ +10 za mikrozysk >0.05% (było źródłem reward hacking)
   - ❌ Kary za HOLD bez pozycji (overtrading trap)
   - ❌ Linearne kary za drawdown (zastąpione soft liq)

PPO HYPERPARAMETERS:
   - ent_coef = 0.05 (defibrylator — wymusza eksplorację po śpiączce 95.5%)
   - max_grad_norm = 0.5 (stabilizuje gradient)
   - n_steps = 2048, batch_size = 64 (bez zmian)
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
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import BaseCallback

from ..utils.logger import log


# ═══════════════════════════════════════════════════════════════════════════
# STAŁE KALIBRACYJNE — zmień tylko te wartości do tuningowania
# ═══════════════════════════════════════════════════════════════════════════

# Blood Toll
FEE_TAKER  = 0.0004   # 0.04% MEXC taker fee
SLIPPAGE   = 0.0002   # 0.02% market slippage

# Delta PnL scaling
DELTA_SCALE = 0.5     # 1% ruch = +0.5 pkt nagrody per krok

# Close reward
WIN_LINEAR_SCALE  = 8.0   # zysk: pnl_pct * 8.0
LOSS_EXP_BASE     = 6.0   # strata: -|pnl_pct|^1.5 * 6.0
BIG_WIN_THRESHOLD = 1.5   # % powyżej którego bonus za trzymanie trendu
BIG_WIN_BONUS     = 4.0   # bonus za każdy % powyżej progu

# Funding rate per krok w pozycji
FUNDING_PER_STEP = 0.003

# Soft liquidation
SOFT_LIQ_DRAWDOWN_NORMAL = 0.35   # -35% od szczytu epizodu
SOFT_LIQ_DRAWDOWN_PROFIT = 0.40   # -40% jeśli balance > 130% initial (korygujemy po hossie)
PROFIT_THRESHOLD_FOR_RELAX = 1.30 # 30% zysku = rozluźnienie
SOFT_LIQ_PENALTY = -200.0         # nie -1000 — nie dominuje gradient

# Bankruptcy (absolutne dno)
BANKRUPTCY_THRESHOLD = 0.20       # balance < 20% initial
BANKRUPTCY_PENALTY   = -500.0

# Hard reward clip (ochrona przed fat tails krypto)
REWARD_CLIP_MAX =  10.0
REWARD_CLIP_MIN = -10.0


# ═══════════════════════════════════════════════════════════════════════════
# 1. TRADING ENVIRONMENT (Gym/Gymnasium)
# ═══════════════════════════════════════════════════════════════════════════

class TradingEnv(gym.Env):
    """
    Środowisko giełdowe zgodne z Gymnasium API.

    OBSERVATION SPACE:
    - Technical Indicators: RSI, MACD, ATR, Volume, etc. (19 features)
    - LSTM Prediction: Prawdopodobieństwo wzrostu (0-1)
    - LSTM Confidence: Pewność predykcji (0-1)
    - Portfolio State: position, entry_dist, size, pnl, balance, drawdown, steps_in_pos

    ACTION SPACE:
    - 0: HOLD
    - 1: OPEN_LONG
    - 2: OPEN_SHORT
    - 3: CLOSE
    """

    metadata = {'render.modes': ['human']}

    def __init__(
        self,
        df: pd.DataFrame,
        initial_balance: float = 1000.0,
        leverage: int = 20,
        trading_fee: float = FEE_TAKER,
        spread: float = SLIPPAGE,
        funding_rate_hourly: float = 0.0001,
        lstm_predictions: Optional[pd.Series] = None,
        lstm_confidences: Optional[pd.Series] = None,
        max_episode_steps: Optional[int] = None,
    ):
        super(TradingEnv, self).__init__()

        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.trading_fee = trading_fee
        self.spread = spread
        self.funding_rate_hourly = funding_rate_hourly
        self.max_episode_steps = max_episode_steps

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

        # ── WALK-FORWARD NORMALIZATION (Eliminacja Lookahead Bias) ──────────
        # Problem: mean/std z całego df zawiera dane z przyszłości.
        # Krok 1 w treningu używałby średniej liczonej z kroków 1-180000.
        # W Live Trading nie znasz przyszłej średniej → backtest zbyt optymistyczny.
        #
        # Rozwiązanie: expanding window — w kroku N używamy tylko danych 0..N-1.
        # min_periods=200 — pierwsze 200 kroków ma stałe wartości (brak historii).
        # Stabilne, szybkie (pandas vectorized), brak wycieku przyszłości.
        WARMUP = 200  # kroków przed stabilizacją statystyk
        self.rolling_means = {}
        self.rolling_stds  = {}
        for col in self.feature_cols:
            # .shift(1) → wartość z poprzedniego kroku (nie bieżącego!)
            exp_mean = self.df[col].expanding(min_periods=WARMUP).mean().shift(1)
            exp_std  = self.df[col].expanding(min_periods=WARMUP).std().shift(1)
            # Wypełnij NaN (pierwsze WARMUP kroków) globalną średnią tylko z warmup okna
            warmup_mean = self.df[col].iloc[:WARMUP].mean()
            warmup_std  = self.df[col].iloc[:WARMUP].std() + 1e-8
            self.rolling_means[col] = exp_mean.fillna(warmup_mean).values
            self.rolling_stds[col]  = exp_std.fillna(warmup_std).clip(lower=1e-8).values


        # --- NUMPY ARRAYS FOR FAST ACCESS ---
        self._prices = self.df['close'].values.astype(np.float32)
        self._features_arr = self.df[self.feature_cols].values.astype(np.float32)

        self._lstm_preds = self.lstm_predictions.values.astype(np.float32) if self.lstm_predictions is not None else None
        self._lstm_confs = self.lstm_confidences.values.astype(np.float32) if self.lstm_confidences is not None else None

        self._rolling_means_arr = np.column_stack([self.rolling_means[col] for col in self.feature_cols]).astype(np.float32)
        self._rolling_stds_arr = np.column_stack([self.rolling_stds[col] for col in self.feature_cols]).astype(np.float32)
        # State dimensions
        n_features = len(self.feature_cols)
        n_lstm_features = 2
        n_portfolio_features = 7
        state_dim = n_features + n_lstm_features + n_portfolio_features

        self.observation_space = spaces.Box(
            low=-5.0, high=5.0, shape=(state_dim,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(4)

        # Episode tracking
        self.current_step = 0
        self.max_steps = len(df) - 1

        # Portfolio state
        self.balance = initial_balance
        self.peak_balance = initial_balance
        self.episode_peak_balance = initial_balance  # NOWE: peak per epizod dla smart drawdown
        self.position = 0
        self.entry_price = 0.0
        self.position_size = 0.0
        self.steps_in_position = 0
        self.prev_unrealized_pnl = 0.0  # NOWE: dla Delta PnL

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.episode_history = []
        self.trade_history = []

    def reset(self, seed=None, options=None):
        """Reset environment."""
        super().reset(seed=seed)

        if self.max_episode_steps and len(self.df) > self.max_episode_steps:
            max_start = len(self.df) - self.max_episode_steps - 1
            self.current_step = np.random.randint(0, max_start) if max_start > 0 else 0
        else:
            self.current_step = 0

        self.start_step = self.current_step
        self.steps_in_episode = 0

        self.balance = self.initial_balance
        self.peak_balance = self.initial_balance
        self.episode_peak_balance = self.initial_balance  # Reset per epizod
        self.position = 0
        self.entry_price = 0.0
        self.position_size = 0.0
        self.steps_in_position = 0
        self.prev_unrealized_pnl = 0.0

        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.trade_history = []

        if not hasattr(self, '_episode_count'):
            self._episode_count = 0
        self._episode_count += 1

        if self._episode_count % 100 == 0:
            log(f"🔄 PPO Episode #{self._episode_count} started | "
                f"Dataset: {len(self.df)} candles | "
                f"Max Steps: {self.max_episode_steps}",
                "INFO", ppo_only=True)

        return self._get_observation(), {}

    def step(self, action: int):
        """
        Wykonuje akcję i zwraca (observation, reward, terminated, truncated, info).
        """
        current_price = float(self._prices[self.current_step])
        reward = 0.0

        # ═══════════════════════════════════════════════════════════════════
        # KROK 1: DELTA PnL — nagroda/kara za każdą świecę w pozycji
        # Rynek płaci dniówkę kiedy idziesz z trendem.
        # Kiedy zawraca — odbiera.
        # ═══════════════════════════════════════════════════════════════════
        if self.position != 0:
            current_unrealized_pnl = self._calculate_pnl_pct(current_price)

            # Delta = zmiana unrealized PnL w stosunku do poprzedniego kroku
            delta_pnl = current_unrealized_pnl - self.prev_unrealized_pnl
            reward += delta_pnl * DELTA_SCALE

            # Funding rate — koszt martwej pozycji (kara za stanie w miejscu)
            reward -= FUNDING_PER_STEP

            # Koszt funding rate na balance (co 8h = 480 kroków)
            if self.steps_in_position > 0 and self.steps_in_position % 480 == 0:
                funding_cost = self.position_size * self.funding_rate_hourly * 8
                self.balance -= funding_cost

            # AI Alignment Bonus (subtelny sygnał — nie dominuje)
            if self.lstm_predictions is not None:
                try:
                    pred = float(self._lstm_preds[self.current_step]) if self.current_step < len(self._lstm_preds) else 0.5
                    if pred > 0.7 and self.position == 1:
                        reward += 0.05
                    elif pred < 0.3 and self.position == -1:
                        reward += 0.05
                except Exception:
                    pass

            self.prev_unrealized_pnl = current_unrealized_pnl
            self.steps_in_position += 1
        else:
            # Brak pozycji — resetuj delta tracker
            self.prev_unrealized_pnl = 0.0

        # ═══════════════════════════════════════════════════════════════════
        # KROK 2: Wykonaj akcję
        # ═══════════════════════════════════════════════════════════════════
        if action == 0:  # HOLD — brak kary (pozycja płaska to też pozycja)
            pass

        elif action == 1:  # OPEN LONG
            if self.position == 0:
                reward += self._open_position(current_price, "LONG")

        elif action == 2:  # OPEN SHORT
            if self.position == 0:
                reward += self._open_position(current_price, "SHORT")

        elif action == 3:  # CLOSE
            if self.position != 0:
                reward += self._close_position(current_price)

        # ═══════════════════════════════════════════════════════════════════
        # KROK 3: Aktualizacja wirtualnego balansu i szczytów
        # ═══════════════════════════════════════════════════════════════════
        # Calculate Virtual Balance to prevent holding positions that wipe out the account
        virtual_balance = self.balance
        if self.position != 0:
            current_unrealized_pnl_pct = self._calculate_pnl_pct(current_price)
            unrealized_usdt = ((self.position_size / self.leverage) * current_unrealized_pnl_pct) / 100.0
            close_cost = self.position_size * (self.trading_fee + self.spread)
            virtual_balance += (unrealized_usdt - close_cost)

        if virtual_balance > self.peak_balance:
            self.peak_balance = virtual_balance
            reward += 1.0  # Skromny bonus — nie dominuje nad Delta PnL

        if virtual_balance > self.episode_peak_balance:
            self.episode_peak_balance = virtual_balance  # Aktualizuj peak epizodu

        # ═══════════════════════════════════════════════════════════════════
        # KROK 4: Warunki zakończenia epizodu
        # ═══════════════════════════════════════════════════════════════════
        self.current_step += 1
        self.steps_in_episode += 1

        terminated = False
        truncated = False

        # --- BANKRUPTCY CHECK (absolutne dno) ---
        if virtual_balance < (self.initial_balance * BANKRUPTCY_THRESHOLD):
            if self.position != 0:
                reward += self._close_position(current_price, forced=True)
            reward += BANKRUPTCY_PENALTY
            terminated = True
            log(f"💀 RL Episode TERMINATED: Bankructwo! Balance={self.balance:.2f} (Virtual: {virtual_balance:.2f})", "ERROR")

        # --- INTELIGENTNY SOFT LIQUIDATION ---
        # Jeśli agent zarobił dużo i rynek koryguje — nie karz za naturalny oddech
        if not terminated:
            episode_drawdown_pct = ((self.episode_peak_balance - virtual_balance) / max(self.episode_peak_balance, 1.0)) * 100

            # Rozluźnij próg jeśli agent jest na znacznym plusie
            if virtual_balance > self.initial_balance * PROFIT_THRESHOLD_FOR_RELAX:
                soft_liq_threshold = SOFT_LIQ_DRAWDOWN_PROFIT * 100
            else:
                soft_liq_threshold = SOFT_LIQ_DRAWDOWN_NORMAL * 100

            if episode_drawdown_pct > soft_liq_threshold:
                if self.position != 0:
                    reward += self._close_position(current_price, forced=True)
                reward += SOFT_LIQ_PENALTY  # -200
                terminated = True
                log(f"🔴 RL SOFT LIQUIDATION: Drawdown={episode_drawdown_pct:.1f}% > {soft_liq_threshold:.0f}%. Balance={self.balance:.2f}", "ERROR")

        # --- KONIEC DANYCH / LIMIT KROKÓW ---
        if not terminated:
            data_ended = self.current_step >= len(self.df) - 1
            episode_limit_reached = (self.max_episode_steps is not None) and (self.steps_in_episode >= self.max_episode_steps)

            if data_ended or episode_limit_reached:
                truncated = True
                if self.position != 0:
                    reward += self._close_position(current_price, forced=True)

                if hasattr(self, '_episode_count') and self._episode_count % 100 == 0:
                    reason = "data_ended" if data_ended else "step_limit"
                    log(f"🏁 Episode #{self._episode_count} ({reason}) | "
                        f"Steps: {self.steps_in_episode} | "
                        f"Trades: {self.total_trades} (W:{self.winning_trades}, L:{self.losing_trades}) | "
                        f"Balance: ${self.balance:.2f}",
                        "INFO", ppo_only=True)

        # ═══════════════════════════════════════════════════════════════════
        # KROK 5: HARD REWARD CLIP — ochrona przed fat tails krypto
        # Bez tego: 15% świeca → eksponencjalny wzór → reward = -200 → zabija gradient
        # ═══════════════════════════════════════════════════════════════════
        reward = max(min(reward, REWARD_CLIP_MAX), REWARD_CLIP_MIN)

        # ═══════════════════════════════════════════════════════════════════
        # KROK 6: Zwróć wyniki
        # ═══════════════════════════════════════════════════════════════════
        virtual_balance = self.balance
        if self.position != 0:
            current_unrealized_pnl_pct = self._calculate_pnl_pct(current_price)
            unrealized_usdt = ((self.position_size / self.leverage) * current_unrealized_pnl_pct) / 100.0
            close_cost = self.position_size * (self.trading_fee + self.spread)
            virtual_balance += (unrealized_usdt - close_cost)

        drawdown_pct = ((self.peak_balance - virtual_balance) / max(self.peak_balance, 1.0)) * 100
        observation = self._get_observation()

        info = {
            'balance': virtual_balance,
            'position': self.position,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.winning_trades / max(self.total_trades, 1),
            'loss_rate': self.losing_trades / max(self.total_trades, 1),
            'total_pnl': self.total_pnl,
            'drawdown_pct': drawdown_pct,
        }

        return observation, reward, terminated, truncated, info

    def _get_observation(self) -> np.ndarray:
        """Zwraca obecny stan środowiska (Normalized)."""
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1

        # 1. Technical indicators — Walk-Forward Z-score (bez lookahead bias)
        # Używamy mean/std wyliczonej tylko z danych PRZED bieżącym krokiem.
        raw_features = self._features_arr[self.current_step]
        means = self._rolling_means_arr[self.current_step]
        stds = self._rolling_stds_arr[self.current_step]
        features = np.clip((raw_features - means) / stds, -5.0, 5.0)

        # 2. LSTM predictions
        lstm_features = [0.0, 0.0]
        if self.lstm_predictions is not None:
            pred = float(self._lstm_preds[self.current_step]) if self.current_step < len(self._lstm_preds) else 0.5
            conf = float(self._lstm_confs[self.current_step]) if self._lstm_confs is not None and self.current_step < len(self._lstm_confs) else 0.5
            lstm_features = [(pred - 0.5) * 2.0, (conf - 0.5) * 2.0]

        # 3. Portfolio state
        current_price = float(self._prices[self.current_step])
        pnl_pct = self._calculate_pnl_pct(current_price) if self.position != 0 else 0.0

        virtual_balance = self.balance
        if self.position != 0:
            unrealized_usdt = ((self.position_size / self.leverage) * pnl_pct) / 100.0
            close_cost = self.position_size * (self.trading_fee + self.spread)
            virtual_balance += (unrealized_usdt - close_cost)

        drawdown_pct = ((self.peak_balance - virtual_balance) / max(self.peak_balance, 1.0)) * 100

        entry_price_norm = 0.0
        if self.position != 0 and self.entry_price > 0:
            entry_price_norm = np.log(current_price / self.entry_price) * 100

        balance_norm = np.log(max(virtual_balance, 1.0) / self.initial_balance)

        size_norm = 0.0
        if virtual_balance > 0:
            size_norm = self.position_size / (virtual_balance * self.leverage)

        portfolio_features = [
            float(self.position),
            entry_price_norm,
            size_norm,
            pnl_pct / 10.0,
            balance_norm,
            drawdown_pct / 20.0,
            np.log1p(self.steps_in_position) / 3.0
        ]

        observation = np.concatenate([features, lstm_features, portfolio_features]).astype(np.float32)
        observation = np.nan_to_num(observation, nan=0.0, posinf=5.0, neginf=-5.0)
        return observation

    def _open_position(self, price: float, side: str) -> float:
        """
        Otwiera pozycję. Blood Toll — natychmiastowy koszt wejścia.
        Pozycja startuje z ujemnym PnL = -(fee + slippage) * leverage.
        """
        risk_amount = self.balance * 0.10
        self.position_size = risk_amount * self.leverage

        # Blood Toll: fee + slippage odejmowane z balance natychmiast
        total_entry_cost = self.position_size * (self.trading_fee + self.spread)
        self.balance -= total_entry_cost

        self.position = 1 if side == "LONG" else -1
        self.entry_price = price
        self.steps_in_position = 0
        self.prev_unrealized_pnl = 0.0

        return 0.0  # Brak nagrody za samo otwarcie

    def _close_position(self, price: float, forced: bool = False) -> float:
        """
        Zamyka pozycję. Asymetryczna nagroda/kara.

        Zysk: liniowy * WIN_LINEAR_SCALE + bonus za duże wygrane
        Strata: eksponencjalny ból -|pnl|^1.5 * LOSS_EXP_BASE
        """
        pnl_pct = self._calculate_pnl_pct(price)
        pnl_usdt = ((self.position_size / self.leverage) * pnl_pct) / 100.0

        # Blood Toll przy zamknięciu
        close_cost = self.position_size * (self.trading_fee + self.spread)
        net_pnl = pnl_usdt - close_cost
        self.balance += net_pnl
        self.total_pnl += net_pnl

        self.total_trades += 1
        if net_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Zapis historii transakcji
        self.trade_history.append({
            'step': self.current_step,
            'position_type': 'LONG' if self.position == 1 else 'SHORT',
            'entry_price': self.entry_price,
            'exit_price': price,
            'pnl_pct': pnl_pct,
            'pnl_usdt': net_pnl,
            'duration_steps': self.steps_in_position,
            'is_winner': net_pnl > 0,
            'forced_close': forced
        })

        # ── REWARD CALCULATION ──────────────────────────────────────────
        # Odepnij funkcję nagrody PPO (Reward Function) od sztywnych, matematycznych progów
        # PPO ma otrzymywać dodatnie punkty wyłącznie za zrealizowany PnL (zysk)
        # i kary za uderzenie w MAE (Stop Loss)

        reward = 0.0

        if net_pnl > 0:
            # Czysty zrealizowany zysk - podstawa do nagrody (liniowo oparty na PnL w dolarach / jednostkach balansu)
            # Normalizujemy przez początkowy balans, by skala nie wyleciała w kosmos (albo przez wielkość pozycji).
            # net_pnl jest w dolarach. Prostsze: używamy net_pnl / position_size jako % ruchu ceny brutto
            reward += net_pnl / max(1.0, self.position_size) * WIN_LINEAR_SCALE * 10.0 # Wzmocnienie by było podobne do starej skali
        else:
            # Kara za uderzenie w MAE / wymuszone zamknięcie ze stratą
            # PPO jest karane proporcjonalnie do utraconego kapitału
            loss_pct = abs(net_pnl) / max(1.0, self.position_size) * 100.0

            # Jeżeli zamknięto pozycję, a jest na stratach, po prostu wlep karę.
            # Im głębsza strata tym większa kara, ale bez sztucznych skoków jak -67 pkt za 5%
            reward -= (abs(net_pnl) / max(1.0, self.position_size)) * LOSS_EXP_BASE * 10.0

        if forced and net_pnl < 0:
            # Gdy wymuszone zamknięcie np. z powodu wyjścia z odcinka czasu lub limitu
            reward -= 20.0

        # Reset pozycji
        self.position = 0
        self.entry_price = 0.0
        self.position_size = 0.0
        self.steps_in_position = 0
        self.prev_unrealized_pnl = 0.0

        return reward

    def _calculate_pnl_pct(self, current_price: float) -> float:
        """Oblicza % PnL (ROE) dla otwartej pozycji z uwzględnieniem dźwigni."""
        if self.position == 0:
            return 0.0
        if self.position == 1:  # LONG
            return ((current_price - self.entry_price) / self.entry_price) * 100.0 * self.leverage
        else:  # SHORT
            return ((self.entry_price - current_price) / self.entry_price) * 100.0 * self.leverage

    def render(self, mode='human'):
        """Renderuje stan środowiska."""
        current_price = float(self._prices[self.current_step])
        pnl_pct = self._calculate_pnl_pct(current_price) if self.position != 0 else 0.0
        print(f"\n{'='*60}")
        print(f"Step: {self.current_step}/{self.max_steps}")
        print(f"Price: ${current_price:.2f}")
        print(f"Balance: ${self.balance:.2f} (Peak: ${self.peak_balance:.2f})")
        pos_label = ['SHORT', 'NEUTRAL', 'LONG'][self.position + 1]
        print(f"Position: {pos_label}")
        if self.position != 0:
            print(f"Entry: ${self.entry_price:.2f} | PnL: {pnl_pct:+.2f}%")
        print(f"Trades: {self.total_trades} (W:{self.winning_trades}, L:{self.losing_trades})")
        print(f"Win Rate: {self.winning_trades / max(self.total_trades, 1) * 100:.1f}%")
        print(f"Total PnL: ${self.total_pnl:+.2f}")
        print(f"{'='*60}\n")

    def get_losing_trades_summary(self) -> Dict:
        """Zwraca szczegółowe podsumowanie przegranych transakcji."""
        if not self.trade_history:
            return {'total_trades': 0, 'losing_trades': 0, 'message': 'No trades yet'}

        losing = [t for t in self.trade_history if not t['is_winner']]
        if not losing:
            return {'total_trades': len(self.trade_history), 'losing_trades': 0, 'message': 'No losing trades! 🎉'}

        return {
            'total_trades': len(self.trade_history),
            'losing_trades': len(losing),
            'loss_rate': len(losing) / len(self.trade_history) * 100,
            'avg_loss_pct': np.mean([t['pnl_pct'] for t in losing]),
            'avg_loss_usdt': np.mean([t['pnl_usdt'] for t in losing]),
            'max_loss_pct': min([t['pnl_pct'] for t in losing]),
            'avg_duration_steps': np.mean([t['duration_steps'] for t in losing]),
            'losing_longs': sum(1 for t in losing if t['position_type'] == 'LONG'),
            'losing_shorts': sum(1 for t in losing if t['position_type'] == 'SHORT'),
            'recent_5_losses': losing[-5:] if len(losing) >= 5 else losing
        }


# ═══════════════════════════════════════════════════════════════════════════
# 2. PPO AGENT WRAPPER
# ═══════════════════════════════════════════════════════════════════════════

class PPOTradingAgent:
    """
    Wrapper dla Stable-Baselines3 PPO Agent.

    KLUCZOWE ZMIANY v3.0:
    - Monitor(env) wrapper — ep_info_buffer działa poprawnie
    - ent_coef = 0.05 — defibrylator po śpiączce 95.5%
    - max_grad_norm = 0.5 — stabilizuje gradient
    """

    def __init__(
        self,
        env: TradingEnv,
        model_path: str = "models/ppo_trading_agent",
        tensorboard_log: str = "./logs/tensorboard/"
    ):
        self.model_path = model_path
        self.tensorboard_log = tensorboard_log

        # KLUCZOWE: Monitor wrapper — bez niego ep_info_buffer jest pusty
        # i TradingCallback widzi Episodes: 0 przez cały trening
        monitored_env = Monitor(env)
        self.env = DummyVecEnv([lambda: monitored_env])

        # PPO z parametrami Spartan+Titan v3.1
        # ent_coef ustawiony jako schedulowany — EntropyDecayCallback
        # zmniejsza go liniowo od 0.05 do 0.005 przez cały trening.
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
            ent_coef=0.05,       # Startowa wartość — EntropyDecayCallback zmniejsza do 0.005
            vf_coef=0.5,
            max_grad_norm=0.5,   # Stabilizuje gradient
            verbose=1,
            tensorboard_log=tensorboard_log
        )

    def train(self, total_timesteps: int = 100000, callback=None):
        log(f"🚀 Starting PPO training (Spartan+Titan) for {total_timesteps} timesteps...", "INFO")
        self.model.learn(total_timesteps=total_timesteps, callback=callback)
        log(f"✅ Training complete!", "SUCCESS")

    def save(self):
        self.model.save(self.model_path)
        log(f"💾 Model saved to {self.model_path}", "SUCCESS")

    def load(self):
        self.model = PPO.load(self.model_path, env=self.env)
        log(f"📂 Model loaded from {self.model_path}", "SUCCESS")

    def predict(self, observation):
        action, _states = self.model.predict(observation, deterministic=True)
        return action


# ═══════════════════════════════════════════════════════════════════════════
# 3. TRAINING CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

class TradingCallback(BaseCallback):
    """
    Custom callback do monitoringu treningu PPO.
    Loguje progress, win rate, trade stats, checkpoints.
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
        self.log_interval = 2048
        self._training_env = None

        self.winning_episodes = 0
        self.losing_episodes = 0
        self.total_episodes = 0
        self.cumulative_pnl = 0.0

        self.checkpoint_interval = checkpoint_interval
        self.checkpoint_dir = checkpoint_dir
        self.last_checkpoint_step = 0

        import os
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        log(f"🎯 PPO Training Target: {total_timesteps} timesteps", "INFO", ppo_only=True)
        log(f"💾 Auto-checkpoint: Every {checkpoint_interval} steps → {self.checkpoint_dir}", "INFO", ppo_only=True)

    def _init_callback(self) -> None:
        super()._init_callback()
        self._training_env = self.model.get_env()

    def _on_step(self) -> bool:
        # PPO PAUSE LOGIC REMOVED: PPO trenuje się cały czas niezależnie od LSTM

        if self.num_timesteps - self.last_log_step >= self.log_interval:
            self._log_training_progress()
            self.last_log_step = self.num_timesteps

        if self.num_timesteps - self.last_checkpoint_step >= self.checkpoint_interval:
            self._save_checkpoint()
            self.last_checkpoint_step = self.num_timesteps

        return True

    def _on_rollout_end(self) -> None:
        buffer_size = len(self.model.ep_info_buffer) if hasattr(self.model, 'ep_info_buffer') else 0

        if (self.num_timesteps // self.log_interval) % 10 == 0:
            log(f"🔍 ep_info_buffer size = {buffer_size}",
                "WARNING" if buffer_size == 0 else "INFO", ppo_only=True)

            if buffer_size == 0:
                log(f"⚠️ Episodes=0 — sprawdź czy Monitor(env) jest aktywny!", "ERROR", ppo_only=True)

        if len(self.model.ep_info_buffer) > 0:
            mean_reward = np.mean([ep['r'] for ep in self.model.ep_info_buffer])
            mean_length = np.mean([ep['l'] for ep in self.model.ep_info_buffer])

            for ep in self.model.ep_info_buffer:
                self.total_episodes += 1
                if ep['r'] > 0:
                    self.winning_episodes += 1
                else:
                    self.losing_episodes += 1
                self.cumulative_pnl += ep['r']

            win_rate = (self.winning_episodes / self.total_episodes * 100) if self.total_episodes > 0 else 0.0
            loss_rate = (self.losing_episodes / self.total_episodes * 100) if self.total_episodes > 0 else 0.0

            log(f"📊 PPO Rollout #{self.num_timesteps//self.log_interval}: "
                f"Mean Reward={mean_reward:.2f}, "
                f"Mean Length={mean_length:.0f}, "
                f"Win Rate={win_rate:.1f}%, "
                f"Loss Rate={loss_rate:.1f}%, "
                f"Episodes={self.total_episodes} (W:{self.winning_episodes}, L:{self.losing_episodes})",
                "INFO", ppo_only=True)

            # Co 10 rolloutów — analiza przegranych transakcji
            if (self.num_timesteps // self.log_interval) % 10 == 0:
                try:
                    if hasattr(self._training_env, 'envs') and len(self._training_env.envs) > 0:
                        env = self._training_env.envs[0]
                        if hasattr(env, 'unwrapped'):
                            env = env.unwrapped
                        if hasattr(env, 'get_losing_trades_summary'):
                            summary = env.get_losing_trades_summary()
                            if summary.get('losing_trades', 0) > 0:
                                log(f"📉 Losing Trades: {summary['losing_trades']} ({summary['loss_rate']:.1f}%) | "
                                    f"Avg Loss: {summary['avg_loss_pct']:.2f}% | Max Loss: {summary['max_loss_pct']:.2f}%",
                                    "WARNING", ppo_only=True)
                except Exception:
                    pass

    def _log_training_progress(self):
        progress_pct = (self.num_timesteps / self.total_timesteps) * 100
        win_rate = (self.winning_episodes / self.total_episodes * 100) if self.total_episodes > 0 else 0.0

        trade_stats = ""
        try:
            if hasattr(self._training_env, 'envs') and len(self._training_env.envs) > 0:
                env = self._training_env.envs[0]
                if hasattr(env, 'unwrapped'):
                    env = env.unwrapped
                total_t = getattr(env, 'total_trades', 0)
                win_t = getattr(env, 'winning_trades', 0)
                loss_t = getattr(env, 'losing_trades', 0)
                twr = (win_t / total_t * 100) if total_t > 0 else 0.0
                trade_stats = f" | Trades: {total_t} (W:{win_t}, L:{loss_t}, WR:{twr:.1f}%)"
        except Exception:
            pass

        log(f"🎯 PPO Progress: {self.num_timesteps}/{self.total_timesteps} steps ({progress_pct:.1f}%) | "
            f"Episodes: {self.total_episodes} (W:{self.winning_episodes}, L:{self.losing_episodes}) | "
            f"Episode Win Rate: {win_rate:.1f}% | "
            f"Accuracy: {win_rate:.1f}%{trade_stats} | "
            f"Cumulative Reward: {self.cumulative_pnl:.2f}",
            "SUCCESS", ppo_only=True)

    def _save_checkpoint(self):
        import os
        try:
            win_rate = (self.winning_episodes / self.total_episodes * 100) if self.total_episodes > 0 else 0.0
            progress_pct = (self.num_timesteps / self.total_timesteps) * 100
            checkpoint_name = f"ppo_checkpoint_{self.num_timesteps}"
            checkpoint_path = os.path.join(self.checkpoint_dir, checkpoint_name)

            self.model.save(checkpoint_path)

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

            with open(checkpoint_path + '_metadata.json', 'w') as f:
                json.dump(metadata, f, indent=2)

            log(f"💾 Checkpoint: {checkpoint_name}.zip | "
                f"Steps: {self.num_timesteps}/{self.total_timesteps} ({progress_pct:.1f}%) | "
                f"Win Rate: {win_rate:.1f}%",
                "SUCCESS", ppo_only=True)

        except Exception as e:
            log(f"❌ Checkpoint save failed: {e}", "ERROR", ppo_only=True)


# ═══════════════════════════════════════════════════════════════════════════
# 4. ENTROPY DECAY CALLBACK
# ═══════════════════════════════════════════════════════════════════════════

class EntropyDecayCallback(BaseCallback):
    """
    Liniowy decay entropii od ent_coef_start do ent_coef_end.

    DLACZEGO:
    - Faza eksploracji (start): ent_coef = 0.05 — wymusza eksplorację,
      wyrywa agenta ze zdegenerowanej polityki (95.5% jedna akcja).
    - Faza eksploatacji (koniec): ent_coef = 0.005 — agent precyzyjnie
      uderza w znalezione okazje zamiast rzucać monetą.

    Zmiana jest płynna i liniowa — brak skoków które destabilizowałyby trening.

    Użycie (w process_rl_trainer.py):
        callback = [TradingCallback(...), EntropyDecayCallback(total_timesteps)]
        agent.train(total_timesteps=total_timesteps, callback=callback)
    """

    def __init__(
        self,
        total_timesteps: int,
        ent_coef_start: float = 0.05,
        ent_coef_end: float   = 0.005,
        verbose: int = 0
    ):
        super().__init__(verbose)
        self.total_timesteps  = total_timesteps
        self.ent_coef_start   = ent_coef_start
        self.ent_coef_end     = ent_coef_end
        self._last_logged_pct = -1

    def _on_step(self) -> bool:
        # Liniowa interpolacja: 0.05 → 0.005 przez cały trening
        progress = min(self.num_timesteps / self.total_timesteps, 1.0)
        new_ent_coef = self.ent_coef_start + (self.ent_coef_end - self.ent_coef_start) * progress
        self.model.ent_coef = float(new_ent_coef)

        # Log co 10% postępu (nie spamuj)
        pct = int(progress * 10)
        if pct != self._last_logged_pct:
            self._last_logged_pct = pct
            log(f"🔧 Entropy Decay: ent_coef={new_ent_coef:.4f} "
                f"(progress={progress*100:.0f}%)",
                "INFO", ppo_only=True)

        return True




def create_env_from_data(
    df: pd.DataFrame,
    lstm_predictions: Optional[pd.Series] = None,
    lstm_confidences: Optional[pd.Series] = None,
    initial_balance: float = 1000.0,
    **kwargs
) -> TradingEnv:
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
    env = create_env_from_data(test_df, lstm_predictions, lstm_confidences, initial_balance)
    obs, _ = env.reset()

    total_reward = 0.0
    done = False

    log(f"🔬 Starting backtest on {len(test_df)} candles...", "INFO")

    while not done:
        action = agent.predict(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        done = terminated or truncated

        if render and env.current_step % 100 == 0:
            env.render()

    final_balance = info['balance']
    total_return_pct = ((final_balance - initial_balance) / initial_balance) * 100
    win_rate = info['win_rate'] * 100

    log(f"✅ Backtest Complete!", "SUCCESS")
    log(f"   Initial Balance: ${initial_balance:.2f}", "INFO")
    log(f"   Final Balance: ${final_balance:.2f}", "INFO")
    log(f"   Total Return: {total_return_pct:+.2f}%",
        "SUCCESS" if total_return_pct > 0 else "ERROR")
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
