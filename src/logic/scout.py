from src.utils.logger import log
import pandas as pd
import numpy as np
import datetime
import pandas_ta as ta
from src.utils.data_provider import MarketDataProvider


# Check for GPU acceleration
try:
    import cupy as cp
    HAS_CUPY = True
except ImportError:
    HAS_CUPY = False

class MatrixScout:
    def __init__(self, data_provider=None, tickers=None):
        self.data_provider = data_provider if data_provider else MarketDataProvider()
        # Initial default, but can be updated via fetch_top_assets
        self.tickers = tickers if tickers else ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'DOT/USDT', 'LINK/USDT']

        # Check if running under cudf.pandas
        self.is_gpu_pandas = 'cudf' in pd.__name__
        if self.is_gpu_pandas:
            log("MatrixScout: Running with cudf.pandas (GPU Acceleration ACTIVE)", "SUCCESS")
        elif HAS_CUPY:
             log("MatrixScout: CuPy detected but cudf.pandas not active. Partial GPU support.", "INFO")

    def fetch_top_assets(self, limit=50):
        """
        Fetches top assets by volume from the exchange to scale the matrix.
        Updates self.tickers with the new list.
        """
        hardcoded_top_10 = [
            'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT',
            'AVAX/USDT', 'LINK/USDT', 'MATIC/USDT', 'DOGE/USDT', 'DOT/USDT'
        ]
        try:
            log(f"MatrixScout: Fetching top {limit} assets by volume...", "INFO")
            if not self.data_provider.exchange:
                raise ValueError("Exchange not initialized")

            # Fetch all tickers
            tickers = self.data_provider.exchange.fetch_tickers()

            # Filter for USDT pairs and sort by quote volume
            usdt_pairs = []
            for symbol, data in tickers.items():
                if '/USDT' in symbol and data.get('quoteVolume'):
                    # Filter out unwanted tickers
                    if 'BTCDOM' in symbol or 'BTC.D' in symbol:
                        continue
                    usdt_pairs.append({
                        'symbol': symbol,
                        'volume': float(data['quoteVolume'])
                    })

            # Sort descending by volume
            usdt_pairs.sort(key=lambda x: x['volume'], reverse=True)

            # Take top N
            top_assets = [p['symbol'] for p in usdt_pairs[:limit]]

            if top_assets:
                self.tickers = top_assets
                log(f"MatrixScout: Updated tickers list with {len(self.tickers)} assets.", "SUCCESS")
            else:
                raise ValueError("Pusta lista tickerów od giełdy")

        except Exception as e:
            
            log(f"⚠️ Błąd pobierania Top rynków: {e}. Używam hardkodowanego TOP 10 (Fallback).", "WARNING")
            self.tickers = hardcoded_top_10

    def calculate_correlation_matrix(self):
        try:
            log("MatrixScout: Fetching data for correlation matrix...", "INFO")
            close_prices = {}

            # Limit to 50 just in case list is huge
            target_tickers = self.tickers[:50]

            for ticker in target_tickers:
                # Fetch 7 days of 1h data (approx 168 candles)
                # Using 4h candles might be faster/smoother for correlation: 7 days * 6 = 42 candles
                df = self.data_provider.fetch_candles(ticker, timeframe='1h', limit=168)
                if df is not None and not df.empty:
                    close_prices[ticker] = df['close']

            if not close_prices:
                log("MatrixScout: No data fetched.", "WARNING")
                return {}

            # Create DataFrame
            market_df = pd.DataFrame(close_prices)

            # Forward fill then drop na to align timestamps
            market_df.ffill(inplace=True)
            market_df.dropna(inplace=True)

            if market_df.empty:
                return {}

            # Correlation
            # With Titan Stack (cudf.pandas), this runs on GPU automatically
            corr_matrix = market_df.corr(method='pearson')

            # If using raw pandas but have cupy, we could accelerate here manually,
            # but cudf.pandas is preferred.

            # Convert to standard pandas for JSON serialization if it's a cudf DataFrame
            # cudf.pandas usually handles this transparently, but if we need to iterate rows:
            if hasattr(corr_matrix, 'to_pandas'):
                corr_matrix = corr_matrix.to_pandas()

            # --- APEXCHARTS SERIES TRANSFORMATION ---
            # Output format:
            # {
            #   "timestamp": "...",
            #   "series": [
            #       { "name": "BTC", "data": [ {"x": "ETH", "y": 0.95}, ... ] },
            #       ...
            #   ]
            # }

            heatmap_series = []

            # Iterate rows
            for row_ticker in corr_matrix.index:
                row_data = []
                for col_ticker in corr_matrix.columns:
                    val = corr_matrix.loc[row_ticker, col_ticker]
                    # ApexCharts expects x (category) and y (value)
                    row_data.append({
                        "x": col_ticker.split('/')[0], # Short name
                        "y": round(float(val), 2) # Ensure float
                    })

                heatmap_series.append({
                    "name": row_ticker.split('/')[0],
                    "data": row_data
                })

            output = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "series": heatmap_series
            }

            return output

        except Exception as e:
            log(f"MatrixScout Error: {e}", "ERROR")
            return {}

    def scan_correlations(self, ticker=None):
        return self.calculate_correlation_matrix()

