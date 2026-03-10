import pandas as pd
import pandas_ta as ta
import numpy as np
import logging

logger = logging.getLogger("MultiTimeframe")

class TrendClassifier:
    """
    Component 5.1: Determines the trend for a single timeframe using 3 voting methods.
    """
    def __init__(self):
        self.min_consensus = 2 # Need 2 out of 3 votes

    def analyze(self, df: pd.DataFrame) -> str:
        """
        Returns 'BULLISH', 'BEARISH', or 'NEUTRAL'.
        """
        if df is None or len(df) < 50:
            return "NEUTRAL"

        votes = []

        # Method A: SMA Crossover (20 vs 50)
        votes.append(self._check_sma(df))

        # Method B: Price Action (Structure)
        votes.append(self._check_price_action(df))

        # Method C: ADX + DI
        votes.append(self._check_adx(df))

        # Tally votes
        bullish_votes = votes.count("BULLISH")
        bearish_votes = votes.count("BEARISH")

        if bullish_votes >= self.min_consensus:
            return "BULLISH"
        elif bearish_votes >= self.min_consensus:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def _check_sma(self, df: pd.DataFrame) -> str:
        try:
            # SMA 20 vs 50
            sma20 = ta.sma(df['close'], length=20)
            sma50 = ta.sma(df['close'], length=50)

            if sma20 is None or sma50 is None: return "NEUTRAL"

            last_close = df['close'].iloc[-1]
            s20 = sma20.iloc[-1]
            s50 = sma50.iloc[-1]

            # Bullish: Close > SMA20 > SMA50
            if last_close > s20 > s50:
                return "BULLISH"
            # Bearish: Close < SMA20 < SMA50
            elif last_close < s20 < s50:
                return "BEARISH"

            return "NEUTRAL"
        except Exception:
            return "NEUTRAL"

    def _check_price_action(self, df: pd.DataFrame) -> str:
        """
        Detects Higher Highs + Higher Lows (Bullish) or Lower Highs + Lower Lows (Bearish).
        Uses a simple pivot detection on the last 30 candles.
        """
        try:
            window = 5 # Local window for pivots
            subset = df.iloc[-40:].copy() # Look at recent history
            if len(subset) < 10: return "NEUTRAL"

            highs = subset['high'].values
            lows = subset['low'].values

            # Simple local extrema
            # We look for peaks and valleys
            peaks = []
            valleys = []

            for i in range(window, len(subset) - window):
                is_peak = True
                is_valley = True
                for j in range(1, window + 1):
                    if highs[i] <= highs[i-j] or highs[i] <= highs[i+j]: is_peak = False
                    if lows[i] >= lows[i-j] or lows[i] >= lows[i+j]: is_valley = False

                if is_peak: peaks.append(highs[i])
                if is_valley: valleys.append(lows[i])

            # Check Structure
            if len(peaks) >= 2 and len(valleys) >= 2:
                last_2_peaks = peaks[-2:]
                last_2_valleys = valleys[-2:]

                # Bullish: HH + HL
                if last_2_peaks[1] > last_2_peaks[0] and last_2_valleys[1] > last_2_valleys[0]:
                    return "BULLISH"

                # Bearish: LH + LL
                if last_2_peaks[1] < last_2_peaks[0] and last_2_valleys[1] < last_2_valleys[0]:
                    return "BEARISH"

            return "NEUTRAL"
        except Exception:
            return "NEUTRAL"

    def _check_adx(self, df: pd.DataFrame) -> str:
        try:
            # ADX 14
            adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
            if adx_df is None or adx_df.empty: return "NEUTRAL"

            # Columns usually: ADX_14, DMP_14 (Plus), DMN_14 (Minus)
            # Find exact col names
            adx_col = [c for c in adx_df.columns if c.startswith('ADX')][0]
            dmp_col = [c for c in adx_df.columns if c.startswith('DMP')][0]
            dmn_col = [c for c in adx_df.columns if c.startswith('DMN')][0]

            adx = adx_df[adx_col].iloc[-1]
            dmp = adx_df[dmp_col].iloc[-1]
            dmn = adx_df[dmn_col].iloc[-1]

            if adx > 25:
                if dmp > dmn: return "BULLISH"
                if dmn > dmp: return "BEARISH"

            return "NEUTRAL"
        except Exception:
            return "NEUTRAL"


