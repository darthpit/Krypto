import pandas as pd
import numpy as np
import datetime
import json
import logging

# Configure local logger if not global
logger = logging.getLogger("PSNDEngine")

class PricePatternRecognizer:
    """
    Detects 12 classic candlestick patterns + 6 SMC patterns.
    """

    PATTERNS = {
        # Bullish Patterns
        'HAMMER': {'reliability': 0.72, 'min_body_ratio': 0.3},
        'MORNING_STAR': {'reliability': 0.78, 'confirmation_candles': 3},
        'BULLISH_ENGULFING': {'reliability': 0.63, 'volume_spike': 1.5},

        # Bearish Patterns
        'SHOOTING_STAR': {'reliability': 0.69, 'upper_shadow_ratio': 2.0},
        'EVENING_STAR': {'reliability': 0.75, 'confirmation_candles': 3},
        'BEARISH_ENGULFING': {'reliability': 0.66, 'volume_spike': 1.5},

        # SMC Patterns (Simplified Logic)
        'ORDER_BLOCK': {'reliability': 0.81, 'lookback': 20},
        'FAIR_VALUE_GAP': {'reliability': 0.68, 'min_gap_size': 0.002},
        'LIQUIDITY_SWEEP': {'reliability': 0.73, 'wick_extension': 0.015},
        'BREAK_OF_STRUCTURE': {'reliability': 0.77, 'swing_points': 3}
    }

    def analyze(self, candles: pd.DataFrame) -> dict:
        """
        Returns:
        {
            'pattern': 'MORNING_STAR',
            'reliability': 0.78,
            'direction': 'BULLISH',
            'confidence': 0.85,  # Adjusted by volume/context
            'invalidation_price': 45200.00
        }
        """
        if candles is None or len(candles) < 5:
            return {'pattern': 'NONE', 'direction': 'NEUTRAL', 'confidence': 0.0, 'reliability': 0.0}

        last = candles.iloc[-1]
        prev = candles.iloc[-2]
        prev2 = candles.iloc[-3]

        pattern_name = 'NONE'
        direction = 'NEUTRAL'
        reliability = 0.0

        # --- Classic Patterns ---

        # Hammer (Bullish) / Shooting Star (Bearish)
        body_size = abs(last['close'] - last['open'])
        candle_range = last['high'] - last['low']
        lower_wick = min(last['close'], last['open']) - last['low']
        upper_wick = last['high'] - max(last['close'], last['open'])

        if candle_range > 0:
            body_ratio = body_size / candle_range
            lower_wick_ratio = lower_wick / candle_range
            upper_wick_ratio = upper_wick / candle_range

            if body_ratio < 0.3 and lower_wick_ratio > 0.6 and upper_wick_ratio < 0.1:
                pattern_name = 'HAMMER'
                direction = 'BULLISH'
                reliability = self.PATTERNS['HAMMER']['reliability']
            elif body_ratio < 0.3 and upper_wick_ratio > 0.6 and lower_wick_ratio < 0.1:
                pattern_name = 'SHOOTING_STAR'
                direction = 'BEARISH'
                reliability = self.PATTERNS['SHOOTING_STAR']['reliability']

        # Engulfing
        if pattern_name == 'NONE':
            is_prev_red = prev['close'] < prev['open']
            is_curr_green = last['close'] > last['open']

            if is_prev_red and is_curr_green:
                if last['open'] <= prev['close'] and last['close'] >= prev['open']:
                    pattern_name = 'BULLISH_ENGULFING'
                    direction = 'BULLISH'
                    reliability = self.PATTERNS['BULLISH_ENGULFING']['reliability']

            is_prev_green = prev['close'] > prev['open']
            is_curr_red = last['close'] < last['open']

            if is_prev_green and is_curr_red:
                if last['open'] >= prev['close'] and last['close'] <= prev['open']:
                    pattern_name = 'BEARISH_ENGULFING'
                    direction = 'BEARISH'
                    reliability = self.PATTERNS['BEARISH_ENGULFING']['reliability']

        # Morning/Evening Star (3 candles)
        if pattern_name == 'NONE':
            # Morning Star: Red, Small, Green (closes > midpoint of Red)
            first_red = prev2['close'] < prev2['open']
            second_small = abs(prev['close'] - prev['open']) < abs(prev2['close'] - prev2['open']) * 0.5
            third_green = last['close'] > last['open']

            if first_red and second_small and third_green:
                midpoint = (prev2['open'] + prev2['close']) / 2
                if last['close'] > midpoint:
                    pattern_name = 'MORNING_STAR'
                    direction = 'BULLISH'
                    reliability = self.PATTERNS['MORNING_STAR']['reliability']

            # Evening Star: Green, Small, Red
            first_green = prev2['close'] > prev2['open']

            if first_green and second_small and not third_green: # Third red
                midpoint = (prev2['open'] + prev2['close']) / 2
                if last['close'] < midpoint:
                    pattern_name = 'EVENING_STAR'
                    direction = 'BEARISH'
                    reliability = self.PATTERNS['EVENING_STAR']['reliability']

        # --- SMC Patterns ---

        # 1. Order Block (Simplified Detection)
        # Bullish OB: Last bearish candle before a strong move up.
        # Bearish OB: Last bullish candle before a strong move down.
        # Priority: Check OB even if Engulfing was found, as OB is "stronger" signal.

        # Look for strong move in current candle
        range_len = last['high'] - last['low']
        is_strong_move = False
        if range_len > 0:
            is_strong_move = abs(last['close'] - last['open']) > range_len * 0.6

        if is_strong_move:
             # Bullish Impulsive Move
             if last['close'] > last['open']:
                  # Previous candle was bearish?
                  if prev['close'] < prev['open']:
                       # Override lower reliability patterns
                       if pattern_name == 'NONE' or reliability < self.PATTERNS['ORDER_BLOCK']['reliability']:
                           pattern_name = 'ORDER_BLOCK'
                           direction = 'BULLISH'
                           reliability = self.PATTERNS['ORDER_BLOCK']['reliability']

             # Bearish Impulsive Move
             elif last['close'] < last['open']:
                  # Previous candle was bullish?
                  if prev['close'] > prev['open']:
                       if pattern_name == 'NONE' or reliability < self.PATTERNS['ORDER_BLOCK']['reliability']:
                           pattern_name = 'ORDER_BLOCK'
                           direction = 'BEARISH'
                           reliability = self.PATTERNS['ORDER_BLOCK']['reliability']

        # 2. Fair Value Gap (FVG) detection
        # Bullish FVG: Low of candle 3 > High of candle 1 (sequence: prev2, prev, last)
        if pattern_name == 'NONE' or reliability < self.PATTERNS['FAIR_VALUE_GAP']['reliability']:
            if prev2['high'] < last['low']:
                 gap = last['low'] - prev2['high']
                 if gap > (last['close'] * self.PATTERNS['FAIR_VALUE_GAP']['min_gap_size']):
                     pattern_name = 'FAIR_VALUE_GAP' # Bullish
                     direction = 'BULLISH'
                     reliability = self.PATTERNS['FAIR_VALUE_GAP']['reliability']

            elif prev2['low'] > last['high']:
                 gap = prev2['low'] - last['high']
                 if gap > (last['close'] * self.PATTERNS['FAIR_VALUE_GAP']['min_gap_size']):
                     pattern_name = 'FAIR_VALUE_GAP' # Bearish
                     direction = 'BEARISH'
                     reliability = self.PATTERNS['FAIR_VALUE_GAP']['reliability']


        confidence = reliability
        # Volume boost if available
        if 'volume' in candles.columns:
            vol_ma = candles['volume'].rolling(20).mean().iloc[-1]
            if vol_ma > 0 and last['volume'] > vol_ma * 1.5:
                confidence = min(1.0, confidence * 1.2)

        return {
            'pattern': pattern_name,
            'reliability': reliability,
            'direction': direction,
            'confidence': confidence,
            'invalidation_price': last['low'] if direction == 'BULLISH' else last['high']
        }


