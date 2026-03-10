import threading
import datetime
import time
import os
import json
import pandas as pd
import ccxt
from src.utils.logger import log
from src.database_queue import get_db_queue

class BackgroundHistorySync:
    """Handles background historical data backfilling with persistence to SQLite."""
    def __init__(self, tickers, lookback_days=30):
        self.tickers = tickers
        self.lookback_days = lookback_days
        self.stop_event = threading.Event()
        self.db = get_db_queue()

    def update_status(self, progress, message, current_date, target_date, status="RUNNING", current_ticker=None):
        """Update sync status in DB."""
        data = {
            "status": status,
            "progress_percent": progress,
            "message": message,
            "current_fetching_date": current_date,
            "target_date": target_date,
            "current_ticker": current_ticker,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            query = "INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at"
            self.db.execute(query, ("history_sync", json.dumps(data)))
        except Exception as e:
            log(f"Error updating background sync status: {e}", "ERROR")

    def run(self):
        """Main worker function for backfill."""
        log("Starting Background History Sync...", "INFO")

        # Initialize status
        self.update_status(0, "Initializing background sync...", "Now", f"{self.lookback_days} days ago")

        now = datetime.datetime.now()

        # Create separate exchange instance with rate limiting
        try:
            exchange = ccxt.mexc({
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {
                    'defaultType': 'swap',
                }
            })
        except Exception as e:
            log(f"Background Sync failed to init exchange: {e}", "ERROR")
            self.update_status(0, f"Error: {str(e)}", "", "", "ERROR")
            return

        total_steps = self.lookback_days * len(self.tickers)
        if total_steps == 0: total_steps = 1 # Prevent division by zero
        steps_done = 0

        # Iterate backwards: Yesterday -> T-30
        for i in range(1, self.lookback_days + 1):
            if self.stop_event.is_set(): break

            target_date = now - datetime.timedelta(days=i)
            date_str = target_date.strftime("%Y-%m-%d")

            for ticker in self.tickers:
                if self.stop_event.is_set(): break

                msg = f"Downloading {ticker} for {date_str}"
                progress = int((steps_done / total_steps) * 100) if total_steps > 0 else 0
                self.update_status(progress, msg, date_str, (now - datetime.timedelta(days=self.lookback_days)).strftime("%Y-%m-%d"), current_ticker=ticker)

                try:
                    # Fetch OHLCV for the specific day
                    since_dt = datetime.datetime.combine(target_date.date(), datetime.time.min)
                    since_ts = int(since_dt.timestamp() * 1000)

                    # Fetching logic simplified: just get 1000 candles from start of day
                    # 15m candles: 24h * 4 = 96. 1000 is plenty.
                    ohlcv = exchange.fetch_ohlcv(ticker, timeframe='15m', since=since_ts, limit=1000)

                    if ohlcv:
                        # Insert into DB
                        # Structure: [timestamp, open, high, low, close, volume]
                        for candle in ohlcv:
                            ts_ms = candle[0]
                            ts_str = datetime.datetime.fromtimestamp(ts_ms/1000.0).strftime('%Y-%m-%d %H:%M:%S')

                            query = """
                                INSERT INTO candles (ticker, timestamp, open, high, low, close, volume, timeframe)
                                VALUES (?, ?, ?, ?, ?, ?, ?, '15m')
                                ON CONFLICT (ticker, timestamp, timeframe) DO UPDATE SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close, volume=EXCLUDED.volume
                            """
                            # Convert to native Python types to avoid PostgreSQL schema errors
                            self.db.execute(query, (
                                ticker, ts_str,
                                float(candle[1]) if candle[1] is not None else 0.0,
                                float(candle[2]) if candle[2] is not None else 0.0,
                                float(candle[3]) if candle[3] is not None else 0.0,
                                float(candle[4]) if candle[4] is not None else 0.0,
                                float(candle[5]) if candle[5] is not None else 0.0
                            ))

                    # Rate limit sleep
                    time.sleep(0.5)

                except Exception as e:
                    log(f"Error fetching history for {ticker} on {date_str}: {e}", "ERROR")

                steps_done += 1

        # Explicitly update status to COMPLETE as requested
        self.update_status(100, "Historical Backfill Complete", "Done", "Done", "COMPLETE")
        log("Background History Sync Complete.", "SUCCESS")
