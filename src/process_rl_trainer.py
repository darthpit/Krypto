"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  RL TRAINING PROCESS (FAZA 4) - PRIORYTET 3 (TŁO)                           ║
║  PPO Training Script for Trading Agent                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Ten skrypt trenuje agenta Reinforcement Learning na danych historycznych.

HIERARCHIA PROCESÓW (NOWA):
─────────────────────────────────────────────────────────────────────────────
Priorytet 1 (Krytyczny): Pobieranie świeżych świeczek (Data Sync)
Priorytet 2 (Wysoki):    Trening LSTM Ensemble v3.4 (co 30 min)
Priorytet 3 (Tło):       Trening PPO Agent (tylko gdy P1 i P2 nie są aktywne)

PPO może być pauzowany przez LSTM (Priority 2 > 3).

WORKFLOW:
─────────────────────────────────────────────────────────────────────────────
1. Pobierz 6 miesięcy danych historycznych (1min OHLCV) - ~260,000 świeczek
2. Wygeneruj technical indicators (RSI, MACD, ATR, etc.)
3. Wytrenuj obecny model LSTM/Ensemble (dla LSTM predictions)
4. Stwórz TradingEnv z danymi + LSTM predictions
5. Trenuj PPO Agent przez 100k-1M steps
6. Zapisz wytrenowany model
7. Przeprowadź backtest na danych walidacyjnych
8. Zapisz wyniki i metryki

URUCHOMIENIE:
─────────────────────────────────────────────────────────────────────────────
python3.12 src/process_rl_trainer.py --timesteps 100000 --balance 1000 --data-days 180

