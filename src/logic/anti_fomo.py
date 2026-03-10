import time
import pandas as pd
import pandas_ta as ta
import logging
from src.database import Database

# Configure logger
logger = logging.getLogger("AntiFOMO")

class AntiFOMOModule:
    """
    Module 7: Anti-FOMO & Anti-Panic
    Prevents emotional trading decisions: Pump & Dump, Panic Sells, Overtrading, Revenge Trading.
    """

    def __init__(self, db: Database):
        self.db = db
        # Cache for cooldowns: {ticker: expire_timestamp}
        self.cooldowns = {}

    def check_pump_dump(self, ticker: str, df: pd.DataFrame, news_impact_score: float = 0.0) -> dict:
        """
        7.1 Pump & Dump Detector
        Blocks BUY signals if sudden spike without fundamental backing.
        """
        if df is None or len(df) < 20:
            return {'status': 'PASS'}

        try:
            last = df.iloc[-1]

            # 1. Price Change > 5% in 15m (assuming 15m candles? Or we calculate change from open)
            # If timeframe is 1m, we need to look back 15 candles.
            # If timeframe is 15m, just current candle.
            # We will assume df passed is relevant timeframe or we check last N candles.
            # Let's assume input df is 1m or we just look at the last candle change if it's 15m.
            # Safest is to calculate change over last 15 minutes explicitly if index is datetime.

            # Use simple pct_change relative to 15 mins ago
            current_price = last['close']

            # Find price 15 mins ago
            price_15m_ago = current_price
            if len(df) >= 15:
                price_15m_ago = df.iloc[-15]['open']
            else:
                price_15m_ago = df.iloc[0]['open']

            pct_change = (current_price - price_15m_ago) / price_15m_ago

            # 2. Volume > 300% avg
            vol_ma = df['volume'].rolling(20).mean().iloc[-1]
            vol_spike = (last['volume'] > vol_ma * 3.0)

            # 3. RSI > 75
            rsi = 50
            if 'rsi' in last:
                rsi = last['rsi']
            elif 'RSI_14' in last:
                rsi = last['RSI_14']

            is_pump = (pct_change > 0.05) and vol_spike and (rsi > 75)

            if is_pump:
                # Exception: News
                if news_impact_score > 0.5:
                    return {'status': 'PASS', 'note': 'Pump detected but justified by News'}

                # Action: Block
                self._set_cooldown(ticker, 30, 'PUMP_DETECTED')
                self._log_event(ticker, 'PUMP', 'BLOCK_BUY_30M')
                return {
                    'status': 'HALT',
                    'reason': f'Pump & Dump Detected (+{pct_change*100:.1f}%, Vol Spike)',
                    'cooldown': 30
                }

        except Exception as e:
            logger.error(f"Pump check error: {e}")

        return {'status': 'PASS'}

    def check_panic_sell(self, ticker: str, df: pd.DataFrame, fear_greed_index: int) -> dict:
        """
        7.2 Panic Sell Blocker
        Blocks SELL signals during panic dumps.
        """
        if df is None or len(df) < 15:
            return {'status': 'PASS'}

        try:
            last = df.iloc[-1]
            current_price = last['close']

            # Price drop > 5% in 15m
            price_15m_ago = df.iloc[-15]['open'] if len(df) >= 15 else df.iloc[0]['open']
            pct_change = (current_price - price_15m_ago) / price_15m_ago

            # Volume > 400% avg
            vol_ma = df['volume'].rolling(20).mean().iloc[-1]
            vol_spike = (last['volume'] > vol_ma * 4.0)

            is_panic = (pct_change < -0.05) and vol_spike and (fear_greed_index < 20)

            if is_panic:
                self._log_event(ticker, 'PANIC_DUMP', 'BLOCK_SELL_WIDEN_SL')
                return {
                    'status': 'HALT',
                    'reason': 'Panic Dump Detected',
                    'action': 'WIDEN_SL' # Caller should handle this
                }

        except Exception as e:
            logger.error(f"Panic check error: {e}")

        return {'status': 'PASS'}

    def check_overtrading(self, ticker: str) -> dict:
        """
        7.3 Overtrading Limiter
        """
        try:
            now = time.time()
            hour_ago = now - 3600

            # Query DB for trades in last hour
            # We look at 'trades' table
            # Assuming 'timestamp' is DATETIME string or timestamp.
            # In `database.py`, it's DATETIME DEFAULT CURRENT_TIMESTAMP.

            # Max 3 trades on ticker per hour
            q_ticker = """
                SELECT count(*) FROM trades
                WHERE ticker = ? AND timestamp >= NOW() - INTERVAL '1 hour'
            """
            count_ticker = self.db.query(q_ticker, (ticker,))[0][0]

            if count_ticker >= 3:
                self._set_cooldown(ticker, 30, 'OVERTRADING_TICKER')
                self._log_event(ticker, 'OVERTRADING', 'HALT_30M')
                return {'status': 'HALT', 'reason': 'Overtrading (Ticker limit)'}

            # Max 10 trades total per hour
            q_total = """
                SELECT count(*) FROM trades
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
            """
            count_total = self.db.query(q_total)[0][0]

            if count_total >= 10:
                return {'status': 'HALT', 'reason': 'Overtrading (Global limit)'}

            # Max 2 consecutive losses
            # Fetch last 2 trades for ticker
            q_losses = """
                SELECT pnl FROM trades
                WHERE ticker = ?
                ORDER BY id DESC LIMIT 2
            """
            rows = self.db.query(q_losses, (ticker,))
            if len(rows) == 2:
                # Assuming pnl is stored. If not calculated yet (open trades), this might be tricky.
                # But 'trades' table usually records entry/exit or actions.
                # If we record 'SELL' with pnl, we can check.
                # We need to check only CLOSED trades (SELLs) for PnL.
                q_closed = """
                    SELECT pnl FROM trades
                    WHERE ticker = ? AND action = 'SELL'
                    ORDER BY id DESC LIMIT 2
                """
                closed_rows = self.db.query(q_closed, (ticker,))
                if len(closed_rows) == 2:
                    if closed_rows[0][0] < 0 and closed_rows[1][0] < 0:
                        self._set_cooldown(ticker, 30, 'CONSECUTIVE_LOSSES')
                        return {'status': 'HALT', 'reason': '2 Consecutive Losses'}

        except Exception as e:
            logger.error(f"Overtrading check error: {e}")

        return {'status': 'PASS'}

    def check_revenge_trading(self, ticker: str) -> dict:
        """
        7.4 Revenge Trading Preventer
        """
        try:
            # Check last trade outcome
            q_last = """
                SELECT pnl, timestamp FROM trades
                WHERE ticker = ? AND action = 'SELL'
                ORDER BY id DESC LIMIT 1
            """
            rows = self.db.query(q_last, (ticker,))

            if rows:
                pnl = rows[0][0]
                # If lost, check time elapsed
                # SQLite timestamp might be string
                # We can use SQL time diff or parse in python.
                # Let's rely on Python parsing if needed, or query logic

                if pnl < 0:
                     # Check if within 3 hours
                     # We can simplify by querying count of losses in last 3h
                     q_recent_loss = """
                        SELECT count(*) FROM trades
                        WHERE ticker = ? AND action = 'SELL' AND pnl < 0
                        AND timestamp >= NOW() - INTERVAL '3 hours'
                        ORDER BY id DESC LIMIT 1
                     """
                     # Wait, we need to know if the *last* trade was a loss and was recent.
                     # The query above counts *any* loss in 3h.
                     # We specifically want: Last trade was SELL, it was < 3h ago, and PNL < 0.

                     q_verify = """
                        SELECT pnl FROM trades
                        WHERE ticker = ? AND action = 'SELL'
                        AND timestamp >= NOW() - INTERVAL '3 hours'
                        ORDER BY id DESC LIMIT 1
                     """
                     verify_rows = self.db.query(q_verify, (ticker,))
                     if verify_rows and verify_rows[0][0] < 0:
                         return {
                             'status': 'CAUTION',
                             'reason': 'Revenge Trading Risk',
                             'modifiers': {'psnd_mult': 2.0, 'size_mult': 0.5}
                         }

        except Exception as e:
            logger.error(f"Revenge check error: {e}")

        return {'status': 'PASS', 'modifiers': {'psnd_mult': 1.0, 'size_mult': 1.0}}

    def is_in_cooldown(self, ticker: str) -> bool:
        """Checks if ticker is in cooldown."""
        if ticker in self.cooldowns:
            if time.time() < self.cooldowns[ticker]:
                return True
            else:
                del self.cooldowns[ticker]
        return False

    def _set_cooldown(self, ticker, minutes, reason):
        self.cooldowns[ticker] = time.time() + (minutes * 60)
        self._log_event(ticker, 'COOLDOWN_START', f"{reason} ({minutes}m)")

    def _log_event(self, ticker, event_type, action):
        try:
            self.db.execute(
                "INSERT INTO emotion_events (ticker, timestamp, event_type, action_taken, cooldown_until) VALUES (?, ?, ?, ?, ?) ON CONFLICT (ticker, timestamp) DO UPDATE SET event_type=EXCLUDED.event_type, action_taken=EXCLUDED.action_taken, cooldown_until=EXCLUDED.cooldown_until",
                (ticker, int(time.time()), event_type, action, self.cooldowns.get(ticker, 0))
            )
        except Exception as e:
            logger.error(f"Log event error: {e}")
