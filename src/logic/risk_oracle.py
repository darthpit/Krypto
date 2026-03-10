import time
import json
import logging
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta

from src.utils.logger import log

class RiskOracle:
    """
    Safety Valve Logic (Risk Oracle).
    Provides VETO power over trading decisions based on:
    1. Max Drawdown Limits (MDL)
    2. Volatility Filters (VF)
    3. Time-Window Validation (TWV)
    4. Forced Hold Periods (FHP)
    """

    def __init__(self, db, data_provider):
        self.db = db
        self.data_provider = data_provider
        self.config = self._load_config()

        # State Cache
        self.peak_balance = 0.0
        self.current_risk_level = "NORMAL"
        self.recovery_mode = False
        self.active_constraints = {}

        # Initialize Risk State
        self._initialize_state()

    def _load_config(self):
        """Loads risk configuration or sets defaults."""
        defaults = {
            "max_drawdown": {
                "daily": 0.05,
                "weekly": 0.12,
                "monthly": 0.20,
                "peak": 0.15
            },
            "forced_hold": {
                "scalp": 5,   # minutes
                "swing": 15,
                "position": 60
            },
            "volatility_multiplier": 3.0,
            "weights": {
                "1m": 10,
                "5m": 15,
                "15m": 20,
                "1h": 30,
                "4h": 25
            }
        }
        try:
            with open('config.json', 'r') as f:
                user_config = json.load(f)
                if 'risk_management' in user_config:
                    # Merge defaults with user config (simple depth-1 merge)
                    for k, v in user_config['risk_management'].items():
                        if isinstance(v, dict) and k in defaults:
                            defaults[k].update(v)
                        else:
                            defaults[k] = v
        except Exception:
            pass
        return defaults

    def _initialize_state(self):
        """Restores state from DB."""
        try:
            # Get latest risk record
            query = "SELECT peak_balance, risk_level, recovery_mode, active_constraints FROM risk_monitoring ORDER BY id DESC LIMIT 1"
            rows = self.db.query(query)
            if rows:
                self.peak_balance = rows[0][0]
                self.current_risk_level = rows[0][1]
                self.recovery_mode = bool(rows[0][2])
                try:
                    self.active_constraints = json.loads(rows[0][3])
                except:
                    self.active_constraints = {}
            else:
                self.peak_balance = 0.0
        except Exception as e:
            log(f"RiskOracle Init Error: {e}", "ERROR")

    # ==========================================
    # 2.1 Max Drawdown Limiter (MDL)
    # ==========================================
    def update_risk_metrics(self, current_total_balance):
        """
        Called every loop to update global risk metrics.
        Returns: Dict with status (NORMAL/HALT) and reason.
        """
        try:
            now = time.time()

            # 1. Update Peak
            if current_total_balance > self.peak_balance:
                self.peak_balance = current_total_balance

            # 2. Calculate Drawdowns
            peak_dd = (self.peak_balance - current_total_balance) / self.peak_balance if self.peak_balance > 0 else 0

            # Fetch historical balances for time-based DD
            # We assume wallet_balances stores snapshots or we use trades history to reconstruct?
            # For simplicity, we track 'risk_monitoring' snapshots.

            # Daily (24h ago)
            daily_dd = self._calculate_time_drawdown(current_total_balance, 86400)
            weekly_dd = self._calculate_time_drawdown(current_total_balance, 86400 * 7)
            monthly_dd = self._calculate_time_drawdown(current_total_balance, 86400 * 30)

            # 3. Check Limits
            limits = self.config['max_drawdown']
            new_status = "NORMAL"
            constraints = {}

            if peak_dd > limits['peak']:
                new_status = "HALT"
                constraints = {"reason": "PEAK_DD_BREACH", "until": now + 86400} # 24h
            elif monthly_dd > limits['monthly']:
                new_status = "HALT"
                constraints = {"reason": "MONTHLY_DD_BREACH", "until": now + (86400 * 7)} # 7 days
            elif weekly_dd > limits['weekly']:
                new_status = "HALT"
                constraints = {"reason": "WEEKLY_DD_BREACH", "until": now + 86400}
            elif daily_dd > limits['daily']:
                # Soft Stop
                new_status = "WARNING"
                constraints = {"reason": "DAILY_DD_BREACH", "until": now + (3600 * 6)} # 6 hours

            # 4. Handle Recovery Mode Logic
            if self.current_risk_level in ["HALT", "WARNING"] and new_status == "NORMAL":
                self.recovery_mode = True # Enter recovery
                log("RiskOracle: Entering RECOVERY MODE.", "WARNING")

            # If in recovery, check if we can exit (5 profitable trades?) -> impl simplified: manual or time based?
            # For now, stay in recovery until next restart or manual reset.

            self.current_risk_level = new_status
            self.active_constraints = constraints

            # 5. Persist
            query = """
                INSERT INTO risk_monitoring
                (timestamp, current_balance, peak_balance, drawdown_daily, drawdown_weekly, drawdown_monthly, peak_drawdown, volatility_index, risk_level, recovery_mode, active_constraints)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.db.execute(query, (
                int(now), current_total_balance, self.peak_balance,
                daily_dd, weekly_dd, monthly_dd, peak_dd,
                0.0, # Volatility Index placeholder
                new_status, 1 if self.recovery_mode else 0, json.dumps(constraints)
            ))

            return {"status": new_status, "constraints": constraints}

        except Exception as e:
            log(f"MDL Update Error: {e}", "ERROR")
            return {"status": "ERROR", "reason": str(e)}

    def _calculate_time_drawdown(self, current_balance, seconds_ago):
        try:
            t_target = time.time() - seconds_ago
            # Get the highest balance in that window
            query = "SELECT MAX(current_balance) FROM risk_monitoring WHERE timestamp >= ?"
            rows = self.db.query(query, (int(t_target),))
            if rows and rows[0][0]:
                high_water_mark = rows[0][0]
                return (high_water_mark - current_balance) / high_water_mark
            return 0.0
        except:
            return 0.0

    # ==========================================
    # 2.2 Volatility Filter (VF)
    # ==========================================
    def check_volatility(self, ticker, df):
        """
        Checks for abnormal volatility.
        Returns: (is_safe: bool, multiplier: float)
        """
        try:
            if df is None or df.empty:
                return True, 1.0

            # 1. ATR Spike
            if 'atr' not in df.columns:
                return True, 1.0

            current_atr = df['atr'].iloc[-1]

            # Ensure we have enough data
            if len(df) < 55:
                avg_atr = df['atr'].mean()
            else:
                avg_atr = df['atr'].rolling(50).mean().iloc[-1]

            spike_detected = False
            if avg_atr > 0 and current_atr > (avg_atr * self.config['volatility_multiplier']):
                spike_detected = True
                # log(f"[{ticker}] Volatility Spike: ATR {current_atr:.2f} > {self.config['volatility_multiplier']}x Avg", "WARNING")

            # 2. Rapid Price Movement (10% in 5 min?)
            # Assuming 1m candles, last 5
            closes = df['close'].tail(5)
            max_p = closes.max()
            min_p = closes.min()
            change_pct = (max_p - min_p) / min_p

            rapid_move = False
            if change_pct > 0.10:
                rapid_move = True
                # log(f"[{ticker}] Rapid Price Move: {change_pct*100:.1f}% in 5m", "WARNING")

            # 3. Volume Anomaly
            current_vol = df['volume'].iloc[-1]
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]

            vol_anomaly = False
            if avg_vol > 0 and current_vol > (avg_vol * 5):
                vol_anomaly = True
                # log(f"[{ticker}] Volume Anomaly: {current_vol:.0f} vs Avg {avg_vol:.0f}", "WARNING")

            warnings = sum([spike_detected, rapid_move, vol_anomaly])

            if warnings >= 2:
                return False, 0.0 # HALT
            elif warnings == 1:
                return True, 0.5 # Half Size

            return True, 1.0

        except Exception as e:
            log(f"VF Check Error: {e}", "ERROR")
            return True, 1.0

    # ==========================================
    # 2.3 Time-Window Validation (TWV)
    # ==========================================
    def validate_timeframes(self, ticker, signal_direction="BUY"):
        """
        Checks trend alignment across timeframes.
        Returns: Score (0-100)
        """
        try:
            # We already have 15m/1m likely in TraderProcess, but to be pure, we fetch what we need.
            # Optimization: 1m is highly volatile, 1h and 4h are key.
            # We define:
            # BULLISH: Price > SMA20 > SMA50
            # BEARISH: Price < SMA20 < SMA50
            # NEUTRAL: Else

            score = 0
            total_weight = 0

            # Map timeframes to weights
            tfs = {
                '1m': self.config['weights']['1m'],
                '5m': self.config['weights']['5m'],
                '15m': self.config['weights']['15m'],
                '1h': self.config['weights']['1h'],
                '4h': self.config['weights']['4h']
            }

            for tf, weight in tfs.items():
                # Fetch small limit for SMA calculation
                limit = 55
                # Use data provider to fetch
                df = self.data_provider.fetch_candles(ticker, timeframe=tf, limit=limit)

                trend = "NEUTRAL"
                if df is not None and not df.empty:
                    df['sma20'] = ta.sma(df['close'], length=20)
                    df['sma50'] = ta.sma(df['close'], length=50)

                    last = df.iloc[-1]
                    price = last['close']
                    sma20 = last['sma20']
                    sma50 = last['sma50']

                    if sma20 and sma50:
                        if price > sma20 and sma20 > sma50:
                            trend = "BULLISH"
                        elif price < sma20 and sma20 < sma50:
                            trend = "BEARISH"

                # Scoring
                if signal_direction == "BUY":
                    if trend == "BULLISH":
                        score += weight
                    elif trend == "NEUTRAL":
                        score += (weight / 2)
                    # BEARISH adds 0

                total_weight += weight

            # Normalize to 100
            final_score = (score / total_weight) * 100 if total_weight > 0 else 0
            return final_score

        except Exception as e:
            # log(f"TWV Error for {ticker}: {e}", "ERROR")
            return 50.0 # Neutral fallback

    # ==========================================
    # 2.4 Forced Hold Period (FHP)
    # ==========================================
    def can_exit_trade(self, ticker, reason="SIGNAL"):
        """
        Determines if a trade can be closed based on hold time.
        """
        try:
            # Exceptions
            if reason in ["STOP_LOSS", "LIQUIDATION", "FORCED_LIQ"]:
                return True, "Emergency Override"

            # Check open trade
            query = "SELECT timestamp, strategy FROM trades WHERE ticker = ? AND action = 'BUY' ORDER BY id DESC LIMIT 1"
            # Note: This assumes we haven't sold it yet.
            # Real implementation needs to track 'open positions' better or rely on wallet logic.
            # Assuming 'trades' logs are history.
            # Better check: active_strategies or memory?
            # Let's rely on checking the LAST BUY timestamp.

            rows = self.db.query(query, (ticker,))
            if not rows:
                return True, "No active trade record"

            entry_ts_str = rows[0][0]
            strategy = rows[0][1]

            # Parse timestamp (DB stores as string usually in trades table based on process_trader)
            # Actually process_trader does insert ... VALUES (..., datetime('now'), ...)
            # So it is a string YYYY-MM-DD HH:MM:SS

            try:
                entry_time = datetime.strptime(entry_ts_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Try ISO format if changed
                entry_time = datetime.fromisoformat(entry_ts_str)

            now = datetime.now()
            duration_min = (now - entry_time).total_seconds() / 60

            # Determine required hold
            required = self.config['forced_hold']['swing'] # Default
            if "SCALP" in str(strategy).upper():
                required = self.config['forced_hold']['scalp']
            elif "TREND" in str(strategy).upper():
                required = self.config['forced_hold']['position']

            if duration_min < required:
                return False, f"Hold Period Active ({int(duration_min)}/{required}m)"

            return True, "Hold Period Elapsed"

        except Exception as e:
            log(f"FHP Check Error: {e}", "ERROR")
            return True, "Error -> Safe Open"

    def is_recovery_mode(self):
        return self.recovery_mode
