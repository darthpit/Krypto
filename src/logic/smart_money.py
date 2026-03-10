import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("SmartMoney")

class SmartMoneyTracker:
    def __init__(self, db, data_provider):
        self.db = db
        self.data_provider = data_provider
        # self.btc_dominance_ticker = "BTCDOM/USDT"
        # BTCDOM/USDT removed as per configuration update to avoid exchange errors

    def check_btc_dominance(self):
        """
        Component 3.1: BTC Dominance Gate.
        Fetches BTCDOM ticker and evaluates the 24h change.

        DISABLED: Returns NEUTRAL to avoid errors with BTCDOM/USDT pairs.
        """
        return {
            'status': 'NEUTRAL',
            'change_24h': 0.0,
            'message': "BTC Dominance check disabled",
            'multiplier': 1.0
        }

    def calculate_vwap_metrics(self, candles_df):
        """
        Component 3.2: VWAP Analysis (Triple Confirmation).
        Calculates Rolling VWAP for 1h, 4h, and 1d windows.

        Args:
            candles_df (pd.DataFrame): Must have 'close', 'high', 'low', 'volume', datetime index.

        Returns:
            dict: {
                'vwap_1h': float,
                'vwap_4h': float,
                'vwap_1d': float,
                'price': float,
                'signal': 'BULLISH' | 'BEARISH' | 'NEUTRAL'
            }
        """
        if candles_df is None or candles_df.empty:
            return None

        try:
            df = candles_df.copy()

            # Calculate Typical Price
            df['tp'] = (df['high'] + df['low'] + df['close']) / 3
            df['pv'] = df['tp'] * df['volume']

            # Ensure index is sorted
            df = df.sort_index()

            vwap_1h = 0.0
            vwap_4h = 0.0
            vwap_1d = 0.0

            # Ensure DateTime Index for time-based rolling
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                else:
                    # Fallback to integer rolling if no datetime available (Assuming 1m data)
                    vwap_1h = (df['pv'].rolling(window=60).sum() / df['volume'].rolling(window=60).sum()).iloc[-1]
                    vwap_4h = (df['pv'].rolling(window=240).sum() / df['volume'].rolling(window=240).sum()).iloc[-1]
                    vwap_1d = (df['pv'].rolling(window=1440).sum() / df['volume'].rolling(window=1440).sum()).iloc[-1]
            else:
                # Time Based Rolling
                vwap_1h = (df['pv'].rolling('1h').sum() / df['volume'].rolling('1h').sum()).iloc[-1]
                vwap_4h = (df['pv'].rolling('4h').sum() / df['volume'].rolling('4h').sum()).iloc[-1]
                vwap_1d = (df['pv'].rolling('1d').sum() / df['volume'].rolling('1d').sum()).iloc[-1]

            current_price = df['close'].iloc[-1]

            # Triple Confirmation Logic
            # Price > ALL VWAPS -> BULLISH
            # Price < ALL VWAPS -> BEARISH
            signal = "NEUTRAL"
            if current_price > vwap_1h and current_price > vwap_4h and current_price > vwap_1d:
                signal = "BULLISH"
            elif current_price < vwap_1h and current_price < vwap_4h and current_price < vwap_1d:
                signal = "BEARISH"

            return {
                'vwap_1h': vwap_1h,
                'vwap_4h': vwap_4h,
                'vwap_1d': vwap_1d,
                'price': current_price,
                'signal': signal
            }

        except Exception as e:
            logger.error(f"Error calculating VWAP: {e}")
            return None

    def analyze_institutional_flow(self, ticker):
        """
        Component 3.3: Institutional Order Flow Detection.
        Analyzes Order Book, Tape (Trades), and Iceberg Orders.
        """
        try:
            # 1. Fetch Order Book
            ob = self.data_provider.fetch_order_book(ticker, limit=50)
            if not ob:
                return {'score': 0, 'signal': 'NEUTRAL'}

            bids = ob['bids'] # [[price, amount], ...]
            asks = ob['asks']

            bid_vol = sum([p * a for p, a in bids])
            ask_vol = sum([p * a for p, a in asks])

            # Bid-Ask Imbalance
            imbalance_ratio = bid_vol / (ask_vol + 1e-9) # Avoid div/0

            # 2. Fetch Recent Trades (Tape)
            trades = self.data_provider.fetch_trades(ticker, limit=100)
            large_buy_vol = 0
            large_sell_vol = 0
            iceberg_score = 0

            whale_threshold = 100000 # $100k threshold (Updated per spec)

            if trades:
                # Analyze for Whales
                for t in trades:
                    cost = t['price'] * t['amount']
                    if cost > whale_threshold:
                        if t['side'] == 'buy':
                            large_buy_vol += cost
                        else:
                            large_sell_vol += cost

                # Analyze for Icebergs (Repeated identical size orders)
                # Group by amount and count occurrences
                amounts = [t['amount'] for t in trades]
                from collections import Counter
                counts = Counter(amounts)

                # Check if any amount appears > 10 times
                detected_icebergs = {k: v for k, v in counts.items() if v >= 10}

                if detected_icebergs:
                    # Determine direction of icebergs (are they buys or sells?)
                    # Simplified: if we have icebergs, assume institutional presence
                    # We can check the side of these iceberg trades
                    iceberg_buys = 0
                    iceberg_sells = 0
                    for t in trades:
                        if t['amount'] in detected_icebergs:
                            if t['side'] == 'buy': iceberg_buys += 1
                            else: iceberg_sells += 1

                    if iceberg_buys > iceberg_sells:
                        iceberg_score = 2 # Hidden Buying
                        logger.info(f"[{ticker}] ICEBERG BUY DETECTED: {len(detected_icebergs)} clusters")
                    elif iceberg_sells > iceberg_buys:
                        iceberg_score = -2 # Hidden Selling
                        logger.info(f"[{ticker}] ICEBERG SELL DETECTED: {len(detected_icebergs)} clusters")


            # 3. Scoring
            flow_signal = "NEUTRAL"
            score = 0

            # Imbalance Logic
            if imbalance_ratio > 1.5: # 50% more bids
                score += 1
            elif imbalance_ratio < 0.6:
                score -= 1

            # Whale Tape Logic
            if large_buy_vol > large_sell_vol * 1.5:
                score += 2
            elif large_sell_vol > large_buy_vol * 1.5:
                score -= 2

            # Add Iceberg Score
            score += iceberg_score

            if score >= 2:
                flow_signal = "BULLISH"
            elif score <= -2:
                flow_signal = "BEARISH"

            return {
                'signal': flow_signal,
                'score': score,
                'bid_vol': bid_vol,
                'ask_vol': ask_vol,
                'whale_buys': large_buy_vol,
                'whale_sells': large_sell_vol,
                'iceberg_detected': bool(iceberg_score != 0)
            }

        except Exception as e:
            logger.error(f"Error analyzing flow for {ticker}: {e}")
            return {'score': 0, 'signal': 'NEUTRAL'}
