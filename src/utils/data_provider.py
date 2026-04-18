import ccxt
import pandas as pd
import time
import logging
import json
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - DATA_PROVIDER - %(levelname)s - %(message)s')

class MarketDataProvider:
    def __init__(self, config_path='config.json'):
        self.config = self._load_config(config_path)
        self.exchange = self._initialize_exchange()
        self.binance_exchange = self._initialize_binance()  # Binance for historical data

    def _load_config(self, path):
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return {}

    def _initialize_exchange(self):
        try:
            # Load config
            exchange_config = self.config.get('exchange', {})
            exchange_id = exchange_config.get('id', 'mexc')

            import os
            from dotenv import load_dotenv
            load_dotenv()

            api_key = exchange_config.get('api_key', None)
            if api_key == "ENV_MEXC_API_KEY":
                api_key = os.getenv('MEXC_API_KEY')

            secret = exchange_config.get('secret_key', None)
            if secret == "ENV_MEXC_API_SECRET":
                secret = os.getenv('MEXC_API_SECRET')

            # Initialize CCXT Class
            if not hasattr(ccxt, exchange_id):
                logging.error(f"Exchange {exchange_id} not found in ccxt.")
                return None

            exchange_class = getattr(ccxt, exchange_id)

            exchange_params = {
                'enableRateLimit': True,
                'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'options': {
                    'defaultType': 'swap', # Force Futures
                }
            }

            if api_key and secret:
                exchange_params['apiKey'] = api_key
                exchange_params['secret'] = secret

            exchange = exchange_class(exchange_params)

            # Load markets to ensure we can see the symbols
            # exchange.load_markets() # Can be slow on init, maybe do it lazily or here if needed.
            # Doing it here ensures 'swap' markets are loaded.
            try:
                exchange.load_markets()
            except Exception as e:
                logging.warning(f"Failed to load markets on init: {e}")

            return exchange
        except Exception as e:
            logging.error(f"Failed to initialize exchange: {e}")
            return None
    
    def _initialize_binance(self):
        """
        Initialize Binance exchange for historical data (180 days).
        MEXC limit: 30 days, so we use Binance for archival data.
        """
        try:
            binance_config = self.config.get('binance', {})
            api_key = binance_config.get('api_key', None)
            secret = binance_config.get('secret_key', None)
            
            if not api_key or not secret:
                logging.warning("⚠️ Binance API credentials not found in config. Historical data (>30 days) will not be available.")
                return None
            
            binance_params = {
                'enableRateLimit': True,
                'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'options': {
                    'defaultType': 'future',  # Binance Futures
                },
                'apiKey': api_key,
                'secret': secret
            }
            
            binance = ccxt.binance(binance_params)
            
            try:
                binance.load_markets()
                logging.info("✅ Binance exchange initialized for historical data (180 days)")
            except Exception as e:
                logging.warning(f"Failed to load Binance markets: {e}")
            
            return binance
            
        except Exception as e:
            logging.error(f"Failed to initialize Binance exchange: {e}")
            return None

    def fetch_ohlcv(self, ticker, timeframe='1m', since=None, limit=100):
        """
        Fetches OHLCV data with optional 'since' parameter.
        Returns DataFrame with index as datetime.
        
        Args:
            ticker: Trading pair (e.g., 'BTC/USDT:USDT' or 'BTC/USDT')
            timeframe: Candle timeframe (e.g., '1m', '5m', '1h')
            since: Start timestamp in milliseconds (optional)
            limit: Max number of candles (default 100, None = max available)
        """
        if not self.exchange:
            logging.error("Exchange not initialized.")
            return None

        # AUTO-FIX: MEXC Futures symbol format
        # Try multiple symbol formats for Futures compatibility
        symbols_to_try = [ticker]
        
        # If ticker has :USDT suffix, try without it first (MEXC format)
        if ':USDT' in ticker:
            base_symbol = ticker.split(':')[0]
            symbols_to_try = [base_symbol, ticker]  # Try BTC/USDT first, then BTC/USDT:USDT
        
        max_retries = 3
        last_error = None
        
        for symbol in symbols_to_try:
            for attempt in range(max_retries):
                try:
                    # CCXT returns: [timestamp, open, high, low, close, volume]
                    ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)

                    if not ohlcv:
                        logging.warning(f"No data returned for {symbol}")
                        last_error = f"No data for {symbol}"
                        break  # Try next symbol

                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)

                    # Ensure float types
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = df[col].astype(float)

                    if symbol != ticker:
                        logging.info(f"✅ AUTO-FIX: Fetched {symbol} instead of {ticker} (MEXC Futures format)")

                    return df

                except ccxt.NetworkError as e:
                    logging.warning(f"Network error fetching {symbol} (Attempt {attempt+1}/{max_retries}): {e}")
                    time.sleep(1 * (attempt + 1))
                    last_error = str(e)
                except ccxt.ExchangeError as e:
                    logging.warning(f"Exchange error fetching {symbol}: {e}")
                    last_error = str(e)
                    break  # Try next symbol
                except Exception as e:
                    logging.warning(f"Error fetching {symbol}: {e}")
                    last_error = str(e)
                    break  # Try next symbol
        
        # All attempts failed
        logging.error(f"Failed to fetch data for {ticker} (tried: {symbols_to_try}). Last error: {last_error}")
        return None
    
    def fetch_candles(self, ticker, timeframe='1m', limit=100):
        """
        Fetches OHLCV data (wrapper for backwards compatibility).
        Returns DataFrame with index as datetime.
        """
        return self.fetch_ohlcv(ticker, timeframe, since=None, limit=limit)
    
    def fetch_ticker(self, ticker):
        """
        Fetches current ticker data.
        """
        if not self.exchange:
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.exchange.fetch_ticker(ticker)
            except Exception as e:
                logging.warning(f"Error fetching ticker {ticker} (Attempt {attempt+1}): {e}")
                time.sleep(0.5 * (attempt + 1))

        return None

    def fetch_full_history(self, ticker, timeframe='15m', start_date='2020-01-01', limit=1000, callback=None, target_days=None):
        """
        Fetches full history since start_date.
        Invokes callback(df_chunk, progress_info) for each chunk.
        
        Args:
            ticker: Trading pair symbol
            timeframe: Candle timeframe (e.g., '1m', '15m', '1h')
            start_date: Start date for history fetch
            limit: Number of candles per API request
            callback: Callback function invoked for each chunk
            target_days: Target number of days to fetch (optional, for progress calculation)
        """
        if not self.exchange:
            logging.error("Exchange not initialized.")
            return

        # Convert start_date to timestamp ms
        since = int(pd.Timestamp(start_date).timestamp() * 1000)
        end_timestamp = int(pd.Timestamp.utcnow().timestamp() * 1000)
        
        total_fetched = 0
        chunk_count = 0
        failed_chunks = 0
        max_failed_chunks = 5  # Stop after 5 consecutive failures

        logging.info(f"{'='*80}")
        logging.info(f"📥 STARTING HISTORY SYNC: {ticker}")
        logging.info(f"{'='*80}")
        logging.info(f"📅 Start date: {start_date}")
        logging.info(f"📊 Timeframe: {timeframe}")
        logging.info(f"🎯 Target: {target_days} days" if target_days else "🎯 Target: Fetch until present")
        logging.info(f"📦 Chunk size: {limit} candles")
        logging.info(f"{'='*80}")

        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(ticker, timeframe, since=since, limit=limit)

                if not ohlcv:
                    logging.warning(f"⚠️ No data returned from API (attempt {failed_chunks + 1}/{max_failed_chunks})")
                    failed_chunks += 1
                    if failed_chunks >= max_failed_chunks:
                        logging.error(f"🚫 Stopped: {max_failed_chunks} consecutive empty responses from API")
                        break
                    time.sleep(5)
                    continue

                # Reset failed counter on success
                failed_chunks = 0
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)

                # Ensure float types
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)

                count = len(df)
                total_fetched += count
                chunk_count += 1

                # Update since for next batch (last timestamp + 1ms)
                last_ts = ohlcv[-1][0]
                since = last_ts + 1

                # Calculate progress
                current_date = df.index[-1]
                days_fetched = (current_date - pd.Timestamp(start_date)).days
                
                # Enhanced progress logging
                if target_days:
                    progress_pct = (days_fetched / target_days) * 100
                    remaining_days = max(0, target_days - days_fetched)
                    
                    # Log every 10 chunks with detailed progress
                    if chunk_count % 10 == 0:
                        logging.info(f"📊 Progress: {days_fetched}/{target_days} days ({progress_pct:.1f}%) | "
                                   f"Downloaded: {total_fetched:,} candles | "
                                   f"Remaining: {remaining_days} days | "
                                   f"Current date: {current_date.strftime('%Y-%m-%d')}")
                else:
                    # Log every 10 chunks without target
                    if chunk_count % 10 == 0:
                        logging.info(f"📊 Fetched: {days_fetched} days | "
                                   f"Total: {total_fetched:,} candles | "
                                   f"Current date: {current_date.strftime('%Y-%m-%d')}")

                if callback:
                    callback(df, {
                        'total_candles': total_fetched,
                        'current_date': current_date,
                        'days_fetched': days_fetched,
                        'target_days': target_days,
                        'progress_pct': (days_fetched / target_days * 100) if target_days else None
                    })

                # If we reached close to now, break
                if current_date > pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(minutes=5):
                    logging.info(f"✅ Reached current time. Sync complete!")
                    break
                
                # If we reached target days (with 1% margin), break
                if target_days and days_fetched >= target_days * 0.99:
                    logging.info(f"✅ Reached target of {target_days} days. Sync complete!")
                    break

                time.sleep(self.exchange.rateLimit / 1000 if self.exchange.rateLimit else 1)

            except ccxt.RateLimitExceeded as e:
                logging.warning(f"🚫 API Rate limit exceeded. Waiting 60 seconds...")
                time.sleep(60)
            except Exception as e:
                logging.error(f"❌ Error fetching history chunk {chunk_count}: {e}")
                failed_chunks += 1
                if failed_chunks >= max_failed_chunks:
                    logging.error(f"🚫 Stopped: {max_failed_chunks} consecutive errors")
                    break
                time.sleep(5)
        
        # Final summary
        logging.info(f"{'='*80}")
        logging.info(f"✅ HISTORY SYNC COMPLETE: {ticker}")
        logging.info(f"{'='*80}")
        logging.info(f"📊 Total candles: {total_fetched:,}")
        logging.info(f"📊 Total chunks: {chunk_count}")
        if target_days:
            final_days = total_fetched // (1440 // self._timeframe_to_minutes(timeframe))
            logging.info(f"📊 Days fetched: {final_days}/{target_days} ({final_days/target_days*100:.1f}%)")
        logging.info(f"{'='*80}")
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes."""
        units = {'m': 1, 'h': 60, 'd': 1440, 'w': 10080}
        return int(timeframe[:-1]) * units.get(timeframe[-1], 1)
    
    def fetch_dual_exchange_history(self, ticker, timeframe='1m', target_days=180, limit=1000, callback=None):
        """
        Intelligent dual-exchange data fetching strategy:
        - Binance: Historical data (older than 30 days) - up to 180 days
        - MEXC: Current data (last 30 days) - fresh live data
        
        This ensures:
        1. Maximum historical depth (180 days from Binance)
        2. Most accurate current data (30 days from MEXC where we trade)
        3. No gaps in data
        
        Args:
            ticker: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (e.g., '1m', '15m', '1h')
            target_days: Total days to fetch (default 180)
            limit: Number of candles per API request
            callback: Callback function invoked for each chunk
        """
        logging.info(f"{'='*80}")
        logging.info(f"🔄 DUAL-EXCHANGE DATA FETCH STRATEGY")
        logging.info(f"{'='*80}")
        logging.info(f"📊 Target: {target_days} days of {ticker} {timeframe} data")
        logging.info(f"🏦 Binance: Historical data (31-{target_days} days ago)")
        logging.info(f"🏦 MEXC: Current data (last 30 days)")
        logging.info(f"{'='*80}")
        
        # Calculate date boundaries (tz-naive to match exchange data)
        now = pd.Timestamp.utcnow().tz_localize(None)
        mexc_start = now - pd.Timedelta(days=30)
        binance_start = now - pd.Timedelta(days=target_days)
        binance_end = mexc_start
        
        total_candles_fetched = 0
        all_data = []
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1: BINANCE - Historical Data (31-180 days ago)
        # ═══════════════════════════════════════════════════════════════════
        if target_days > 30 and self.binance_exchange:
            logging.info(f"")
            logging.info(f"📥 PHASE 1: Fetching HISTORICAL data from Binance")
            logging.info(f"   Date range: {binance_start.strftime('%Y-%m-%d')} to {binance_end.strftime('%Y-%m-%d')}")
            logging.info(f"   Target: {target_days - 30} days")
            
            try:
                # Convert symbol format for Binance (BTC/USDT -> BTC/USDT:USDT for futures)
                binance_symbol = ticker if ':USDT' in ticker else f"{ticker}:USDT"
                
                since = int(binance_start.timestamp() * 1000)
                end_timestamp = int(binance_end.timestamp() * 1000)
                
                chunk_count = 0
                failed_chunks = 0
                max_failed_chunks = 5
                
                while since < end_timestamp:
                    try:
                        ohlcv = self.binance_exchange.fetch_ohlcv(binance_symbol, timeframe, since=since, limit=limit)
                        
                        if not ohlcv:
                            failed_chunks += 1
                            if failed_chunks >= max_failed_chunks:
                                logging.error(f"🚫 Binance: Stopped after {max_failed_chunks} consecutive failures")
                                break
                            time.sleep(5)
                            continue
                        
                        failed_chunks = 0
                        
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                        df.set_index('timestamp', inplace=True)
                        
                        for col in ['open', 'high', 'low', 'close', 'volume']:
                            df[col] = df[col].astype(float)
                        
                        all_data.append(df)
                        count = len(df)
                        total_candles_fetched += count
                        chunk_count += 1
                        
                        last_ts = ohlcv[-1][0]
                        since = last_ts + 1
                        
                        current_date = df.index[-1]
                        days_fetched = (current_date - binance_start).days
                        progress_pct = (days_fetched / (target_days - 30)) * 100
                        
                        if chunk_count % 10 == 0:
                            logging.info(f"   📊 Binance Progress: {days_fetched}/{target_days - 30} days ({progress_pct:.1f}%) | "
                                       f"Candles: {total_candles_fetched:,} | Date: {current_date.strftime('%Y-%m-%d')}")
                        
                        if callback:
                            callback(df, {
                                'source': 'binance',
                                'total_candles': total_candles_fetched,
                                'current_date': current_date,
                                'days_fetched': days_fetched,  # Days from binance_start
                                'target_days': target_days,    # Target days total
                                'progress_pct': progress_pct
                            })
                        
                        # Stop if we reached MEXC boundary
                        if current_date >= binance_end:
                            logging.info(f"   ✅ Binance: Reached 30-day boundary. Switching to MEXC...")
                            break
                        
                        time.sleep(self.binance_exchange.rateLimit / 1000 if self.binance_exchange.rateLimit else 1)
                    
                    except ccxt.RateLimitExceeded:
                        logging.warning(f"🚫 Binance: Rate limit exceeded. Waiting 60 seconds...")
                        time.sleep(60)
                    except Exception as e:
                        logging.error(f"❌ Binance: Error fetching chunk {chunk_count}: {e}")
                        failed_chunks += 1
                        if failed_chunks >= max_failed_chunks:
                            logging.error(f"🚫 Binance: Stopped after {max_failed_chunks} consecutive errors")
                            break
                        time.sleep(5)
                
                logging.info(f"   ✅ Binance Phase Complete: {total_candles_fetched:,} candles from historical period")
            
            except Exception as e:
                logging.error(f"❌ Failed to fetch Binance data: {e}")
                logging.warning(f"⚠️ Continuing with MEXC data only...")
        
        elif target_days > 30 and not self.binance_exchange:
            logging.warning(f"⚠️ Binance not configured. Can only fetch 30 days from MEXC.")
            logging.warning(f"   Add Binance API credentials to config.json for 180-day history.")
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2: MEXC - Current Data (Last 30 days)
        # ═══════════════════════════════════════════════════════════════════
        logging.info(f"")
        logging.info(f"📥 PHASE 2: Fetching CURRENT data from MEXC")
        logging.info(f"   Date range: {mexc_start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}")
        logging.info(f"   Target: 30 days (live trading data)")
        
        if not self.exchange:
            logging.error("❌ MEXC exchange not initialized!")
            return
        
        try:
            since = int(mexc_start.timestamp() * 1000)
            end_timestamp = int(now.timestamp() * 1000)
            
            chunk_count = 0
            failed_chunks = 0
            max_failed_chunks = 5
            mexc_candles = 0
            
            while since < end_timestamp:
                try:
                    # Try multiple symbol formats for MEXC
                    symbols_to_try = [ticker.split(':')[0] if ':' in ticker else ticker, ticker]
                    ohlcv = None
                    
                    for symbol in symbols_to_try:
                        try:
                            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
                            if ohlcv:
                                break
                        except:
                            continue
                    
                    if not ohlcv:
                        failed_chunks += 1
                        if failed_chunks >= max_failed_chunks:
                            logging.error(f"🚫 MEXC: Stopped after {max_failed_chunks} consecutive failures")
                            break
                        time.sleep(5)
                        continue
                    
                    failed_chunks = 0
                    
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)
                    
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = df[col].astype(float)
                    
                    all_data.append(df)
                    count = len(df)
                    mexc_candles += count
                    total_candles_fetched += count
                    chunk_count += 1
                    
                    last_ts = ohlcv[-1][0]
                    since = last_ts + 1
                    
                    current_date = df.index[-1]
                    # Calculate cumulative days_fetched from the very beginning (binance_start)
                    days_fetched_total = (current_date - binance_start).days
                    days_fetched_mexc = (current_date - mexc_start).days
                    progress_pct = (days_fetched_mexc / 30) * 100
                    
                    if chunk_count % 10 == 0:
                        logging.info(f"   📊 MEXC Progress: {days_fetched_mexc}/30 days ({progress_pct:.1f}%) | "
                                   f"Candles: {mexc_candles:,} | Date: {current_date.strftime('%Y-%m-%d')}")
                    
                    if callback:
                        callback(df, {
                            'source': 'mexc',
                            'total_candles': total_candles_fetched,
                            'current_date': current_date,
                            'days_fetched': days_fetched_total,  # Cumulative days for caller
                            'target_days': target_days,         # Total target for caller
                            'progress_pct': progress_pct
                        })
                    
                    # Stop if we reached present
                    if current_date >= now - pd.Timedelta(minutes=5):
                        logging.info(f"   ✅ MEXC: Reached current time.")
                        break
                    
                    time.sleep(self.exchange.rateLimit / 1000 if self.exchange.rateLimit else 1)
                
                except ccxt.RateLimitExceeded:
                    logging.warning(f"🚫 MEXC: Rate limit exceeded. Waiting 60 seconds...")
                    time.sleep(60)
                except Exception as e:
                    logging.error(f"❌ MEXC: Error fetching chunk {chunk_count}: {e}")
                    failed_chunks += 1
                    if failed_chunks >= max_failed_chunks:
                        logging.error(f"🚫 MEXC: Stopped after {max_failed_chunks} consecutive errors")
                        break
                    time.sleep(5)
            
            logging.info(f"   ✅ MEXC Phase Complete: {mexc_candles:,} candles from current period")
        
        except Exception as e:
            logging.error(f"❌ Failed to fetch MEXC data: {e}")
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 3: MERGE & SUMMARY
        # ═══════════════════════════════════════════════════════════════════
        logging.info(f"")
        logging.info(f"{'='*80}")
        logging.info(f"✅ DUAL-EXCHANGE FETCH COMPLETE")
        logging.info(f"{'='*80}")
        logging.info(f"📊 Total candles: {total_candles_fetched:,}")
        
        if all_data:
            # Merge all data
            merged_df = pd.concat(all_data)
            merged_df = merged_df[~merged_df.index.duplicated(keep='first')]  # Remove duplicates
            merged_df = merged_df.sort_index()  # Sort by timestamp
            
            actual_days = (merged_df.index[-1] - merged_df.index[0]).days
            coverage = (actual_days / target_days) * 100
            
            logging.info(f"📊 Date range: {merged_df.index[0].strftime('%Y-%m-%d')} to {merged_df.index[-1].strftime('%Y-%m-%d')}")
            logging.info(f"📊 Actual days: {actual_days} / {target_days} ({coverage:.1f}% coverage)")
            logging.info(f"📊 Data sources: Binance (historical) + MEXC (current)")
            logging.info(f"{'='*80}")
            
            return merged_df
        else:
            logging.error(f"❌ No data fetched from either exchange!")
            return None

    def fetch_trades(self, ticker, limit=100):
        if not self.exchange:
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.exchange.fetch_trades(ticker, limit=limit)
            except Exception as e:
                logging.warning(f"Error fetching trades {ticker} (Attempt {attempt+1}): {e}")
                time.sleep(0.5 * (attempt + 1))

        return None

    def fetch_order_book(self, ticker, limit=50):
        if not self.exchange:
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.exchange.fetch_order_book(ticker, limit=limit)
            except Exception as e:
                logging.warning(f"Error fetching order book {ticker} (Attempt {attempt+1}): {e}")
                time.sleep(0.5 * (attempt + 1))

        return None
    
    def fetch_funding_rate(self, ticker):
        """
        Fetch current funding rate for futures contract.
        
        CRITICAL for Futures Trading:
        - Positive rate: Longs pay shorts (Longs overcrowded → Potential SHORT)
        - Negative rate: Shorts pay longs (Shorts overcrowded → Potential LONG)
        
        Returns: dict with 'fundingRate' or None
        """
        if not self.exchange:
            logging.error("Exchange not initialized.")
            return None
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # CCXT standard method for futures funding rate
                funding = self.exchange.fetch_funding_rate(ticker)
                
                if funding and 'fundingRate' in funding:
                    logging.info(f"Funding Rate for {ticker}: {funding['fundingRate']:.6f}")
                    return funding
                
                return None
                
            except ccxt.NotSupported:
                logging.warning(f"Exchange does not support funding rates")
                return None
            except Exception as e:
                logging.warning(f"Error fetching funding rate {ticker} (Attempt {attempt+1}): {e}")
                time.sleep(0.5 * (attempt + 1))
        
        return None
    
    def fetch_funding_rate_history(self, ticker, limit=8):
        """
        Fetch funding rate history (last 8 periods for trend analysis).
        
        Returns: list of funding rates or None
        """
        if not self.exchange:
            return None
        
        try:
            # Try to fetch funding rate history
            history = self.exchange.fetch_funding_rate_history(ticker, limit=limit)
            
            if history:
                rates = [h.get('fundingRate', 0) for h in history]
                logging.info(f"Funding Rate History for {ticker}: {len(rates)} periods")
                return rates
            
            return None
            
        except ccxt.NotSupported:
            logging.debug(f"Exchange does not support funding rate history")
            return None
        except Exception as e:
            logging.warning(f"Error fetching funding rate history: {e}")
            return None

    def fetch_live_metrics(self, ticker):
        """
        Fetches live order flow metrics directly from Binance Futures endpoints.
        This provides real-time data for the AI when historical archives are delayed.
        
        Args:
            ticker: Trading pair symbol (e.g., 'BTC/USDT')
            
        Returns:
            dict: Current metrics {open_interest, oi_value_usdt, top_trader_ls_ratio, taker_buy_sell_ratio, timestamp}
        """
        import requests
        
        try:
            # Binance Futures uses symbols like 'BTCUSDT'
            symbol = ticker.replace('/', '').replace(':', '')
            if symbol.endswith('USDTUSDT'):
                symbol = symbol.replace('USDTUSDT', 'USDT')
                
            metrics = {
                'open_interest': 0.0,
                'oi_value_usdt': 0.0,
                'top_trader_ls_ratio': 1.0,
                'taker_buy_sell_ratio': 1.0,
                'timestamp': None
            }
            
            # Fetch Open Interest
            # GET /fapi/v1/openInterest
            try:
                oi_resp = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}", timeout=5)
                if oi_resp.status_code == 200:
                    oi_data = oi_resp.json()
                    metrics['open_interest'] = float(oi_data.get('openInterest', 0))
                    
                    # Also need current price to calculate oi_value_usdt
                    ticker_data = self.fetch_ticker(ticker)
                    if ticker_data and 'last' in ticker_data:
                        metrics['oi_value_usdt'] = metrics['open_interest'] * float(ticker_data['last'])
            except Exception as e:
                logging.warning(f"Error fetching live Open Interest: {e}")

            # Fetch Long/Short Ratio (Top Traders)
            # GET /futures/data/topLongShortAccountRatio
            try:
                ls_resp = requests.get(f"https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol={symbol}&period=5m&limit=1", timeout=5)
                if ls_resp.status_code == 200:
                    ls_data = ls_resp.json()
                    if ls_data and len(ls_data) > 0:
                        metrics['top_trader_ls_ratio'] = float(ls_data[0].get('longShortRatio', 1.0))
            except Exception as e:
                logging.warning(f"Error fetching live L/S Ratio: {e}")

            # Fetch Taker Buy/Sell Volume
            # GET /futures/data/takerbuySellVol
            try:
                taker_resp = requests.get(f"https://fapi.binance.com/futures/data/takerbuySellVol?symbol={symbol}&period=5m&limit=1", timeout=5)
                if taker_resp.status_code == 200:
                    taker_data = taker_resp.json()
                    if taker_data and len(taker_data) > 0:
                        buy_vol = float(taker_data[0].get('buyVol', 0))
                        sell_vol = float(taker_data[0].get('sellVol', 0))
                        
                        if sell_vol > 0:
                            metrics['taker_buy_sell_ratio'] = buy_vol / sell_vol
                        else:
                            metrics['taker_buy_sell_ratio'] = 1.0
            except Exception as e:
                logging.warning(f"Error fetching live Taker Buy/Sell Volume: {e}")
                
            # Set timestamp to current time (rounded down to minute)
            import datetime
            now_utc = datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0)
            metrics['timestamp'] = now_utc.isoformat()
            
            logging.info(f"✅ Fetched Live Metrics for {ticker}: OI={metrics['open_interest']}, L/S={metrics['top_trader_ls_ratio']:.2f}, Buy/Sell={metrics['taker_buy_sell_ratio']:.2f}")
            return metrics
            
        except Exception as e:
            logging.error(f"❌ Critical error in fetch_live_metrics: {e}")
            return None

    def save_live_metrics(self, ticker, metrics_dict, db):
        """
        Saves live metrics to the futures_metrics table with ON CONFLICT DO UPDATE.
        
        Args:
            ticker: Trading pair symbol (e.g., 'BTC/USDT')
            metrics_dict: Dictionary returned from fetch_live_metrics
            db: Database connection instance
        """
        if not metrics_dict or not db:
            return False
            
        try:
            # Use standardized ticker format for futures_metrics table
            standard_ticker = f"{ticker[:3]}/{ticker[4:]}" if 'USDT:USDT' in ticker else ticker
            
            query = """
                INSERT INTO futures_metrics 
                (ticker, timestamp, open_interest, oi_value_usdt, top_trader_ls_ratio, taker_buy_sell_ratio)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (ticker, timestamp) DO UPDATE 
                SET open_interest = EXCLUDED.open_interest,
                    oi_value_usdt = EXCLUDED.oi_value_usdt,
                    top_trader_ls_ratio = EXCLUDED.top_trader_ls_ratio,
                    taker_buy_sell_ratio = EXCLUDED.taker_buy_sell_ratio
            """
            
            db.execute(query, (
                standard_ticker,
                metrics_dict['timestamp'],
                float(metrics_dict['open_interest']),
                float(metrics_dict['oi_value_usdt']),
                float(metrics_dict['top_trader_ls_ratio']),
                float(metrics_dict['taker_buy_sell_ratio'])
            ))
            
            logging.debug(f"Saved live metrics to DB for {standard_ticker} at {metrics_dict['timestamp']}")
            return True
            
        except Exception as e:
            logging.error(f"Error saving live metrics to database: {e}")
            return False