class SentimentAnalyzer:
    """
    Aggregates data from Fear & Greed, Social Media, etc.
    Current implementation uses SIMULATION/PLACEHOLDERS as we lack API access.
    """

    def get_market_sentiment(self, ticker: str) -> dict:
        """
        Returns sentiment analysis dictionary.
        """
        fg_index = self._fetch_fear_greed()
        social = self._analyze_social_media(ticker)
        trends = self._get_google_trends(ticker)

        # Weighted composite
        # Convert FG (0-100) to (-1 to 1) for composite calc
        fg_normalized = (fg_index - 50) / 50.0

        composite = (
            fg_normalized * 0.4 +
            social * 0.35 +
            trends * 0.25
        )

        return {
            'fear_greed_index': fg_index,
            'social_score': social,
            'trend_score': trends,
            'composite_sentiment': composite,
            'signal': self._classify_sentiment(composite)
        }

    def _fetch_fear_greed(self):
        # Placeholder: Simulate or Return Neutral 50
        return 50

    def _analyze_social_media(self, ticker):
        # Placeholder: Return 0.0 (Neutral)
        return 0.0

    def _get_google_trends(self, ticker):
        # Placeholder
        return 0.0

    def _classify_sentiment(self, composite):
        if composite > 0.5: return 'EXTREME_GREED'
        if composite > 0.2: return 'GREED'
        if composite < -0.5: return 'EXTREME_FEAR'
        if composite < -0.2: return 'FEAR'
        return 'NEUTRAL'


