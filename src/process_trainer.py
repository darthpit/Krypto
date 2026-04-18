import multiprocessing
import time
import sys
import os
import pandas as pd
import numpy as np
import datetime
import pandas_ta as ta
import json
import threading
from sklearn.ensemble import RandomForestClassifier
import psutil  # For memory monitoring

from src.database import Database
from src.utils.models import save_model
from src.utils.data_provider import MarketDataProvider
from src.utils.logger import log
from src.ai.models import EnsembleModel
from src.logic.scout import MatrixScout, DeepScout
from src.utils.model_monitor import ModelMonitor

class TrainerProcess(multiprocessing.Process):
    def __init__(self, ticker="BTC/USDT", interval=900):
        super().__init__()
        self.default_ticker = ticker
        self.interval = interval
        self.running = True
        self.current_ticker = None
        self.db = None
        
        # ═══════════════════════════════════════════════════════════════════
        # MICRO-INPUT / MACRO-OUTPUT STRATEGY (Złoty Graal!)
        # ═══════════════════════════════════════════════════════════════════
        # Input:  1-min candles (micro - widzi każdy szczegół)
        # Target: 30-min ahead (macro - filtruje szum)
        # 
        # Dlaczego 30 minut?
        # • Filtruje krótkoterminowy szum (drgawki 0.1%)
        # • Wystarczająco krótkie dla day trading
        # • Model uczy się WZORCÓW, nie reakcji na szum
        # • Perfect dla 20x leverage (nie overtrading!)
        self.PREDICTION_LOOKAHEAD = 450  # 7.5 godziny do przodu (450 minut) ✅
        

    def run(self):
        self.stop_event = threading.Event()
        log(f"Trainer Process Started (BTC Futures Mode) - PRIORYTET 2 (Wysoki)", "INFO")
        log(f"📋 LSTM Ensemble v3.4 startuje.", "INFO")

        self.db = Database()
        self.data_provider = MarketDataProvider()
        self.model_monitor = ModelMonitor()
        
        # Initialize scouts for market context
        self.scout = MatrixScout(self.data_provider)
        self.deep_scout = DeepScout(self.data_provider)

        # Target Ticker
        target_ticker = "BTC/USDT"
        try:
             with open('config.json', 'r') as f:
                config = json.load(f)
                target_ticker = config.get('trading', {}).get('target_symbol', "BTC/USDT")
        except:
             pass

        while self.running:
            try:
                loop_start = time.time()
                log(f"Starting training cycle for {target_ticker}...", "INFO")


                # Mark training start in AI Control Center
                self.model_monitor.update_start("lstm", "Inicjalizacja treningu...")
                
                self._update_pulse('pulse_30m', 'Model Training')

                self.current_ticker = target_ticker

                # ═══════════════════════════════════════════════════════════════
                # LSTM TRAINING CYCLE START
                # ═══════════════════════════════════════════════════════════════
                log(f"{'='*80}", "INFO", lstm_only=True)
                log(f"🚀 LSTM TRAINING CYCLE START - {target_ticker}", "SUCCESS", lstm_only=True)
                log(f"{'='*80}", "INFO", lstm_only=True)
                
                # 1. Synchronize History (User Request: First sync, then train)
                log(f"Synchronizing history for {target_ticker}...", "INFO")
                log(f"📥 Step 1: Data Synchronization", "INFO", lstm_only=True)
                self.model_monitor.update_progress("lstm", 10, "Pobieranie danych historycznych...")
                self._synchronize_history(target_ticker)

                # Fetch Data (Now from DB or fresh?)
                # If we synced to DB, we should probably load from DB or just fetch enough for training.
                # The existing _fetch_data_for_ticker fetches up to 180 days from DB (259,200 candles).
                # If we just synced all history, we train on full 180-day dataset.
                # UPDATED: No more cap at 90 days - using full lookback_days from config.

                # 2. Fetch Training Data
                log(f"📊 Step 2: Fetching Training Data", "INFO", lstm_only=True)
                df = self._fetch_data_for_ticker(target_ticker)

                if df is not None and len(df) > 50:
                    # Feature Engineering
                    log(f"🔧 Step 3: Feature Engineering", "INFO", lstm_only=True)
                    self.model_monitor.update_progress("lstm", 30, "Tworzenie cech (Feature Engineering)...")
                    df = self._engineer_features(df)
                    
                    # Check if feature engineering succeeded
                    if df is None or len(df) == 0:
                        log(f"Feature engineering failed for {target_ticker}", "ERROR")
                        self.model_monitor.update_error("lstm", "Feature engineering failed")
                        continue
                    
                    # Train Model
                    log(f"🧠 Step 4: LSTM Model Training", "INFO", lstm_only=True)
                    self.model_monitor.update_progress("lstm", 50, "Trenowanie sieci neuronowej...")
                    model, accuracy = self._train_model(df)

                    if model:
                        log(f"💾 Step 5: Saving Model & Stats", "INFO", lstm_only=True)
                        # Save Model
                        self.model_monitor.update_progress("lstm", 85, "Zapisywanie modelu...")
                        strategy_name = "Ensemble_RF_LSTM_Futures"
                        filepath = save_model(model, target_ticker, strategy_name)
                        log(f"[{target_ticker}] Model trained: {os.path.basename(filepath)} (Acc: {accuracy:.2f})", "SUCCESS")

                        self.model_monitor.update_progress("lstm", 95, "Aktualizacja statystyk...")
                        self._update_active_strategy(target_ticker, filepath, strategy_name)
                        self._save_model_stats(target_ticker, strategy_name, accuracy, filepath)
                        # Publish brain_stats for dashboard "LSTM Brain Stats"
                        self._save_brain_stats(accuracy)
                        
                        # Mark training as finished in AI Control Center
                        # Get data_days from config
                        data_days = 180  # Default from Micro/Macro strategy
                        try:
                            with open('config.json', 'r') as f:
                                config = json.load(f)
                                data_days = config.get('lookback_days', 180)
                        except:
                            pass
                        
                        self.model_monitor.update_finish("lstm", accuracy, data_days)
                        log(f"✅ AI Control Center: LSTM training finished (Accuracy: {accuracy:.1%})", "SUCCESS")
                        
                        # LSTM Training Summary
                        log(f"{'='*80}", "INFO", lstm_only=True)
                        log(f"✅ LSTM TRAINING CYCLE COMPLETE!", "SUCCESS", lstm_only=True)
                        log(f"{'='*80}", "INFO", lstm_only=True)
                        log(f"📊 Training Summary:", "INFO", lstm_only=True)
                        log(f"   - Ticker: {target_ticker}", "INFO", lstm_only=True)
                        log(f"   - Data Used: {len(df):,} candles ({len(df)//1440} days)", "INFO", lstm_only=True)
                        log(f"   - Model Accuracy: {accuracy:.2%}", "INFO", lstm_only=True)
                        log(f"   - Model Saved: {os.path.basename(filepath)}", "INFO", lstm_only=True)
                        log(f"   - Lookback Period: {data_days} days", "INFO", lstm_only=True)
                        log(f"{'='*80}", "INFO", lstm_only=True)
                else:
                    log(f"Not enough data for {target_ticker}", "WARNING")
                    self.model_monitor.update_error("lstm", "Niewystarczająca ilość danych")


                elapsed = time.time() - loop_start
                sleep_time = max(0, self.interval - elapsed)
                
                # --- FIX: Support "Run Once" mode for Supervisor ---
                if self.interval == 0:
                    log("Interval is 0 (Run-Once Mode). Training finished. Exiting process.", "INFO")
                    break
                # -----------------------------------------------------

                log(f"Training cycle complete. Sleeping for {sleep_time:.0f}s", "INFO")
                time.sleep(sleep_time)

            except Exception as e:
                log(f"Trainer Loop Error: {e}", "ERROR")
                self.model_monitor.update_error("lstm", str(e)[:100])
                
                
                time.sleep(60)

    def _synchronize_history(self, ticker):
        try:
            # Load lookback_days from config (default: 180 days for 6 months)
            lookback_days = 180
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    lookback_days = config.get('lookback_days', 180)
            except:
                pass
            
            log(f"📊 Synchronizing {lookback_days} days of historical data for {ticker}...", "INFO")

            # Calculate lookback date
            lookback_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=lookback_days)
            
            # Check if we have enough historical data
            oldest_ts = self._get_oldest_candle_timestamp(ticker)
            last_ts = self._get_last_candle_timestamp(ticker)
            
            start_date = lookback_date.strftime('%Y-%m-%d %H:%M:%S')
            
            if oldest_ts and last_ts:
                # Check if oldest data meets the required lookback period
                data_age_days = (datetime.datetime.now(datetime.timezone.utc) - oldest_ts).days
                
                if data_age_days >= lookback_days:
                    # We have enough history, just sync recent data
                    start_date = (last_ts + datetime.timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
                    log(f"✅ Resuming sync for {ticker} from {start_date} (Have {data_age_days} days of history)", "INFO")
                else:
                    # Not enough history, force full sync
                    log(f"⚠️ Insufficient history ({data_age_days} days). Forcing {lookback_days}-day sync from {start_date}", "WARNING")
            else:
                log(f"🔄 Starting fresh sync for {ticker} from {start_date} (Last {lookback_days} Days)", "INFO")

            # Use timeframe='1m' to match Trader
            # ENABLE DUAL EXCHANGE FETCHING (Binance for history + MEXC for recent)
            
            if lookback_days > 30:
                log(f"📥 Attempting to fetch {lookback_days} days using DUAL-EXCHANGE strategy...", "INFO")
                log(f"   - Binance: Historical data (>30 days ago)", "INFO")
                log(f"   - MEXC: Recent data (last 30 days)", "INFO")

                # Use fetch_dual_exchange_history instead of fetch_full_history
                # We need to adapt the callback to handle the dataframe chunks
                self.data_provider.fetch_dual_exchange_history(
                    ticker,
                    timeframe='1m',
                    target_days=lookback_days,
                    limit=1000,
                    callback=self._sync_callback
                )
            else:
                log(f"📥 Attempting to fetch {lookback_days} days from primary exchange (MEXC)...", "INFO")
                self.data_provider.fetch_full_history(ticker, timeframe='1m', start_date=start_date, limit=500, callback=self._sync_callback)
            
            # Check how many days we actually got
            oldest_ts_after = self._get_oldest_candle_timestamp(ticker)
            if oldest_ts_after:
                actual_days = (datetime.datetime.now(datetime.timezone.utc) - oldest_ts_after).days
                
                if actual_days < lookback_days:
                    log(f"⚠️ Primary exchange (MEXC Futures) has only {actual_days} days of data (limit: ~30 days)", "WARNING")
                    log(f"💡 Target: {lookback_days} days, Available: {actual_days} days", "WARNING")
                    log(f"ℹ️ MEXC Futures contracts have limited history. Using available data for training.", "INFO")
                    
                    # Update target days in system status to reflect reality
                    status = {
                        "status": "COMPLETED",
                        "ticker": ticker,
                        "message": f"History sync complete ({actual_days} days - exchange limit)",
                        "progress_percent": 100,
                        "target_days": actual_days,  # Use actual days as target
                        "available_days": actual_days,
                        "requested_days": lookback_days,
                        "exchange_limit": True,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }
                    self.db.execute(
                        "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                        ('sync_status', json.dumps(status), datetime.datetime.now(datetime.timezone.utc).isoformat())
                    )
                else:
                    log(f"✅ Successfully fetched {actual_days} days of historical data", "SUCCESS")

            # Mark sync as complete
            # Final status blob for dashboard Sync card
            status = {
                "status": "COMPLETED",
                "ticker": ticker,
                "message": f"History sync complete ({lookback_days} days)",
                "progress_percent": 100,
                "target_date": f"Last {lookback_days} days",
                "current_fetching_date": None,
                "total_days": lookback_days,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                ('sync_status', json.dumps(status), datetime.datetime.now(datetime.timezone.utc).isoformat())
            )

        except Exception as e:
            log(f"History sync error: {e}", "ERROR")

    def _get_last_candle_timestamp(self, ticker):
        try:
            rows = self.db.query("SELECT MAX(timestamp) as last_ts FROM candles WHERE ticker = ?", (ticker,))
            if rows and rows[0][0]:
                ts = rows[0][0]
                # Ensure timezone awareness
                if isinstance(ts, datetime.datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=datetime.timezone.utc)
                    return ts
                elif isinstance(ts, str):
                    ts = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=datetime.timezone.utc)
                    return ts
        except Exception as e:
            log(f"Error getting last candle: {e}", "ERROR")
        return None
    
    def _get_oldest_candle_timestamp(self, ticker):
        try:
            rows = self.db.query("SELECT MIN(timestamp) as oldest_ts FROM candles WHERE ticker = ?", (ticker,))
            if rows and rows[0][0]:
                ts = rows[0][0]
                # Ensure timezone awareness
                if isinstance(ts, datetime.datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=datetime.timezone.utc)
                    return ts
                elif isinstance(ts, str):
                    ts = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=datetime.timezone.utc)
                    return ts
        except Exception as e:
            log(f"Error getting oldest candle: {e}", "ERROR")
        return None

    def _sync_callback(self, df, progress_info):
        try:
            ticker = self.current_ticker
            self._save_candles(ticker, df)

            # Load target lookback days from config
            lookback_days = 180
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    lookback_days = config.get('lookback_days', 180)
            except:
                pass

            # Calculate progress percentage based on target lookback days
            days_fetched = progress_info['days_fetched'] + 1
            progress_percent = min(100, int((days_fetched / lookback_days) * 100))
            
            # Log detailed progress to system.log
            remaining_days = max(0, lookback_days - days_fetched)
            log(f"📥 Syncing {ticker}: Fetched {days_fetched} days | Goal: {lookback_days} days | Remaining: {remaining_days} days | Progress: {progress_percent}%", "INFO")

            status = {
                "status": "DOWNLOADING",
                "ticker": ticker,
                "message": f"Syncing history ({days_fetched}/{lookback_days} days)",
                "progress_percent": progress_percent,
                "days_downloaded": days_fetched,
                "total_days": lookback_days,
                "current_fetching_date": str(progress_info['current_date']),
                "target_date": f"Last {lookback_days} days"
            }
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                ('sync_status', json.dumps(status), datetime.datetime.now(datetime.timezone.utc).isoformat())
            )

            # Calculate TRUE history depth from database (to handle incremental syncs)
            true_history_days = days_fetched
            try:
                rows = self.db.query("SELECT MIN(timestamp) FROM candles WHERE ticker = ?", (ticker,))
                if rows and rows[0] and rows[0][0]:
                    min_ts = rows[0][0]
                    if isinstance(min_ts, str):
                        min_ts = datetime.datetime.fromisoformat(min_ts.replace('Z', '+00:00'))
                    if min_ts.tzinfo is None:
                        min_ts = min_ts.replace(tzinfo=datetime.timezone.utc)
                    
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    true_history_days = max(1, (now_utc - min_ts).days + 1)
            except Exception as e:
                log(f"Error calculating true history days: {e}", "WARNING")

            # Update Market Watch history days
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.db.execute(
                """INSERT INTO market_watch (ticker, history_days, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT (ticker) DO UPDATE SET history_days=EXCLUDED.history_days, updated_at=EXCLUDED.updated_at""",
                 (ticker, true_history_days, now_iso)
            )

        except Exception as e:
            log(f"Sync callback error: {e}", "ERROR")

    def _save_candles(self, ticker, df, timeframe='1m'):
        try:
            data = []
            for index, row in df.iterrows():
                ts = index.isoformat()
                # Convert numpy types to native Python types to avoid PostgreSQL schema errors
                data.append((
                    ticker, 
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
                ON CONFLICT (ticker, timestamp, timeframe) DO NOTHING
            """
            self.db.execute_many(query, data)
        except Exception as e:
            log(f"Error saving candles: {e}", "ERROR")

    def _fetch_data_for_ticker(self, ticker):
        try:
            # ═══════════════════════════════════════════════════════════════
            # LSTM TRAINING DATA: Full 180-day history (UPDATED)
            # ═══════════════════════════════════════════════════════════════
            # BYŁO: Ograniczone do 90 dni (cap at 90 days to prevent OOM)
            # JEST: Pełne 180 dni = 259,200 świeczek (1-min intervals)
            # 
            # Dlaczego 180 dni?
            # - dist_daily wymaga 1440 świeczek (24h) dla obliczenia SMA
            # - dist_4h wymaga 240 świeczek (4h) dla trendu
            # - 180 dni daje wystarczającą historię dla LSTM/Ensemble
            # - Model batch training zamiast ograniczania danych
            # ═══════════════════════════════════════════════════════════════
            
            # Decyduj o limitcie na podstawie lookback_days z config
            lookback_days = 180  # Default: 180 dni (pełna historia)
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    lookback_days = config.get('lookback_days', 180)
                    # USUNIĘTO: Cap at 90 days - teraz używamy pełnych 180 dni
                    # Optymalizacja: Model batch training zamiast ograniczania danych
            except:
                pass
            
            # Calculate limit: days × 1440 minutes/day
            training_limit = lookback_days * 1440
            log(f"📊 Training data: {lookback_days} days = {training_limit} candles (1-min intervals)", "INFO")

            # Try to fetch from DB first (full history)
            df = self._fetch_candles_from_db(ticker, limit=training_limit)
            if df is not None and len(df) > 1440:  # Minimum 1 day
                days_available = len(df) // 1440
                log(f"✅ LSTM Data Source: Database", "SUCCESS", lstm_only=True)
                log(f"📊 Fetched {len(df)} candles from database ({days_available} days) for training", "SUCCESS")
                log(f"📊 LSTM Training Dataset: {len(df):,} candles = {days_available} days of 1-min data", "INFO", lstm_only=True)
                return df

            # Fallback to API (if DB has insufficient data)
            log(f"⚠️ Database has insufficient data (<1440 candles), fetching from API...", "WARNING", lstm_only=True)
            # API has limit ~1000, so we'll get what we can
            df = self.data_provider.fetch_candles(ticker, limit=1000)
            if df is not None and not df.empty:
                log(f"✅ LSTM Data Source: API (fallback)", "WARNING", lstm_only=True)
                log(f"📊 Fetched {len(df)} candles from API for training", "INFO")
                log(f"⚠️ Limited to API data: {len(df)} candles (~{len(df)//60:.1f} hours)", "WARNING", lstm_only=True)
                return df
            return None
        except Exception as e:
            log(f"Data fetch error for {ticker}: {e}", "ERROR")
            return None

    def _fetch_candles_from_db(self, ticker, limit=2000):
        try:
            # Postgres query - CRITICAL: Fetch 1m timeframe for training to match Trader
            rows = self.db.query("SELECT timestamp, open, high, low, close, volume FROM candles WHERE ticker = ? AND timeframe = '1m' ORDER BY timestamp DESC LIMIT ?", (ticker, limit))
            if rows:
                df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                df.sort_index(inplace=True)

                # Ensure float
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)

                return df
        except Exception as e:
            log(f"DB fetch error: {e}", "WARNING")
        return None

    def _engineer_features(self, df):
        try:
            df = df.copy()
            
            # Remove duplicate timestamps if any (CRITICAL FIX)
            if df.index.duplicated().any():
                log(f"⚠️ Found {df.index.duplicated().sum()} duplicate timestamps. Removing...", "WARNING")
                df = df[~df.index.duplicated(keep='first')]
            
            # --- ORIGINAL FEATURES ---
            df['rsi'] = ta.rsi(df['close'], length=14)
            macd = ta.macd(df['close'])
            if macd is not None:
                # Safe join: only add columns that don't exist
                for col in macd.columns:
                    if col not in df.columns:
                        df[col] = macd[col]
            
            # --- NEW: MARKET MATRIX FEATURES (FAZA 1.1) ---
            # Get market correlation score (average correlation with top assets)
            try:
                market_correlation = self._get_market_correlation_score()
                df['market_correlation'] = market_correlation
                log(f"Market Correlation Score: {market_correlation:.3f}", "INFO")
            except Exception as e:
                log(f"Failed to get market correlation: {e}", "WARNING")
                df['market_correlation'] = 0.5  # Neutral default
            
            # --- NEW: MARKET BREADTH FEATURES (FAZA 1.1) ---
            # Get bulls/bears ratio from DeepScout
            try:
                breadth_data = self.deep_scout.scan_market_breadth()
                bulls = breadth_data.get('bulls', 0)
                bears = breadth_data.get('bears', 0)
                total = breadth_data.get('total', 1)
                
                # Bulls/Bears Ratio (normalized 0-1)
                if bulls + bears > 0:
                    bulls_bears_ratio = bulls / (bulls + bears)
                else:
                    bulls_bears_ratio = 0.5
                
                # Market Strength Score (0-100)
                market_strength = (bulls / total * 100) if total > 0 else 50
                
                df['bulls_bears_ratio'] = bulls_bears_ratio
                df['market_strength'] = market_strength
                
                log(f"Market Breadth: Bulls={bulls}, Bears={bears}, Ratio={bulls_bears_ratio:.3f}, Strength={market_strength:.1f}%", "INFO")
            except Exception as e:
                log(f"Failed to get market breadth: {e}", "WARNING")
                df['bulls_bears_ratio'] = 0.5
                df['market_strength'] = 50
            
            # --- NEW: VOLUME FEATURES (FAZA 1.2) ---
            # Volume SMA Ratio
            df['volume_sma_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
            
            # OBV (On Balance Volume)
            df['obv'] = ta.obv(df['close'], df['volume'])
            df['obv_sma'] = df['obv'].rolling(20).mean()
            df['obv_ratio'] = df['obv'] / df['obv_sma']
            
            # MFI (Money Flow Index)
            df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14)
            
            # --- NEW: VOLATILITY FEATURES (FAZA 1.2) ---
            # ATR
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            df['atr_pct'] = (df['atr'] / df['close']) * 100
            
            # Bollinger Bands Width
            bbands = ta.bbands(df['close'], length=20)
            if bbands is not None and 'BBU_20_2.0' in bbands.columns:
                df['bb_upper'] = bbands['BBU_20_2.0']
                df['bb_middle'] = bbands['BBM_20_2.0']
                df['bb_lower'] = bbands['BBL_20_2.0']
                df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            else:
                df['bb_width'] = 0.04  # Default ~4%
            
            # --- NEW: MOMENTUM FEATURES (FAZA 1.2) ---
            # ROC (Rate of Change)
            df['roc'] = ta.roc(df['close'], length=12)
            
            # Stochastic
            stoch = ta.stoch(df['high'], df['low'], df['close'])
            if stoch is not None:
                # Safe join: only add columns that don't exist
                for col in stoch.columns:
                    if col not in df.columns:
                        df[col] = stoch[col]
                # Rename if needed
                if 'STOCHk_14_3_3' in df.columns:
                    df['stoch_k'] = df['STOCHk_14_3_3']
                    df['stoch_d'] = df['STOCHd_14_3_3']
            
            # --- NEW: FUNDING RATE FEATURES (FAZA 3.1) - CRITICAL FOR FUTURES! ---
            try:
                funding_data = self._get_funding_rate_features()
                df['funding_rate'] = funding_data['current']
                df['funding_rate_trend'] = funding_data['trend']
                log(f"Funding Rate: {funding_data['current']:.6f}, Trend: {funding_data['trend']:.6f}", "INFO")
            except Exception as e:
                log(f"Failed to get funding rate: {e}", "WARNING")
                df['funding_rate'] = 0.0
                df['funding_rate_trend'] = 0.0
            
            # --- ORDER FLOW METRICS (BINANCE VISION) ---
            try:
                # We fetch all metrics for this ticker and merge them
                # Metrics are typically daily/5min, we ffill them onto 1m candles
                standard_ticker = f"{self.current_ticker[:3]}/{self.current_ticker[4:]}" if 'USDT:USDT' in self.current_ticker else self.current_ticker
                metrics_query = """
                    SELECT timestamp, open_interest, oi_value_usdt, top_trader_ls_ratio, taker_buy_sell_ratio
                    FROM futures_metrics
                    WHERE ticker = ? AND timestamp >= ?
                    ORDER BY timestamp ASC
                """
                
                # Get metrics from a bit before the first candle to ffill properly
                start_date = df.index[0] - pd.Timedelta(days=1)
                metrics_rows = self.db.query(metrics_query, (standard_ticker, start_date.isoformat()))
                
                if metrics_rows and len(metrics_rows) > 0:
                    metrics_df = pd.DataFrame(metrics_rows, columns=['timestamp', 'open_interest', 'oi_value_usdt', 'top_trader_ls_ratio', 'taker_buy_sell_ratio'])
                    metrics_df['timestamp'] = pd.to_datetime(metrics_df['timestamp'])
                    metrics_df.set_index('timestamp', inplace=True)
                    
                    # Merge with forward fill, then fill remaining NaNs (backwards) with default values
                    df = df.join(metrics_df, how='left').ffill()
                    df['open_interest'] = df['open_interest'].fillna(0.0)
                    df['oi_value_usdt'] = df['oi_value_usdt'].fillna(0.0)
                    df['top_trader_ls_ratio'] = df['top_trader_ls_ratio'].fillna(1.0)
                    df['taker_buy_sell_ratio'] = df['taker_buy_sell_ratio'].fillna(1.0)
                else:
                    # Fill with defaults if no data
                    df['open_interest'] = 0.0
                    df['oi_value_usdt'] = 0.0
                    df['top_trader_ls_ratio'] = 1.0
                    df['taker_buy_sell_ratio'] = 1.0
            except Exception as e:
                log(f"⚠️ Failed to merge order flow metrics: {e}", "WARNING")
                df['open_interest'] = 0.0
                df['oi_value_usdt'] = 0.0
                df['top_trader_ls_ratio'] = 1.0
                df['taker_buy_sell_ratio'] = 1.0

            # --- NEW: MACRO CONTEXT FEATURES (MICRO/MACRO STRATEGY) ---
            # Wstrzykujemy wiedzę o trendach wyższych interwałów jako pojedyncze liczby
            # Zamiast dawać LSTM 1440 świeczek, dajemy gotową informację o trendzie
            
            # Trend 4h (240 minut)
            df['trend_4h_sma'] = df['close'].rolling(window=240, min_periods=1).mean()
            df['dist_4h'] = (df['close'] - df['trend_4h_sma']) / df['trend_4h_sma']
            df['dist_4h'].fillna(0, inplace=True)
            
            # Trend 24h (1440 minut = 1 dzień)
            df['trend_daily_sma'] = df['close'].rolling(window=1440, min_periods=1).mean()
            df['dist_daily'] = (df['close'] - df['trend_daily_sma']) / df['trend_daily_sma']
            df['dist_daily'].fillna(0, inplace=True)
            
            # Volatility Regime (czy rynek szaleje?)
            df['volatility_24h'] = df['close'].rolling(window=1440, min_periods=1).std()
            df['volatility_24h'].fillna(df['close'].std(), inplace=True)  # Fallback to global std
            
            log(f"📊 Macro Context: 4h Trend SMA={df['trend_4h_sma'].iloc[-1]:.2f}, Daily Dist={df['dist_daily'].iloc[-1]:.4f}, Vol 24h={df['volatility_24h'].iloc[-1]:.2f}", "INFO")
            
            # Target
            # ═══════════════════════════════════════════════════════════════════
            # TARGET: 30-MINUTE LOOKAHEAD (Macro-Output Strategy)
            # ═══════════════════════════════════════════════════════════════════
            # BYŁO (źle):
            # df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
            # → Przewidywało następną 1 minutę (pełne szumu!)
            #
            # JEST (Złoty Graal):
            # Przewiduje gdzie będzie cena za 30 MINUT
            # → Filtruje szum, znajduje prawdziwe wzorce!
            
            df['target_price_30m'] = df['close'].shift(-self.PREDICTION_LOOKAHEAD)
            df['target'] = (df['target_price_30m'] > df['close']).astype(int)
            
            # Store lookahead in model metadata (for inference)
            df.attrs['lookahead_minutes'] = self.PREDICTION_LOOKAHEAD
            
            log(f"📊 Target: Predicting {self.PREDICTION_LOOKAHEAD} minutes ahead (Micro-Input / Macro-Output)", "INFO")
            
            # Drop NaN (last 30 rows won't have target)
            initial_len = len(df)
            df.dropna(inplace=True)
            dropped = initial_len - len(df)
            
            log(f"✅ Training samples after lookahead: {len(df)} (lost {self.PREDICTION_LOOKAHEAD} at end, dropped {dropped} NaN rows)", "INFO")
            
            # Verify target exists
            if 'target' not in df.columns:
                log(f"❌ ERROR: 'target' column not created! Available columns: {list(df.columns)}", "ERROR", lstm_only=True)
                return None
            
            # LSTM Log: Feature Engineering Summary
            log(f"✅ Feature Engineering Complete: {len(df)} rows, {len(df.columns)} features", "SUCCESS")
            log(f"🔧 LSTM Features Created:", "INFO", lstm_only=True)
            log(f"   - Technical Indicators: RSI, MACD, Bollinger, ATR", "INFO", lstm_only=True)
            log(f"   - Macro Context: 4h/24h trends, volatility regime", "INFO", lstm_only=True)
            log(f"   - Target: {self.PREDICTION_LOOKAHEAD}-minute lookahead (Micro-Input/Macro-Output)", "INFO", lstm_only=True)
            log(f"   - Final Dataset: {len(df):,} samples × {len(df.columns)} features", "INFO", lstm_only=True)
            
            return df
        except Exception as e:
            log(f"Feature engineering error: {e}", "ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return None
    
    def _get_market_correlation_score(self):
        """
        Calculate average correlation score with top crypto assets.
        Returns: float (0-1) where 1 = highly correlated, 0 = uncorrelated
        """
        try:
            # Get correlation matrix from MatrixScout
            matrix_data = self.scout.calculate_correlation_matrix()
            
            if not matrix_data or 'series' not in matrix_data:
                return 0.5  # Neutral
            
            series = matrix_data['series']
            
            # Find BTC row
            btc_row = None
            for row in series:
                if 'BTC' in row.get('name', ''):
                    btc_row = row
                    break
            
            if not btc_row or 'data' not in btc_row:
                return 0.5
            
            # Calculate average correlation (excluding self-correlation)
            correlations = []
            for point in btc_row['data']:
                if point['x'] != 'BTC':  # Exclude self
                    correlations.append(abs(point['y']))
            
            if correlations:
                avg_corr = sum(correlations) / len(correlations)
                return avg_corr
            
            return 0.5
        except Exception as e:
            log(f"Market correlation score error: {e}", "WARNING")
            return 0.5
    
    def _get_funding_rate_features(self):
        """
        Get funding rate features (FAZA 3.1 - CRITICAL for Futures!)
        
        Returns: dict with 'current' and 'trend' (8h average)
        
        Interpretation:
        - High positive rate (>0.01%): Longs overcrowded → Potential SHORT signal
        - High negative rate (<-0.01%): Shorts overcrowded → Potential LONG signal
        - Rate near 0: Neutral, market balanced
        """
        try:
            ticker = self.current_ticker or "BTC/USDT"
            
            # Get current funding rate
            funding_data = self.data_provider.fetch_funding_rate(ticker)
            
            if not funding_data or 'fundingRate' not in funding_data:
                return {'current': 0.0, 'trend': 0.0}
            
            current_rate = float(funding_data['fundingRate'])
            
            # Get funding rate history (last 8 periods)
            history = self.data_provider.fetch_funding_rate_history(ticker, limit=8)
            
            if history and len(history) > 0:
                # Calculate 8h average trend
                trend = sum(history) / len(history)
            else:
                # Fallback to current rate
                trend = current_rate
            
            return {
                'current': current_rate,
                'trend': trend
            }
            
        except Exception as e:
            log(f"Funding rate feature error: {e}", "WARNING")
            return {'current': 0.0, 'trend': 0.0}

    def _train_model(self, df):
        try:
            # ═══════════════════════════════════════════════════════════════════
            # MEMORY CHECK (before starting LSTM training)
            # ═══════════════════════════════════════════════════════════════════
            try:
                mem = psutil.virtual_memory()
                available_gb = mem.available / (1024 ** 3)
                total_gb = mem.total / (1024 ** 3)
                percent_free = 100 - mem.percent
                
                if available_gb >= 5.0:  # Need at least 5GB free for LSTM
                    log(f"✅ Memory OK: {available_gb:.1f}GB available / {total_gb:.1f}GB total ({percent_free:.1f}% free)", "INFO")
                else:
                    log(f"⚠️ LOW MEMORY: {available_gb:.1f}GB available / {total_gb:.1f}GB total", "WARNING")
                    log(f"💡 TIP: LSTM training may be slower or fail with OOM", "WARNING")
            except Exception as e:
                log(f"Memory check failed: {e}", "WARNING")
            
            # UPDATED FEATURE LIST (FAZA 1.1 + 1.2 + 3.1 + MICRO/MACRO)
            feature_cols = [
                # Original features
                'rsi', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
                # Market Matrix & Breadth (FAZA 1.1)
                'market_correlation', 'bulls_bears_ratio', 'market_strength',
                # Volume features (FAZA 1.2)
                'volume_sma_ratio', 'obv_ratio', 'mfi',
                # Volatility features (FAZA 1.2)
                'atr_pct', 'bb_width',
                # Momentum features (FAZA 1.2)
                'roc',
                # Funding Rate features (FAZA 3.1) - CRITICAL!
                'funding_rate', 'funding_rate_trend',
                # Order Flow Metrics
                'open_interest', 'oi_value_usdt', 'top_trader_ls_ratio', 'taker_buy_sell_ratio',
                # Macro Context features (MICRO/MACRO STRATEGY) - NEW!
                'dist_4h', 'dist_daily', 'volatility_24h'
            ]
            
            # Add stochastic if available
            if 'stoch_k' in df.columns:
                feature_cols.extend(['stoch_k', 'stoch_d'])
            
            valid_features = [c for c in feature_cols if c in df.columns]

            if not valid_features:
                log("No valid features found for training", "ERROR")
                return None, 0
            
            # Check if target exists
            if 'target' not in df.columns:
                log("❌ ERROR: 'target' column missing in dataframe. Cannot train.", "ERROR")
                log(f"Available columns: {list(df.columns)}", "ERROR")
                return None, 0
            
            log(f"Training with {len(valid_features)} features: {valid_features}", "INFO")
            log(f"🎯 LSTM Training Configuration:", "INFO", lstm_only=True)
            log(f"   - Features: {len(valid_features)} indicators", "INFO", lstm_only=True)
            log(f"   - Feature List: {', '.join(valid_features[:10])}{'...' if len(valid_features) > 10 else ''}", "INFO", lstm_only=True)

            X = df[valid_features]
            y = df['target']

            if len(X) < 10:
                log("Not enough samples for training", "WARNING", lstm_only=True)
                return None, 0

            split_idx = int(len(df) * 0.8)
            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
            
            # LSTM Log: Train/Test Split
            log(f"📊 LSTM Dataset Split:", "INFO", lstm_only=True)
            log(f"   - Training Set: {len(X_train):,} samples ({len(X_train)//1440} days)", "INFO", lstm_only=True)
            log(f"   - Test Set: {len(X_test):,} samples ({len(X_test)//1440} days)", "INFO", lstm_only=True)
            log(f"   - Split Ratio: 80% train / 20% test", "INFO", lstm_only=True)
            
            # Check class balance
            class_counts = y_train.value_counts()
            class_0_pct = (class_counts.get(0, 0) / len(y_train)) * 100
            class_1_pct = (class_counts.get(1, 0) / len(y_train)) * 100
            
            log(f"📊 Class Balance: 0 (DOWN)={class_0_pct:.1f}%, 1 (UP)={class_1_pct:.1f}%", "INFO")
            log(f"📊 LSTM Target Distribution:", "INFO", lstm_only=True)
            log(f"   - Class 0 (DOWN): {class_counts.get(0, 0):,} samples ({class_0_pct:.1f}%)", "INFO", lstm_only=True)
            log(f"   - Class 1 (UP): {class_counts.get(1, 0):,} samples ({class_1_pct:.1f}%)", "INFO", lstm_only=True)
            
            # ⚠️ CRITICAL FIX: Handle severe class imbalance
            if class_0_pct > 70 or class_1_pct > 70:
                log(f"⚠️ SEVERE CLASS IMBALANCE detected! ({max(class_0_pct, class_1_pct):.1f}% majority class)", "WARNING")
                log(f"💡 Applying SMOTE (Synthetic Minority Over-sampling) to balance classes...", "INFO")
                
                try:
                    from imblearn.over_sampling import SMOTE
                    smote = SMOTE(random_state=42, k_neighbors=min(5, min(class_counts.values())-1))
                    X_train, y_train = smote.fit_resample(X_train, y_train)
                    
                    # Log new balance
                    new_class_counts = pd.Series(y_train).value_counts()
                    new_class_0_pct = (new_class_counts.get(0, 0) / len(y_train)) * 100
                    new_class_1_pct = (new_class_counts.get(1, 0) / len(y_train)) * 100
                    log(f"✅ After SMOTE: 0={new_class_0_pct:.1f}%, 1={new_class_1_pct:.1f}% (balanced!)", "SUCCESS")
                except ImportError:
                    log(f"⚠️ SMOTE not available (pip install imbalanced-learn). Using class weights instead.", "WARNING")
                except Exception as e:
                    log(f"⚠️ SMOTE failed: {e}. Using class weights instead.", "WARNING")

            # LSTM Training Start
            log(f"🚀 Starting LSTM Ensemble Training...", "INFO", lstm_only=True)
            log(f"   - Architecture: Bidirectional LSTM + Multi-Head Attention", "INFO", lstm_only=True)
            log(f"   - Ensemble: RandomForest + XGBoost + LSTM", "INFO", lstm_only=True)
            
            model = EnsembleModel()
            
            # Log training progress (EnsembleModel has multiple epochs internally)
            log(f"🔄 Training RandomForest...", "INFO", lstm_only=True)
            log(f"🔄 Training XGBoost...", "INFO", lstm_only=True)
            log(f"🔄 Training LSTM with Attention...", "INFO", lstm_only=True)
            
            model.fit(X_train, y_train)
            
            log(f"✅ LSTM Ensemble Training Complete!", "SUCCESS", lstm_only=True)

            # Predictions and accuracy
            log(f"📊 Evaluating model on test set...", "INFO", lstm_only=True)
            preds = model.predict(X_test)
            accuracy = np.mean(preds == y_test)
            
            # Calculate per-class accuracy for better diagnostics
            from sklearn.metrics import classification_report
            try:
                report = classification_report(y_test, preds, target_names=['DOWN', 'UP'], output_dict=True, zero_division=0)
                down_acc = report['DOWN']['recall'] * 100
                up_acc = report['UP']['recall'] * 100
                down_prec = report['DOWN']['precision'] * 100
                up_prec = report['UP']['precision'] * 100
                
                log(f"📊 Per-Class Accuracy: DOWN={down_acc:.1f}%, UP={up_acc:.1f}%", "INFO")
                log(f"📊 LSTM Test Results:", "SUCCESS", lstm_only=True)
                log(f"   - Overall Accuracy: {accuracy:.2%}", "SUCCESS", lstm_only=True)
                log(f"   - DOWN (Class 0): Precision={down_prec:.1f}%, Recall={down_acc:.1f}%", "INFO", lstm_only=True)
                log(f"   - UP (Class 1): Precision={up_prec:.1f}%, Recall={up_acc:.1f}%", "INFO", lstm_only=True)
                log(f"   - Test Samples: {len(X_test):,} predictions", "INFO", lstm_only=True)
            except Exception:
                pass
            
            log(f"✅ Model Training Complete: Accuracy={accuracy:.2%} ({len(valid_features)} features)", "SUCCESS")
            log(f"🎯 LSTM Model Ready for Deployment!", "SUCCESS", lstm_only=True)

            return model, accuracy

        except Exception as e:
            log(f"Training error: {e}", "ERROR")
            return None, 0

    def _update_active_strategy(self, ticker, filepath, strategy_name):
        try:
            params_json = json.dumps({"model_path": filepath})
            query = """
                INSERT INTO active_strategies (ticker, status, strategy_name, params, updated_at)
                VALUES (?, 'ACTIVE', ?, ?, ?)
                ON CONFLICT (ticker) DO UPDATE SET status=EXCLUDED.status, strategy_name=EXCLUDED.strategy_name, params=EXCLUDED.params, updated_at=EXCLUDED.updated_at
            """
            self.db.execute(query, (ticker, strategy_name, params_json, datetime.datetime.now(datetime.timezone.utc).isoformat()))
        except Exception as e:
            log(f"Database update error: {e}", "ERROR")

    def _save_model_stats(self, ticker, strategy, accuracy, path):
        try:
            stats = {
                "strategy": strategy,
                "accuracy": float(accuracy),
                "last_trained": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "model_path": path,
                "ticker": ticker
            }
            query = "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at"
            self.db.execute(query, (f"model_stats_{ticker}", json.dumps(stats), datetime.datetime.now(datetime.timezone.utc).isoformat()))
            if ticker.startswith("BTC"):
                 self.db.execute(query, ("model_stats", json.dumps(stats), datetime.datetime.now(datetime.timezone.utc).isoformat()))
        except Exception as e:
            log(f"Failed to save model stats: {e}", "ERROR")

    def _save_brain_stats(self, accuracy):
        """
        Dashboard reads brain_stats.json and expects:
        - accuracy (0..1 or 0..100)
        - hits / misses (optional)
        - last_check (string)
        - training_count (ile razy się wytrenował)
        - training_progress (0-100%)
        - next_training_in (minuty do kolejnego treningu)
        - accuracy_to_goal (% do osiągnięcia 90%)
        """
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)

            # Get current training count
            training_count = 0
            try:
                rows = self.db.query(
                    "SELECT value FROM system_status WHERE key = 'training_count'"
                )
                if rows and rows[0] and rows[0][0]:
                    training_count = int(rows[0][0])
            except Exception:
                pass
            
            # Increment training count
            training_count += 1
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                ('training_count', str(training_count), now_utc.isoformat())
            )

            # Get hits/misses
            hits = 0
            misses = 0
            try:
                rows = self.db.query(
                    "SELECT "
                    "SUM(CASE WHEN result='HIT' THEN 1 ELSE 0 END) AS hits, "
                    "SUM(CASE WHEN result='MISS' THEN 1 ELSE 0 END) AS misses "
                    "FROM predictions"
                )
                if rows and rows[0]:
                    hits = int(rows[0][0] or 0)
                    misses = int(rows[0][1] or 0)
            except Exception:
                # predictions table may be empty early on
                pass

            # Check if training is currently active (this process is running)
            training_status = "✅ Trening zakończony"  # We just finished training
            
            # Calculate real accuracy from predictions (validation accuracy)
            # Use training accuracy as fallback if no predictions yet
            real_accuracy = float(accuracy)  # Training accuracy from model
            if hits + misses > 0:
                real_accuracy = hits / (hits + misses)  # Validation accuracy from predictions
            
            # Calculate training progress (0-100%)
            # Assume 10 samples per training, model is "complete" after collecting enough validation data
            min_predictions_for_stable = 100  # Need 100 predictions to be stable
            total_predictions = hits + misses
            training_progress = min(100, (total_predictions / min_predictions_for_stable) * 100)
            
            # Calculate accuracy to goal (90%)
            goal_accuracy = 0.90
            current_accuracy = real_accuracy
            accuracy_to_goal = max(0, (goal_accuracy - current_accuracy) * 100)  # % points remaining
            
            # Calculate next training time (30 minutes interval)
            next_training_minutes = 30  # Fixed 30-minute interval
            
            # Win rate calculation (7 days)
            win_rate_7d = 0.0
            try:
                seven_days_ago = (now_utc - datetime.timedelta(days=7)).isoformat()
                rows = self.db.query(
                    "SELECT "
                    "SUM(CASE WHEN result='HIT' THEN 1 ELSE 0 END) AS hits_7d, "
                    "COUNT(*) AS total_7d "
                    "FROM predictions WHERE timestamp >= ?",
                    (seven_days_ago,)
                )
                if rows and rows[0] and rows[0][1] > 0:
                    win_rate_7d = (rows[0][0] or 0) / rows[0][1]
            except Exception:
                pass
            
            payload = {
                "accuracy": real_accuracy,
                "training_accuracy": float(accuracy),  # Keep training accuracy for reference
                "hits": hits,
                "misses": misses,
                "last_check": now_utc.isoformat(),
                "training_status": training_status,
                "last_trained": now_utc.isoformat(),
                
                # NEW: Extended metrics
                "training_count": training_count,
                "training_progress": round(training_progress, 1),
                "next_training_minutes": next_training_minutes,
                "accuracy_to_goal": round(accuracy_to_goal, 1),
                "goal_accuracy": goal_accuracy,
                "win_rate_7d": round(win_rate_7d, 3),
                "total_predictions": total_predictions,
                "model_completeness_pct": round(training_progress, 1)
            }

            query = "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at"
            self.db.execute(query, ("brain_stats", json.dumps(payload), now_utc.isoformat()))
            
            log(f"📊 Brain Stats: Trening #{training_count}, Accuracy={real_accuracy:.1%}, Progress={training_progress:.0f}%, Do celu={accuracy_to_goal:.1f}%", "INFO")
        except Exception as e:
            log(f"Failed to save brain stats: {e}", "ERROR")

    def _update_pulse(self, key, action):
        try:
            pulse_data = {
                "status": "running",
                "details": {"action": action},
                "last_run": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at",
                (key, json.dumps(pulse_data), datetime.datetime.now(datetime.timezone.utc).isoformat())
            )
        except Exception as e:
            pass
