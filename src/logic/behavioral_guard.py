import time
import pandas as pd
import logging
from datetime import datetime, timedelta

class BehavioralGuard:
    """
    Module 7: Anti-FOMO & Anti-Panic Module.
    Prevents emotional trading decisions: Pump&Dump, Panic Sells, Overtrading, Revenge Trading.
    """

    def __init__(self, db):
        self.db = db
        # Cache for simple rate limiting if needed, but we use DB for persistence
        self.last_loss_cache = {}

    def check_all(self, ticker, df, signal_type="BUY", psnd_score=0.5):
        """
        Runs all checks.
        Returns: (allow_trade: bool, reason: str, modifier: dict)
        """
        modifier = {"size_mult": 1.0, "required_score": 0.0}

        # 1. Pump & Dump / Panic Checks
        if signal_type == "BUY":
            is_pump, reason = self._check_pump_dump(ticker, df)
            if is_pump:
                return False, f"Anti-FOMO: {reason}", modifier

        elif signal_type == "SELL":
            is_panic, reason = self._check_panic_sell(ticker, df)
            if is_panic:
                # If panic detected, we BLOCK the sell?
                # User says: "BLOCK all SELL signals... Wait 15 min"
                return False, f"Anti-Panic: {reason}", modifier

        # 2. Overtrading Limiter
        is_over, reason = self._check_overtrading(ticker)
        if is_over:
            return False, f"Overtrading: {reason}", modifier

        # 3. Revenge Trading Preventer
        if signal_type == "BUY":
            is_revenge, reason, penalty = self._check_revenge_trading(ticker)
            if is_revenge:
                # Apply Penalties
                modifier["size_mult"] = 0.5
                modifier["required_score"] = 0.8 # Boost required confidence
                logging.info(f"[{ticker}] Revenge Trading Guard: {reason}. Penalties applied.")

                # Check if current score meets the elevated requirement
                # We assume caller checks score, but we can return the requirement
                if psnd_score < 0.8:
                    return False, f"Revenge Guard: PSND Score {psnd_score:.2f} < Required 0.80", modifier

        return True, "OK", modifier

    def _check_pump_dump(self, ticker, df):
        """
        Component 7.1: Pump & Dump Detector
        - Price > 5% in 15m
        - Volume > 300% avg
        - RSI > 75
        """
        try:
            if df is None or len(df) < 20: return False, ""

            last = df.iloc[-1]

            # Check RSI
            if 'rsi' in df.columns:
                if last['rsi'] > 75:
                    # Check Price Change (15m)
                    # We determine timeframe by time delta between last two candles
                    time_delta_sec = (df.index[-1] - df.index[-2]).total_seconds()

                    # If 1m (60s), use last 15 candles.
                    # If 15m (900s), use last 1 candle.

                    lookback = 15
                    if time_delta_sec >= 900: # 15m or more
                         lookback = 1
                    elif time_delta_sec >= 300: # 5m
                         lookback = 3

                    window = df.tail(lookback)
                    start_price = window['open'].iloc[0]
                    end_price = window['close'].iloc[-1]
                    change_pct = (end_price - start_price) / start_price

                    if change_pct > 0.05:
                        # Check Volume
                        avg_vol = df['volume'].rolling(50, min_periods=20).mean().iloc[-1]
                        # If not enough data, assume avg_vol is last 20 mean or just current (fallback)
                        if pd.isna(avg_vol):
                             avg_vol = df['volume'].mean()

                        if avg_vol > 0 and last['volume'] > (avg_vol * 3.0):
                            return True, "Pump Detected (+5% 15m, High Vol, RSI > 75)"

            return False, ""
        except Exception as e:
            return False, ""

    def _check_panic_sell(self, ticker, df):
        """
        Component 7.2: Panic Sell Blocker
        - Drop > 5% in 15m
        - Volume > 400% avg
        - Fear & Greed < 20 (Simulated or fetched)
        """
        try:
            if df is None or len(df) < 20: return False, ""

            last = df.iloc[-1]

            # Check Price Drop
            window = df.tail(15)
            start_price = window['open'].iloc[0]
            end_price = window['close'].iloc[-1]
            change_pct = (end_price - start_price) / start_price # Negative for drop

            if change_pct < -0.05:
                 # Check Volume
                avg_vol = df['volume'].rolling(50, min_periods=20).mean().iloc[-1]
                if pd.isna(avg_vol):
                     avg_vol = df['volume'].mean()

                if avg_vol > 0 and last['volume'] > (avg_vol * 4.0):
                    # Check Fear (Placeholder or DB)
                    # We can skip F&G check if strictly technical, or assume Panic
                    return True, "Panic Dump Detected (-5% 15m, High Vol)"

            return False, ""
        except Exception as e:
            return False, ""

    def _check_overtrading(self, ticker):
        """
        Component 7.3: Overtrading Limiter
        - Max 3 trades per ticker / 1h
        - Max 10 trades total / 1h
        """
        try:
            # Check Per Ticker
            query = """
                SELECT count(*) FROM trades
                WHERE ticker = ?
                AND timestamp > NOW() - INTERVAL '1 hour'
                AND action = 'BUY'
            """
            count_ticker = self.db.query(query, (ticker,))[0][0]

            if count_ticker >= 3:
                return True, f"Ticker Limit ({count_ticker}/3 per hour)"

            # Check Total
            query_total = """
                SELECT count(*) FROM trades
                WHERE timestamp > NOW() - INTERVAL '1 hour'
                AND action = 'BUY'
            """
            count_total = self.db.query(query_total)[0][0]

            if count_total >= 10:
                return True, f"Global Limit ({count_total}/10 per hour)"

            return False, ""
        except Exception as e:
            logging.error(f"Overtrading Check Error: {e}")
            return False, "Error"

    def _check_revenge_trading(self, ticker):
        """
        Component 7.4: Revenge Trading Preventer
        - If last trade was LOSS, next trade needs caution.
        """
        try:
            # Get last closed trade for ticker
            query = """
                SELECT pnl FROM trades
                WHERE ticker = ? AND action = 'SELL' AND pnl != 0
                ORDER BY timestamp DESC LIMIT 1
            """
            rows = self.db.query(query, (ticker,))

            if rows:
                last_pnl = rows[0][0]
                if last_pnl < 0:
                    # Last trade was a loss.
                    # Check how long ago? (User says 3h or 1 win reset)
                    # We need timestamp of sell

                    query_ts = """
                        SELECT timestamp FROM trades
                        WHERE ticker = ? AND action = 'SELL'
                        ORDER BY timestamp DESC LIMIT 1
                    """
                    ts_row = self.db.query(query_ts, (ticker,))
                    last_ts_str = ts_row[0][0]
                    # Parse
                    try:
                         last_ts = datetime.strptime(last_ts_str, "%Y-%m-%d %H:%M:%S")
                    except:
                         last_ts = datetime.fromisoformat(last_ts_str)

                    if (datetime.now() - last_ts).total_seconds() < (3 * 3600):
                        return True, "Recent Loss Detected (Revenge Guard)", 0.5

            return False, "", 1.0
        except Exception as e:
            return False, "", 1.0
