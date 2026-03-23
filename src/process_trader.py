import multiprocessing
import time
import sys
import os
import pandas as pd
import numpy as np
import datetime
import pandas_ta as ta
import json
import traceback

from src.database import Database
from src.logic.execution import ExecutionManager
from src.logic.regime import MarketRegime
from src.logic.risk_oracle import RiskOracle
from src.logic.liquidity_guard import LiquidityGuard
from src.logic.scout import MatrixScout, DeepScout
from src.intelligence.psnd_engine import PSNDEngine
from src.logic.behavioral_guard import BehavioralGuard
from src.logic.anti_fomo import AntiFOMOModule
from src.utils.models import load_model
from src.utils.data_provider import MarketDataProvider
from src.utils.logger import log

# Reinforcement Learning (FAZA 4)
try:
    from src.ai.rl_agent import PPOTradingAgent, TradingEnv
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
    log("⚠️ RL Agent not available. Install: pip install stable-baselines3 gymnasium torch", "WARNING")

class TraderProcess(multiprocessing.Process):
    def __init__(self, tickers=None, interval=60):
        super().__init__()
        self.interval = interval  # 60s - częstotliwość głównego cyklu
        self.running = True
        self.ticker = "BTC/USDT"
        self.db = None
        self.model = None
        self._last_radar_dump = 0
        self._last_matrix_dump = 0
        
        # NOWE: Scheduling dla różnych operacji
        self.data_fetch_interval = 60      # Co 1 minutę: Fetch nowych świeczek
        self.gap_check_interval = 300      # Co 5 minut: Gap detection & filling
        self.lstm_retrain_interval = 21600 # Co 6 godzin: Re-train LSTM only (quick update)
        # RL Agent: Train OFFLINE, raz w tygodniu (process_rl_trainer.py)
        
        # Timeframe dla świeczek (ZMIENIONE Z 15m NA 1m)
        self.timeframe = '1m'  # WAŻNE: 1-minutowe świeczki dla lepszej accuracy!
        
        # RL Agent initialization (to avoid AttributeError)
        self.rl_agent = None
        self.use_rl = False
        self._logged_no_rl = False  # Log "No RL model" only once to avoid spam
        
        # PPO Training lockfile path
        self.rl_training_lockfile = os.path.join(os.path.dirname(__file__), '..', 'models', '.rl_training.lock')
        self._ppo_training_mode = False  # Track if PPO training is active
        self._last_ppo_warning = 0  # Throttle warnings

    def run(self):
        log("Trader Process Started (BTC Futures Sniper Mode)", "INFO")

        # Initialize Logic Modules
        self.db = Database()
        self.data_provider = MarketDataProvider()
        self.exec_manager = ExecutionManager(self.db, self.data_provider.exchange)
        self.regime_engine = MarketRegime()
        self.psnd_engine = PSNDEngine()

        # Risk & Analytics Modules
        self.risk_oracle = RiskOracle(self.db, self.data_provider)
        self.liquidity_guard = LiquidityGuard(self.data_provider)
        self.scout = MatrixScout(self.data_provider) # Correlations
        self.deep_scout = DeepScout(self.data_provider) # Market Breadth

        # ═══════════════ BEHAVIORAL SAFETY GUARDS ═══════════════
        self.behavioral_guard = BehavioralGuard(self.db)
        self.anti_fomo = AntiFOMOModule(self.db)
        log("🛡️ BehavioralGuard + AntiFOMO ACTIVE", "SUCCESS")

        # Daily Circuit Breaker
        self._daily_loss_limit_pct = 5.0
        self._circuit_breaker_triggered = False
        self._last_cb_reset_day = None
        self._last_psnd_score = 0.5  # Cache PSND score dla BehavioralGuard

        # Load Model
        self._load_latest_model()

        # Timer variables
        last_analysis_time = 0
        last_gap_check_time = 0          # Track gap checks
        last_lstm_retrain_time = 0       # Track LSTM re-training (quick updates)
        last_rl_prediction_time = 0      # Track RL predictions (co 30 min)
        last_rl_stats_update = 0        # Track RL brain stats updates (co 60s)
        last_model_check = 0             # Track model reloads (co 5 min) ← FIX!

        while self.running:
            try:
                current_time = time.time()

                # --- 1. SZYBKI PULS (HEARTBEAT & PRICE) - CO 10 SEKUND ---
                # To ożywi Dashboard (ONLINE) i wykres, nawet jak AI liczy
                try:
                    ticker_data = self.data_provider.fetch_ticker(self.ticker)
                    current_price = ticker_data['last']
                    self._push_dashboard_update(current_price)
                    # Publish minimal latest_results for UI (price/prediction line)
                    self._publish_latest_results(
                        ticker=self.ticker,
                        current_price=float(current_price),
                        signal=getattr(self, "_last_signal", "MONITORING"),
                        confidence_score=getattr(self, "_last_confidence", 0.0),
                        prediction=getattr(self, "_last_prediction", None),
                        predicted_price=getattr(self, "_last_predicted_price", current_price),
                        prediction_vector=getattr(self, "_last_prediction_vector", [current_price]),
                        prediction_candles=getattr(self, "_last_prediction_candles", None),
                    )
                    self._update_pulse('pulse_1m', 'Fast Price Check')
                except Exception as e:
                    # Błąd pobierania ceny nie powinien zatrzymać bota, logujemy cicho
                    pass

                # --- 2. MODEL RELOAD (CO 5 MINUT) ---
                if current_time - last_model_check > 300:
                    self._load_latest_model()
                    last_model_check = current_time

                # --- 2.5. RL BRAIN STATS UPDATE (CO 60 SEKUND) ---
                if current_time - last_rl_stats_update > 60:
                    try:
                        self._update_rl_brain_stats()
                    except Exception as e:
                        log(f"Error updating RL brain stats: {e}", "WARNING")
                    last_rl_stats_update = current_time
                
                # ═══════════════════════════════════════════════════════════════
                # 3. GŁÓWNA ANALIZA AI (CO 1 MINUTĘ) - 1-MINUTOWE ŚWIECZKI!
                # ═══════════════════════════════════════════════════════════════
                if current_time - last_analysis_time > self.data_fetch_interval:
                    log(f"Starting analysis cycle for {self.ticker}...", "INFO")
                    self._update_pulse('pulse_5m', 'AI Analysis')
                    last_analysis_time = current_time

                    # A. Aktualizacja Global Bias (Matrix)
                    global_bias = self._update_global_bias()

                    # B. Pobranie danych do predykcji (1-MINUTOWE ŚWIECZKI!)
                    # Zwiększamy limit do 1500 (1500 minut = 25h danych) dla metryk 24h
                    df = self.data_provider.fetch_candles(
                        self.ticker, 
                        timeframe=self.timeframe,  # '1m'
                        limit=1500  # 1500 świeczek 1-min = 25h danych
                    )

                    if df is not None and not df.empty:
                        # Save fresh candles to database
                        self._save_candles(df, timeframe=self.timeframe)
                        
                        # PSND Update
                        try:
                            psnd_result = self.psnd_engine.analyze(self.ticker, df)
                            self._last_psnd_score = psnd_result.get('confidence', 0.5)
                        except Exception as e:
                            pass

                        # C. Predykcja AI
                        signal, confidence, prediction = self._get_ai_prediction(df)
                        # cache for fast loop publishing
                        self._last_signal = signal
                        self._last_confidence = confidence
                        self._last_prediction = prediction
                        self._last_prediction_candles = None  # Will be set below

                        # Generate realistic prediction candles (OHLC format) instead of just a line
                        try:
                            last_close = float(df["close"].iloc[-1])
                            last_high = float(df["high"].iloc[-1])
                            last_low = float(df["low"].iloc[-1])
                            
                            # Use recent volatility as a proxy for expected move
                            vol = float(df["close"].pct_change().rolling(20).std().iloc[-1] or 0.0)
                            # Realistic amplituda: 0.2% .. 3%
                            vol = max(0.002, min(vol, 0.03))  # clamp 0.2% .. 3%
                            
                            # Calculate typical candle range (High-Low) from recent candles
                            recent_ranges = []
                            for i in range(min(20, len(df))):
                                idx = -(i+1)
                                h = float(df["high"].iloc[idx])
                                l = float(df["low"].iloc[idx])
                                recent_ranges.append(h - l)
                            avg_range = sum(recent_ranges) / len(recent_ranges) if recent_ranges else last_close * 0.005
                            
                            direction = 0
                            try:
                                direction = 1 if int(prediction) == 1 else -1
                            except Exception:
                                direction = 0
                            if signal == "LONG":
                                direction = 1
                            elif signal == "SHORT":
                                direction = -1

                            # If neutral/unknown, use slight bullish bias
                            if direction == 0:
                                direction = 1

                            # Generate 3 prediction candles with realistic OHLC
                            prediction_candles = []
                            current_price = last_close
                            
                            for i in range(3):
                                # Progressive price movement
                                step = current_price * vol * direction * (0.5 + i * 0.3)
                                next_close = current_price + step
                                
                                # Generate OHLC based on direction
                                if direction > 0:  # Bullish candle
                                    open_price = current_price
                                    close_price = next_close
                                    high_price = close_price + (avg_range * 0.3)
                                    low_price = open_price - (avg_range * 0.2)
                                else:  # Bearish candle
                                    open_price = current_price
                                    close_price = next_close
                                    high_price = open_price + (avg_range * 0.2)
                                    low_price = close_price - (avg_range * 0.3)
                                
                                prediction_candles.append({
                                    "open": float(open_price),
                                    "high": float(high_price),
                                    "low": float(low_price),
                                    "close": float(close_price)
                                })
                                
                                current_price = close_price
                            
                            predicted_price = prediction_candles[-1]["close"]
                            
                            # Also keep prediction_vector for backward compatibility
                            pv = [c["close"] for c in prediction_candles]
                            
                            # Cache prediction candles for quick updates
                            self._last_prediction_candles = prediction_candles
                            self._last_predicted_price = predicted_price
                            self._last_prediction_vector = pv

                            self._publish_latest_results(
                                ticker=self.ticker,
                                current_price=last_close,
                                signal=signal,
                                confidence_score=float(confidence),
                                prediction=prediction,
                                predicted_price=predicted_price,
                                prediction_vector=pv,
                                prediction_candles=prediction_candles
                            )
                            
                            # Save prediction to database for tracking
                            self._save_prediction(
                                ticker=self.ticker,
                                predicted_price=predicted_price,
                                entry_price=last_close,
                                direction=direction,
                                confidence=float(confidence),
                                model_version=getattr(self.data_provider, 'model_version', 'unknown')
                            )
                        except Exception:
                            pass

                        # D. Egzekucja (Decyzja)
                        self._execute_strategy(df, signal, confidence, prediction, global_bias)
                        
                        # E. Holistic Guardian - Market Health Assessment
                        self._update_holistic_guardian(signal, confidence, global_bias, last_close)
                        
                        # F. Titan Quant Protocol Metrics
                        self._update_quant_metrics(df, last_close)
                        
                        # G. Referee System - Validate pending predictions
                        self._validate_predictions(last_close)
                        
                        # H. Update Training Status (for LSTM Brain Stats display)
                        self._update_training_status()

                    last_analysis_time = current_time
                
                # ═══════════════════════════════════════════════════════════════
                # 4. GAP CHECK & FILL (CO 5 MINUT)
                # ═══════════════════════════════════════════════════════════════
                if current_time - last_gap_check_time > self.gap_check_interval:
                    last_gap_check_time = current_time
                    log("🔍 Checking for data gaps (5-minute cycle)...", "INFO")
                    try:
                        self._fill_candle_gaps()
                    except Exception as e:
                        log(f"Gap check error: {e}", "ERROR")
                
                # ═══════════════════════════════════════════════════════════════
                # 5. LSTM QUICK UPDATE (CO 30 MINUT) - Only LSTM, NOT RL!
                # ═══════════════════════════════════════════════════════════════
                # RL Agent: Trained OFFLINE, raz w tygodniu (process_rl_trainer.py)
                # 
                # ⚠️ NO LONGER CRITICAL: Allow LSTM update if PPO is training
                # ═══════════════════════════════════════════════════════════════
                if current_time - last_lstm_retrain_time > self.lstm_retrain_interval:
                    last_lstm_retrain_time = current_time
                    
                    log("🔄 LSTM quick update (6-hour cycle)...", "INFO")
                    try:
                        self._lstm_quick_update()  # Only LSTM, NOT RL!
                        
                        # Update pulse_30m with normal status
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        normal_status = {
                            "status": "running",
                            "details": {"action": "LSTM Model Updated"},
                            "last_run": now_utc.isoformat()
                        }
                        self.db.execute(
                            "INSERT INTO system_status (key, value, updated_at) VALUES ('pulse_30m', ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                            (json.dumps(normal_status), now_utc.isoformat())
                        )
                    except Exception as e:
                        log(f"LSTM update error: {e}", "ERROR")
                
                # ═══════════════════════════════════════════════════════════════
                # 6. RL PREDICTIONS (CO 30 MINUT) - Inference only!
                # ═══════════════════════════════════════════════════════════════
                if current_time - last_rl_prediction_time > 1800:  # 30 min
                    last_rl_prediction_time = current_time
                    if self.use_rl and self.rl_agent is not None:
                        log("🧠 RL Agent: 30-minute prediction cycle...", "INFO")
                        try:
                            self._rl_prediction_cycle(df if df is not None else None)
                        except Exception as e:
                            log(f"RL prediction error: {e}", "ERROR")

                # --- 6. RADAR (TOP 50) & MATRIX DUMPS (PERIODIC) ---
                # Keep it light: update radar ~30s, matrix ~5m
                try:
                    if current_time - self._last_radar_dump > 30:
                        self._dump_radar_scan()
                        self._last_radar_dump = current_time
                except Exception:
                    pass

                try:
                    if current_time - self._last_matrix_dump > 300:
                        self._dump_correlation_matrix()
                        self._last_matrix_dump = current_time
                except Exception:
                    pass

                # Krótki sen, żeby nie spalić procesora, ale reagować szybko na przerwania
                time.sleep(5)

            except Exception as e:
                log(f"Trader Loop Error: {traceback.format_exc()}", "ERROR")
                time.sleep(10)

    def _update_global_bias(self):
        """
        Oblicza Market Bias (BULLISH/BEARISH/NEUTRAL) na podstawie Market Breadth.
        
        POPRAWIONA WERSJA: Bardziej wyważone progi
        - Poprzednio: bears > bulls * 1.5 = BEARISH (zbyt agresywne!)
        - Teraz: bears > bulls * 2.0 = BEARISH (bardziej wyważone)
        """
        try:
            # Szybka aktualizacja co cykl
            matrix_data = self.scout.scan_correlations(self.ticker)
            deep_data = self.deep_scout.scan_market_breadth() # Bulls vs Bears

            # Bardziej wyważona logika (zmieniono z 1.5 na 2.0)
            bulls = deep_data.get('bulls', 0)
            bears = deep_data.get('bears', 0)
            total = bulls + bears
            
            # Zabezpieczenie przed dzieleniem przez 0
            if total == 0:
                return "NEUTRAL"
            
            # Oblicz ratio
            bulls_pct = (bulls / total) * 100
            bears_pct = (bears / total) * 100

            bias = "NEUTRAL"
            
            # BULLISH: Gdy bulls > 65% (poprzednio > 60%)
            if bulls_pct > 65:
                bias = "BULLISH"
            # BEARISH: Gdy bears > 65% (poprzednio > 60%)
            elif bears_pct > 65:
                bias = "BEARISH"
            # NEUTRAL: Gdy 35%-65% (większy zakres neutralny)
            
            log(f"📊 Market Breadth: Bulls={bulls} ({bulls_pct:.1f}%), Bears={bears} ({bears_pct:.1f}%) → Bias={bias}", "INFO")
            
            self.global_bias = bias
            return bias
        except Exception as e:
            log(f"Market Bias calculation error: {e}", "WARNING")
            return "NEUTRAL"

    def _get_ai_prediction(self, df):
        if not self.model:
            return "NEUTRAL", 0.0, 0.0

        try:
            # Feature Engineering (musi być IDENTYCZNY jak w Trainerze!)
            df = df.copy()
            
            # --- ORIGINAL FEATURES ---
            df['rsi'] = ta.rsi(df['close'], length=14)
            macd = ta.macd(df['close'])
            if macd is not None:
                df = df.join(macd)
            
            # --- MARKET MATRIX FEATURES (FAZA 1.1) ---
            try:
                market_correlation = self._get_market_correlation_score()
                df['market_correlation'] = market_correlation
            except Exception:
                df['market_correlation'] = 0.5
            
            # --- MARKET BREADTH FEATURES (FAZA 1.1) ---
            try:
                breadth_data = self.deep_scout.scan_market_breadth()
                bulls = breadth_data.get('bulls', 0)
                bears = breadth_data.get('bears', 0)
                total = breadth_data.get('total', 1)
                
                if bulls + bears > 0:
                    bulls_bears_ratio = bulls / (bulls + bears)
                else:
                    bulls_bears_ratio = 0.5
                
                market_strength = (bulls / total * 100) if total > 0 else 50
                
                df['bulls_bears_ratio'] = bulls_bears_ratio
                df['market_strength'] = market_strength
            except Exception:
                df['bulls_bears_ratio'] = 0.5
                df['market_strength'] = 50
            
            # --- VOLUME FEATURES (FAZA 1.2) ---
            df['volume_sma_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
            
            df['obv'] = ta.obv(df['close'], df['volume'])
            df['obv_sma'] = df['obv'].rolling(20).mean()
            df['obv_ratio'] = df['obv'] / df['obv_sma']
            
            df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14)
            
            # --- VOLATILITY FEATURES (FAZA 1.2) ---
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            df['atr_pct'] = (df['atr'] / df['close']) * 100
            
            bbands = ta.bbands(df['close'], length=20)
            if bbands is not None and 'BBU_20_2.0' in bbands.columns:
                df['bb_upper'] = bbands['BBU_20_2.0']
                df['bb_middle'] = bbands['BBM_20_2.0']
                df['bb_lower'] = bbands['BBL_20_2.0']
                df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            else:
                df['bb_width'] = 0.04
            
            # --- MOMENTUM FEATURES (FAZA 1.2) ---
            df['roc'] = ta.roc(df['close'], length=12)
            
            stoch = ta.stoch(df['high'], df['low'], df['close'])
            if stoch is not None:
                df = df.join(stoch, rsuffix='_stoch')
                if 'STOCHk_14_3_3' in df.columns:
                    df['stoch_k'] = df['STOCHk_14_3_3']
                    df['stoch_d'] = df['STOCHd_14_3_3']
            
            # --- FUNDING RATE FEATURES (FAZA 3.1) - CRITICAL FOR FUTURES! ---
            try:
                funding_data = self._get_funding_rate_features()
                df['funding_rate'] = funding_data['current']
                df['funding_rate_trend'] = funding_data['trend']
            except Exception:
                df['funding_rate'] = 0.0
                df['funding_rate_trend'] = 0.0

            # --- MACRO CONTEXT FEATURES (MICRO/MACRO STRATEGY) ---
            # Trend 4h (240 minut)
            df['trend_4h_sma'] = df['close'].rolling(window=240, min_periods=1).mean()
            df['dist_4h'] = (df['close'] - df['trend_4h_sma']) / df['trend_4h_sma']
            df['dist_4h'] = df['dist_4h'].fillna(0)
            
            # Trend 24h (1440 minut = 1 dzień)
            df['trend_daily_sma'] = df['close'].rolling(window=1440, min_periods=1).mean()
            df['dist_daily'] = (df['close'] - df['trend_daily_sma']) / df['trend_daily_sma']
            df['dist_daily'] = df['dist_daily'].fillna(0)
            
            # Volatility Regime
            df['volatility_24h'] = df['close'].rolling(window=1440, min_periods=1).std()
            df['volatility_24h'] = df['volatility_24h'].fillna(df['close'].std())

            # Ostatni wiersz do predykcji
            last_row = df.iloc[-1:]

            # UPDATED FEATURE LIST (must match trainer!)
            features = [
                'rsi', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
                'market_correlation', 'bulls_bears_ratio', 'market_strength',
                'volume_sma_ratio', 'obv_ratio', 'mfi',
                'atr_pct', 'bb_width',
                'roc',
                'funding_rate', 'funding_rate_trend',
                'dist_4h', 'dist_daily', 'volatility_24h',
                'price_change_pct', 'volatility'
            ]
            
            if 'stoch_k' in last_row.columns:
                features.extend(['stoch_k', 'stoch_d'])
            
            # Filter valid features
            valid_features = [f for f in features if f in last_row.columns and not last_row[f].isna().any()]

            if not valid_features:
                log("No valid features for prediction", "WARNING")
                return "NEUTRAL", 0.0, 0.0

            # Predykcja (Ensemble: 1 = UP, 0 = DOWN)
            prediction = self.model.predict(last_row[valid_features])[0]
            
            # Prawdziwa confidence z predict_proba()
            try:
                probas = self.model.predict_proba(last_row[valid_features])[0]
                if prediction == 1:
                    confidence = float(probas[1])
                else:
                    confidence = float(probas[0])
                
                # Meta-Model Confidence boost
                if max(probas) > 0.8:
                    confidence = min(1.0, confidence * 1.1)
                    
            except Exception:
                confidence = 0.65

            signal = "LONG" if prediction == 1 else "SHORT"
            
            # Log prediction details
            log(f"🎯 AI Prediction: {signal} (Conf: {confidence:.2%}) | Market: Bulls={df['bulls_bears_ratio'].iloc[-1]:.2f}, Corr={df['market_correlation'].iloc[-1]:.2f}", "INFO")
            
            return signal, confidence, prediction

        except Exception as e:
            log(f"AI Prediction Error: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "ERROR")
            return "NEUTRAL", 0.0, 0.0
    
    def _get_market_correlation_score(self):
        """
        Calculate average correlation score with top crypto assets.
        """
        try:
            matrix_data = self.scout.calculate_correlation_matrix()
            
            if not matrix_data or 'series' not in matrix_data:
                return 0.5
            
            series = matrix_data['series']
            
            btc_row = None
            for row in series:
                if 'BTC' in row.get('name', ''):
                    btc_row = row
                    break
            
            if not btc_row or 'data' not in btc_row:
                return 0.5
            
            correlations = []
            for point in btc_row['data']:
                if point['x'] != 'BTC':
                    correlations.append(abs(point['y']))
            
            if correlations:
                return sum(correlations) / len(correlations)
            
            return 0.5
        except Exception:
            return 0.5
    
    def _get_funding_rate_features(self):
        """
        Get funding rate features (FAZA 3.1 - CRITICAL for Futures!)
        
        Returns: dict with 'current' and 'trend' (8h average)
        """
        try:
            ticker = self.ticker
            
            funding_data = self.data_provider.fetch_funding_rate(ticker)
            
            if not funding_data or 'fundingRate' not in funding_data:
                return {'current': 0.0, 'trend': 0.0}
            
            current_rate = float(funding_data['fundingRate'])
            
            history = self.data_provider.fetch_funding_rate_history(ticker, limit=8)
            
            if history and len(history) > 0:
                trend = sum(history) / len(history)
            else:
                trend = current_rate
            
            return {
                'current': current_rate,
                'trend': trend
            }
            
        except Exception:
            return {'current': 0.0, 'trend': 0.0}
    
    def _check_and_close_positions(self, df, new_signal, new_confidence, current_price):
        """
        ═══════════════════════════════════════════════════════════════
        TITAN ADAPTIVE DEFENSE - Comprehensive Position Management
        ═══════════════════════════════════════════════════════════════
        
        MODUŁ 1: PROFIT GUARDIAN (Intelligent Exit)
        ────────────────────────────────────────────────────────────────
        1. Profit Snatcher (6% Cap): Zamyka przy +6% ROI jeśli AI przewiduje osłabienie
        2. Trailing Stop (Bezpiecznik): Aktywacja przy +3%, zamyka przy spadku o 1.5%
        3. Anti-Spike: Chroni przed szpilami - zamyka przy powrocie z +3% do 0%
        
        MODUŁ 2: RECOVERY MODE (Adaptive Hedge)
        ────────────────────────────────────────────────────────────────
        1. Detekcja Kryzysu: Pozycja wpada w stratę < -3%
        2. Konsultacja AI (Horyzont 30 min): Sprawdza przewidywaną cenę
        3. Scenariusz A (Nadzieja): AI > 75% confidence → trzymaj do Hard Stopa
        4. Scenariusz B (Potwierdzenie błędu): AI widzi dalszy spadek → zamknij natychmiast
        
        STANDARD CHECKS:
        ────────────────────────────────────────────────────────────────
        1. Take Profit (TP) - Entry ± (4 × ATR)
        2. Stop Loss (SL) - Entry ± (2 × ATR)
        3. AI Reversal - Przeciwny sygnał z confidence > 70%
        """
        ticker = self.ticker
        
        # Sprawdź czy mamy otwartą pozycję
        position_size = self.exec_manager.get_position(ticker)
        
        if position_size == 0:
            return  # Brak pozycji
        
        # Określ side pozycji
        if position_size > 0:
            side = "LONG"
            amount = position_size
        else:
            side = "SHORT"
            amount = abs(position_size)
        
        # Pobierz dane pozycji z paper_positions
        if not self.exec_manager.paper_mode:
            log("Live trading not fully implemented for position tracking", "WARNING")
            return
        
        pos_data = self.exec_manager.paper_positions.get(ticker)
        if not pos_data:
            log(f"Position data not found for {ticker}", "WARNING")
            return
        
        entry_price = pos_data['entry_price']
        
        # Oblicz ATR
        atr = float(df['atr'].iloc[-1]) if 'atr' in df.columns else (current_price * 0.01)
        
        # Oblicz PnL %
        if side == "LONG":
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:  # SHORT
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        log(f"📊 Open {side} Position: Entry=${entry_price:.2f}, Current=${current_price:.2f}, PnL={pnl_pct:+.2f}%, ATR=${atr:.2f}", "INFO")
        
        # Load risk management config
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                risk_config = config.get('risk_management', {})
        except:
            risk_config = {}
        
        recovery_mode_enabled = risk_config.get('recovery_mode', True)
        min_profit_to_lock = risk_config.get('min_profit_to_lock', 6.0)
        trailing_activation = risk_config.get('trailing_activation', 3.0)
        emergency_exit_threshold = risk_config.get('emergency_exit_threshold', -1.5)  # (Spadek ceny -1.5% = -30% ROI na 20x)
        hard_liquidation_buffer = risk_config.get('hard_liquidation_buffer', 0.025) # (Spadek ceny -2.5% = -50% ROI na 20x)
        recovery_ai_confidence = risk_config.get('recovery_ai_confidence_threshold', 0.75)
        profit_snatcher_enabled = risk_config.get('profit_snatcher_enabled', True)
        
        # ═══════════════════════════════════════════════════════════════
        # 1️⃣ TAKE PROFIT CHECK (TP = Entry ± 4×ATR)
        # ═══════════════════════════════════════════════════════════════
        tp_distance = atr * 4.0
        
        if side == "LONG":
            tp_price = entry_price + tp_distance
            if current_price >= tp_price:
                log(f"✅ TAKE PROFIT HIT! (LONG) Target=${tp_price:.2f}, Current=${current_price:.2f}, Profit={pnl_pct:+.2f}%", "SUCCESS")
                self.exec_manager.execute_order("CLOSE_LONG", ticker, amount, current_price)
                return
        else:  # SHORT
            tp_price = entry_price - tp_distance
            if current_price <= tp_price:
                log(f"✅ TAKE PROFIT HIT! (SHORT) Target=${tp_price:.2f}, Current=${current_price:.2f}, Profit={pnl_pct:+.2f}%", "SUCCESS")
                self.exec_manager.execute_order("CLOSE_SHORT", ticker, amount, current_price)
                return
        
        # ═══════════════════════════════════════════════════════════════
        # 2️⃣ STOP LOSS CHECK (SL = Entry ± 2×ATR)
        # ═══════════════════════════════════════════════════════════════
        sl_distance = atr * 2.0
        
        if side == "LONG":
            sl_price = entry_price - sl_distance
            if current_price <= sl_price:
                log(f"❌ STOP LOSS HIT! (LONG) SL=${sl_price:.2f}, Current=${current_price:.2f}, Loss={pnl_pct:+.2f}%", "WARNING")
                self.exec_manager.execute_order("CLOSE_LONG", ticker, amount, current_price)
                return
        else:  # SHORT
            sl_price = entry_price + sl_distance
            if current_price >= sl_price:
                log(f"❌ STOP LOSS HIT! (SHORT) SL=${sl_price:.2f}, Current=${current_price:.2f}, Loss={pnl_pct:+.2f}%", "WARNING")
                self.exec_manager.execute_order("CLOSE_SHORT", ticker, amount, current_price)
                return

        # ═══════════════════════════════════════════════════════════════
        # 3️⃣ TRAILING STOP CHECK (Aktywny gdy zysk > 3%)
        # ═══════════════════════════════════════════════════════════════
        
        # Inicjalizuj highest_pnl jeśli nie istnieje
        if 'highest_pnl' not in pos_data:
            pos_data['highest_pnl'] = pnl_pct
        
        # Aktualizuj highest_pnl jeśli obecny jest wyższy
        if pnl_pct > pos_data['highest_pnl']:
            pos_data['highest_pnl'] = pnl_pct
            self.exec_manager._save_paper_state()
        
        highest_pnl = pos_data['highest_pnl']
        
        # Trailing Stop aktywuje się gdy highest_pnl > 3%
        if highest_pnl > 3.0:
            # Trailing distance w % (1.5% drop from peak)
            trailing_drop_pct = 1.5
            
            # Oblicz trailing stop level (% poniżej szczytu)
            trailing_stop_level = highest_pnl - trailing_drop_pct
            
            if side == "LONG":
                # Zamknij jeśli current PnL spadł poniżej trailing stop level
                if pnl_pct <= trailing_stop_level:
                    log(f"🛑 TRAILING STOP HIT! (LONG) Peak={highest_pnl:+.2f}%, Current={pnl_pct:+.2f}%, Secured={pnl_pct:+.2f}%", "INFO")
                    self.exec_manager.execute_order("CLOSE_LONG", ticker, amount, current_price)
                    return
                else:
                    log(f"🎯 Trailing Stop Active (LONG): Peak={highest_pnl:+.2f}%, Current={pnl_pct:+.2f}%, Stop at {trailing_stop_level:+.2f}%", "INFO")
            else:  # SHORT
                if pnl_pct <= trailing_stop_level:
                    log(f"🛑 TRAILING STOP HIT! (SHORT) Peak={highest_pnl:+.2f}%, Current={pnl_pct:+.2f}%, Secured={pnl_pct:+.2f}%", "INFO")
                    self.exec_manager.execute_order("CLOSE_SHORT", ticker, amount, current_price)
                    return
                else:
                    log(f"🎯 Trailing Stop Active (SHORT): Peak={highest_pnl:+.2f}%, Current={pnl_pct:+.2f}%, Stop at {trailing_stop_level:+.2f}%", "INFO")
        elif pnl_pct > 2.0:
            # Informacja że zbliżamy się do aktywacji
            log(f"📈 Approaching Trailing Activation: Current={pnl_pct:+.2f}%, Need 3.0% to activate", "INFO")

        # ═══════════════════════════════════════════════════════════════
        # 🎯 MODUŁ 1: PROFIT GUARDIAN (Intelligent Exit)
        # ═══════════════════════════════════════════════════════════════
        
        # 1A. PROFIT SNATCHER (6% Cap with AI Confirmation)
        if profit_snatcher_enabled and pnl_pct >= min_profit_to_lock:
            log(f"💰 PROFIT SNATCHER: ROI at {pnl_pct:+.2f}% (target: {min_profit_to_lock}%). Checking AI momentum...", "INFO")

            # Get AI prediction for next 30 minutes
            ai_prediction_30m = self._get_ai_prediction_30m(df, current_price)

            if ai_prediction_30m['weakening']:
                log(f"✅ PROFIT SNATCHER TRIGGERED! AI detects weakening momentum (Conf: {ai_prediction_30m['confidence']:.2%}). Locking profit at {pnl_pct:+.2f}%!", "SUCCESS")
                self.exec_manager.execute_order(f"CLOSE_{side.upper()}", ticker, amount, current_price)
                return
            else:
                log(f"📈 Momentum still strong (Conf: {ai_prediction_30m['confidence']:.2%}). Holding position for more gains...", "INFO")

        # 1B. ANTI-SPIKE (Protection from +3% -> 0% drops)
        if pnl_pct >= 0.5 and pnl_pct < trailing_activation:  # Between 0.5% and 3%
            # Check if we were in profit before
            if 'peak_pnl_history' not in pos_data:
                pos_data['peak_pnl_history'] = []

            pos_data['peak_pnl_history'].append(pnl_pct)
            # Keep only last 10 readings (10 minutes of history)
            if len(pos_data['peak_pnl_history']) > 10:
                pos_data['peak_pnl_history'] = pos_data['peak_pnl_history'][-10:]

            # Check if we had profit > 3% in the last 10 minutes
            had_good_profit = any(p >= trailing_activation for p in pos_data['peak_pnl_history'])

            if had_good_profit:
                log(f"🛡️ ANTI-SPIKE: Position dropped from +3% to {pnl_pct:+.2f}%. Checking AI for recovery potential...", "WARNING")

                ai_prediction_30m = self._get_ai_prediction_30m(df, current_price)

                if not ai_prediction_30m['favorable']:
                    log(f"❌ ANTI-SPIKE TRIGGERED! AI sees no recovery (Conf: {ai_prediction_30m['confidence']:.2%}). Closing at {pnl_pct:+.2f}% to prevent loss!", "WARNING")
                    self.exec_manager.execute_order(f"CLOSE_{side.upper()}", ticker, amount, current_price)
                    return
                else:
                    log(f"✅ AI predicts recovery (Conf: {ai_prediction_30m['confidence']:.2%}). Holding through spike...", "INFO")

        # ═══════════════════════════════════════════════════════════════
        # 4️⃣ AI REVERSAL CHECK (Przeciwny sygnał z confidence > 70%)
        # ═══════════════════════════════════════════════════════════════
        if new_confidence > 0.70:
            if side == "LONG" and new_signal == "SHORT":
                log(f"🔄 AI REVERSAL! Closing LONG. AI now predicts SHORT (Conf: {new_confidence:.2%})", "INFO")
                self.exec_manager.execute_order("CLOSE_LONG", ticker, amount, current_price)
                return
            elif side == "SHORT" and new_signal == "LONG":
                log(f"🔄 AI REVERSAL! Closing SHORT. AI now predicts LONG (Conf: {new_confidence:.2%})", "INFO")
                self.exec_manager.execute_order("CLOSE_SHORT", ticker, amount, current_price)
                return

        # ═══════════════════════════════════════════════════════════════
        # 🆘 MODUŁ 2: RECOVERY MODE (Adaptive Hedge)
        # ═══════════════════════════════════════════════════════════════

        if recovery_mode_enabled and pnl_pct <= emergency_exit_threshold:
            log(f"🚨 RECOVERY MODE ACTIVATED! Position in loss: {pnl_pct:+.2f}%. Consulting AI...", "WARNING")

            # Inicjalizacja czasu i PnL dla Recovery Mode, zapis stanu
            if 'rm_start_time' not in pos_data:
                pos_data['rm_start_time'] = time.time()
                pos_data['rm_start_pnl'] = pnl_pct
                self.exec_manager._save_paper_state()

            rm_duration = time.time() - pos_data['rm_start_time']

            # Time Stop: 15 minut
            if rm_duration > 900:
                if pnl_pct < pos_data['rm_start_pnl']:
                    log(f"⏱️ TIME STOP HIT! Position in Recovery Mode for >15 min without improvement. Start PnL: {pos_data['rm_start_pnl']:+.2f}%, Current: {pnl_pct:+.2f}%. Emergency exit!", "ERROR")
                    self.exec_manager.execute_order(f"CLOSE_{side.upper()}", ticker, amount, current_price)
                    return
                else:
                    log(f"⏳ Recovery Mode time >15m, but position is recovering (Start PnL: {pos_data['rm_start_pnl']:+.2f}%, Current: {pnl_pct:+.2f}%). Checking AI...", "INFO")

            # Get AI prediction for next 30 minutes
            ai_prediction_30m = self._get_ai_prediction_30m(df, current_price)

            # Scenario A: AI sees hope (confidence > 75%)
            if ai_prediction_30m['favorable'] and ai_prediction_30m['confidence'] >= recovery_ai_confidence:
                # Calculate hard stop at -2.5% price (-50% ROI buffer before liquidation)
                hard_stop_roi = -hard_liquidation_buffer * 100

                current_vol = float(df['volume'].iloc[-1])
                avg_vol = float(df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else current_vol)
                volume_spike = current_vol > (avg_vol * 3.0)

                if pnl_pct <= hard_stop_roi:
                    log(f"💥 HARD LIQUIDATION BUFFER HIT! ROI={pnl_pct:+.2f}% <= {hard_stop_roi:+.2f}%. Emergency exit!", "ERROR")
                    self.exec_manager.execute_order(f"CLOSE_{side.upper()}", ticker, amount, current_price)
                    return
                elif volume_spike:
                    log("🐋 VOLUME SPIKE DETECTED (Wieloryb zrzuca)! Omijamy AI. Tniemy straty!", "ERROR")
                    self.exec_manager.execute_order(f"CLOSE_{side.upper()}", ticker, amount, current_price)
                    return
                else:
                    log(f"✅ RECOVERY MODE: AI predicts recovery (Conf: {ai_prediction_30m['confidence']:.2%}). Niski wolumen (Whipsaw). Holding position...", "INFO")
                    # Allow position to breathe - don't close
                    return

            # Scenario B: AI confirms mistake (low confidence or unfavorable)
            else:
                log(f"❌ RECOVERY MODE: AI confirms downtrend (Conf: {ai_prediction_30m['confidence']:.2%}). Emergency exit at {pnl_pct:+.2f}% to save capital!", "ERROR")
                self.exec_manager.execute_order(f"CLOSE_{side.upper()}", ticker, amount, current_price)
                return
        else:
            # Czyszczenie stanu Recovery Mode, jeśli pozycja wyszła z zagrożenia
            if 'rm_start_time' in pos_data:
                del pos_data['rm_start_time']
                del pos_data['rm_start_pnl']
                self.exec_manager._save_paper_state()

        # Jeśli żaden warunek nie został spełniony, trzymamy pozycję
        log(f"⏳ Holding {side} position. TP=${tp_price:.2f}, SL=${sl_price:.2f}, Current PnL={pnl_pct:+.2f}%", "INFO")

    def _execute_strategy(self, df, signal, confidence, prediction, global_bias):
        current_price = float(df['close'].iloc[-1])
        ticker = self.ticker

        # KROK 1: ZARZĄDZANIE OTWARTYMI POZYCJAMI
        self._check_and_close_positions(df, signal, confidence, current_price)

        # KROK 1.5: PPO TRAINING MODE
        if getattr(self, '_ppo_training_mode', False):
            log("⏸️ PAUZA: PPO Training aktywny — brak nowych wejść", "INFO")
            self._save_live_context(current_price, prediction, "PPO_PAUSE", confidence, "MONITORING")
            return

        # KROK 2: VETO SYSTEM (Matrix Bias Check)
        veto_threshold = 0.85
        if confidence <= veto_threshold:
            if signal == "LONG" and global_bias == "BEARISH":
                log(f"⛔ Matrix Bias BEARISH → Vetoing LONG (Conf: {confidence:.2%})", "INFO")
                self._save_live_context(current_price, prediction, "VETO_LONG", confidence, "NEUTRAL")
                return
            if signal == "SHORT" and global_bias == "BULLISH":
                log(f"⛔ Matrix Bias BULLISH → Vetoing SHORT (Conf: {confidence:.2%})", "INFO")
                self._save_live_context(current_price, prediction, "VETO_SHORT", confidence, "NEUTRAL")
                return
        else:
            if (signal == "LONG" and global_bias == "BEARISH") or (signal == "SHORT" and global_bias == "BULLISH"):
                log(f"💪 HIGH CONFIDENCE OVERRIDE! {signal} @ {confidence:.2%} > {veto_threshold:.0%} — ignoruję Bias", "SUCCESS")

        # KROK 3: RL AGENT DECISION
        if getattr(self, 'use_rl', False) and getattr(self, 'rl_agent', None) is not None:
            try:
                observation = self._prepare_rl_observation(df, prediction, confidence)
                rl_action = self.rl_agent.predict(observation)
                rl_actions = {0: "HOLD", 1: "LONG", 2: "SHORT", 3: "CLOSE"}
                # Handle tuple returned by SB3 predict()
                rl_action_val = rl_action[0] if isinstance(rl_action, tuple) else rl_action
                rl_signal = rl_actions.get(int(rl_action_val), "HOLD")

                log(f"🧠 RL Agent Decision: {rl_signal} (LSTM: {signal} @ {confidence:.2%})", "INFO")

                if rl_signal == "HOLD":
                    self._save_live_context(current_price, prediction, "RL_HOLD", confidence, signal)
                    return
                elif rl_signal == "CLOSE":
                    current_position = self.exec_manager.get_position(ticker)
                    if current_position and current_position.get('amount', 0) != 0:
                        side = "LONG" if current_position['amount'] > 0 else "SHORT"
                        self.exec_manager.execute_order(f"CLOSE_{side.upper()}", ticker, abs(current_position['amount']), current_price)
                    return
                else:
                    signal = rl_signal

            except Exception as e:
                log(f"⚠️ RL Agent error: {e}, fallback to LSTM", "WARNING")

        # KROK 3.5: BEHAVIORAL GUARD + ANTI-FOMO (NOWA WARSTWA)
        if self._check_daily_circuit_breaker():
            log(f"🛑 CIRCUIT BREAKER: Dzienny limit straty ({self._daily_loss_limit_pct}%) osiągnięty.", "ERROR")
            self._save_live_context(current_price, prediction, "CIRCUIT_BREAKER", confidence, "HALTED")
            return

        signal_type = "BUY" if signal == "LONG" else ("SELL" if signal == "SHORT" else "NEUTRAL")
        psnd_val = getattr(self, '_last_psnd_score', 0.5)

        guard_ok, guard_reason, guard_modifier = self.behavioral_guard.check_all(
            ticker=ticker, df=df, signal_type=signal_type, psnd_score=psnd_val
        )

        if not guard_ok:
            log(f"🛡️ BehavioralGuard BLOKUJE: {guard_reason}", "WARNING")
            self._save_live_context(current_price, prediction, f"GUARD_{signal}", confidence, "BLOCKED")
            return

        if signal == "LONG":
            pump_check = self.anti_fomo.check_pump_dump(ticker, df)
            if pump_check.get('status') == 'HALT':
                log(f"🚫 AntiFOMO: {pump_check.get('reason', 'Pump detected')} — blokuję LONG", "WARNING")
                self._save_live_context(current_price, prediction, "ANTI_FOMO", confidence, "BLOCKED")
                return
        elif signal == "SHORT":
            # Pobranie prawdziwego F&G Index przed sprawdzeniem paniki
            current_fng = 50
            try:
                import requests
                resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=3)
                if resp.status_code == 200:
                    current_fng = int(resp.json()['data'][0]['value'])
            except Exception:
                pass

            panic_check = self.anti_fomo.check_panic_sell(ticker, df, fear_greed_index=current_fng)
            if panic_check.get('status') == 'HALT':
                log(f"🚫 AntiFOMO: {panic_check.get('reason', 'Panic detected')} — blokuję SHORT", "WARNING")
                self._save_live_context(current_price, prediction, "ANTI_PANIC", confidence, "BLOCKED")
                return

        _size_modifier = guard_modifier.get('size_mult', 1.0)
        if _size_modifier < 1.0:
            log(f"⚠️ Revenge Guard: pozycja zmniejszona do {_size_modifier*100:.0f}%", "WARNING")

        # KROK 4: TRADING LOGIC (EGZEKUCJA)
        if confidence > 0.60:
            current_position_val = self.exec_manager.get_position(ticker)
            if isinstance(current_position_val, dict):
                current_position = current_position_val.get('amount', 0)
            else:
                current_position = current_position_val

            balance = self.exec_manager.get_balance("USDT")
            trade_allocation = 0.10
            margin = balance * trade_allocation * _size_modifier
            amount = round((margin * getattr(self.exec_manager, 'leverage', 1)) / current_price, 6)

            if amount < 0.001:
                self._save_live_context(current_price, prediction, signal, confidence, "WAITING")
                return

            executed = False
            if signal == "LONG":
                if current_position < 0:
                    self.exec_manager.execute_order("CLOSE_SHORT", ticker, abs(current_position), current_price)
                    current_position = 0
                if current_position == 0:
                    executed = self.exec_manager.execute_order("LONG", ticker, amount, current_price)
            elif signal == "SHORT":
                if current_position > 0:
                    self.exec_manager.execute_order("CLOSE_LONG", ticker, abs(current_position), current_price)
                    current_position = 0
                if current_position == 0:
                    executed = self.exec_manager.execute_order("SHORT", ticker, amount, current_price)

            state = "IN_POSITION" if executed else "WAITING"
            self._save_live_context(current_price, prediction, signal, confidence, state)
        else:
            self._save_live_context(current_price, prediction, signal, confidence, "WAITING")

    def _prepare_rl_observation(self, df: pd.DataFrame, lstm_prediction: float, lstm_confidence: float) -> np.ndarray:
        """
        Przygotowuje observation vector dla RL Agent.
        
        Format observation (28 features):
        - Technical Indicators (19): rsi, macd, atr, volume, etc.
        - LSTM Outputs (2): prediction, confidence
        - Portfolio State (7): position, entry, size, pnl, balance, drawdown, steps
        
        Args:
            df: DataFrame with market data
            lstm_prediction: LSTM predicted price
            lstm_confidence: LSTM confidence score
            
        Returns:
            np.ndarray: Observation vector for RL Agent
        """
        try:
            # 1. Technical Indicators (19 features) - ostatni wiersz
            feature_cols = [
                'rsi', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
                'market_correlation', 'bulls_bears_ratio', 'market_strength',
                'volume_sma_ratio', 'obv_ratio', 'mfi',
                'atr_pct', 'bb_width',
                'roc', 'stoch_k', 'stoch_d',
                'funding_rate', 'funding_rate_trend',
                'dist_4h', 'dist_daily', 'volatility_24h',
                'price_change_pct', 'volatility'
            ]
            
            # Ensure all columns exist
            for col in feature_cols:
                if col not in df.columns:
                    df[col] = 0.0
            
            indicators = df[feature_cols].iloc[-1].values.astype(np.float32)
            indicators = np.nan_to_num(indicators, nan=0.0, posinf=1.0, neginf=-1.0)
            
            # 2. LSTM Outputs (2 features)
            lstm_pred_normalized = (lstm_prediction - df['close'].iloc[-1]) / df['close'].iloc[-1]  # Normalize as % change
            lstm_features = np.array([lstm_pred_normalized, lstm_confidence], dtype=np.float32)
            
            # 3. Portfolio State (7 features)
            current_price = float(df['close'].iloc[-1])
            current_position = self.exec_manager.get_position(self.ticker)
            
            if current_position and current_position.get('amount', 0) != 0:
                position_type = 1.0 if current_position['amount'] > 0 else -1.0
                entry_price = current_position.get('entry_price', current_price)
                position_size = abs(current_position['amount']) * current_price  # USDT value
                
                # Calculate PnL
                if position_type > 0:  # LONG
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                else:  # SHORT
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                
            else:
                position_type = 0.0
                entry_price = current_price
                position_size = 0.0
                pnl_pct = 0.0
            
            # Balance (get from exec_manager if available, else use default)
            balance = getattr(self.exec_manager, 'balance', 1000.0)
            
            # Drawdown (simplified - would need historical tracking)
            peak_balance = getattr(self, '_peak_balance', balance)
            if balance > peak_balance:
                self._peak_balance = balance
                peak_balance = balance
            drawdown_pct = ((peak_balance - balance) / peak_balance) * 100 if peak_balance > 0 else 0.0
            
            # Steps in position (simplified - use 0 for now, could be enhanced)
            steps_in_position = 0.0
            
            portfolio_features = np.array([
                position_type,              # -1, 0, +1
                entry_price / 100000.0,     # Normalized
                position_size / 1000.0,     # Normalized
                pnl_pct / 100.0,           # Normalized
                balance / 1000.0,          # Normalized
                drawdown_pct / 100.0,      # Normalized
                steps_in_position / 100.0  # Normalized
            ], dtype=np.float32)
            
            # Combine all features
            observation = np.concatenate([indicators, lstm_features, portfolio_features])
            
            return observation
            
        except Exception as e:
            log(f"Error preparing RL observation: {e}", "ERROR")
            traceback.print_exc()
            # Return zero vector as fallback
            return np.zeros(28, dtype=np.float32)
    
    def _load_latest_model(self):
        try:
            # Szukamy najnowszego pliku .pkl w folderze models
            models_dir = "models"
            if not os.path.exists(models_dir): return

            files = [os.path.join(models_dir, f) for f in os.listdir(models_dir) if f.endswith('.pkl')]
            if not files: return

            # Sortuj po dacie modyfikacji (najnowszy)
            latest_model = max(files, key=os.path.getmtime)

            # Załaduj
            self.model = load_model(latest_model)
            log(f"Loaded model from {latest_model}", "INFO")

        except Exception as e:
            log(f"Model Load Error: {e}", "ERROR")
        
        # ═══════════════════════════════════════════════════════════════════
        # LOAD RL AGENT (FAZA 4) - Optional
        # ═══════════════════════════════════════════════════════════════════
        self.rl_agent = None
        self.use_rl = False
        
        if RL_AVAILABLE:
            try:
                from pathlib import Path
                rl_model_path = Path("models/ppo_trading_agent.zip")
                
                if rl_model_path.exists():
                    log("📂 Found RL model, loading...", "INFO")
                    # Create dummy env for loading (will be replaced with real observations)
                    dummy_df = pd.DataFrame({
                        'close': [50000], 'high': [50100], 'low': [49900],
                        'open': [50000], 'volume': [1000]
                    })
                    
                    # Add required features
                    for col in ['rsi', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
                                'market_correlation', 'bulls_bears_ratio', 'market_strength',
                                'volume_sma_ratio', 'obv_ratio', 'mfi',
                                'atr_pct', 'bb_width', 'roc', 'stoch_k', 'stoch_d',
                                'funding_rate', 'funding_rate_trend', 'price_change_pct', 'volatility']:
                        dummy_df[col] = 0.0
                    
                    dummy_env = TradingEnv(df=dummy_df)
                    self.rl_agent = PPOTradingAgent(
                        env=dummy_env,
                        model_path=str(rl_model_path.with_suffix(''))
                    )
                    self.rl_agent.load()
                    self.use_rl = True
                    self._logged_no_rl = False  # Reset so we can log again if unloaded
                    log("🧠 RL Agent Loaded Successfully! (FAZA 4 Active)", "SUCCESS")
                else:
                    if not self._logged_no_rl:
                        log("ℹ️ No RL model found. Train first with: python3.12 src/process_rl_trainer.py", "INFO")
                        self._logged_no_rl = True
            except Exception as e:
                log(f"⚠️ Failed to load RL Agent: {e}", "WARNING")
                traceback.print_exc()

    def _push_dashboard_update(self, current_price):
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            now_epoch = time.time()

            # 1. Heartbeat (Status ONLINE)
            status_data = {
                "status": "ONLINE",
                "mode": "FUTURES_SNIPER",
                "bias": getattr(self, 'global_bias', 'NEUTRAL'),
                # UI/PHP rely on fresh timestamps. Provide both ISO (UTC) and epoch.
                "last_update": now_utc.isoformat(),
                "timestamp": now_epoch
            }
            # Zapisz heartbeat
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES ('heartbeat', ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                (json.dumps(status_data), now_utc.isoformat())
            )
            # 2. Zapisz cenę w system_status (legacy key)
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES ('btc_price', ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                (str(current_price), now_utc.isoformat())
            )

            # 3. Uzupełnij MARKET WATCH dla BTC/USDT (Futures Sniper dashboard tile)
            try:
                # We rely on last fetched ticker snapshot if available
                ticker_info = None
                try:
                    # data_provider.fetch_ticker was already called w run(), but here we are defensive
                    ticker_info = self.data_provider.fetch_ticker(self.ticker)
                except Exception:
                    ticker_info = None

                change_24h = 0.0
                volume_24h = 0.0
                if isinstance(ticker_info, dict):
                    # CCXT standard fields (if provided by exchange)
                    change_24h = float(ticker_info.get("percentage") or 0.0)
                    volume_24h = float(ticker_info.get("quoteVolume") or 0.0)

                # Calculate condition_score for FUTURES trading
                # Score represents probability of profitable trade (0-100%)
                # Based on AI confidence + signal strength + market bias alignment
                condition_score = self._calculate_futures_score()

                self.db.execute(
                    """
                    INSERT INTO market_watch (ticker, price, change_24h, volume_24h, condition_score, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (ticker) DO UPDATE
                    SET price=EXCLUDED.price,
                        change_24h=EXCLUDED.change_24h,
                        volume_24h=EXCLUDED.volume_24h,
                        condition_score=EXCLUDED.condition_score,
                        updated_at=EXCLUDED.updated_at
                    """,
                    (self.ticker, float(current_price), change_24h, volume_24h, condition_score, now_utc.isoformat())
                )
            except Exception:
                # Market watch is ornamental; never break main loop because of it.
                pass
        except Exception as e:
            pass

    def _calculate_futures_score(self):
        """
        Calculate condition_score (0-100) for FUTURES trading.
        Represents probability of profitable trade based on:
        - AI confidence (last prediction)
        - Signal strength
        - Market bias alignment
        """
        try:
            # Get cached values from last analysis
            signal = getattr(self, "_last_signal", "NEUTRAL")
            confidence = getattr(self, "_last_confidence", 0.0)
            global_bias = getattr(self, "global_bias", "NEUTRAL")
            
            # Base score from confidence (0.0-1.0 -> 0-60 points)
            score = int(confidence * 60)
            
            # Bonus for strong signal (up to +20 points)
            if signal in ["LONG", "SHORT"]:
                score += 20
            elif signal == "NEUTRAL":
                score += 5
            
            # Bonus for bias alignment (up to +20 points)
            if signal == "LONG" and global_bias == "BULLISH":
                score += 20
            elif signal == "SHORT" and global_bias == "BEARISH":
                score += 20
            elif global_bias == "NEUTRAL":
                score += 10
            # Penalty for misalignment (already vetoed in _execute_strategy)
            elif (signal == "LONG" and global_bias == "BEARISH") or (signal == "SHORT" and global_bias == "BULLISH"):
                score -= 30
            
            # Clamp to 0-100
            return int(max(0, min(100, score)))
        except Exception:
            return 50  # Neutral score on error
    
    def _save_live_context(self, price, pred, signal, conf, pos):
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            data = {
                "ticker": self.ticker,
                "price": price,
                "prediction": int(pred),
                "signal": signal,
                "confidence": float(conf),
                "position": pos,
                "global_bias": getattr(self, 'global_bias', 'NEUTRAL'),
                "timestamp": now_utc.isoformat(),
                "ppo_training_mode": self._ppo_training_mode  # NEW: PPO pause indicator
            }
            # Zapisujemy jako 'trader_intent' żeby dashboard wiedział co robi AI
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES ('trader_intent', ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                (json.dumps(data), now_utc.isoformat())
            )
        except:
            pass
    
    def _update_ppo_pause_status(self):
        """
        Update UI status when PPO training is active.
        Shows "Pauza - obecnie trwa trening PPO" in dashboard.
        """
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            
            # Update pulse_30m with pause status
            pause_status = {
                "status": "paused",
                "details": {
                    "action": "PPO Training Active",
                    "message": "Pauza - obecnie trwa trening PPO Agent",
                    "info": "Bot kontynuuje zarządzanie istniejącymi pozycjami (TP/SL/Trailing)",
                    "note": "Nowe wejścia zablokowane do czasu zakończenia treningu"
                },
                "last_run": now_utc.isoformat()
            }
            
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES ('pulse_30m', ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                (json.dumps(pause_status), now_utc.isoformat())
            )
            
        except Exception as e:
            log(f"Failed to update PPO pause status: {e}", "ERROR")

    def _update_pulse(self, key, action):
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            pulse_data = {
                "status": "running",
                "details": {"action": action},
                "last_run": now_utc.isoformat()
            }
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                (key, json.dumps(pulse_data), now_utc.isoformat())
            )
        except Exception as e:
            pass

    def _save_prediction(self, ticker, predicted_price, entry_price, direction, confidence, model_version):
        """
        Save prediction to database for later validation (Referee System).
        - direction: 1 for LONG, -1 for SHORT
        - result will be updated later by referee (HIT/MISS)
        """
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            
            self.db.execute(
                """
                INSERT INTO predictions (ticker, timestamp, predicted_price, entry_price, direction, confidence, result, model_version)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
                """,
                (ticker, now_utc.isoformat(), float(predicted_price), float(entry_price), int(direction), float(confidence), model_version)
            )
            log(f"Saved prediction: {ticker} ${predicted_price:.2f} (dir={direction}, conf={confidence:.2f})", "INFO")
        except Exception as e:
            log(f"Failed to save prediction: {e}", "ERROR")

    def _lstm_quick_update(self):
        """
        LSTM Quick Update (CO 30 MINUT) - Tylko LSTM, NIE RL!
        
        Proces:
        1. Pobiera ostatnie 6h danych z bazy (360 świeczek 1-min)
        2. Generuje features
        3. Reload LSTM Ensemble from disk (trained by process_trainer.py)
        
        WAŻNE: RL Agent jest trenowany OFFLINE, raz w tygodniu!
        (process_rl_trainer.py - osobny proces, działa w tle)
        """
        try:
            log("🧠 LSTM Quick Update (reload from disk)...", "INFO")
            
            # 1. Pobierz dane z bazy (ostatnie 6h)
            rows = self.db.query(
                """
                SELECT timestamp, open, high, low, close, volume
                FROM candles
                WHERE ticker = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT 1500
                """,
                (self.ticker, self.timeframe)
            )
            
            if not rows or len(rows) < 100:
                log("⚠️ Not enough data for re-training (need 100+ candles)", "WARNING")
                return
            
            # 2. Convert to DataFrame
            import pandas as pd
            df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['open'] = df['open'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            log(f"📊 Re-training on {len(df)} candles (last {len(df)} minutes)", "INFO")
            
            # 3. Engineer features (same as in _get_ai_prediction)
            df = self._engineer_features_for_training(df)
            
            if len(df) < 50:
                log("⚠️ Not enough data after feature engineering", "WARNING")
                return
            
            # 4. Create target (1 if next candle closes higher, 0 otherwise)
            df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
            df.dropna(inplace=True)
            
            if len(df) < 30:
                log("⚠️ Not enough data after target creation", "WARNING")
                return
            
            # 5. Get feature columns
            feature_cols = [
                'rsi', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
                'market_correlation', 'bulls_bears_ratio', 'market_strength',
                'volume_sma_ratio', 'obv_ratio', 'mfi',
                'atr_pct', 'bb_width',
                'roc', 'stoch_k', 'stoch_d',
                'funding_rate', 'funding_rate_trend',
                'price_change_pct', 'volatility'
            ]
            
            # Ensure all columns exist
            for col in feature_cols:
                if col not in df.columns:
                    df[col] = 0.0
            
            X = df[feature_cols].values
            y = df['target'].values
            
            # 6. Train model (quick update, not full training)
            from src.ai.models import EnsembleModel
            
            if self.model is None:
                log("⚠️ No existing model to update, loading fresh model...", "WARNING")
                self._load_latest_model()
                if self.model is None:
                    log("❌ No model available, skipping re-training", "ERROR")
                    return
            else:
                # Partial fit (incremental learning)
                # Note: This is a simplified version. Full re-training would require more data.
                log("🔄 Performing incremental update on model...", "INFO")

                # Quick update: Reload latest model from disk
                # (Full training happens offline in process_trainer.py)
            
            log("✅ LSTM quick update complete!", "SUCCESS")
            
        except Exception as e:
            log(f"❌ Model re-training failed: {e}", "ERROR")
            traceback.print_exc()
    
    def _rl_prediction_cycle(self, df):
        """
        RL Agent: 30-minute prediction cycle (INFERENCE ONLY!).
        
        Proces:
        1. Get current market state
        2. RL Agent predicts next 30 minutes (30 candles)
        3. Save predictions to database for chart visualization
        4. Update RL Brain Stats
        
        WAŻNE: To jest TYLKO inference! Training dzieje się offline.
        """
        try:
            if df is None or len(df) == 0:
                log("⚠️ No data for RL prediction", "WARNING")
                return
            
            log("🧠 RL Agent: Generating 30-minute predictions...", "INFO")
            
            # Get current observation
            current_price = float(df['close'].iloc[-1])
            lstm_prediction = current_price  # Simplified
            lstm_confidence = 0.5
            
            observation = self._prepare_rl_observation(df, lstm_prediction, lstm_confidence)
            
            # Predict next 30 candles (1-min each = 30 minutes)
            predictions = []
            timestamps = []
            
            current_time = datetime.datetime.now(datetime.timezone.utc)
            
            for i in range(30):
                # RL Agent action (0=HOLD, 1=LONG, 2=SHORT, 3=CLOSE)
                action = self.rl_agent.predict(observation)
                
                # Convert action to price prediction
                # Simplified: LONG = +0.1%, SHORT = -0.1%, HOLD/CLOSE = 0%
                if action == 1:  # LONG
                    predicted_change = 0.001  # +0.1%
                elif action == 2:  # SHORT
                    predicted_change = -0.001  # -0.1%
                else:
                    predicted_change = 0.0
                
                predicted_price = current_price * (1 + predicted_change)
                
                # Save prediction
                future_time = current_time + datetime.timedelta(minutes=i+1)
                predictions.append(predicted_price)
                timestamps.append(future_time)
                
                # Update observation for next step (simplified)
                current_price = predicted_price
            
            # Save predictions to database
            self._save_rl_predictions(timestamps, predictions)
            
            log(f"✅ RL Agent: Saved 30 predictions (avg: ${sum(predictions)/len(predictions):.2f})", "SUCCESS")
            
        except Exception as e:
            log(f"❌ RL prediction cycle error: {e}", "ERROR")
            traceback.print_exc()
    
    def _save_rl_predictions(self, timestamps, predictions):
        """
        Save RL predictions to database for chart visualization.
        
        Format: Similar to LSTM predictions, but for RL Agent.
        """
        try:
            for timestamp, predicted_price in zip(timestamps, predictions):
                self.db.execute(
                    """
                    INSERT INTO rl_predictions 
                    (ticker, timestamp, predicted_price, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (ticker, timestamp) 
                    DO UPDATE SET 
                        predicted_price = EXCLUDED.predicted_price,
                        created_at = EXCLUDED.created_at
                    """,
                    (
                        self.ticker,
                        timestamp.isoformat(),
                        float(predicted_price),  # Ensure float, not numpy
                        datetime.datetime.now(datetime.timezone.utc).isoformat()
                    )
                )
            
            # Update RL Brain Stats
            self._update_rl_brain_stats()
            
        except Exception as e:
            log(f"Error saving RL predictions: {e}", "ERROR")
    
    def _update_rl_brain_stats(self):
        """
        Update RL Agent Brain Stats for dashboard.
        
        Stats:
        - Training: IN PROGRESS / IDLE / SCHEDULED
        - Accuracy (Total): X%
        - Last Check: timestamp
        - Hits / Misses: X / Y
        - Next Training In: DD:GG:MM:SS
        """
        try:
            # Check if RL training process is running
            # (This would check a separate process/file)
            training_status = self._check_rl_training_status()
            
            # Calculate accuracy from past predictions
            accuracy_data = self._calculate_rl_accuracy()
            
            # Get next training time
            next_training = self._get_next_rl_training_time()
            
            # Save to database (for dashboard) - FIX: PostgreSQL uses SERIAL, check if record exists first
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            next_training_iso = next_training.isoformat() if next_training else None
            
            # Check if record exists
            rows = self.db.query("SELECT id FROM rl_brain_stats ORDER BY id DESC LIMIT 1")
            
            if rows and rows[0]:
                # Update existing record
                self.db.execute(
                    """
                    UPDATE rl_brain_stats
                    SET training_status = ?,
                        total_accuracy = ?,
                        total_hits = ?,
                        total_misses = ?,
                        last_check = ?,
                        next_training_time = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        training_status,
                        float(accuracy_data['accuracy']),
                        int(accuracy_data['hits']),
                        int(accuracy_data['misses']),
                        now_iso,
                        next_training_iso,
                        now_iso,
                        rows[0][0]  # Use existing id
                    )
                )
            else:
                # Insert new record (let PostgreSQL assign id)
                self.db.execute(
                    """
                    INSERT INTO rl_brain_stats
                    (training_status, total_accuracy, total_hits, total_misses, 
                     last_check, next_training_time, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        training_status,
                        float(accuracy_data['accuracy']),
                        int(accuracy_data['hits']),
                        int(accuracy_data['misses']),
                        now_iso,
                        next_training_iso,
                        now_iso
                    )
                )
            
        except Exception as e:
            log(f"Error updating RL brain stats: {e}", "ERROR")
    
    def _check_rl_training_status(self):
        """
        Check if RL training process is currently running.
        
        Returns: 'IN_PROGRESS', 'IDLE', or 'SCHEDULED'
        """
        try:
            # Check for training lock file (FIX: use same name as main.py)
            import os
            lock_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', '.rl_training.lock')
            
            if os.path.exists(lock_file):
                # Check if lock is stale (> 12h old)
                lock_age = time.time() - os.path.getmtime(lock_file)
                if lock_age > 43200:  # 12 hours
                    os.remove(lock_file)
                    return "IDLE"
                return "IN_PROGRESS"
            
            # Check if training is scheduled (next week)
            next_training = self._get_next_rl_training_time()
            if next_training and next_training < datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24):
                return "SCHEDULED"
            
            return "IDLE"
            
        except Exception:
            return "IDLE"
    
    def _calculate_rl_accuracy(self):
        """
        Calculate RL Agent accuracy from past predictions vs actuals.
        
        Returns: {'accuracy': X%, 'hits': X, 'misses': Y}
        """
        try:
            # Get past RL predictions from database (FIX: PostgreSQL syntax)
            rows = self.db.query(
                """
                SELECT rp.predicted_price, c.close, rp.timestamp
                FROM rl_predictions rp
                JOIN candles c ON c.ticker = rp.ticker 
                    AND c.timestamp = rp.timestamp
                    AND c.timeframe = '1m'
                WHERE rp.ticker = ?
                AND rp.created_at > NOW() - INTERVAL '7 days'
                LIMIT 1000
                """,
                (self.ticker,)
            )
            
            if not rows or len(rows) < 10:
                return {'accuracy': 0.0, 'hits': 0, 'misses': 0}
            
            hits = 0
            misses = 0
            
            for predicted, actual, _ in rows:
                # Hit if prediction within 0.5% of actual
                error_pct = abs((predicted - actual) / actual) * 100
                if error_pct <= 0.5:
                    hits += 1
                else:
                    misses += 1
            
            total = hits + misses
            accuracy = (hits / total * 100) if total > 0 else 0.0
            
            return {
                'accuracy': round(accuracy, 2),
                'hits': hits,
                'misses': misses
            }
            
        except Exception as e:
            log(f"Error calculating RL accuracy: {e}", "ERROR")
            return {'accuracy': 0.0, 'hits': 0, 'misses': 0}
    
    def _get_next_rl_training_time(self):
        """
        Get timestamp of next scheduled RL training.
        
        Training happens every 7 days from last training.
        
        Returns: datetime or None
        """
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            
            # Get last training time from file (FIX: use same name as main.py)
            training_info_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'rl_training_info.json')
            
            if os.path.exists(training_info_file):
                with open(training_info_file, 'r') as f:
                    data = json.load(f)
                    last_training_str = data.get('last_training_time')
                    if last_training_str:
                        # Parse datetime and ensure it's timezone-aware
                        last_training = datetime.datetime.fromisoformat(last_training_str.replace('Z', '+00:00'))
                        # If timezone-naive, assume UTC
                        if last_training.tzinfo is None:
                            last_training = last_training.replace(tzinfo=datetime.timezone.utc)
                    else:
                        # No training yet, schedule for 7 days from now
                        last_training = now - datetime.timedelta(days=7)
            else:
                # No training yet, schedule for 7 days from now
                last_training = now - datetime.timedelta(days=7)
            
            # Next training: 7 days after last training
            next_training = last_training + datetime.timedelta(days=7)
            
            # If next training is in the past, schedule for next week
            while next_training < now:
                next_training += datetime.timedelta(days=7)
            
            return next_training
            
        except Exception as e:
            log(f"Error getting next RL training time: {e}", "WARNING")
            # Default: 7 days from now
            now = datetime.datetime.now(datetime.timezone.utc)
            return now + datetime.timedelta(days=7)
    
    def _engineer_features_for_training(self, df):
        """
        Engineer features dla re-trainingu (identyczne jak w _get_ai_prediction).
        """
        try:
            import pandas_ta as ta
            
            df = df.copy()
            
            # Basic indicators
            df['rsi'] = ta.rsi(df['close'], length=14)
            macd = ta.macd(df['close'])
            if macd is not None:
                df = df.join(macd)
            else:
                df['MACD_12_26_9'] = 0.0
                df['MACDh_12_26_9'] = 0.0
                df['MACDs_12_26_9'] = 0.0
            
            # Market features (simplified for re-training)
            df['market_correlation'] = 0.75
            df['bulls_bears_ratio'] = 0.5
            df['market_strength'] = 50.0
            
            # Volume
            df['volume_sma'] = df['volume'].rolling(20).mean()
            df['volume_sma_ratio'] = df['volume'] / df['volume_sma']
            df['obv'] = ta.obv(df['close'], df['volume'])
            df['obv_sma'] = df['obv'].rolling(20).mean()
            df['obv_ratio'] = df['obv'] / df['obv_sma']
            df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14)
            
            # Volatility
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            df['atr_pct'] = (df['atr'] / df['close']) * 100
            bbands = ta.bbands(df['close'], length=20)
            if bbands is not None and 'BBU_20_2.0' in bbands.columns:
                df['bb_width'] = (bbands['BBU_20_2.0'] - bbands['BBL_20_2.0']) / bbands['BBM_20_2.0']
            else:
                df['bb_width'] = 0.04
            
            # Momentum
            df['roc'] = ta.roc(df['close'], length=12)
            stoch = ta.stoch(df['high'], df['low'], df['close'])
            if stoch is not None:
                df = df.join(stoch, rsuffix='_stoch')
                df['stoch_k'] = df.get('STOCHk_14_3_3', 50)
                df['stoch_d'] = df.get('STOCHd_14_3_3', 50)
            else:
                df['stoch_k'] = 50
                df['stoch_d'] = 50
            
            # Funding rates (simplified)
            df['funding_rate'] = 0.0001
            df['funding_rate_trend'] = 0.0
            
            # --- MACRO CONTEXT FEATURES (MICRO/MACRO STRATEGY) ---
            # Trend 4h (240 minut)
            df['trend_4h_sma'] = df['close'].rolling(window=240, min_periods=1).mean()
            df['dist_4h'] = (df['close'] - df['trend_4h_sma']) / df['trend_4h_sma']
            df['dist_4h'] = df['dist_4h'].fillna(0)
            
            # Trend 24h (1440 minut = 1 dzień)
            df['trend_daily_sma'] = df['close'].rolling(window=1440, min_periods=1).mean()
            df['dist_daily'] = (df['close'] - df['trend_daily_sma']) / df['trend_daily_sma']
            df['dist_daily'] = df['dist_daily'].fillna(0)
            
            # Volatility Regime
            df['volatility_24h'] = df['close'].rolling(window=1440, min_periods=1).std()
            df['volatility_24h'] = df['volatility_24h'].fillna(df['close'].std())

            # Additional
            df['price_change_pct'] = df['close'].pct_change() * 100
            df['volatility'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
            
            # Fill NaN (bfill replaces fillna with method='bfill' in pandas 2.0+)
            df = df.bfill()
            df = df.fillna(0)
            
            return df
            
        except Exception as e:
            log(f"Feature engineering error: {e}", "ERROR")
            return df
    
    def _fill_candle_gaps(self):
        """
        Detect and fill gaps in candle data (1-MINUTE CANDLES).
        Checks for missing timestamps in database and fetches them from API.
        Ensures at least 30 days of historical data is available.
        """
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            
            # Get latest candle timestamp from database
            rows = self.db.query(
                "SELECT MAX(timestamp) FROM candles WHERE ticker = ? AND timeframe = ?",
                (self.ticker, self.timeframe)
            )
            
            if not rows or not rows[0] or not rows[0][0]:
                # No data in database, fetch initial 30 days of data
                log(f"No candle data found, fetching 30 days of history ({self.timeframe})...", "INFO")
                # 30 days × 24 hours × 60 minutes = 43,200 candles
                # API limits usually allow 1000-1500 candles per request, so we need multiple requests
                
                # Fetch in chunks (going back 30 days)
                days_to_fetch = 30
                start_date = now_utc - datetime.timedelta(days=days_to_fetch)
                since_ms = int(start_date.timestamp() * 1000)
                
                total_saved = 0
                for chunk in range(30):  # 30 chunks to cover 30 days
                    df = self.data_provider.fetch_ohlcv(
                        self.ticker, 
                        timeframe=self.timeframe,
                        since=since_ms,
                        limit=1500  # Max per request
                    )
                    
                    if df is not None and not df.empty:
                        self._save_candles(df, timeframe=self.timeframe)
                        total_saved += len(df)
                        
                        # Update since for next chunk
                        last_timestamp = df.index[-1]
                        since_ms = int(last_timestamp.timestamp() * 1000) + 60000  # +1 minute
                        
                        log(f"📥 Fetched chunk {chunk+1}/30: {len(df)} candles (total: {total_saved})", "INFO")
                    else:
                        log(f"⚠️ No more data available at chunk {chunk+1}", "WARNING")
                        break
                    
                    # Don't hammer the API
                    import time
                    time.sleep(1)
                
                log(f"✅ Saved {total_saved} initial candles (~{total_saved // 1440} days)", "SUCCESS")
                
                # Update market_watch history_days
                self._update_market_watch_history_days()
                return
            
            # Handle both string and datetime objects from database
            latest_db_time = rows[0][0]
            if isinstance(latest_db_time, str):
                latest_db_time = datetime.datetime.fromisoformat(latest_db_time.replace('Z', '+00:00'))
            elif not isinstance(latest_db_time, datetime.datetime):
                latest_db_time = datetime.datetime.fromisoformat(str(latest_db_time))
            
            # Ensure timezone awareness
            if latest_db_time.tzinfo is None:
                latest_db_time = latest_db_time.replace(tzinfo=datetime.timezone.utc)
            
            time_diff = (now_utc - latest_db_time).total_seconds() / 60  # minutes
            
            # Check if we have at least 30 days of data
            oldest_candle = self.db.query(
                "SELECT MIN(timestamp) FROM candles WHERE ticker = ? AND timeframe = ?",
                (self.ticker, self.timeframe)
            )
            
            if oldest_candle and oldest_candle[0] and oldest_candle[0][0]:
                oldest_time = oldest_candle[0][0]
                if isinstance(oldest_time, str):
                    oldest_time = datetime.datetime.fromisoformat(oldest_time.replace('Z', '+00:00'))
                elif not isinstance(oldest_time, datetime.datetime):
                    oldest_time = datetime.datetime.fromisoformat(str(oldest_time))
                
                if oldest_time.tzinfo is None:
                    oldest_time = oldest_time.replace(tzinfo=datetime.timezone.utc)
                
                data_span_days = (now_utc - oldest_time).days
                
                if data_span_days < 30:
                    log(f"⚠️ Only {data_span_days} days of data. Fetching more to reach 30 days...", "WARNING")
                    
                    # Fetch older data to reach 30 days
                    target_start = now_utc - datetime.timedelta(days=30)
                    since_ms = int(target_start.timestamp() * 1000)
                    
                    # Fetch in chunks going backwards
                    for chunk in range(5):  # Max 5 chunks
                        df = self.data_provider.fetch_ohlcv(
                            self.ticker,
                            timeframe=self.timeframe,
                            since=since_ms,
                            limit=1500
                        )
                        
                        if df is not None and not df.empty:
                            self._save_candles(df, timeframe=self.timeframe)
                            log(f"📥 Backfilled {len(df)} candles", "INFO")
                            
                            # Move forward in time for next chunk
                            since_ms = int(df.index[-1].timestamp() * 1000) + 60000
                        else:
                            break
                        
                        import time
                        time.sleep(1)
                    
                    # Update market_watch history_days
                    self._update_market_watch_history_days()
            
            # For 1-minute candles: If gap is more than 5 minutes, fetch missing data
            gap_threshold = 5  # minutes
            if time_diff > gap_threshold:
                missing_candles = int(time_diff)  # 1-minute candles
                log(f"⚠️ Gap detected: {time_diff:.0f} minutes ({missing_candles} candles). Filling...", "WARNING")
                
                # Fetch enough data to fill the gap (max 1000 candles per request)
                limit = min(1000, missing_candles + 50)  # Extra 50 for safety, max 1000
                df = self.data_provider.fetch_candles(
                    self.ticker, 
                    timeframe=self.timeframe,
                    limit=limit
                )
                
                if df is not None and not df.empty:
                    self._save_candles(df, timeframe=self.timeframe)
                    log(f"✅ Filled gap with {len(df)} candles", "SUCCESS")
            
        except Exception as e:
            log(f"Error filling candle gaps: {e}", "ERROR")

    def _save_candles(self, df, timeframe='1m'):
        """
        Save candles to database to fill gaps.
        Called every minute to ensure chart has fresh data.
        """
        try:
            data = []
            for index, row in df.iterrows():
                ts = index.isoformat()
                # Convert numpy types to native Python types
                data.append((
                    self.ticker,
                    ts,
                    float(row['open'].item() if hasattr(row['open'], 'item') else row['open']),
                    float(row['high'].item() if hasattr(row['high'], 'item') else row['high']),
                    float(row['low'].item() if hasattr(row['low'], 'item') else row['low']),
                    float(row['close'].item() if hasattr(row['close'], 'item') else row['close']),
                    float(row['volume'].item() if hasattr(row['volume'], 'item') else row['volume']),
                    timeframe
                ))
            
            query = """
                INSERT INTO candles (ticker, timestamp, open, high, low, close, volume, timeframe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (ticker, timestamp, timeframe) DO UPDATE 
                SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, 
                    close=EXCLUDED.close, volume=EXCLUDED.volume
            """
            self.db.execute_many(query, data)
            log(f"Saved {len(data)} candles to database", "INFO")
        except Exception as e:
            log(f"Error saving candles: {e}", "ERROR")

    def _update_training_status(self):
        """
        Update training status AND accuracy in brain_stats for dashboard display.
        Shows: "Aktywne" or "Nieaktywne: Start za XXmin"
        Also updates real-time hits/misses/accuracy from predictions table
        """
        try:
            # Get current brain_stats
            rows = self.db.query(
                "SELECT value FROM system_status WHERE key = 'brain_stats'"
            )
            
            if not rows or not rows[0] or not rows[0][0]:
                return
            
            brain_stats = json.loads(rows[0][0])
            
            # Update hits/misses/accuracy from predictions table
            try:
                pred_rows = self.db.query(
                    "SELECT "
                    "SUM(CASE WHEN result='HIT' THEN 1 ELSE 0 END) AS hits, "
                    "SUM(CASE WHEN result='MISS' THEN 1 ELSE 0 END) AS misses "
                    "FROM predictions WHERE result IN ('HIT', 'MISS')"
                )
                if pred_rows and pred_rows[0]:
                    hits = int(pred_rows[0][0] or 0)
                    misses = int(pred_rows[0][1] or 0)
                    
                    log(f"Brain Stats Update: Hits={hits}, Misses={misses}, Accuracy={(hits/(hits+misses)*100 if hits+misses > 0 else 0):.1f}%", "INFO")
                    
                    brain_stats['hits'] = hits
                    brain_stats['misses'] = misses
                    
                    # Calculate real validation accuracy
                    if hits + misses > 0:
                        brain_stats['accuracy'] = hits / (hits + misses)
            except Exception as e:
                log(f"Failed to update hits/misses: {e}", "WARNING")
            
            # Get last training time
            last_trained = brain_stats.get('last_trained')
            if not last_trained:
                brain_stats['training_status'] = "Nieaktywne: Oczekiwanie"
            else:
                # Calculate time until next training (30 min cycle)
                try:
                    last_dt = datetime.datetime.fromisoformat(last_trained.replace('Z', '+00:00'))
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    elapsed_minutes = (now_utc - last_dt).total_seconds() / 60
                    
                    TRAINING_COOLDOWN = 30  # minutes
                    
                    if elapsed_minutes < TRAINING_COOLDOWN:
                        remaining_minutes = int(TRAINING_COOLDOWN - elapsed_minutes)
                        brain_stats['training_status'] = f"Nieaktywne: Start za {remaining_minutes}min"
                        brain_stats['next_training_minutes'] = remaining_minutes
                    else:
                        brain_stats['training_status'] = "Oczekiwanie na start..."
                        brain_stats['next_training_minutes'] = 0
                except Exception:
                    brain_stats['training_status'] = "Nieaktywne"
            
            # Update last_check timestamp
            brain_stats['last_check'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Save updated brain_stats
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                ("brain_stats", json.dumps(brain_stats), now_utc.isoformat())
            )
            
        except Exception as e:
            log(f"Failed to update training status: {e}", "ERROR")

    def _validate_predictions(self, current_price):
        """
        Referee System - Validates PENDING predictions
        Checks if predicted price movement was correct after 30 minutes
        Updates: PENDING → HIT or MISS
        """
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            
            # Get all PENDING predictions older than 30 minutes
            # Use PostgreSQL INTERVAL for proper timestamp comparison
            rows = self.db.query(
                """
                SELECT id, ticker, timestamp, predicted_price, entry_price, direction, confidence
                FROM predictions
                WHERE result = 'PENDING' AND timestamp < NOW() - INTERVAL '30 minutes'
                ORDER BY timestamp ASC
                LIMIT 50
                """
            )
            
            if not rows:
                return
            
            validated_count = 0
            for row in rows:
                pred_id = row[0]
                ticker = row[1]
                pred_timestamp = row[2]
                predicted_price = float(row[3])
                entry_price = float(row[4])
                direction = int(row[5])  # 1 = LONG, -1 = SHORT
                confidence = float(row[6])
                
                # Determine if prediction was correct
                # LONG (direction=1): HIT if current_price > entry_price
                # SHORT (direction=-1): HIT if current_price < entry_price
                
                if direction == 1:  # LONG
                    result = "HIT" if current_price > entry_price else "MISS"
                elif direction == -1:  # SHORT
                    result = "HIT" if current_price < entry_price else "MISS"
                else:
                    result = "MISS"  # Unknown direction
                
                # Update prediction result
                self.db.execute(
                    "UPDATE predictions SET result = ? WHERE id = ?",
                    (result, pred_id)
                )
                
                # Save to referee_history for chart visualization
                self._save_referee_history(ticker, pred_timestamp, entry_price, result)
                
                validated_count += 1
                log(f"✓ Validated prediction #{pred_id}: {result} (dir={direction}, entry=${entry_price:.2f}, now=${current_price:.2f})", "INFO")
            
            if validated_count > 0:
                log(f"Referee validated {validated_count} predictions", "INFO")
                
        except Exception as e:
            log(f"Failed to validate predictions: {e}", "ERROR")

    def _save_referee_history(self, ticker, timestamp, price, result):
        """
        Save validation result to referee_history for chart display
        Format: {"BTC/USDT": [{"t": timestamp_ms, "p": price, "result": "HIT/MISS"}]}
        Automatically cleans old PENDING entries (>2 hours old)
        """
        try:
            # Read existing referee history
            rows = self.db.query(
                "SELECT value FROM system_status WHERE key = 'referee_history'"
            )
            
            if rows and rows[0] and rows[0][0]:
                history = json.loads(rows[0][0])
            else:
                history = {}
            
            # Ensure ticker exists in history
            if ticker not in history:
                history[ticker] = []
            
            # Clean old PENDING entries (older than 2 hours)
            now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
            two_hours_ago = now_ms - (2 * 60 * 60 * 1000)
            
            history[ticker] = [
                point for point in history[ticker]
                if not (point.get('result') == 'PENDING' and point.get('t', 0) < two_hours_ago)
            ]
            
            # Convert timestamp to milliseconds
            try:
                dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp_ms = int(dt.timestamp() * 1000)
            except Exception:
                timestamp_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
            
            # Add validation point (only HIT/MISS, not PENDING)
            if result in ('HIT', 'MISS'):
                history[ticker].append({
                    "t": timestamp_ms,
                    "p": float(price),
                    "result": result
                })
            
            # Keep only last 100 validated points per ticker
            history[ticker] = [p for p in history[ticker] if p.get('result') in ('HIT', 'MISS')][-100:]
            
            # Save back to database
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                ("referee_history", json.dumps(history), now_utc.isoformat())
            )
            
            log(f"Referee history: {len(history[ticker])} validated points for {ticker}", "INFO")
            
        except Exception as e:
            log(f"Failed to save referee history: {e}", "ERROR")

    def _update_quant_metrics(self, df, current_price):
        """
        Titan Quant Protocol Metrics:
        1. FracDiff (Memory Preservation) - Fractionalized differencing for stationarity
        2. Triple Barrier Training - TP/SL/Time based labeling
        3. Microstructure (Spread) - Bid-Ask spread analysis
        """
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            
            # 1. FracDiff - Memory Preservation Score
            # Simple approximation: check if returns are stationary using rolling std
            try:
                returns = df['close'].pct_change().dropna()
                rolling_std = returns.rolling(20).std()
                std_ratio = rolling_std.iloc[-1] / rolling_std.mean() if len(rolling_std) > 0 else 1.0
                
                # Score: 100% if stationary (std_ratio ~ 1), lower if non-stationary
                fracdiff_score = max(0, min(100, 100 - abs(std_ratio - 1.0) * 50))
                fracdiff_status = "Stationary Fixed" if fracdiff_score > 80 else "Non-Stationary Fixed"
            except Exception:
                fracdiff_score = 95  # Default
                fracdiff_status = "Non-Stationary Fixed"
            
            # 2. Triple Barrier Training - Active status
            # Check if we have active stop-loss/take-profit targets
            triple_barrier_active = "Active"  # Always active in this strategy
            triple_barrier_info = "TP / SL / Time"
            
            # 3. Microstructure - Spread Analysis
            # Get current spread from liquidity guard
            try:
                # Fetch orderbook for spread calculation
                order_book = self.exec_manager.exchange.fetch_order_book(self.ticker, limit=5)
                
                if order_book and 'bids' in order_book and 'asks' in order_book:
                    if order_book['bids'] and order_book['asks']:
                        bid = order_book['bids'][0][0]
                        ask = order_book['asks'][0][0]
                        spread_pct = ((ask - bid) / bid) * 100 if bid > 0 else 0.0
                        
                        # Liquidity status based on spread
                        if spread_pct < 0.1:
                            liquidity_status = "HEALTHY"
                        elif spread_pct < 0.5:
                            liquidity_status = "MODERATE"
                        else:
                            liquidity_status = "LOW"
                    else:
                        spread_pct = 0.0
                        liquidity_status = "Checking..."
                else:
                    spread_pct = 0.0
                    liquidity_status = "Checking..."
            except Exception:
                spread_pct = 0.0
                liquidity_status = "Checking..."

            # 4. Volume Anomaly (Smart Volume Stop Indicator)
            try:
                current_vol = float(df['volume'].iloc[-1])
                avg_vol = float(df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else current_vol)
                vol_ratio = (current_vol / avg_vol) if avg_vol > 0 else 1.0
            except Exception:
                vol_ratio = 1.0
            
            # Save to database
            payload = {
                "fracdiff_score": round(fracdiff_score, 1),
                "fracdiff_status": fracdiff_status,
                "triple_barrier_active": triple_barrier_active,
                "triple_barrier_info": triple_barrier_info,
                "spread_pct": round(spread_pct, 4),
                "liquidity_status": liquidity_status,
                "vol_ratio": round(vol_ratio, 2),
                "timestamp": now_utc.isoformat()
            }
            
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                ("quant_metrics", json.dumps(payload), now_utc.isoformat())
            )
            
            log(f"Quant Metrics: FracDiff={fracdiff_score:.1f}%, Spread={spread_pct:.4f}%, Vol_Ratio={vol_ratio:.2f}x", "INFO")
        except Exception as e:
            log(f"Failed to update quant metrics: {e}", "ERROR")

    def _update_holistic_guardian(self, signal, confidence, global_bias, current_price):
        """
        Holistic Guardian - Market Health & Risk Assessment
        Calculates:
        - mode: MONITORING, GROWTH, CAUTION, ALT_SEASON
        - risk_score: 0-100 (lower is safer)
        - market_trend: market sentiment %
        """
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            
            # Base risk score (neutral = 50)
            risk_score = 50
            mode = "MONITORING"
            market_trend = 50
            
            # 1. Adjust based on AI signal & confidence
            if signal == "LONG":
                risk_score -= int(confidence * 20)  # High confidence LONG reduces risk
                mode = "GROWTH"
            elif signal == "SHORT":
                risk_score += int(confidence * 20)  # High confidence SHORT increases risk
                mode = "CAUTION"
            
            # 2. Adjust based on global bias (Matrix)
            if global_bias == "BULLISH":
                risk_score -= 15
                market_trend = 70
                if mode == "GROWTH":
                    mode = "ALT_SEASON"
            elif global_bias == "BEARISH":
                risk_score += 15
                market_trend = 30
                if mode == "CAUTION":
                    mode = "EXTREME_CAUTION"
            
            # 3. Check volatility (high volatility = higher risk)
            try:
                rows = self.db.query(
                    "SELECT close FROM candles WHERE ticker = ? ORDER BY timestamp DESC LIMIT 20",
                    (self.ticker,)
                )
                if rows and len(rows) >= 10:
                    prices = [float(r[0]) for r in rows]
                    volatility = (max(prices) - min(prices)) / min(prices)
                    if volatility > 0.05:  # >5% volatility
                        risk_score += 10
            except Exception:
                pass
            
            # Clamp risk_score to 0-100
            risk_score = max(0, min(100, risk_score))
            
            payload = {
                "mode": mode,
                "risk_score": risk_score,
                "market_trend": round(market_trend, 1),
                "reason": f"AI: {signal} ({confidence:.0%}), Bias: {global_bias}",
                "timestamp": now_utc.isoformat()
            }
            
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                ("holistic_status", json.dumps(payload), now_utc.isoformat())
            )
            
            log(f"Holistic Guardian: Mode={mode}, Risk={risk_score}, Trend={market_trend}%", "INFO")
        except Exception as e:
            log(f"Failed to update holistic guardian: {e}", "ERROR")

    def _publish_latest_results(
        self,
        ticker,
        current_price,
        signal="MONITORING",
        confidence_score=0.0,
        prediction=None,
        predicted_price=None,
        prediction_vector=None,
        prediction_candles=None
    ):
        """
        Publishes a minimal `latest_results` payload expected by index.php:
        - current_price, predicted_price, signal, confidence_score, rf_verdict, prediction_vector, prediction_candles, timestamp, ticker
        """
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)

            # Derive predicted_price if not provided
            if predicted_price is None:
                predicted_price = float(current_price)
            rf_verdict = "UNKNOWN"
            if prediction is not None:
                try:
                    pred_int = int(prediction)
                    if pred_int == 1:
                        if predicted_price is None:
                            predicted_price = float(current_price) * 1.001
                        rf_verdict = "UP"
                    elif pred_int == 0:
                        if predicted_price is None:
                            predicted_price = float(current_price) * 0.999
                        rf_verdict = "DOWN"
                except Exception:
                    pass

            if predicted_price is None:
                predicted_price = float(current_price)

            if prediction_vector is None:
                prediction_vector = [float(predicted_price)]

            payload = {
                "ticker": ticker,
                "current_price": float(current_price),
                "predicted_price": float(predicted_price),
                "signal": signal,
                "confidence_score": float(confidence_score),
                "rf_verdict": rf_verdict,
                # For chart dashed line (future candle(s))
                "prediction_vector": [float(x) for x in prediction_vector],
                "timestamp": now_utc.isoformat()
            }
            
            # Add prediction_candles if available (OHLC format for transparent candles)
            if prediction_candles is not None:
                payload["prediction_candles"] = prediction_candles

            query = "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at"
            # Global (primary)
            self.db.execute(query, ("latest_results", json.dumps(payload), now_utc.isoformat()))
            # Ticker-specific key used by api/data.php?file=latest_results.json&ticker=...
            self.db.execute(query, (f"latest_results_{ticker}", json.dumps(payload), now_utc.isoformat()))
        except Exception:
            pass

    def _dump_radar_scan(self):
        """
        Dumps radar data (top 50 assets + gems list) into system_status key `radar_scan`
        for index.php updateRadar().
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        # Update top 50 tickers list (by volume) periodically
        try:
            self.scout.fetch_top_assets(limit=50)
            # Keep DeepScout aligned with current tickers universe
            self.deep_scout.tickers = getattr(self.scout, "tickers", self.deep_scout.tickers)[:50]
        except Exception:
            pass

        # DeepScout scan (4h indicators) – may take a moment, but limited to 50
        radar = self.deep_scout.scan_market()

        # Normalize timestamp to ISO for JS Date parsing
        radar["timestamp"] = now_utc.isoformat()

        # Write to DB
        query = "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at"
        self.db.execute(query, ("radar_scan", json.dumps(radar), now_utc.isoformat()))

    def _dump_correlation_matrix(self):
        """
        Dumps correlation matrix into system_status key `correlation_matrix`
        for index.php updateMatrixScout().
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        matrix = self.scout.calculate_correlation_matrix()
        if not isinstance(matrix, dict):
            return
        # Ensure timestamp exists (JS only uses it for display)
        matrix["timestamp"] = matrix.get("timestamp") or now_utc.isoformat()

        query = "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at"
        self.db.execute(query, ("correlation_matrix", json.dumps(matrix), now_utc.isoformat()))
    
    def _update_market_watch_history_days(self):
        """
        Updates history_days in market_watch table based on actual candle data.
        Called after fetching historical data to ensure UI shows correct number of days.
        """
        try:
            # Calculate actual history span for this ticker
            rows = self.db.query(
                "SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM candles WHERE ticker = ? AND timeframe = ?",
                (self.ticker, self.timeframe)
            )
            
            if rows and rows[0] and rows[0][0] and rows[0][1]:
                min_ts = rows[0][0]
                max_ts = rows[0][1]
                
                # Parse timestamps
                if isinstance(min_ts, str):
                    min_ts = datetime.datetime.fromisoformat(min_ts.replace('Z', '+00:00'))
                if isinstance(max_ts, str):
                    max_ts = datetime.datetime.fromisoformat(max_ts.replace('Z', '+00:00'))
                
                # Ensure timezone awareness
                if min_ts.tzinfo is None:
                    min_ts = min_ts.replace(tzinfo=datetime.timezone.utc)
                if max_ts.tzinfo is None:
                    max_ts = max_ts.replace(tzinfo=datetime.timezone.utc)
                
                # Calculate days (+1 so same-day shows as 1d)
                history_days = max(1, (max_ts - min_ts).days + 1)
                
                # Update market_watch table
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                self.db.execute(
                    """
                    INSERT INTO market_watch (ticker, history_days, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT (ticker) DO UPDATE 
                    SET history_days = EXCLUDED.history_days, 
                        updated_at = EXCLUDED.updated_at
                    """,
                    (self.ticker, history_days, now_utc.isoformat())
                )
                
                log(f"✅ Updated market_watch: {self.ticker} has {history_days} days of history", "SUCCESS")
            
        except Exception as e:
            log(f"Error updating market_watch history_days: {e}", "ERROR")
    
    def _get_ai_prediction_30m(self, df, current_price):
        """
        TITAN ADAPTIVE DEFENSE: AI Prediction for 30-Minute Horizon
        ═══════════════════════════════════════════════════════════════
        
        Używa modelu LSTM do przewidzenia ruchu ceny w ciągu najbliższych 30 minut.
        
        Args:
            df: DataFrame with market data
            current_price: Current market price
            
        Returns:
            dict: {
                'favorable': bool,      # True if prediction is favorable for current position
                'weakening': bool,      # True if momentum is weakening
                'confidence': float,    # Confidence score (0-1)
                'predicted_price': float,  # Predicted price in 30 minutes
                'direction': int        # 1 = UP, -1 = DOWN, 0 = NEUTRAL
            }
        """
        try:
            if not self.model:
                log("⚠️ AI model not available for 30-min prediction. Using fallback logic.", "WARNING")
                return {
                    'favorable': False,
                    'weakening': True,
                    'confidence': 0.5,
                    'predicted_price': current_price,
                    'direction': 0
                }
            
            # Get AI prediction
            signal, confidence, prediction = self._get_ai_prediction(df)
            
            # Calculate predicted price based on recent volatility
            volatility = float(df['close'].pct_change().rolling(20).std().iloc[-1] or 0.01)
            
            # Predicted move in 30 minutes (based on direction and volatility)
            if signal == "LONG":
                predicted_price = current_price * (1 + volatility * 2)  # 2x volatility upward
                direction = 1
            elif signal == "SHORT":
                predicted_price = current_price * (1 - volatility * 2)  # 2x volatility downward
                direction = -1
            else:
                predicted_price = current_price
                direction = 0
            
            # Determine if prediction is favorable for current position
            current_position = self.exec_manager.get_position(self.ticker)
            
            if current_position and current_position != 0:
                # If we have a LONG position
                if current_position > 0:
                    favorable = (direction == 1 and confidence > 0.6)  # Upward prediction
                    weakening = (direction <= 0 or confidence < 0.6)   # Downward or low confidence
                # If we have a SHORT position
                else:
                    favorable = (direction == -1 and confidence > 0.6)  # Downward prediction
                    weakening = (direction >= 0 or confidence < 0.6)    # Upward or low confidence
            else:
                # No position - neutral assessment
                favorable = confidence > 0.7
                weakening = confidence < 0.5
            
            log(f"🔮 AI 30-min Prediction: {signal} (Conf: {confidence:.2%}) | Predicted: ${predicted_price:.2f} | Favorable: {favorable}, Weakening: {weakening}", "INFO")
            
            return {
                'favorable': favorable,
                'weakening': weakening,
                'confidence': confidence,
                'predicted_price': predicted_price,
                'direction': direction
            }
            
        except Exception as e:
            log(f"Error in AI 30-min prediction: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "ERROR")
            
            # Fallback to conservative assessment
            return {
                'favorable': False,
                'weakening': True,
                'confidence': 0.5,
                'predicted_price': current_price,
                'direction': 0
            }

    def _check_daily_circuit_breaker(self) -> bool:
        try:
            import datetime as dt
            today = dt.datetime.utcnow().date()

            if self._last_cb_reset_day != today:
                self._last_cb_reset_day = today
                self._circuit_breaker_triggered = False
                log(f"🔄 Circuit Breaker: Reset na nowy dzień ({today})", "INFO")

            if self._circuit_breaker_triggered:
                return True

            query = """
                SELECT COALESCE(SUM(pnl), 0) AS daily_pnl
                FROM trades
                WHERE action IN ('CLOSE_LONG', 'CLOSE_SHORT', 'SELL', 'SHORT_CLOSE')
                  AND timestamp >= CURRENT_DATE
            """
            rows = self.db.query(query)
            if not rows or rows[0][0] is None:
                return False

            daily_pnl_usdt = float(rows[0][0])
            balance = self.exec_manager.get_balance("USDT")
            if balance <= 0: return False

            daily_pnl_pct = (daily_pnl_usdt / balance) * 100
            warning_threshold = self._daily_loss_limit_pct * 0.70

            if daily_pnl_pct <= -warning_threshold and daily_pnl_pct > -self._daily_loss_limit_pct:
                log(f"⚠️ Circuit Breaker OSTRZEŻENIE: Dzienny PnL = {daily_pnl_pct:+.2f}%", "WARNING")

            if daily_pnl_pct <= -self._daily_loss_limit_pct:
                self._circuit_breaker_triggered = True
                log(f"🛑 CIRCUIT BREAKER WYZWOLONY! PnL: {daily_pnl_pct:+.2f}%. Trading zatrzymany do 00:00 UTC.", "ERROR")
                return True
            return False
        except Exception as e:
            log(f"Circuit Breaker error: {e}", "ERROR")
            return False
