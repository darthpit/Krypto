import os
import sys
import logging
import time
import multiprocessing
import signal
import asyncio
import json
import subprocess
from datetime import datetime, timedelta, timezone

# Define Log File
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'system.log')

# Ensure logs directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from database import Database
from src.database_queue import DatabaseQueue, get_db_queue
from process_trader import TraderProcess
from process_trainer import TrainerProcess
from src.utils.model_monitor import ModelMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - SUPERVISOR - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Supervisor")

def initialize_database_schema():
    """
    Initialize database schema.
    Uses PostgreSQL Database class to ensure tables exist.
    """
    logger.info("Initializing database schema...")
    try:
        # Initializing the Database class triggers create_tables
        db = Database()
        logger.info("Database schema initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
        return False

class AsyncSupervisor:
    def __init__(self):
        self.processes = {}
        self.is_running = True
        self.config = self.load_config()
        self.training_queue = self.get_all_tickers()
        self.current_training_index = 0
        
        # --- MODEL MONITOR (AI Control Center) ---
        self.model_monitor = ModelMonitor()
        
        # --- FIX: ZMIENNE DO KONTROLI CZASU ---
        self.last_training_cycle_time = 0
        self.TRAINING_COOLDOWN = 1800  # 30 minut w sekundach
        
        # --- SATELITA CRYPTO SCHEDULER ---
        self.last_satellite_run = None
        self.satellite_target_hour = 1  # 1:00 AM
        self.satellite_file = os.path.join(os.path.dirname(__file__), 'satellite.py')
        
        # --- RL AGENT SCHEDULER ---
        self.rl_training_interval_days = 7  # Re-train every 7 days
        self.rl_trainer_file = os.path.join(os.path.dirname(__file__), 'src', 'process_rl_trainer.py')
        self.rl_training_lockfile = os.path.join(os.path.dirname(__file__), 'models', '.rl_training.lock')
        self.rl_training_info_file = os.path.join(os.path.dirname(__file__), 'models', 'rl_training_info.json')
        
        # --- LSTM LOCKFILE (dla PPO, aby sprawdzać czy LSTM się trenuje) ---
        self.lstm_lockfile = os.path.join(os.path.dirname(__file__), 'models', '.lstm_training.lock')
        
        # Track last check to avoid spam
        self._last_rl_check_time = 0
        self._rl_training_started = False  # Flag to prevent multiple starts
        
        logger.info(f"📋 Training Queue Loaded: {self.training_queue}")

    def load_config(self):
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except:
            return {}

    def get_all_tickers(self):
        tickers = []
        assets = self.config.get('assets', {})
        for category in assets.values():
            if isinstance(category, dict) and 'tickers' in category:
                tickers.extend(category['tickers'])
        
        tickers = list(set(tickers))
        # BTC always first as market leader
        if "BTC/USDT" in tickers:
            tickers.remove("BTC/USDT")
            tickers.insert(0, "BTC/USDT")
        
        return tickers if tickers else ["BTC/USDT"]

    async def monitor_processes(self):
        logger.info("Supervisor Monitor Loop Started (Smart Scheduler Mode)...")
        
        # Start Trader immediately
        self.restart_trader()
        
        # Check if LSTM model needs training (6-day auto-retrain)
        await self._check_and_schedule_lstm_training()
        
        # Check if model is outdated at startup and trigger immediate training if needed
        self._check_model_freshness_and_train()
        
        # Check and run satellite if needed at startup
        await self._check_and_run_satellite()
        
        # Check and update RL Agent status at startup
        await self._check_and_schedule_rl_training()

        while self.is_running:
            try:
                # 1. Monitor Trader (Musi działać NON-STOP)
                if 'trader' not in self.processes or not self.processes['trader'].is_alive():
                    logger.warning("🚨 Trader Process died! Restarting immediately...")
                    self.restart_trader()

                # 2. Monitor Trainer (Smart Schedule)
                trainer_is_working = 'trainer' in self.processes and self.processes['trainer'].is_alive()

                if not trainer_is_working:
                    now = time.time()
                    
                    # Sprawdź, czy minęło 30 minut od ostatniego PEŁNEGO cyklu
                    # Jeśli mamy tylko 1 ticker, cykl kończy się po każdym treningu.
                    time_since_last = now - self.last_training_cycle_time
                    
                    if time_since_last < self.TRAINING_COOLDOWN:
                         # Czekamy... nie uruchamiaj trenera
                         # (Opcjonalnie: loguj co jakiś czas "Waiting for next cycle...")
                         pass
                    else:
                        # ═══════════════════════════════════════════════════════════
                        # CRITICAL: Block LSTM training if PPO is active (OOM protection)
                        # ═══════════════════════════════════════════════════════════
                        if os.path.exists(self.rl_training_lockfile):
                            # PPO is training, skip LSTM to prevent memory conflict
                            if not hasattr(self, '_last_rl_block_warning') or (time.time() - self._last_rl_block_warning) > 600:
                                logger.warning("⏸️ LSTM training postponed: PPO Agent is training (memory protection)")
                                self._last_rl_block_warning = time.time()
                            # Don't update last_training_cycle_time - will retry in next cycle
                            pass
                        # ═══════════════════════════════════════════════════════════
                        elif self.training_queue:
                            # Czas na trening!
                            next_ticker = self.training_queue[self.current_training_index]
                            logger.info(f"🚀 Starting scheduled training for: {next_ticker}")
                            self.start_trainer_task(next_ticker)

                            # Przesuń wskaźnik
                            self.current_training_index = (self.current_training_index + 1) % len(self.training_queue)
                            
                            # Jeśli wróciliśmy na początek listy (zrobiliśmy kółko), zapisz czas
                            # W przypadku jednego tickera (BTC), dzieje się to za każdym razem.
                            if self.current_training_index == 0:
                                self.last_training_cycle_time = now
                                logger.info(f"⏳ Cycle complete. Next training in {self.TRAINING_COOLDOWN/60:.0f} minutes.")
                        else:
                            logger.warning("No tickers in queue.")
                
                # 3. Monitor LSTM Model Training (Auto-retrain after 6 days)
                await self._check_and_schedule_lstm_training()
                
                # 4. Monitor Satellite Crypto (Daily at 1:00 AM)
                await self._check_and_run_satellite()
                
                # 5. Monitor RL Agent Training (Weekly on Sunday at 2:00 AM)
                await self._check_and_schedule_rl_training()

                await asyncio.sleep(5) # Sprawdzaj stan co 5 sekund

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor Loop Error: {e}")
                await asyncio.sleep(5)

    def restart_trader(self):
        # Trader gets all tickers to observe
        if 'trader' in self.processes and self.processes['trader'].is_alive():
            self.processes['trader'].terminate()
            self.processes['trader'].join()
            
        # Interval 60s for trader is OK (checks prices)
        p = TraderProcess(tickers=self.get_all_tickers(), interval=60)
        p.start()
        self.processes['trader'] = p
        logger.info(f"Trader Process (re)started (PID: {p.pid})")

    def start_trainer_task(self, ticker):
        # interval=0 means "Run Once"
        p = TrainerProcess(ticker=ticker, interval=0) 
        p.start()
        self.processes['trainer'] = p
    
    async def _check_and_run_satellite(self):
        """
        Check if Satellite Crypto should run:
        1. Daily at 1:00 AM
        2. If data is stale (not updated in last 7 days)
        """
        try:
            now = datetime.now()
            
            # Check if satellite data file exists and is fresh
            satellite_data_file = os.path.join(os.path.dirname(__file__), 'api', 'satellite_data.json')
            should_run = False
            
            # Check 1: Data file exists and age
            if os.path.exists(satellite_data_file):
                file_age_days = (time.time() - os.path.getmtime(satellite_data_file)) / (24 * 3600)
                
                if file_age_days > 7:
                    # Data is stale (older than 7 days), force update
                    logger.warning(f"🛰️ Satellite data is {file_age_days:.1f} days old. Triggering immediate update...")
                    should_run = True
            else:
                # No data file, run immediately
                logger.warning("🛰️ Satellite data file not found. Triggering initial update...")
                should_run = True
            
            # Check 2: Daily scheduled run at 1:00 AM
            if not should_run:
                # Check if it's the target hour and we haven't run today
                if now.hour == self.satellite_target_hour:
                    if self.last_satellite_run is None or self.last_satellite_run.date() < now.date():
                        logger.info(f"🛰️ Daily Satellite Crypto update scheduled (1:00 AM)")
                        should_run = True
            
            # Run satellite if needed
            if should_run:
                logger.info("🛰️ Running Satellite Crypto analysis...")
                try:
                    # Run satellite.py as subprocess
                    result = subprocess.run(
                        [sys.executable, self.satellite_file],
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minutes timeout
                    )
                    
                    if result.returncode == 0:
                        logger.info("✅ Satellite Crypto update completed successfully")
                        logger.info(result.stdout)
                        self.last_satellite_run = now
                    else:
                        logger.error(f"❌ Satellite Crypto failed: {result.stderr}")
                        
                except subprocess.TimeoutExpired:
                    logger.error("❌ Satellite Crypto timeout (5 minutes)")
                except Exception as e:
                    logger.error(f"❌ Satellite Crypto error: {e}")
                    
        except Exception as e:
            logger.error(f"Error in satellite check: {e}")
    
    async def _check_and_schedule_lstm_training(self):
        """
        Check and schedule LSTM model training:
        1. Auto-start training if no model exists
        2. Re-train every 6 days from last training (or co 30 minut w trybie live)
        3. Update AI Control Center status
        
        NOWA HIERARCHIA PRIORYTETÓW:
        - LSTM Ensemble v3.4 ma PRIORYTET 2 (Wysoki) - NIE JEST blokowany przez PPO
        - PPO Agent ma PRIORYTET 3 (Tło) - jest pauzowany gdy LSTM się trenuje
        """
        try:
            # ═══════════════════════════════════════════════════════════════════
            # NOWA LOGIKA: LSTM MA PIERWSZEŃSTWO! Nie sprawdzamy PPO locka.
            # ═══════════════════════════════════════════════════════════════════
            # Usunięto starą blokadę: "Block LSTM if PPO is active"
            # LSTM Ensemble v3.4 to fundament handlu i musi być zawsze aktualny.
            # ═══════════════════════════════════════════════════════════════════
            
            # Check if LSTM needs training (6-day threshold)
            if self.model_monitor.check_needs_training("lstm", max_age_days=6):
                # Check if training is not already in progress
                if not self.model_monitor.is_training_active("lstm"):
                    logger.info("🧠 LSTM Model needs retraining (>6 days old). Triggering training...")
                    
                    # Mark training as started in monitor
                    self.model_monitor.update_start("lstm", "Zaplanowano trening LSTM...")
                    
                    # Start trainer process for BTC/USDT
                    target_ticker = self.config.get('trading', {}).get('target_symbol', "BTC/USDT")
                    
                    # Check if trainer is not already running
                    if 'trainer' not in self.processes or not self.processes['trainer'].is_alive():
                        self.start_trainer_task(target_ticker)
                        logger.info(f"✅ LSTM training started for {target_ticker}")
                    else:
                        logger.info("⏳ LSTM training already in progress, waiting...")
            else:
                # Model is fresh, update status if needed
                status = self.model_monitor.get_status("lstm")
                if status and status.get("status") == "IDLE":
                    # Update next training time in status
                    time_to_next = self.model_monitor.get_time_to_next_training("lstm")
                    if time_to_next:
                        days_remaining = time_to_next.days
                        if days_remaining <= 1:
                            logger.debug(f"🧠 LSTM next training in {time_to_next.total_seconds()/3600:.1f} hours")
                        
        except Exception as e:
            logger.error(f"Error in LSTM training check: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def _check_and_schedule_rl_training(self):
        """
        Check and schedule RL Agent training:
        1. Auto-start training if no model exists
        2. Re-train every 7 days from last training
        3. Incremental data: 30 days base + 7 days each re-training
        
        NOWA HIERARCHIA PRIORYTETÓW:
        - PPO Agent ma PRIORYTET 3 (Tło) - NIE może trenować gdy LSTM jest aktywny
        - LSTM Ensemble v3.4 ma PRIORYTET 2 (Wysoki) - może przerwać PPO
        """
        try:
            # Throttle checks to avoid spam (check every 60 seconds max)
            now_time = time.time()
            if now_time - self._last_rl_check_time < 60:
                return
            self._last_rl_check_time = now_time
            
            # ═══════════════════════════════════════════════════════════════════
            # NOWA LOGIKA: PPO czeka jeśli LSTM się trenuje (Priorytet 2 > 3)
            # ═══════════════════════════════════════════════════════════════════
            if os.path.exists(self.lstm_lockfile):
                # LSTM is training, don't start PPO to allow LSTM priority
                if not hasattr(self, '_last_ppo_lstm_block_log') or (time.time() - self._last_ppo_lstm_block_log) > 1800:
                    logger.warning("⏸️ PAUZA: Trening LSTM Ensemble v3.4 w toku - PPO update postponed (Priority 2 > 3)")
                    self._last_ppo_lstm_block_log = time.time()
                return  # Exit early - LSTM has priority!
            # ═══════════════════════════════════════════════════════════════════
            
            now = datetime.now()
            rl_model_path = os.path.join(os.path.dirname(__file__), 'models', 'ppo_trading_agent.zip')
            
            # Check if training is already in progress
            if os.path.exists(self.rl_training_lockfile):
                # Check if process is actually running (Zombie detection)
                training_info = self._load_rl_training_info()
                pid = training_info.get('pid')
                
                is_running = False
                if pid:
                    try:
                        # Signal 0 checks if process exists and we have permission
                        os.kill(pid, 0)
                        is_running = True
                    except OSError:
                        is_running = False
                
                if is_running:
                    # Training truly in progress, update stats
                    logger.debug(f"🧠 RL Training process (PID {pid}) is active. Lockfile exists.")
                    self._update_rl_brain_stats_training_in_progress()
                    return
                else:
                    # Zombie detected! Process dead but lockfile exists
                    logger.error(f"💀 ZOMBIE LOCK DETECTED! Process {pid} is dead but lockfile exists. Cleaning up...")
                    
                    # 1. Remove lockfile
                    try:
                        os.remove(self.rl_training_lockfile)
                        logger.info("🗑️ Zombie lockfile removed.")
                    except Exception as e:
                        logger.error(f"Failed to remove zombie lockfile: {e}")
                    
                    # 2. Check if we should auto-restart from last checkpoint
                    should_auto_restart = self._check_for_auto_restart(training_info)
                    
                    if should_auto_restart:
                        # AUTO-RESTART: Resume from last checkpoint
                        logger.info("🔄 AUTO-RESTART: Attempting to resume training from last checkpoint...")
                        
                        # Update UI
                        self.model_monitor.update_start("rl_agent", "Auto-restart po OOM: Wznowienie od checkpointu...")
                        
                        # Reset internal flag
                        self._rl_training_started = False
                        
                        # Trigger restart with resume flag
                        await self._run_rl_training_with_resume(training_info)
                        return
                    else:
                        # No auto-restart, mark as failed
                        training_info['status'] = 'failed'
                        training_info['error'] = 'Process crashed / Zombie detected (OOM?) - No checkpoint available'
                        training_info['completed_at'] = datetime.now().isoformat()
                        self._save_rl_training_info(training_info)
                        
                        # Update UI via ModelMonitor
                        self.model_monitor.update_error("rl_agent", "KRYTYCZNY: Proces treningowy 'zabity' (Brak Pamięci/OOM).")
                        
                        # Reset internal flag
                        self._rl_training_started = False
                        
                        # Continue execution -> This allows system to retry or wait for next schedule
                        return

            # Load training info (last training timestamp, data months used)
            training_info = self._load_rl_training_info()
            
            # Check if RL model exists
            model_exists = os.path.exists(rl_model_path)
            
            if not model_exists:
                # No model = start initial training immediately (but only once)
                if self._rl_training_started:
                    # Already started, just update stats
                    self._update_rl_brain_stats_training_in_progress()
                    return
                
                logger.info("🧠 RL Agent model not found. Starting initial training in background...")
                # Update stats to show training will start
                self._update_rl_brain_stats_training_in_progress()
                self._rl_training_started = True  # Set flag to prevent multiple starts
                await self._run_rl_training(initial_training=True)
                return
            
            # Model exists, check if 7 days passed since last training
            last_training_time = training_info.get('last_training_time')
            
            if last_training_time:
                last_training_dt = datetime.fromisoformat(last_training_time)
                # If timezone-naive, assume UTC
                if last_training_dt.tzinfo is None:
                    last_training_dt = last_training_dt.replace(tzinfo=timezone.utc)
                days_since_training = (now - last_training_dt).total_seconds() / (24 * 3600)
                
                if days_since_training >= self.rl_training_interval_days:
                    logger.info(f"🧠 RL Agent: {days_since_training:.1f} days since last training. Starting re-training...")
                    await self._run_rl_training(initial_training=False)
                else:
                    # Update stats with next training time
                    next_training = last_training_dt + timedelta(days=self.rl_training_interval_days)
                    self._update_rl_brain_stats_scheduled(next_training, training_info)
            else:
                # No training info but model exists (legacy), treat as initial
                logger.info("🧠 RL Agent: No training info found. Starting re-training...")
                # Update stats to show training will start
                self._update_rl_brain_stats_training_in_progress()
                await self._run_rl_training(initial_training=False)
                    
        except Exception as e:
            logger.error(f"Error in RL training check: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _load_rl_training_info(self):
        """Load RL training info from JSON file."""
        try:
            if os.path.exists(self.rl_training_info_file):
                with open(self.rl_training_info_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading RL training info: {e}")
        
        return {}
    
    def _save_rl_training_info(self, info):
        """Save RL training info to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.rl_training_info_file), exist_ok=True)
            with open(self.rl_training_info_file, 'w') as f:
                json.dump(info, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving RL training info: {e}")
    
    def _update_rl_brain_stats_training_in_progress(self):
        """Update RL brain stats to show training is in progress."""
        try:
            db = Database()
            now = datetime.now()
            
            # Check if we already have a record
            rows = db.query("SELECT id FROM rl_brain_stats ORDER BY id DESC LIMIT 1")
            
            if rows:
                # Update existing record
                db.execute(
                    """UPDATE rl_brain_stats 
                       SET training_status = ?, 
                           last_check = ?,
                           updated_at = ?
                       WHERE id = ?""",
                    ('TRAINING IN PROGRESS', now.isoformat(), now.isoformat(), rows[0][0])
                )
            else:
                # Insert new record
                db.execute(
                    """INSERT INTO rl_brain_stats 
                       (training_status, total_accuracy, total_hits, total_misses, last_check, model_version, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    ('TRAINING IN PROGRESS', 0.0, 0, 0, now.isoformat(), 'Training...', now.isoformat())
                )
            
        except Exception as e:
            logger.error(f"Error updating RL brain stats: {e}")
    
    def _update_rl_brain_stats_scheduled(self, next_training_dt, training_info):
        """Update RL brain stats with next scheduled training time."""
        try:
            db = Database()
            now = datetime.now()
            
            # Calculate days until next training
            days_until_training = (next_training_dt - now).total_seconds() / (24 * 3600)
            
            # Check if we already have a record
            rows = db.query("SELECT id FROM rl_brain_stats ORDER BY id DESC LIMIT 1")
            
            training_count = training_info.get('training_count', 0)
            data_months = training_info.get('data_months', 1)
            
            if rows:
                # Update existing record timing info only
                db.execute(
                    """UPDATE rl_brain_stats 
                       SET training_status = ?,
                           last_check = ?,
                           next_training_time = ?,
                           model_version = ?,
                           updated_at = ?
                       WHERE id = ?""",
                    ('ACTIVE', now.isoformat(), next_training_dt.isoformat(), 
                     f'v{training_count}.0 ({data_months}mo data)', now.isoformat(), rows[0][0])
                )
            else:
                # Insert new record if none exists
                db.execute(
                    """INSERT INTO rl_brain_stats 
                       (training_status, total_accuracy, total_hits, total_misses, last_check, next_training_time, model_version, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ('ACTIVE', 0.0, 0, 0, now.isoformat(), next_training_dt.isoformat(), 
                     f'v{training_count}.0 ({data_months}mo data)', now.isoformat())
                )
            
            # Log only once per hour to avoid spam
            if not hasattr(self, '_last_rl_status_log') or (now - self._last_rl_status_log).seconds > 3600:
                logger.info(f"🧠 RL Agent: Training #{training_count}, {data_months}mo data. Next: {next_training_dt.strftime('%Y-%m-%d %H:%M')} ({days_until_training:.1f}d)")
                self._last_rl_status_log = now
            
        except Exception as e:
            logger.error(f"Error updating RL brain stats schedule: {e}")
    
    async def _run_rl_training(self, initial_training=False):
        """
        Run RL Agent training in background.
        
        Args:
            initial_training: If True, start with base data (30 days = ~1 month)
                            If False, add 7 more days to existing data
        """
        try:
            # Load current training info
            training_info = self._load_rl_training_info()
            
            # Calculate data months to use
            if initial_training:
                # Initial training: 30 days = 1 month
                data_months = 1
                training_count = 1
                logger.info("🧠 Starting INITIAL RL Agent training (PRIORYTET 3 - Tło, 30 days data, ~2 hours)...")
                logger.info("   PPO będzie pauzowany jeśli LSTM Ensemble v3.4 będzie wymagał aktualizacji")
            else:
                # Re-training: add 7 days (0.23 months) to existing data
                current_months = training_info.get('data_months', 1)
                data_months = round(current_months + 0.23, 2)  # +7 days ≈ 0.23 months
                training_count = training_info.get('training_count', 0) + 1
                logger.info(f"🧠 Starting RE-TRAINING #{training_count} (PRIORYTET 3 - Tło, adding 7 days → {data_months:.2f} months total data, ~2-3 hours)...")
                logger.info("   PPO będzie pauzowany jeśli LSTM Ensemble v3.4 będzie wymagał aktualizacji")
            
            # Create lockfile to prevent duplicate training
            os.makedirs(os.path.dirname(self.rl_training_lockfile), exist_ok=True)
            with open(self.rl_training_lockfile, 'w') as f:
                f.write(json.dumps({
                    'started_at': datetime.now().isoformat(),
                    'training_count': training_count,
                    'data_months': data_months
                }))
            
            # Update stats to show training in progress
            self._update_rl_brain_stats_training_in_progress()
            
            # Prepare command
            # Use python3.12 in Docker, sys.executable on host
            python_cmd = sys.executable
            # Check if we're in Docker (common indicator: /app working directory)
            if os.path.exists('/.dockerenv') or os.getcwd() == '/app':
                # In Docker, use python3.12 explicitly
                python_cmd = 'python3.12'
            
            # FIXED: Use lookback_days from config.json (180 days)
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    data_days = config.get('lookback_days', 180)  # Default: 180 days
            except:
                data_days = 180  # Fallback: 180 days (6 months)
            
            cmd = [
                python_cmd, 
                self.rl_trainer_file,
                '--timesteps', '200000',  # 2 hours
                '--data-days', str(data_days),  # FIXED: use --data-days (not --data-months)
                '--balance', '1000',
                '--leverage', '20'
                # Note: --auto flag not needed, process_rl_trainer.py runs without confirmation
            ]
            
            logger.info(f"🧠 RL Training command: {' '.join(cmd)}")
            
            # Verify file exists before running
            if not os.path.exists(self.rl_trainer_file):
                logger.error(f"❌ RL trainer file not found: {self.rl_trainer_file}")
                # Remove lockfile on error
                if os.path.exists(self.rl_training_lockfile):
                    os.remove(self.rl_training_lockfile)
                return
            
            logger.info(f"🧠 Starting RL training with command: {' '.join(cmd)}")
            
            # Run train_rl.py as subprocess (async, in background)
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=os.path.dirname(__file__)  # Set working directory
                )
                
                logger.info(f"🧠 RL Training started in background (PID: {process.pid}, {data_months:.2f}mo data)")
            except Exception as e:
                logger.error(f"❌ Failed to start RL training subprocess: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Remove lockfile on error
                if os.path.exists(self.rl_training_lockfile):
                    os.remove(self.rl_training_lockfile)
                return
            
            # Save training info immediately
            training_info = {
                'last_training_time': datetime.now(timezone.utc).isoformat(),
                'training_count': training_count,
                'data_months': data_months,
                'pid': process.pid,
                'status': 'running'
            }
            self._save_rl_training_info(training_info)
            
            # Start background task to monitor completion
            asyncio.create_task(self._monitor_rl_training_completion(process, training_info))
            
        except Exception as e:
            logger.error(f"❌ Failed to start RL training: {e}")
            # Remove lockfile on error
            if os.path.exists(self.rl_training_lockfile):
                os.remove(self.rl_training_lockfile)
    
    def _check_for_auto_restart(self, training_info):
        """
        Check if auto-restart should be triggered.
        
        Returns True if:
        1. Checkpoint exists in models/checkpoints/
        2. Training was not manually cancelled
        3. Not too many restart attempts
        """
        try:
            import glob
            
            # Check for checkpoints
            checkpoint_dir = os.path.join(os.path.dirname(__file__), 'models', 'checkpoints')
            if not os.path.exists(checkpoint_dir):
                return False
            
            checkpoints = glob.glob(os.path.join(checkpoint_dir, 'ppo_checkpoint_*.zip'))
            if not checkpoints:
                logger.warning("⚠️ No checkpoints found for auto-restart")
                return False
            
            # Check restart count (prevent infinite loop)
            restart_count = training_info.get('restart_count', 0)
            if restart_count >= 3:
                logger.error(f"❌ Auto-restart limit reached ({restart_count}/3 attempts)")
                return False
            
            logger.info(f"✅ Auto-restart conditions met: {len(checkpoints)} checkpoints available, attempt {restart_count + 1}/3")
            return True
            
        except Exception as e:
            logger.error(f"Error checking auto-restart: {e}")
            return False
    
    async def _run_rl_training_with_resume(self, training_info):
        """
        Run RL training with resume from last checkpoint.
        Similar to _run_rl_training but with --resume flag.
        """
        try:
            # Find latest checkpoint
            import glob
            checkpoint_dir = os.path.join(os.path.dirname(__file__), 'models', 'checkpoints')
            checkpoints = glob.glob(os.path.join(checkpoint_dir, 'ppo_checkpoint_*.zip'))
            
            if not checkpoints:
                logger.error("❌ No checkpoints found for resume")
                return
            
            # Sort by timesteps to get latest
            def extract_timesteps(path):
                try:
                    basename = os.path.basename(path)
                    return int(basename.split('_')[-1].replace('.zip', ''))
                except:
                    return 0
            
            checkpoints.sort(key=extract_timesteps, reverse=True)
            latest_checkpoint = checkpoints[0].replace('.zip', '')
            
            logger.info(f"🔄 Resuming from checkpoint: {os.path.basename(latest_checkpoint)}")
            
            # Update restart count
            restart_count = training_info.get('restart_count', 0) + 1
            training_info['restart_count'] = restart_count
            
            # Get training parameters
            training_count = training_info.get('training_count', 1)
            # FIXED: Use lookback_days from config.json (180 days), not data_months
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    data_days = config.get('lookback_days', 180)  # Default: 180 days
            except:
                data_days = 180  # Fallback: 180 days (6 months)
            
            logger.info(f"📊 PPO Training will use {data_days} days of data (from config.json)")
            
            # Create lockfile
            os.makedirs(os.path.dirname(self.rl_training_lockfile), exist_ok=True)
            with open(self.rl_training_lockfile, 'w') as f:
                f.write(json.dumps({
                    'started_at': datetime.now().isoformat(),
                    'training_count': training_count,
                    'data_months': data_months,
                    'restart_count': restart_count,
                    'resumed_from': os.path.basename(latest_checkpoint)
                }))
            
            # Prepare command with --resume flag
            python_cmd = sys.executable
            if os.path.exists('/.dockerenv') or os.getcwd() == '/app':
                python_cmd = 'python3.12'
            
            cmd = [
                python_cmd, 
                self.rl_trainer_file,
                '--timesteps', '200000',
                '--data-days', str(data_days),
                '--balance', '1000',
                '--leverage', '20',
                '--resume', latest_checkpoint  # RESUME FLAG
            ]
            
            logger.info(f"🧠 AUTO-RESTART Command: {' '.join(cmd)}")
            
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(__file__)
            )
            
            logger.info(f"🔄 RL Training restarted (PID: {process.pid}, restart #{restart_count})")
            
            # Save updated training info
            training_info['pid'] = process.pid
            training_info['status'] = 'running'
            training_info['last_restart'] = datetime.now(timezone.utc).isoformat()
            self._save_rl_training_info(training_info)
            
            # Monitor completion
            asyncio.create_task(self._monitor_rl_training_completion(process, training_info))
            
        except Exception as e:
            logger.error(f"❌ Failed to restart RL training: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            if os.path.exists(self.rl_training_lockfile):
                os.remove(self.rl_training_lockfile)
    
    async def _monitor_rl_training_completion(self, process, training_info):
        """Monitor RL training process and cleanup when done."""
        try:
            # Read initial stderr to catch early errors
            import select
            import threading
            
            def read_stderr():
                try:
                    if process.stderr:
                        for line in process.stderr:
                            if line:
                                logger.error(f"RL Training stderr: {line.strip()}")
                except Exception:
                    pass
            
            # Start stderr reader in background
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()
            
            while True:
                await asyncio.sleep(60)  # Check every minute
                
                # Check if process is still running
                poll = process.poll()
                if poll is not None:
                    # Process finished
                    if poll == 0:
                        logger.info(f"✅ RL Training completed successfully (Training #{training_info['training_count']})")
                        training_info['status'] = 'completed'
                    else:
                        logger.error(f"❌ RL Training failed with exit code {poll}")
                        # Try to read remaining stderr
                        try:
                            if process.stderr:
                                stderr_output = process.stderr.read()
                                if stderr_output:
                                    logger.error(f"RL Training error output: {stderr_output}")
                        except Exception:
                            pass
                        training_info['status'] = 'failed'
                    
                    training_info['completed_at'] = datetime.now().isoformat()
                    self._save_rl_training_info(training_info)
                    
                    # Remove lockfile
                    if os.path.exists(self.rl_training_lockfile):
                        os.remove(self.rl_training_lockfile)
                    
                    # Reset training started flag
                    self._rl_training_started = False
                    
                    # Update stats with completed training info
                    if poll == 0:  # Success
                        next_training = datetime.now() + timedelta(days=self.rl_training_interval_days)
                        self._update_rl_brain_stats_scheduled(next_training, training_info)
                    
                    break
                    
        except Exception as e:
            logger.error(f"Error monitoring RL training: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Reset flag on error
            self._rl_training_started = False
            if os.path.exists(self.rl_training_lockfile):
                os.remove(self.rl_training_lockfile)
    
    def _check_model_freshness_and_train(self):
        """
        Check if latest model is older than TRAINING_COOLDOWN (30 min).
        If yes, trigger immediate training at startup.
        """
        try:
            models_dir = "models"
            if not os.path.exists(models_dir):
                logger.warning("Models directory not found. Triggering immediate training.")
                # Trigger training immediately for first ticker
                if self.training_queue:
                    self.start_trainer_task(self.training_queue[0])
                    self.last_training_cycle_time = time.time()
                return
            
            # Find latest .pkl model file
            files = [os.path.join(models_dir, f) for f in os.listdir(models_dir) if f.endswith('.pkl')]
            if not files:
                logger.warning("No model files found. Triggering immediate training.")
                if self.training_queue:
                    self.start_trainer_task(self.training_queue[0])
                    self.last_training_cycle_time = time.time()
                return
            
            # Get modification time of latest model
            latest_model = max(files, key=os.path.getmtime)
            model_age = time.time() - os.path.getmtime(latest_model)
            
            if model_age > self.TRAINING_COOLDOWN:
                logger.warning(f"⚠️ Latest model is {model_age/60:.1f} minutes old (>{self.TRAINING_COOLDOWN/60:.0f} min threshold). Triggering immediate training.")
                if self.training_queue:
                    self.start_trainer_task(self.training_queue[0])
                    self.last_training_cycle_time = time.time()
            else:
                logger.info(f"✓ Model is fresh ({model_age/60:.1f} minutes old). Next training in {(self.TRAINING_COOLDOWN - model_age)/60:.1f} minutes.")
                # Set last_training_cycle_time to avoid immediate re-training
                self.last_training_cycle_time = time.time() - model_age
                
        except Exception as e:
            logger.error(f"Error checking model freshness: {e}")
            # On error, trigger training to be safe
            if self.training_queue:
                self.start_trainer_task(self.training_queue[0])
                self.last_training_cycle_time = time.time()

    def stop_all(self):
        logger.info("Stopping all processes...")
        self.is_running = False
        for name, p in self.processes.items():
            if p.is_alive():
                p.terminate()
                p.join()
        logger.info("All processes stopped.")

async def main():
    logger.info("Starting AI Crypto Pilot Supervisor (v4.5 - Titan Stack Async - PostgreSQL)...")

    # 1. Initialize database schema
    if not initialize_database_schema():
        logger.error("Cannot proceed without database. Exiting.")
        return

    # Small delay
    await asyncio.sleep(0.5)

    # 2. Start Database Queue Writer (Passthrough for compatibility)
    try:
        db_queue = get_db_queue()
        db_queue.start()
        logger.info("Database Interface initialized.")

        # Wait for fully initialize
        await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Failed to initialize database queue: {e}")
        return

    supervisor = AsyncSupervisor()

    # Handle Ctrl+C gracefully
    loop = asyncio.get_running_loop()
    stop_signal = asyncio.Event()

    def signal_handler():
        logger.info("Signal received. Shutting down...")
        stop_signal.set()
        supervisor.stop_all()

    # Register signal handlers if supported (Windows has limited signal support)
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        # Run monitor until signal
        monitor_task = asyncio.create_task(supervisor.monitor_processes())

        # Wait for stop signal (or just await monitor if no signal handler logic used)
        if sys.platform != "win32":
            await stop_signal.wait()
            monitor_task.cancel()
        else:
            # On Windows, just await monitor, Ctrl+C will raise KeyboardInterrupt/CancelledError
            await monitor_task

    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        # Fallback for Windows or direct run
        supervisor.stop_all()
    finally:
        # Shutdown database queue
        if 'db_queue' in locals():
            db_queue.stop()
            logger.info("Database Queue stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