class DeepScout:
    def __init__(self, data_provider=None, tickers=None):
        self.data_provider = data_provider if data_provider else MarketDataProvider()
        self.tickers = tickers if tickers else ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'DOT/USDT', 'LINK/USDT']

    def scan_market(self):
        try:
            log("DeepScout: Scanning market...", "INFO")
            gems = []

            for ticker in self.tickers:
                try:
                    df = self.data_provider.fetch_candles(ticker, timeframe='4h', limit=100)

                    # Validation check to prevent NoneType crash
                    if df is None or df.empty:
                        continue

                    # Indicators
                    # ADX
                    adx_df = ta.adx(df['high'], df['low'], df['close'])
                    adx = adx_df['ADX_14'].iloc[-1] if adx_df is not None and 'ADX_14' in adx_df.columns else 0
                    pos_di = adx_df['DMP_14'].iloc[-1] if adx_df is not None and 'DMP_14' in adx_df.columns else 0
                    neg_di = adx_df['DMN_14'].iloc[-1] if adx_df is not None and 'DMN_14' in adx_df.columns else 0

                    # Sanitize ADX
                    if np.isnan(adx) or np.isinf(adx): adx = 0
                    if np.isnan(pos_di) or np.isinf(pos_di): pos_di = 0
                    if np.isnan(neg_di) or np.isinf(neg_di): neg_di = 0

                    # RSI
                    rsi_series = ta.rsi(df['close'])
                    rsi = rsi_series.iloc[-1] if rsi_series is not None and not rsi_series.empty else 0
                    if np.isnan(rsi) or np.isinf(rsi): rsi = 0

                    # Trend
                    trend = "NEUTRAL"
                    if adx > 25:
                        trend = "BULLISH" if pos_di > neg_di else "BEARISH"
                    else:
                        trend = "RANGE"

                    # Volatility (ATR / Price)
                    atr_series = ta.atr(df['high'], df['low'], df['close'])
                    atr = atr_series.iloc[-1] if atr_series is not None and not atr_series.empty else 0
                    price = df['close'].iloc[-1]
                    volatility = (atr / price) * 100 if price > 0 else 0

                    # Volume Change
                    vol_ma = df['volume'].rolling(20).mean().iloc[-1]
                    curr_vol = df['volume'].iloc[-1]
                    vol_status = "HIGH" if curr_vol > vol_ma * 1.5 else "NORMAL"

                    # Ensure all floats are valid
                    price = 0.0 if np.isnan(price) or np.isinf(price) else price
                    volatility = 0.0 if np.isnan(volatility) or np.isinf(volatility) else volatility

                    gems.append({
                        "ticker": ticker,
                        "price": float(price),
                        "trend": trend,
                        "adx": float(round(adx, 2)),
                        "rsi": float(round(rsi, 2)),
                        "volatility": float(round(volatility, 2)),
                        "volume": vol_status
                    })
                except Exception as e:
                    log(f"DeepScout Error while scanning {ticker}: {e}", "WARNING")
                    continue

            # --- WRAPPER TRANSFORMATION ---
            result = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "gems": gems
            }
            return result

        except Exception as e:
            log(f"DeepScout Error: {e}", "ERROR")
            return {"timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "gems": []}

    def scan_market_breadth(self):
        try:
            result = self.scan_market()
            gems = result.get('gems', [])
            bulls = sum(1 for g in gems if g['trend'] == 'BULLISH')
            bears = sum(1 for g in gems if g['trend'] == 'BEARISH')
            return {'bulls': bulls, 'bears': bears, 'total': len(gems), 'raw': gems}
        except Exception as e:
             log(f"DeepScout Breadth Error: {e}", "ERROR")
             return {'bulls': 0, 'bears': 0, 'total': 0, 'raw': []}