class NewsImpactDetector:
    """
    Monitors CryptoPanic, CoinMarketCap, Twitter for critical keywords.
    """

    CRITICAL_KEYWORDS = {
        'NEGATIVE': ['sec', 'lawsuit', 'hack', 'exploit', 'rug pull',
                     'investigation', 'ban', 'delisting'],
        'POSITIVE': ['partnership', 'integration', 'launch', 'approval',
                     'listing', 'upgrade', 'burn']
    }

    def scan_news(self, ticker: str, lookback_minutes: int = 30) -> dict:
        """
        Returns news impact analysis.
        """
        # Placeholder: No real news API currently connected.
        return {'has_critical_news': False, 'impact_score': 0.0, 'articles': [], 'action': 'CONTINUE'}


class DivergenceDetector:
    """
    Detects divergences between Price and Indicators (RSI, Volume).
    """

    def detect_all(self, candles: pd.DataFrame) -> dict:
        rsi_div = self.detect_rsi_divergence(candles)
        vol_div = self.detect_volume_divergence(candles)

        # Composite score
        score = 0.0
        if rsi_div['type'] != 'NONE':
            score += rsi_div.get('strength', 0.5) * (1 if 'BULLISH' in rsi_div['type'] else -1)
        if vol_div['type'] != 'NONE':
             # Volume divergence usually indicates weakness of current trend
             if 'BEARISH' in vol_div['type']: score -= 0.3

        return {
            'rsi': rsi_div,
            'volume': vol_div,
            'composite_score': score
        }

    def detect_rsi_divergence(self, candles: pd.DataFrame) -> dict:
        """
        Regular Bullish: Price makes lower low, RSI makes higher low
        Regular Bearish: Price makes higher high, RSI makes lower high
        """
        if 'rsi' not in candles.columns:
             return {'type': 'NONE'}

        if len(candles) < 5: return {'type': 'NONE'}

        highs = candles['high'].values
        lows = candles['low'].values
        rsis = candles['rsi'].values

        # Simple local extrema detection
        # We need at least 5 points to detect a local peak/valley safely in the middle
        peaks = []
        valleys = []

        # Check from index 2 to len-3 (looking at i as center of 5 points: i-2, i-1, i, i+1, i+2)
        # Adjust range to be safe
        for i in range(2, len(candles) - 2):
            # Peak
            if highs[i] > highs[i-1] and highs[i] > highs[i+1] and highs[i] > highs[i-2] and highs[i] > highs[i+2]:
                 peaks.append(i)
            # Valley
            if lows[i] < lows[i-1] and lows[i] < lows[i+1] and lows[i] < lows[i-2] and lows[i] < lows[i+2]:
                 valleys.append(i)

        # Check Bearish Divergence (Higher High in Price, Lower High in RSI)
        # Compare last two peaks
        if len(peaks) >= 2:
            p2 = peaks[-1]
            p1 = peaks[-2]

            if highs[p2] > highs[p1]: # Higher High Price
                if rsis[p2] < rsis[p1]: # Lower High RSI
                     return {
                        'type': 'REGULAR_BEARISH_DIVERGENCE',
                        'strength': (highs[p2] - highs[p1]) / highs[p1] + (rsis[p1] - rsis[p2]) / 100,
                        'reliability': 0.65
                     }

        # Check Bullish Divergence (Lower Low in Price, Higher Low in RSI)
        if len(valleys) >= 2:
            v2 = valleys[-1]
            v1 = valleys[-2]

            if lows[v2] < lows[v1]: # Lower Low Price
                if rsis[v2] > rsis[v1]: # Higher Low RSI
                     return {
                        'type': 'REGULAR_BULLISH_DIVERGENCE',
                        'strength': (lows[v1] - lows[v2]) / lows[v1] + (rsis[v2] - rsis[v1]) / 100,
                        'reliability': 0.65
                     }

        return {'type': 'NONE'}

    def detect_volume_divergence(self, candles: pd.DataFrame) -> dict:
        """
        Price rising, volume falling = Weak uptrend (Bearish Divergence)
        """
        if 'volume' not in candles.columns or len(candles) < 20:
            return {'type': 'NONE'}

        # Calculate linear regression slope for last 20 candles
        try:
            price_slope = self._slope(candles['close'][-20:])
            vol_slope = self._slope(candles['volume'][-20:])

            if price_slope > 0.01 and vol_slope < -0.01:
                 return {
                    'type': 'BEARISH_VOLUME_DIVERGENCE',
                    'warning': 'Weak buying pressure',
                    'reliability': 0.61
                }
        except:
            pass

        return {'type': 'NONE'}

    def _slope(self, series):
        x = np.arange(len(series))
        y = series.values
        if len(x) != len(y): return 0
        return np.polyfit(x, y, 1)[0]