PARAMETRY:
─────────────────────────────────────────────────────────────────────────────
--timesteps: Liczba kroków treningowych (default: 100000)
--balance: Początkowy kapitał (default: 1000 USDT)
--leverage: Dźwignia (default: 20x)
--data-days: Ile dni danych pobrać (default: 180, tj. 6 miesięcy)
--validate: Czy przeprowadzić walidację po treningu (default: True)
"""

import os
import sys
import argparse
import json
import glob
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.logger import log
from src.utils.data_provider import MarketDataProvider
from src.utils.model_monitor import ModelMonitor
from src.ai.models import EnsembleModel
from src.ai.rl_agent import (
    TradingEnv,
    PPOTradingAgent,
    TradingCallback,
    backtest_agent
)

import pandas_ta as ta
import psutil  # For memory monitoring


def check_memory_available(min_gb_required: float = 10.0) -> tuple:
    """
    Check if enough memory is available for training.
    
    Args:
        min_gb_required: Minimum GB of available memory required
        
    Returns:
        Tuple (available_gb, is_sufficient, message)
    """
    try:
        # Get system memory info
        mem = psutil.virtual_memory()
        available_gb = mem.available / (1024 ** 3)  # Convert bytes to GB
        total_gb = mem.total / (1024 ** 3)
        used_gb = mem.used / (1024 ** 3)
        percent_used = mem.percent
        
        is_sufficient = available_gb >= min_gb_required
        
        if is_sufficient:
            message = f"✅ Memory OK: {available_gb:.1f}GB available / {total_gb:.1f}GB total ({100-percent_used:.1f}% free)"
        else:
            message = f"⚠️ LOW MEMORY: {available_gb:.1f}GB available (need {min_gb_required}GB) / {total_gb:.1f}GB total"
        
        return (available_gb, is_sufficient, message)
        
    except Exception as e:
        # Fallback if psutil fails
        return (0, False, f"❌ Memory check failed: {e}")


class RLTrainer:
    """
    Manager for RL Agent Training Process.
    
    Orchestrates:
    1. Data preparation
    2. Feature engineering
    3. LSTM model training (for predictions)
    4. PPO agent training
    5. Validation and backtesting
    
    MICRO-INPUT / MACRO-OUTPUT STRATEGY:
    • Input: 1-min candles (micro - see every detail)
    • Target: 30-min ahead (macro - filter noise)
    """
    
    def __init__(
        self,
        ticker: str = "BTC/USDT",  # FIXED: Use MEXC format (without :USDT suffix)
        exchange_id: str = "mexc",
        initial_balance: float = 1000.0,
        leverage: int = 20,
        data_days: int = 180,  # Changed from data_months to data_days
        prediction_lookahead: int = 30,  # NEW: 30-minute target
    ):
        """
        Args:
            ticker: Trading pair
            exchange_id: Exchange (mexc, binance, etc.)
            initial_balance: Starting capital
            leverage: Leverage multiplier
            data_days: How many days of data to fetch (default: 180 = 6 months)
        """
        self.ticker = ticker
        self.exchange_id = exchange_id
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.data_days = data_days
        self.data_months = int(data_days / 30)  # Keep for backwards compatibility
        
        log(f"📊 PPO Trainer Configuration:", "INFO")
        log(f"   - Data Days: {data_days} days", "INFO")
        log(f"   - Initial Balance: ${initial_balance:.2f}", "INFO")
        log(f"   - Leverage: {leverage}x", "INFO")
        log(f"   - Prediction Lookahead: {prediction_lookahead} minutes", "INFO")
        self.prediction_lookahead = prediction_lookahead  # 30-minute target ✅
        
        # Initialize data provider
        self.data_provider = MarketDataProvider()
        
        # Initialize Model Monitor (AI Control Center)
        self.model_monitor = ModelMonitor()
        
        # Auto-resume and checkpoint settings
        self.auto_resume = False  # Will be set via command line arg
        self.checkpoint_interval = 10000  # Default checkpoint interval
        
        # Paths
        self.models_dir = Path("models")
        self.models_dir.mkdir(exist_ok=True)
        
        self.rl_model_path = self.models_dir / "ppo_trading_agent"
        self.lstm_model_path = self.models_dir / "ensemble_model"
        self.results_path = self.models_dir / "rl_training_results.json"
        
        # LSTM lockfile path (to check if LSTM is training - Priority 2)
        self.lstm_lockfile = self.models_dir / ".lstm_training.lock"
        
        log(f"🚀 RL Trainer initialized for {ticker}", "SUCCESS")
    
    def _find_latest_checkpoint(self) -> str:
        """
        Find the latest checkpoint in checkpoints directory.
        
        Returns:
            Path to latest checkpoint or None if no checkpoints found
        """
        import os
        import glob
        
        checkpoint_dir = self.models_dir / "checkpoints"
        
        if not checkpoint_dir.exists():
            return None
        
        # Find all checkpoint files
        checkpoints = glob.glob(str(checkpoint_dir / "ppo_checkpoint_*.zip"))
        
        if not checkpoints:
            return None
        
        # Sort by timesteps (extract from filename)
        def extract_timesteps(path):
            try:
                basename = os.path.basename(path)
                # ppo_checkpoint_10000.zip -> 10000
                timesteps = int(basename.split('_')[-1].replace('.zip', ''))
                return timesteps
            except:
                return 0
        
        checkpoints.sort(key=extract_timesteps, reverse=True)
        latest = checkpoints[0]
        
        # Remove .zip extension for loading
        latest_without_ext = latest.replace('.zip', '')
        
        log(f"🔍 Found latest checkpoint: {os.path.basename(latest)} ({extract_timesteps(latest)} steps)", "INFO")
        
        return latest_without_ext
    
    def fetch_training_data(self) -> pd.DataFrame:
        """
        Pobiera dane historyczne do treningu z bazy danych (jeśli dostępne).
        Wykorzystuje dane które zostały już pobrane przez process_trainer.py.
        
        Returns:
            DataFrame with OHLCV data
        """
        log(f"📊 Loading {self.data_days} days ({self.data_months} months) of historical data...", "INFO")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.data_days)
        
        # STEP 1: Try to load from database first (data synced by process_trainer.py)
        try:
            from src.database import Database
            db = Database()
            
            # Query candles from database for 1m timeframe
            query = """
                SELECT timestamp, open, high, low, close, volume 
                FROM candles 
                WHERE ticker = ? AND timestamp >= ? AND timeframe = '1m'
                ORDER BY timestamp ASC
            """
            
            rows = db.query(query, (self.ticker, start_date.isoformat()))
            
            if rows and len(rows) > 0:
                log(f"✅ Found {len(rows)} candles in database", "INFO")
                
                # Convert to DataFrame
                df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                
                # Ensure float types
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                
                # Check if we have enough data
                # REQUIREMENT: At least 90% of requested days (e.g., 162 days for 180 day request)
                # IDEAL: Full requested days = data_days × 1440 candles
                MIN_PERCENTAGE_REQUIRED = 0.90  # Require at least 90% of requested data
                IDEAL_CANDLES = self.data_days * 1440  # e.g., 180 days × 1440 = 259,200
                MIN_CANDLES_REQUIRED = int(IDEAL_CANDLES * MIN_PERCENTAGE_REQUIRED)  # e.g., 233,280 for 90% of 180 days
                
                if len(df) > 0:
                    days_available = len(df) // 1440
                    percentage_available = (len(df) / IDEAL_CANDLES) * 100
                    log(f"📊 Database: {len(df):,} candles ({days_available} days = {percentage_available:.1f}% of {self.data_days} days)", "INFO")
                    
                    # Use database data ONLY if we have at least 90% of requested days
                    if len(df) >= MIN_CANDLES_REQUIRED:
                        log(f"✅ Using database data for PPO training: {len(df):,} candles ({days_available}/{self.data_days} days)", "SUCCESS")
                        
                        if len(df) < IDEAL_CANDLES:
                            missing_days = self.data_days - days_available
                            log(f"ℹ️ Dataset has {days_available}/{self.data_days} days ({percentage_available:.1f}%). Missing {missing_days} days.", "INFO")
                        
                        return df
                    else:
                        log(f"⚠️ Database data insufficient: {len(df):,} candles ({days_available} days = {percentage_available:.1f}%)", "WARNING")
                        log(f"   Required: {MIN_CANDLES_REQUIRED:,} candles ({int(MIN_CANDLES_REQUIRED/1440)} days minimum = {MIN_PERCENTAGE_REQUIRED*100:.0f}%)", "WARNING")
                        log(f"   Attempting API fetch to get full {self.data_days} days...", "INFO")
                else:
                    log(f"⚠️ No data in database for {self.ticker}, fetching from API...", "WARNING")
        except Exception as e:
            log(f"⚠️ Error loading from database: {e}, falling back to API fetch", "WARNING")
        
        # STEP 2: Fallback to DUAL-EXCHANGE API fetch if database doesn't have enough data
        log(f"📥 Fetching from API: {self.data_days} days ({self.data_months} months) of 1-min candles...", "INFO")
        log(f"⏳ Using DUAL-EXCHANGE strategy (Binance for historical + MEXC for current data)", "INFO")
        log(f"⏳ This may take several minutes due to rate limits. Please wait...", "WARNING")
        
        # Use the new dual-exchange fetching method
        df = self.data_provider.fetch_dual_exchange_history(
            ticker=self.ticker,
            timeframe='1m',
            target_days=self.data_days,
            limit=1000,
            callback=None  # No callback needed, logging is handled internally
        )
        
        if df is not None and len(df) > 0:
            days_received = len(df) // 1440
            percentage_received = (days_received / self.data_days) * 100
            
            log(f"{'='*80}", "INFO")
            log(f"✅ DUAL-EXCHANGE FETCH COMPLETE", "SUCCESS")
            log(f"{'='*80}", "INFO")
            log(f"📊 Downloaded: {len(df):,} candles ({days_received} days)", "SUCCESS")
            log(f"📊 Requested: {self.data_days * 1440:,} candles ({self.data_days} days)", "INFO")
            log(f"📊 Progress: {percentage_received:.1f}% of target", "SUCCESS" if percentage_received >= 90 else "WARNING")
            log(f"📅 Date range: {df.index[0]} to {df.index[-1]}", "INFO")
            
            if percentage_received < 90:
                missing_days = self.data_days - days_received
                log(f"⚠️ WARNING: Only {days_received}/{self.data_days} days available (missing {missing_days} days)", "WARNING")
                log(f"💡 TIP: System may have hit API rate limits. Available data will be used.", "INFO")
            
            log(f"{'='*80}", "INFO")
        
        if df is None or len(df) == 0:
            log(f"❌ Failed to fetch data for {self.ticker}", "ERROR")
            log(f"💡 Possible causes:", "ERROR")
            log(f"   1. API rate limit exceeded", "ERROR")
            log(f"   2. Invalid ticker symbol", "ERROR")
            log(f"   3. Network connectivity issues", "ERROR")
            log(f"   4. Exchange API is down", "ERROR")
            return None
        
        return df
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generuje technical indicators dla danych.
        
        Args:
            df: Raw OHLCV DataFrame
            
        Returns:
            DataFrame with added features
        """
        log(f"🔧 Engineering features...", "INFO")
        
        df = df.copy()
        
        # ═══════════════════════════════════════════════════════════════════
        # TECHNICAL INDICATORS (identyczne jak w process_trainer.py)
        # ═══════════════════════════════════════════════════════════════════
        
        # Basic indicators
        df['rsi'] = ta.rsi(df['close'], length=14)
        macd = ta.macd(df['close'])
        if macd is not None:
            df = df.join(macd)
        
        # Market correlation (simplified for training - można rozszerzyć)
        df['market_correlation'] = 0.75  # Placeholder
        df['bulls_bears_ratio'] = 0.5
        df['market_strength'] = 50.0
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_sma_ratio'] = df['volume'] / df['volume_sma']
        df['obv'] = ta.obv(df['close'], df['volume'])
        df['obv_sma'] = df['obv'].rolling(20).mean()
        df['obv_ratio'] = df['obv'] / df['obv_sma']
        df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14)
        
        # Volatility indicators
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['atr_pct'] = (df['atr'] / df['close']) * 100
        
        bbands = ta.bbands(df['close'], length=20)
        if bbands is not None and 'BBU_20_2.0' in bbands.columns:
            df['bb_width'] = (bbands['BBU_20_2.0'] - bbands['BBL_20_2.0']) / bbands['BBM_20_2.0']
        else:
            df['bb_width'] = 0.04
        
        # Momentum indicators
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
        df['funding_rate'] = 0.0001  # Placeholder
        df['funding_rate_trend'] = 0.0
        
        # --- MACRO CONTEXT FEATURES (MICRO/MACRO STRATEGY) ---
        # Trend 4h (240 minut)
        df['trend_4h_sma'] = df['close'].rolling(window=240, min_periods=1).mean()
        df['dist_4h'] = (df['close'] - df['trend_4h_sma']) / df['trend_4h_sma']
        df['dist_4h'].fillna(0, inplace=True)
        
        # Trend 24h (1440 minut)
        df['trend_daily_sma'] = df['close'].rolling(window=1440, min_periods=1).mean()
        df['dist_daily'] = (df['close'] - df['trend_daily_sma']) / df['trend_daily_sma']
        df['dist_daily'].fillna(0, inplace=True)
        
        # Volatility 24h
        df['volatility_24h'] = df['close'].rolling(window=1440, min_periods=1).std() / df['close']
        df['volatility_24h'].fillna(0, inplace=True)
        
        # Additional features for RL
        df['price_change_pct'] = df['close'].pct_change() * 100
        df['volatility'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
        
        # Drop NaN
        df.dropna(inplace=True)
        
        log(f"✅ Features engineered: {len(df)} rows, {len(df.columns)} columns", "SUCCESS")
        
        return df
    
    def train_lstm_model(self, df: pd.DataFrame) -> tuple:
        """
        Trenuje model LSTM/Ensemble do generowania predictions.
        
        Args:
            df: DataFrame with features
            
        Returns:
            (predictions, confidences): LSTM outputs
        """
        log(f"🤖 Training LSTM Ensemble model...", "INFO")
        
        # Feature columns (same as process_trainer.py + macro context)
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
        
        # ═══════════════════════════════════════════════════════════════════
        # TARGET: 30-MINUTE LOOKAHEAD (Micro-Input / Macro-Output)
        # ═══════════════════════════════════════════════════════════════════
        # BYŁO (źle): Przewidywało następną 1 minutę
        # JEST (Złoty Graal): Przewiduje 30 minut do przodu!
        
        log(f"📊 Creating target: {self.prediction_lookahead}-minute lookahead", "INFO")
        
        df['target_price_30m'] = df['close'].shift(-self.prediction_lookahead)
        df['target'] = (df['target_price_30m'] > df['close']).astype(int)
        df.dropna(inplace=True)
        
        log(f"✅ Training samples after {self.prediction_lookahead}-min lookahead: {len(df)}", "INFO")
        
        # Split features and target
        X = df[feature_cols].values
        y = df['target'].values
        
        # Train/test split (80/20)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # Train model
        model = EnsembleModel(use_advanced=True)
        model.fit(X_train, y_train)
        
        # Generate predictions for full dataset
        predictions = model.predict_proba(X)[:, 1]  # Probability of UP
        
        # Confidence = distance from 0.5
        confidences = np.abs(predictions - 0.5) * 2  # Scale to 0-1
        
        # Log prediction stats
        avg_pred = np.mean(predictions)
        avg_conf = np.mean(confidences)
        log(f"📊 Ensemble Predictions: Mean={avg_pred:.4f}, Avg Confidence={avg_conf:.4f}", "INFO")
        
        # Save model
        model.save_custom(str(self.lstm_model_path))
        
        # Evaluate
        test_preds = model.predict_proba(X_test)[:, 1]
        test_acc = np.mean((test_preds > 0.5) == y_test)
        
        log(f"✅ LSTM Model trained! Test Accuracy: {test_acc * 100:.2f}%", "SUCCESS")
        
        return predictions, confidences
    
    def train_rl_agent(
        self,
        df: pd.DataFrame,
        lstm_predictions: np.ndarray,
        lstm_confidences: np.ndarray,
        total_timesteps: int = 100000,
        resume_from_checkpoint: str = None,
        checkpoint_interval: int = 10000,
        max_episode_steps: int = None
    ) -> PPOTradingAgent:
        """
        Trenuje PPO Agent na danych (z opcją resume).
        
        Args:
            df: DataFrame with features
            lstm_predictions: LSTM predictions
            lstm_confidences: LSTM confidences
            total_timesteps: Number of training steps
            resume_from_checkpoint: Path to checkpoint to resume from (optional)
            checkpoint_interval: Save checkpoint every N steps (default: 10000)
            max_episode_steps: Max steps per episode (optional)
            
        Returns:
            Trained PPOTradingAgent
        """
        log(f"🧠 Creating Trading Environment...", "INFO")
        
        # Create environment
        env = TradingEnv(
            df=df,
            initial_balance=self.initial_balance,
            leverage=self.leverage,
            lstm_predictions=pd.Series(lstm_predictions, index=df.index),
            lstm_confidences=pd.Series(lstm_confidences, index=df.index),
            max_episode_steps=max_episode_steps
        )
        
        # Create or load agent
        if resume_from_checkpoint:
            log(f"🔄 Resuming training from checkpoint: {resume_from_checkpoint}", "INFO")
            try:
                # Load checkpoint
                from stable_baselines3 import PPO
                model = PPO.load(resume_from_checkpoint, env=env)
                
                # Create agent wrapper
                agent = PPOTradingAgent(
                    env=env,
                    model_path=str(self.rl_model_path),
                    tensorboard_log="./logs/tensorboard/"
                )
                agent.model = model  # Replace with loaded checkpoint
                
                # Load checkpoint metadata to get timesteps
                import json
                metadata_path = resume_from_checkpoint + '_metadata.json'
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        completed_timesteps = metadata.get('timesteps', 0)
                        log(f"✅ Checkpoint loaded: {completed_timesteps} steps completed", "SUCCESS")
                        log(f"📊 Win Rate: {metadata.get('win_rate', 0):.1f}%, Episodes: {metadata.get('episodes', 0)}", "INFO")
                        
                        # Calculate remaining timesteps
                        remaining_timesteps = total_timesteps - completed_timesteps
                        if remaining_timesteps <= 0:
                            log(f"⚠️ Checkpoint already completed target timesteps! Using full target.", "WARNING")
                            remaining_timesteps = total_timesteps
                        
                        total_timesteps = remaining_timesteps
                        log(f"🎯 Remaining training: {remaining_timesteps} steps", "INFO")
                
            except Exception as e:
                log(f"❌ Failed to load checkpoint: {e}. Starting fresh training.", "ERROR")
                resume_from_checkpoint = None
        
        if not resume_from_checkpoint:
            # Create fresh agent
            agent = PPOTradingAgent(
                env=env,
                model_path=str(self.rl_model_path),
                tensorboard_log="./logs/tensorboard/"
            )
        
        # Train with callback (with detailed PPO logging + checkpoints)
        callback = TradingCallback(
            total_timesteps=total_timesteps,
            checkpoint_interval=checkpoint_interval
        )
        
        log(f"🚀 Starting PPO Training for {total_timesteps} timesteps...", "INFO")
        log(f"   This may take several hours. Monitor progress in:", "INFO")
        log(f"   - PPO.log file: ./logs/PPO.log", "INFO")
        log(f"   - Checkpoints: ./models/checkpoints/ (every {checkpoint_interval} steps)", "INFO")
        log(f"   - TensorBoard: tensorboard --logdir=./logs/tensorboard/", "INFO")
        
        agent.train(total_timesteps=total_timesteps, callback=callback)
        
        # Save model
        agent.save()
        
        log(f"✅ RL Agent training complete!", "SUCCESS")
        
        return agent
    
    def validate_agent(
        self,
        agent: PPOTradingAgent,
        val_df: pd.DataFrame,
        lstm_predictions: np.ndarray,
        lstm_confidences: np.ndarray
    ) -> dict:
        """
        Przeprowadza walidację agenta na nowych danych.
        
        Args:
            agent: Trained agent
            val_df: Validation DataFrame
            lstm_predictions: LSTM predictions for val_df
            lstm_confidences: LSTM confidences
            
        Returns:
            Validation results dict
        """
        log(f"🔬 Validating agent on {len(val_df)} candles...", "INFO")
        
        results = backtest_agent(
            agent=agent,
            test_df=val_df,
            lstm_predictions=pd.Series(lstm_predictions, index=val_df.index),
            lstm_confidences=pd.Series(lstm_confidences, index=val_df.index),
            initial_balance=self.initial_balance,
            render=False
        )
        
        return results
    
    def run_full_training_pipeline(
        self,
        total_timesteps: int = 100000,
        validate: bool = True,
        max_retries: int = 10,
        retry_delay: int = 5
    ):
        """
        Przeprowadza pełny pipeline treningu RL agenta z OOM retry mechanism.
        
        Args:
            total_timesteps: Number of PPO training steps
            validate: Whether to run validation after training
            max_retries: Maximum number of retries on OOM (default: 10)
            retry_delay: Delay in seconds between retries (default: 5s)
        """
        log(f"{'='*80}", "INFO")
        log(f"🚀 STARTING RL AGENT TRAINING PIPELINE (with OOM protection)", "SUCCESS")
        log(f"{'='*80}", "INFO")
        
        # ═══════════════════════════════════════════════════════════════════════
        # NOWA HIERARCHIA PRIORYTETÓW: Sprawdź czy LSTM się nie trenuje
        # ═══════════════════════════════════════════════════════════════════════
        if self.lstm_lockfile.exists():
            log(f"⏸️ BLOKADA: LSTM Ensemble v3.4 training in progress (Priority 2 > 3)", "WARNING")
            log(f"   PPO Agent training postponed. LSTM must complete first.", "WARNING")
            log(f"   Waiting for LSTM to finish... (checking every 60s)", "INFO")
            
            # Wait for LSTM to complete (check every 60 seconds)
            import time
            waited_seconds = 0
            while self.lstm_lockfile.exists():
                time.sleep(60)
                waited_seconds += 60
                log(f"⏳ Still waiting for LSTM... ({waited_seconds//60} minutes elapsed)", "INFO")
                
                # Safety: Don't wait forever (max 2 hours)
                if waited_seconds > 7200:
                    log(f"⚠️ WARNING: LSTM training taking too long (>2h). Proceeding with PPO...", "WARNING")
                    break
            
            log(f"✅ LSTM training complete. Proceeding with PPO Agent training...", "SUCCESS")
        # ═══════════════════════════════════════════════════════════════════════
        
        # ═══════════════════════════════════════════════════════════════════════
        # OOM RETRY WRAPPER
        # ═══════════════════════════════════════════════════════════════════════
        import gc
        import time
        
        for attempt in range(1, max_retries + 1):
            try:
                log(f"🔄 Training attempt {attempt}/{max_retries}...", "INFO")
                
                # Clear any leftover memory before attempt
                gc.collect()
                
                # Run actual training
                result = self._run_training_attempt(total_timesteps, validate)
                
                # Success! Exit retry loop
                log(f"✅ Training completed successfully on attempt {attempt}", "SUCCESS")
                return result
                
            except MemoryError as e:
                log(f"💥 OOM (Out of Memory) on attempt {attempt}/{max_retries}: {e}", "ERROR")
                
                if attempt < max_retries:
                    log(f"⏳ Retrying in {retry_delay} seconds (memory cleanup)...", "WARNING")
                    
                    # Aggressive memory cleanup
                    gc.collect()
                    
                    # Try to free TensorFlow/PyTorch cache
                    try:
                        import tensorflow as tf
                        tf.keras.backend.clear_session()
                        log(f"🧹 TensorFlow session cleared", "INFO")
                    except Exception:
                        pass
                    
                    try:
                        import torch
                        torch.cuda.empty_cache()
                        log(f"🧹 PyTorch GPU cache cleared", "INFO")
                    except Exception:
                        pass
                    
                    time.sleep(retry_delay)
                else:
                    log(f"❌ FAILED: Exhausted all {max_retries} retries. Training aborted.", "ERROR")
                    self.model_monitor.update_error("rl_agent", f"OOM after {max_retries} attempts")
                    raise
                    
            except Exception as e:
                # Other exceptions (not OOM) - don't retry
                log(f"❌ CRITICAL ERROR (non-OOM): {e}", "ERROR")
                import traceback
                log(f"Traceback: {traceback.format_exc()}", "ERROR")
                self.model_monitor.update_error("rl_agent", str(e)[:100])
                raise
        
        log(f"❌ Training failed after {max_retries} attempts", "ERROR")
        return None
    
    def _run_training_attempt(
        self,
        total_timesteps: int,
        validate: bool
    ):
        """
        Single training attempt (extracted for retry wrapper).
        
        Args:
            total_timesteps: Number of PPO training steps
            validate: Whether to run validation after training
            
        Returns:
            Tuple (agent, validation_results) or None
        """
        log(f"{'='*80}", "INFO")
        log(f"🧠 TRAINING ATTEMPT START", "INFO")
        log(f"{'='*80}", "INFO")
        
        # ═══════════════════════════════════════════════════════════════════
        # MEMORY CHECK (before starting training)
        # ═══════════════════════════════════════════════════════════════════
        available_gb, is_sufficient, mem_message = check_memory_available(min_gb_required=10.0)
        log(mem_message, "INFO" if is_sufficient else "WARNING")
        
        if not is_sufficient:
            log(f"⚠️ WARNING: Low memory detected. Training may fail with OOM.", "WARNING")
            log(f"💡 TIP: Close other applications or reduce lookback_days in config.json", "INFO")
        
        # Mark training start in AI Control Center (only on first attempt)
        self.model_monitor.update_start("rl_agent", "Inicjalizacja treningu RL Agent...")
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Fetch Data
        # ═══════════════════════════════════════════════════════════════════
        self.model_monitor.update_progress("rl_agent", 5, f"Pobieranie {self.data_days} dni ({self.data_months} miesięcy) danych...")
        df = self.fetch_training_data()
        if df is None:
            log(f"❌ Data fetch failed. Aborting.", "ERROR")
            self.model_monitor.update_error("rl_agent", "Błąd pobierania danych")
            return None
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Engineer Features
        # ═══════════════════════════════════════════════════════════════════
        self.model_monitor.update_progress("rl_agent", 15, "Feature Engineering (wskaźniki techniczne)...")
        df = self.engineer_features(df)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: Split Data (80% train, 20% validation)
        # ═══════════════════════════════════════════════════════════════════
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx].copy()
        val_df = df.iloc[split_idx:].copy()
        
        log(f"📊 Data split: {len(train_df)} train, {len(val_df)} validation", "INFO")
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: Train LSTM Model
        # ═══════════════════════════════════════════════════════════════════
        self.model_monitor.update_progress("rl_agent", 25, "Trenowanie wewnętrznego modelu LSTM...")
        predictions, confidences = self.train_lstm_model(train_df)
        
        # Generate predictions for validation set
        # Load entire ensemble model from disk (RF, XGBoost, LightGBM, Meta)
        import joblib
        model = joblib.load(str(self.lstm_model_path))
        model.rehydrate(str(self.lstm_model_path))  # Rehydrate LSTM part
        
        val_features = val_df[[
            'rsi', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
            'market_correlation', 'bulls_bears_ratio', 'market_strength',
            'volume_sma_ratio', 'obv_ratio', 'mfi',
            'atr_pct', 'bb_width',
            'roc', 'stoch_k', 'stoch_d',
            'funding_rate', 'funding_rate_trend',
            'dist_4h', 'dist_daily', 'volatility_24h',
            'price_change_pct', 'volatility'
        ]].values
        
        val_predictions = model.predict_proba(val_features)[:, 1]
        val_confidences = np.abs(val_predictions - 0.5) * 2
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: Train RL Agent (with optional resume from checkpoint)
        # ═══════════════════════════════════════════════════════════════════
        
        # Check for latest checkpoint if auto-resume is needed
        resume_checkpoint = None
        if hasattr(self, 'auto_resume') and self.auto_resume:
            resume_checkpoint = self._find_latest_checkpoint()
            if resume_checkpoint:
                log(f"🔄 AUTO-RESUME: Found checkpoint {resume_checkpoint}", "INFO")
        
        self.model_monitor.update_progress("rl_agent", 40, f"Trenowanie PPO Agent ({total_timesteps} steps)...")
        
        # CRITICAL FIX: max_episode_steps MUST be set to reasonable value for PPO
        # PPO uses n_steps=2048 for rollouts. Episodes must complete to calculate rewards!
        # 
        # Previous issues:
        # - None = episodes NEVER complete (dataset is 259,200 candles!) ❌
        # - 1440 = too short (1 day), not enough learning ❌
        # 
        # OPTIMAL: 8192 steps (5.7 days of 1-min data) ✅
        # - Long enough to capture multi-day patterns
        # - Short enough to complete multiple episodes per training run
        # - Allows PPO to properly calculate episode rewards and convergence
        episode_steps = 8192  # 5.7 days (optimal balance for PPO)
        
        if episode_steps:
            log(f"🎯 Episode Length: {episode_steps} steps ({episode_steps/1440:.1f} days)", "INFO")
        else:
            log(f"🎯 Episode Length: Full dataset ({len(train_df)} steps = {len(train_df)/1440:.1f} days)", "INFO")
        
        agent = self.train_rl_agent(
            df=train_df,
            lstm_predictions=predictions,
            lstm_confidences=confidences,
            total_timesteps=total_timesteps,
            resume_from_checkpoint=resume_checkpoint,
            checkpoint_interval=getattr(self, 'checkpoint_interval', 10000),
            max_episode_steps=episode_steps  # FIXED: Use None or 4096+ steps
        )
        
        self.model_monitor.update_progress("rl_agent", 80, "Agent wytrenowany, uruchamiam walidację...")
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 6: Validate (Optional)
        # ═══════════════════════════════════════════════════════════════════
        val_results = None
        if validate:
            self.model_monitor.update_progress("rl_agent", 85, "Walidacja na danych testowych...")
            val_results = self.validate_agent(
                agent=agent,
                val_df=val_df,
                lstm_predictions=val_predictions,
                lstm_confidences=val_confidences
            )
            
            # Save results
            results_data = {
                'timestamp': datetime.now().isoformat(),
                'ticker': self.ticker,
                'data_days': self.data_days,
                'data_months': self.data_months,
                'total_timesteps': total_timesteps,
                'train_candles': len(train_df),
                'val_candles': len(val_df),
                'validation_results': val_results
            }
            
            with open(self.results_path, 'w') as f:
                json.dump(results_data, f, indent=2)
            
            log(f"💾 Results saved to {self.results_path}", "SUCCESS")
        
        # ═══════════════════════════════════════════════════════════════════
        # DONE - Mark as complete in AI Control Center
        # ═══════════════════════════════════════════════════════════════════
        
        # Calculate accuracy metric (from win rate if available)
        accuracy = 0.5  # Default
        if validate and val_results:
            # Use win rate as proxy for accuracy
            accuracy = val_results.get('win_rate', 50) / 100.0
        
        self.model_monitor.update_finish("rl_agent", accuracy, data_days=self.data_days)
        
        log(f"{'='*80}", "INFO")
        log(f"✅ RL AGENT TRAINING PIPELINE COMPLETE!", "SUCCESS")
        log(f"{'='*80}", "INFO")
        log(f"📂 Model saved to: {self.rl_model_path}", "INFO")
        if validate and val_results:
            log(f"📊 Validation Results:", "INFO")
            log(f"   - Final Balance: ${val_results['final_balance']:.2f}", "INFO")
            log(f"   - Total Return: {val_results['total_return_pct']:+.2f}%", "SUCCESS" if val_results['total_return_pct'] > 0 else "ERROR")
            log(f"   - Win Rate: {val_results['win_rate']:.1f}%", "INFO")
            log(f"   - Total Trades: {val_results['total_trades']}", "INFO")
            log(f"   - Max Drawdown: {val_results['max_drawdown_pct']:.2f}%", "WARNING")
        log(f"{'='*80}", "INFO")
        log(f"✅ AI Control Center: RL Agent training finished (Accuracy: {accuracy:.1%})", "SUCCESS")
        
        return (agent, val_results if validate else None)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Train RL Trading Agent with PPO')
    
    parser.add_argument(
        '--timesteps',
        type=int,
        default=100000,
        help='Number of training timesteps (default: 100000)'
    )
    
    parser.add_argument(
        '--balance',
        type=float,
        default=1000.0,
        help='Initial balance in USDT (default: 1000)'
    )
    
    parser.add_argument(
        '--leverage',
        type=int,
        default=20,
        help='Leverage multiplier (default: 20)'
    )
    
    parser.add_argument(
        '--data-days',
        type=int,
        default=180,
        help='Number of days of data to fetch (default: 180 = 6 months)'
    )
    
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip validation after training'
    )
    
    parser.add_argument(
        '--ticker',
        type=str,
        default='BTC/USDT',
        help='Trading pair (default: BTC/USDT for MEXC Futures)'
    )
    
    parser.add_argument(
        '--exchange',
        type=str,
        default='mexc',
        help='Exchange ID (default: mexc)'
    )
    
    parser.add_argument(
        '--resume',
        type=str,
        default=None,
        help='Resume training from checkpoint (e.g., ppo_checkpoint_10000)'
    )
    
    parser.add_argument(
        '--checkpoint-interval',
        type=int,
        default=10000,
        help='Save checkpoint every N steps (default: 10000)'
    )
    
    args = parser.parse_args()
    
    try:
        # Create trainer
        trainer = RLTrainer(
            ticker=args.ticker,
            exchange_id=args.exchange,
            initial_balance=args.balance,
            leverage=args.leverage,
            data_days=args.data_days
        )
        
        # Set checkpoint and resume settings
        trainer.checkpoint_interval = args.checkpoint_interval
        
        # If resume is specified, enable auto-resume and set checkpoint path
        if args.resume:
            trainer.auto_resume = True
            # Validate checkpoint exists
            checkpoint_path = args.resume
            
            # Smart path handling
            # 1. Check if path is absolute or relative to cwd
            if os.path.exists(checkpoint_path + '.zip'):
                pass  # Path is correct as is (minus extension)
            elif os.path.exists(checkpoint_path):
                pass  # Path is correct (maybe has extension or is just base)
            # 2. Check in models/checkpoints if not found
            elif not checkpoint_path.startswith('/') and not checkpoint_path.startswith('./'):
                 checkpoint_path = f"./models/checkpoints/{checkpoint_path}"
            
            # Strip extension if present for internal logic, but check file existence with it
            if checkpoint_path.endswith('.zip'):
                checkpoint_path = checkpoint_path[:-4]
                
            if not os.path.exists(checkpoint_path + '.zip'):
                log(f"❌ Checkpoint not found: {checkpoint_path}.zip", "ERROR")
                log(f"💡 Available checkpoints:", "INFO")
                import glob
                checkpoints = glob.glob("./models/checkpoints/ppo_checkpoint_*.zip")
                if checkpoints:
                    for cp in sorted(checkpoints):
                        log(f"   - {os.path.basename(cp)}", "INFO")
                else:
                    log(f"   No checkpoints found in ./models/checkpoints/", "WARNING")
                sys.exit(1)
            
            log(f"🔄 Resume mode enabled: Will load from {checkpoint_path}", "INFO")
        
        # Run training
        trainer.run_full_training_pipeline(
            total_timesteps=args.timesteps,
            validate=not args.no_validate
        )
    except Exception as e:
        log(f"🔥 CRITICAL FAILURE: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        
        # Update AI Control Center (Emergency reporting)
        try:
            from src.utils.model_monitor import ModelMonitor
            monitor = ModelMonitor()
            monitor.update_error("rl_agent", f"CRITICAL: {str(e)}")
        except Exception as inner_e:
            log(f"Failed to report error to monitor: {inner_e}", "ERROR")
            
        sys.exit(1)


if __name__ == "__main__":
    main()