class MultiTimeframeSystem:
    """
    Component 5.2 - 5.4: Coordinates MTF Checks, Confluence Score, and Conflict Resolution.
    """

    # Hierarchy Weights
    WEIGHTS = {
        '4h': 25,
        '1h': 30,
        '15m': 20,
        '5m': 15,
        '1m': 10
    }

    def __init__(self):
        self.classifier = TrendClassifier()

    def validate_signal(self, ticker: str, signal_direction: str, data_provider, psnd_analysis: dict) -> dict:
        """
        Main Entry Point.
        Fetches data for all timeframes, calculates score, and applies logic.

        signal_direction: "BUY" or "SELL"
        """

        # 1. Fetch & Analyze Timeframes
        # We assume 1m/5m might be partially cached or cheap, but we fetch all fresh to be safe.
        # To optimize, we could pass the 1m DF if already available, but let's keep it clean first.

        timeframes = ['1m', '5m', '15m', '1h', '4h']
        trends = {}

        for tf in timeframes:
            df = data_provider.fetch_candles(ticker, timeframe=tf, limit=100)
            if df is not None:
                trends[tf] = self.classifier.analyze(df)
            else:
                trends[tf] = "NEUTRAL" # Fail safe

        # 2. Calculate Confluence Score
        score = 0
        max_score = 100

        target = "BULLISH" if signal_direction == "BUY" else "BEARISH"

        details = {}

        for tf, weight in self.WEIGHTS.items():
            trend = trends.get(tf, "NEUTRAL")
            contribution = 0

            if trend == target:
                contribution = weight
            elif trend == "NEUTRAL":
                contribution = weight / 2 # Partial credit for non-conflict?
                # Or 0? User example said 15m NEUTRAL (20%) -> +10%. So half credit.
                contribution = weight * 0.5

            score += contribution
            details[tf] = trend

        # 3. Apply Logic Rules (Component 5.2)
        decision = "REJECT"
        size_mult = 0.0

        if score < 50:
            decision = "REJECT_LOW_SCORE"
        elif 50 <= score < 70:
            decision = "WEAK_ALIGNMENT"
            size_mult = 0.5
        elif 70 <= score < 85:
            decision = "GOOD_ALIGNMENT"
            size_mult = 1.0
        else:
            decision = "PERFECT_SETUP"
            size_mult = 1.2

        # 4. Conflict Resolution (Component 5.3) - The Veto
        # Rule: 4h and 1h oppose signal -> AUTOMATIC REJECT
        opposing = "BEARISH" if target == "BULLISH" else "BULLISH"

        veto_active = False
        if trends.get('4h') == opposing and trends.get('1h') == opposing:
            veto_active = True
            decision = "REJECT_MAJOR_TREND_CONFLICT"
            size_mult = 0.0

        # 5. Reversal Exception Logic
        # If Vetoed, check if we can override based on PSND
        is_reversal = False

        if veto_active:
            # Check PSND for Reversal Signs
            # Needs: Bullish Divergence (if BUY) OR Extreme Fear (if BUY)
            # Needs: Bearish Divergence (if SELL) OR Extreme Greed (if SELL)

            can_counter_trade = False
            reversal_reason = ""

            sentiment = psnd_analysis.get('components', {}).get('sentiment', {})
            divergence = psnd_analysis.get('components', {}).get('divergence', {})
            pattern = psnd_analysis.get('components', {}).get('pattern', {})

            if signal_direction == "BUY":
                # Look for Bullish Reversal signs
                if "BULLISH" in divergence.get('rsi', {}).get('type', ''):
                    can_counter_trade = True
                    reversal_reason = "RSI_BULL_DIV"
                elif sentiment.get('signal') == 'EXTREME_FEAR':
                    can_counter_trade = True
                    reversal_reason = "EXTREME_FEAR"
                elif pattern.get('pattern') == 'MORNING_STAR':
                    can_counter_trade = True
                    reversal_reason = "MORNING_STAR_4H" # Ideally we check pattern timeframe, assuming PSND runs on current context (often 1h or 4h?)
                    # Note: PSND usually runs on the 'main' context provided to it. If TraderProcess passes 1m data, this checks 1m.
                    # Ideally we want 4h patterns. But let's use what we have.

            elif signal_direction == "SELL":
                if "BEARISH" in divergence.get('rsi', {}).get('type', ''):
                    can_counter_trade = True
                    reversal_reason = "RSI_BEAR_DIV"
                elif sentiment.get('signal') == 'EXTREME_GREED':
                    can_counter_trade = True
                    reversal_reason = "EXTREME_GREED"

            if can_counter_trade:
                decision = "COUNTER_TREND_REVERSAL"
                size_mult = 0.3 # Reduced size
                veto_active = False # Lift veto

        # 6. Timeframe Divergence Alert (Component 5.4)
        # Low TF Bullish vs High TF Bearish (Scalp against tide)

        sl_mult = 1.0
        tp_mult = 1.0

        if trends.get('4h') == opposing and decision not in ["REJECT_MAJOR_TREND_CONFLICT", "REJECT_LOW_SCORE", "COUNTER_TREND_REVERSAL"]:
             # We are trading against 4H (but 1H might be neutral or supportive enough to pass score)
             sl_mult = 0.5 # Tighter SL (e.g. 1.5% instead of 3%)
             tp_mult = 0.4 # Closer TP (Scalp)
             decision = "SCALP_AGAINST_TREND"

        elif decision == "COUNTER_TREND_REVERSAL":
             # Reversal Logic: Higher Risk/Reward
             tp_mult = 1.5

        return {
            "decision": decision,
            "score": score,
            "size_mult": size_mult,
            "sl_mult": sl_mult,
            "tp_mult": tp_mult,
            "details": details,
            "veto": veto_active,
            "reversal": is_reversal
        }
