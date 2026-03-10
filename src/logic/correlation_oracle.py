import pandas as pd
import numpy as np
import time
import logging
from src.database import Database
from src.utils.data_provider import MarketDataProvider

# Configure logger
logger = logging.getLogger("CorrelationOracle")

class CorrelationOracle:
    """
    Module 8: Correlation Decay Checker
    Validates 'Catch Up' strategies by analyzing multi-period correlation stability and fundamental divergence.
    """

    def __init__(self, db: Database, data_provider: MarketDataProvider):
        self.db = db
        self.data_provider = data_provider

    def validate_catch_up_trade(self, target_ticker: str, leader_ticker: str, psnd_analysis_target: dict = None, psnd_analysis_leader: dict = None) -> dict:
        """
        Validates if target_ticker should theoretically 'catch up' to leader_ticker.
        Returns: {'valid': Bool, 'modifier': float, 'reason': str}
        """
        try:
            # Step 1: Multi-Period Correlation
            corr_score, corr_details = self._calculate_multi_period_correlation(target_ticker, leader_ticker)

            if corr_score < 0.70:
                return {'valid': False, 'reason': f"Correlation too weak ({corr_score:.2f})", 'modifier': 0.0}

            modifier = 1.0
            if corr_score < 0.85:
                modifier = 0.5 # Moderate correlation, reduce size

            # Step 2: Stability Check
            is_stable, std_dev = self._check_stability(target_ticker, leader_ticker)
            if not is_stable:
                return {'valid': False, 'reason': f"Correlation Unstable (StdDev {std_dev:.2f})", 'modifier': 0.0}

            # Step 3: Fundamental Divergence
            # Check if one has news and the other doesn't
            if psnd_analysis_target and psnd_analysis_leader:
                div_check = self._check_fundamental_divergence(psnd_analysis_target, psnd_analysis_leader)
                if not div_check['safe']:
                    return {'valid': False, 'reason': f"Fundamental Divergence: {div_check['reason']}", 'modifier': 0.0}

            # Step 4: Lag Analysis
            lag_check = self._analyze_lag(target_ticker, leader_ticker)
            if lag_check['abnormal']:
                modifier *= 0.7 # Reduce further
                return {'valid': True, 'reason': "Abnormal Lag Detected (Caution)", 'modifier': modifier, 'tight_sl': True}

            return {'valid': True, 'reason': "Correlation Valid", 'modifier': modifier}

        except Exception as e:
            logger.error(f"Correlation validation error: {e}")
            return {'valid': False, 'reason': "Error in Validation", 'modifier': 0.0}

    def _calculate_multi_period_correlation(self, t1: str, t2: str) -> tuple:
        """
        Calculates weighted average of 7d, 30d, 90d correlations.
        Weights: 7d (0.3), 30d (0.4), 90d (0.3)
        """
        # Fetch data: 90 days of 4h candles = 540 candles (approx)
        # Using 4h candles is efficient for long term correlation
        limit = 540
        df1 = self.data_provider.fetch_candles(t1, timeframe='4h', limit=limit)
        df2 = self.data_provider.fetch_candles(t2, timeframe='4h', limit=limit)

        if df1 is None or df2 is None or df1.empty or df2.empty:
            return 0.0, {}

        # Align Data
        # Rename close to ticker name to avoid collision
        s1 = df1['close'].rename(t1)
        s2 = df2['close'].rename(t2)

        combined = pd.concat([s1, s2], axis=1).dropna()

        if len(combined) < 50:
            return 0.0, {} # Not enough data

        # Calculate periods (assuming 4h candles)
        # 7 days = 42 candles
        # 30 days = 180 candles
        # 90 days = 540 candles

        c7 = combined.tail(42).corr().iloc[0, 1]
        c30 = combined.tail(180).corr().iloc[0, 1]
        c90 = combined.corr().iloc[0, 1] # Full set (approx 90d)

        weighted_avg = (c7 * 0.3) + (c30 * 0.4) + (c90 * 0.3)

        # Log to DB for history
        self._log_correlation(t1, t2, '7d', c7)
        self._log_correlation(t1, t2, '30d', c30)
        self._log_correlation(t1, t2, '90d', c90)

        return weighted_avg, {'7d': c7, '30d': c30, '90d': c90}

    def _check_stability(self, t1: str, t2: str) -> tuple:
        """
        Calculates rolling correlation std dev over last 30 days.
        """
        # We need daily correlation snapshots or rolling correlation on 4h candles
        # Let's use the same data fetch strategy but maybe reuse cached data if possible
        # For simplicity, we assume we have the 'combined' df from prev step, but here we re-fetch to keep method pure
        # or we accept DF as arg. Optimally we accept DFs.
        # But for now, let's just do a simpler check:
        # Retrieve stored history from DB if available!

        # Check 'correlation_matrix_history' for '7d' entries over last 30 days
        query = """
            SELECT correlation FROM correlation_matrix_history
            WHERE ticker_a = ? AND ticker_b = ? AND period = '7d'
            AND timestamp > ?
            ORDER BY timestamp ASC
        """
        # We store ordered pairs usually (A < B) or duplicate.
        # Let's try both orders
        t_a, t_b = sorted((t1, t2))

        start_ts = int(time.time()) - (30 * 24 * 3600)
        rows = self.db.query(query, (t_a, t_b, start_ts))

        corrs = [r[0] for r in rows]

        if len(corrs) < 5:
            # Not enough history, default to True (Pass) but log warning?
            # Or calculate from raw data if needed.
            return True, 0.0

        std_dev = np.std(corrs)
        if std_dev > 0.25:
            return False, std_dev

        return True, std_dev

    def _check_fundamental_divergence(self, p1: dict, p2: dict) -> dict:
        """
        Checks if one asset has critical news/events that the other doesn't.
        """
        # Extract News Impact
        # Assuming PSND result structure: {'components': {'news': {'impact_score': ...}}}
        n1 = p1.get('components', {}).get('news', {}).get('impact_score', 0)
        n2 = p2.get('components', {}).get('news', {}).get('impact_score', 0)

        # If difference in impact is high (> 0.5)
        if abs(n1 - n2) > 0.5:
            return {'safe': False, 'reason': f"News Impact Divergence ({n1} vs {n2})"}

        return {'safe': True}

    def _analyze_lag(self, t1: str, t2: str) -> dict:
        """
        Checks if current lag is abnormal.
        """
        # This is complex to calculate accurately without high-res data.
        # Simple heuristic:
        # If t2 (Leader) moved > 5% in last 4h, and t1 (Target) moved < 1% in last 4h + 2h...
        # We need to know typical lag.
        # Placeholder for now: Returns normal.
        return {'abnormal': False}

    def _log_correlation(self, t1, t2, period, value):
        try:
            t_a, t_b = sorted((t1, t2))
            self.db.execute(
                "INSERT INTO correlation_matrix_history (ticker_a, ticker_b, period, correlation, timestamp) VALUES (?, ?, ?, ?, ?) ON CONFLICT (ticker_a, ticker_b, period, timestamp) DO UPDATE SET correlation=EXCLUDED.correlation",
                (t_a, t_b, period, value, int(time.time()))
            )
        except Exception:
            pass