class PSNDEngine:
    """
    Central Market Intelligence Unit (Pattern, Sentiment, News, Divergence).
    """

    def __init__(self):
        self.ppr = PricePatternRecognizer()
        self.sa = SentimentAnalyzer()
        self.nid = NewsImpactDetector()
        self.ds = DivergenceDetector()

    def analyze(self, ticker: str, candles: pd.DataFrame) -> dict:
        """
        Returns a comprehensive market assessment.
        """
        # 1. Check News (DISABLED / BYPASSED)
        # news = self.nid.scan_news(ticker)
        
        # Tworzymy atrapę (Dummy Object), aby kod niżej się nie zepsuł
        news = {'action': 'NONE', 'impact_score': 0.0}

        # 2. Pattern Analysis
        pattern = self.ppr.analyze(candles)

        # 3. Sentiment
        sentiment = self.sa.get_market_sentiment(ticker)

        # 4. Divergence
        divergence = self.ds.detect_all(candles)

        # 5. Weighted Decision Score
        pat_dir = 1 if pattern['direction'] == 'BULLISH' else (-1 if pattern['direction'] == 'BEARISH' else 0)

        score = (
            (pat_dir * pattern['confidence']) * 0.50 +
            sentiment['composite_sentiment'] * 0.25 +
            divergence['composite_score'] * 0.25
            # + news['impact_score'] * 0.0
        )

        return {
            'recommendation': self._classify_score(score),
            'confidence': abs(score),
            'components': {
                'pattern': pattern,
                'sentiment': sentiment,
                'divergence': divergence,
                'news': news
            }
        }

    def _classify_score(self, score):
        if score > 0.6: return 'STRONG_BUY'
        if score > 0.2: return 'BUY'
        if score < -0.6: return 'STRONG_SELL'
        if score < -0.2: return 'SELL'
        return 'NEUTRAL'
