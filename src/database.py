import psycopg2
from psycopg2 import pool, extras
import os
import threading
import json
import logging
import datetime
import time
import random
import traceback
from contextlib import contextmanager

# Optional Redis support
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class Database:
    """
    PostgreSQL Database wrapper.
    Replaces the previous SQLite implementation.
    """
    _instance = None
    _lock = threading.RLock()
    _pool = None
    _pid = None

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            current_pid = os.getpid()
            if cls._instance is None or cls._pid != current_pid:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance._initialized = False
                cls._pid = current_pid
        return cls._instance

    def __init__(self, db_path=None, use_queue=False):
        """
        db_path and use_queue are kept for compatibility with existing calls,
        but are largely ignored/unused for PostgreSQL implementation.
        """
        if self._initialized:
            return

        self._use_queue = False # No need for queue in Postgres
        self.redis_client = None

        # Load config
        self.config = self._load_config()

        # Initialize Pool
        self._init_pool()

        # Redis Connection (Nervous System)
        if REDIS_AVAILABLE:
            self._connect_redis()

        # Ensure tables exist
        self.create_tables()

        self._initialized = True
        logging.info("PostgreSQL Database connection initialized.")

    def _load_config(self):
        try:
            # Assume config.json is in project root
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
            if not os.path.exists(config_path):
                config_path = 'config.json' # Fallback

            with open(config_path, 'r') as f:
                return json.load(f).get('database', {})
        except Exception as e:
            logging.error(f"Failed to load database config: {e}")
            return {}

    def _init_pool(self):
        try:
            db_config = self.config
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                host=db_config.get('host', 'localhost'),
                port=db_config.get('port', 5432),
                user=db_config.get('user', 'postgres'),
                password=db_config.get('password', 'password'),
                dbname=db_config.get('dbname', 'mexc_futures_db')
            )
        except Exception as e:
            logging.critical(f"Failed to create PostgreSQL connection pool: {e}")
            raise

    @contextmanager
    def _get_connection(self):
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def _connect_redis(self):
        """Initializes Redis connection."""
        try:
            host = os.environ.get("REDIS_HOST", "localhost")
            port = int(os.environ.get("REDIS_PORT", 6379))

            self.redis_client = redis.Redis(host=host, port=port, decode_responses=True, socket_connect_timeout=2)
            if self.redis_client.ping():
                logging.info(f"Redis connected at {host}:{port}")
        except Exception as e:
            logging.warning(f"Redis connection failed: {e}. Running without Redis.")
            self.redis_client = None

    def get_connection(self):
        """
        Returns a raw connection from the pool.
        IMPORTANT: User must return it to the pool manually using self._pool.putconn(conn).
        Prefer using internal execute/query methods.
        """
        return self._pool.getconn()

    def execute(self, query, params=(), max_retries=3):
        """
        Execute a query (INSERT, UPDATE, DELETE).
        Returns the cursor (useful for rowcount, etc).
        """
        # Intercept system_status inserts for Redis redirection
        if self.redis_client and "system_status" in query.lower() and "insert" in query.lower():
            self._handle_redis_status_update(query, params)

        # Handle placeholders: SQLite uses ?, Postgres uses %s
        query = query.replace('?', '%s')

        for attempt in range(max_retries):
            try:
                with self._get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(query, params)
                        conn.commit()
                        # We return a dummy cursor-like object because real cursor is closed
                        class MockCursor:
                            def __init__(self, lastrowid, rowcount):
                                self.lastrowid = lastrowid
                                self.rowcount = rowcount
                            def fetchall(self): return []
                            def fetchone(self): return None

                        # lastrowid is not readily available in Postgres unless RETURNING is used
                        # but some legacy code might expect it.
                        lastrowid = 0
                        # If INSERT and has RETURNING id, we can try to fetch it?
                        # But here we don't know.
                        # We rely on code not using lastrowid too critically or adapting code.
                        return MockCursor(lastrowid, cursor.rowcount)

            except psycopg2.OperationalError as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                logging.error(f"Database execution error: {e}")
                raise
            except Exception as e:
                logging.error(f"Database execution error: {e} | Query: {query}")
                raise

    def query(self, query, params=(), max_retries=3):
        """
        Execute a query and return all results.
        ZMODYFIKOWANA WERSJA: Automatycznie naprawia symbol BTC/USDT:USDT -> BTC/USDT
        """
        # Intercept system_status reads for Redis
        if self.redis_client and "select value from system_status" in query.lower() and "key =" in query.lower():
            if params and len(params) > 0:
                key = params[0]
                cached_val = self.redis_client.get(f"status:{key}")
                if cached_val:
                    return [(cached_val,)]

        query = query.replace('?', '%s')

        # --- FIX START: Logika naprawy symbolu ---
        # Funkcja wewnętrzna do wykonania zapytania
        def run_query(q, p):
            for attempt in range(max_retries):
                try:
                    with self._get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(q, p)
                            return cursor.fetchall()
                except psycopg2.OperationalError as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    logging.error(f"Database query error: {e}")
                    raise
                except Exception as e:
                    logging.error(f"Database query error: {e} | Query: {q}")
                    raise
            return []
        
        # 1. Wykonaj normalne zapytanie
        results = run_query(query, params)

        # 2. Jeśli brak wyników, a szukaliśmy symbolu z końcówką :USDT (np. dla Futures)
        # Spróbuj znaleźć wersję bez sufiksu (np. BTC/USDT)
        if not results and params and len(params) > 0:
            symbol_candidate = params[0]
            if isinstance(symbol_candidate, str) and ":USDT" in symbol_candidate:
                clean_symbol = symbol_candidate.split(":")[0] # Zamienia BTC/USDT:USDT na BTC/USDT
                
                # Tworzymy nową listę parametrów z poprawionym symbolem
                new_params = list(params)
                new_params[0] = clean_symbol
                
                logging.info(f"⚠️ AUTO-FIX: Brak danych dla {symbol_candidate}. Próbuję pobrać dla {clean_symbol}...")
                results = run_query(query, tuple(new_params))
                
                if results:
                    logging.info(f"✅ AUTO-FIX: Znaleziono dane dla {clean_symbol}! Zwracam je jako {symbol_candidate}.")

        return results
        # --- FIX END ---

    def _handle_redis_status_update(self, query, params):
        """Redirect system_status writes to Redis for speed."""
        try:
            if len(params) >= 2:
                key, value = params[0], params[1]
                self.redis_client.set(f"status:{key}", value, ex=3600)  # 1 hour expiry
        except Exception as e:
            logging.warning(f"Redis write failed: {e}")

    def execute_many(self, query, params_list, batch_size=100):
        """
        Execute many queries in batches.
        """
        query = query.replace('?', '%s')
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                extras.execute_batch(cursor, query, params_list, page_size=batch_size)
                conn.commit()
                logging.info(f"Inserted {len(params_list)} records via execute_many")

    def close(self):
        """Close database pool"""
        if self._pool:
            self._pool.closeall()

    def create_tables(self):
        """Creates all necessary tables (PostgreSQL dialect)."""

        # SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
        # Postgres: SERIAL PRIMARY KEY or INTEGER GENERATED BY DEFAULT AS IDENTITY

        schemas = [
            """
            CREATE TABLE IF NOT EXISTS wallet_balances (
                currency TEXT PRIMARY KEY,
                amount DOUBLE PRECISION DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT,
                ticker TEXT,
                price DOUBLE PRECISION,
                amount DOUBLE PRECISION,
                cost DOUBLE PRECISION,
                fee DOUBLE PRECISION DEFAULT 0.0,
                pnl DOUBLE PRECISION DEFAULT 0.0,
                strategy TEXT,
                notes TEXT,
                raw_data TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                predicted_price DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                direction INTEGER,
                confidence DOUBLE PRECISION,
                result TEXT DEFAULT 'PENDING',
                model_version TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS active_strategies (
                ticker TEXT PRIMARY KEY,
                status TEXT DEFAULT 'ACTIVE',
                strategy_name TEXT,
                params TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS market_watch (
                ticker TEXT PRIMARY KEY,
                price DOUBLE PRECISION,
                change_24h DOUBLE PRECISION,
                volume_24h DOUBLE PRECISION,
                condition_score INTEGER DEFAULT 0,
                history_days INTEGER DEFAULT 0,
                management_action TEXT DEFAULT 'TRADE',
                status TEXT DEFAULT 'ACTIVE',
                reason TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS candles (
                ticker TEXT,
                timestamp TIMESTAMP,
                open DOUBLE PRECISION,
                high DOUBLE PRECISION,
                low DOUBLE PRECISION,
                close DOUBLE PRECISION,
                volume DOUBLE PRECISION,
                timeframe TEXT DEFAULT '15m',
                PRIMARY KEY (ticker, timestamp, timeframe)
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_candles_ticker_timestamp
            ON candles(ticker, timestamp DESC);
            """,
            """
            CREATE TABLE IF NOT EXISTS system_status (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS risk_monitoring (
                id SERIAL PRIMARY KEY,
                timestamp BIGINT,
                current_balance DOUBLE PRECISION,
                peak_balance DOUBLE PRECISION,
                drawdown_daily DOUBLE PRECISION,
                drawdown_weekly DOUBLE PRECISION,
                drawdown_monthly DOUBLE PRECISION,
                peak_drawdown DOUBLE PRECISION,
                volatility_index DOUBLE PRECISION,
                risk_level TEXT,
                recovery_mode INTEGER DEFAULT 0,
                active_constraints TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS institutional_flow (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                vwap_1h DOUBLE PRECISION,
                vwap_4h DOUBLE PRECISION,
                vwap_1d DOUBLE PRECISION,
                price_vs_vwap DOUBLE PRECISION,
                btc_dominance DOUBLE PRECISION,
                alt_season_index DOUBLE PRECISION,
                flow_signal TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS market_intelligence (
                ticker TEXT,
                timestamp BIGINT,
                pattern_type TEXT,
                pattern_confidence DOUBLE PRECISION,
                sentiment_score DOUBLE PRECISION,
                fear_greed_index INTEGER,
                news_impact DOUBLE PRECISION,
                divergence_type TEXT,
                composite_psnd_score DOUBLE PRECISION,
                PRIMARY KEY (ticker, timestamp)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS trade_history (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                strategy TEXT,
                entry_time BIGINT,
                exit_time BIGINT,
                entry_price DOUBLE PRECISION,
                exit_price DOUBLE PRECISION,
                pnl_percent DOUBLE PRECISION,
                outcome TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS kelly_stats (
                strategy TEXT PRIMARY KEY,
                win_rate DOUBLE PRECISION,
                avg_win DOUBLE PRECISION,
                avg_loss DOUBLE PRECISION,
                kelly_percent DOUBLE PRECISION,
                last_updated BIGINT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS emotion_events (
                ticker TEXT,
                timestamp BIGINT,
                event_type TEXT,
                action_taken TEXT,
                cooldown_until BIGINT,
                PRIMARY KEY (ticker, timestamp)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS correlation_matrix_history (
                ticker_a TEXT,
                ticker_b TEXT,
                period TEXT,
                correlation DOUBLE PRECISION,
                timestamp BIGINT,
                PRIMARY KEY (ticker_a, ticker_b, period, timestamp)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS rl_predictions (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                timestamp TIMESTAMP,
                predicted_price DOUBLE PRECISION,
                actual_price DOUBLE PRECISION,
                hit BOOLEAN DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (ticker, timestamp)
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_rl_predictions_ticker_timestamp
            ON rl_predictions(ticker, timestamp DESC);
            """,
            """
            CREATE TABLE IF NOT EXISTS rl_brain_stats (
                id SERIAL PRIMARY KEY,
                training_status TEXT DEFAULT 'IDLE',
                total_accuracy DOUBLE PRECISION DEFAULT 0.0,
                total_hits INTEGER DEFAULT 0,
                total_misses INTEGER DEFAULT 0,
                last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                next_training_time TIMESTAMP,
                model_version TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        ]

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    for schema in schemas:
                        cursor.execute(schema)
                    conn.commit()

            logging.info("Database tables verified/created.")
            self.migrate_tables()

        except Exception as e:
            logging.error(f"Failed to create tables: {e}")
            # Do not raise here, allow app to try running

    def migrate_tables(self):
        """Checks for missing columns in existing tables and adds them."""
        # This implementation is simplified for now.
        # Checking information_schema.columns
        pass
