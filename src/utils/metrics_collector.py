import os
import requests
import zipfile
import threading
import time
import schedule
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Fix absolute path imports to run independently or as a module
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from src.database import Database
from src.utils.logger import log

class MetricsCollector:
    def __init__(self, db=None, symbol="BTCUSDT"):
        self.db = db if db else Database()
        self.symbol = symbol
        self.is_running = False
        self.sync_thread = None
        
        self.save_dir = Path("data/raw_metrics")
        self.temp_dir = Path("data/temp_zips")
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.total_days_target = 180
        self.days_downloaded = 0
        self.status = "IDLE"

    def start(self):
        """Starts the initial sync in a background thread and schedules daily updates."""
        if self.is_running:
            return
            
        self.is_running = True
        log(f"🚀 Uruchamianie MetricsCollector dla {self.symbol}...", "INFO")
        
        # Start initial sync in background
        self.sync_thread = threading.Thread(target=self._run_initial_sync, daemon=True)
        self.sync_thread.start()
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def _run_initial_sync(self):
        """Runs the 180-day sync."""
        self.download_binance_metrics(days=self.total_days_target, symbol=self.symbol)

    def _run_scheduler(self):
        """Runs the schedule loop checking for daily updates."""
        # Binance Vision daily metrics usually appear a few hours after UTC midnight.
        # We check daily at 07:07:30 UTC.
        schedule.every().day.at("07:07:30").do(self._daily_update)
        
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)

    def _daily_update(self):
        """Fetches just the last 2 days to ensure we have the latest."""
        log(f"🔄 Codzienna aktualizacja Order Flow dla {self.symbol}...", "INFO")
        self.download_binance_metrics(days=2, symbol=self.symbol)

    def download_binance_metrics(self, days=180, symbol="BTCUSDT"):
        """
        Pobiera i rozpakowuje dane metrics z Binance Vision.
        Źródło: https://data.binance.vision/?prefix=data/futures/um/daily/metrics/BTCUSDT/
        """
        base_url = f"https://data.binance.vision/data/futures/um/daily/metrics/{symbol}"
        
        self.status = "DOWNLOADING"
        self.total_days_target = days
        self.days_downloaded = 0

        log(f"🚀 Start pobierania danych Order Flow dla {symbol} (ostatnie {days} dni)...", "INFO")

        # Zaczynamy od wczoraj (bo dzisiejszy plik jeszcze nie istnieje na 100%)
        end_date = datetime.now(timezone.utc) - timedelta(days=1)
        
        downloaded_count = 0
        skipped_count = 0

        for i in range(days):
            if not self.is_running:
                break
                
            current_date = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
            file_name = f"{symbol}-metrics-{current_date}"
            zip_file = f"{file_name}.zip"
            csv_file = f"{file_name}.csv"
            
            url = f"{base_url}/{zip_file}"
            csv_path = self.save_dir / csv_file
            
            # Sprawdź czy już mamy ten plik rozpakowany
            if csv_path.exists():
                skipped_count += 1
                self.days_downloaded += 1
                self._update_status_db()
                continue

            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    zip_path = self.temp_dir / zip_file
                    
                    # Zapisz ZIP
                    with open(zip_path, "wb") as f:
                        f.write(response.content)
                    
                    # Rozpakuj
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(self.save_dir)
                    
                    # Usuń ZIP (sprzątanie)
                    os.remove(zip_path)
                    
                    # Process the CSV immediately
                    self._process_csv(csv_path)
                    
                    downloaded_count += 1
                    self.days_downloaded += 1
                    self._update_status_db()
                    
                    # Small delay to avoid hammering the server
                    time.sleep(0.5)
                else:
                    # Niektóre dni mogą być niedostępne w archiwum
                    pass
                    
            except Exception as e:
                log(f"❌ Błąd przy dacie {current_date}: {e}", "ERROR")

        # Sprzątanie folderu tymczasowego
        if self.temp_dir.exists() and not any(self.temp_dir.iterdir()):
            self.temp_dir.rmdir()

        self.status = "COMPLETED"
        self._update_status_db()
        log(f"✅ KONIEC Order Flow! Pobrano: {downloaded_count}, Pominięto: {skipped_count}. Dane są w: {self.save_dir}", "SUCCESS")

    def _process_csv(self, csv_path):
        """Odczytuje plik CSV i "wlewa" dane do bazy danych PostgreSQL (tabela futures_metrics)."""
        try:
            df = pd.read_csv(csv_path)
            
            # Binance metrics CSV has these columns (might vary slightly, we need to adapt):
            # create_time, symbol, sum_open_interest, sum_open_interest_value, count_toptrader_long_short_ratio, sum_toptrader_long_short_ratio, count_long_short_ratio, sum_long_short_ratio, taker_long_short_ratio
            # We map to:
            # open_interest, oi_value_usdt, top_trader_ls_ratio, taker_buy_sell_ratio
            
            if df.empty:
                return
                
            data_to_insert = []
            
            # CCXT uses format like 'BTC/USDT', so we standardize the ticker name for the DB
            standard_ticker = f"{self.symbol[:3]}/{self.symbol[3:]}" if self.symbol == "BTCUSDT" else self.symbol
            
            for _, row in df.iterrows():
                # create_time is typically in 'YYYY-MM-DD HH:MM:SS' format
                ts_str = row.get('create_time', '')
                if not ts_str:
                    continue
                    
                try:
                    # Check if it's already a string or timestamp
                    if isinstance(ts_str, str):
                        ts = ts_str
                    else:
                        ts = pd.to_datetime(ts_str).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    continue
                    
                oi = float(row.get('sum_open_interest', 0))
                oi_val = float(row.get('sum_open_interest_value', 0))
                # Map according to user instruction
                top_ls = float(row.get('count_toptrader_long_short_ratio', 0))
                taker_ratio = float(row.get('sum_taker_long_short_vol_ratio', row.get('taker_long_short_ratio', 0))) # Fallback
                
                data_to_insert.append((
                    standard_ticker, ts, oi, oi_val, top_ls, taker_ratio
                ))
            
            if data_to_insert:
                query = """
                    INSERT INTO futures_metrics 
                    (ticker, timestamp, open_interest, oi_value_usdt, top_trader_ls_ratio, taker_buy_sell_ratio)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, timestamp) DO UPDATE SET
                    open_interest = EXCLUDED.open_interest,
                    oi_value_usdt = EXCLUDED.oi_value_usdt,
                    top_trader_ls_ratio = EXCLUDED.top_trader_ls_ratio,
                    taker_buy_sell_ratio = EXCLUDED.taker_buy_sell_ratio
                """
                # Using our execute_many which handles replacing ? with %s if needed
                self.db.execute_many(query.replace('%s', '?'), data_to_insert)
                
        except Exception as e:
            log(f"Error processing CSV {csv_path}: {e}", "ERROR")

    def _update_status_db(self):
        """Aktualizuje status w system_status, żeby UI miało do niego dostęp."""
        try:
            progress = min(100, int((self.days_downloaded / self.total_days_target) * 100)) if self.total_days_target > 0 else 100
            
            status_data = {
                "status": self.status,
                "days_downloaded": self.days_downloaded,
                "total_days": self.total_days_target,
                "progress_percent": progress,
                "symbol": self.symbol,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self.db.execute(
                "INSERT INTO system_status (key, value, updated_at) VALUES ('metrics_sync', %s, %s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at".replace('%s', '?'),
                (json.dumps(status_data), datetime.now(timezone.utc).isoformat())
            )
        except Exception as e:
            log(f"Error updating metrics status in DB: {e}", "WARNING")

if __name__ == "__main__":
    # Uruchomienie standalone
    collector = MetricsCollector()
    collector.download_binance_metrics(days=180)
