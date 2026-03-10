import logging
import pandas as pd
from src.logic.performance_tracker import PerformanceTracker

class PositionSizer:
    """
    Module 6: Kelly Criterion Position Sizer.
    Calculates optimal trade size based on historical performance and risk metrics.
    """

    def __init__(self, db, risk_oracle):
        self.db = db
        self.risk_oracle = risk_oracle
        self.tracker = PerformanceTracker(db)
        self.base_fraction = 0.25 # Default fractional Kelly (Quarter Kelly)

    def calculate_size(self, ticker, strategy, capital, current_price, confidence_score=0.5, volatility_score=1.0):
        """
        Returns the safe trade amount in USD.
        """
        try:
            # 1. Get Kelly Metrics
            metrics = self.tracker.get_kelly_metrics(ticker, strategy)

            # Decision Hierarchy for Kelly Source:
            # 1. Ticker specific (if enough data > 10 trades)
            # 2. Strategy specific (if enough data > 20 trades)
            # 3. Overall (if enough data > 30 trades)
            # 4. Fallback (Fixed Risk)

            selected_kelly = 0.0
            source = "FALLBACK"

            # Check Ticker
            if metrics['ticker'] and metrics['ticker']['count'] >= 10:
                selected_kelly = metrics['ticker']['kelly']
                source = "TICKER"
            # Check Strategy
            elif metrics['strategy'] and metrics['strategy']['count'] >= 20:
                selected_kelly = metrics['strategy']['kelly']
                source = "STRATEGY"
            # Check Overall
            elif metrics['overall'] and metrics['overall']['count'] >= 30:
                selected_kelly = metrics['overall']['kelly']
                source = "OVERALL"
            else:
                # Fallback: Use fixed % (e.g. 2% risk) or conservative "Blind Kelly"
                # If we have no data, we assume standard position size (e.g. 10% of equity)
                # But here we return a Kelly-like pct.
                # Let's return 0.10 (10%) as a baseline for new bots
                selected_kelly = 0.10
                source = "DEFAULT"

            # 2. Apply Limits
            if selected_kelly <= 0:
                logging.info(f"[{ticker}] Kelly suggests 0% allocation (Negative Edge). Skipping.")
                return 0.0

            # Cap Kelly at 50% max to prevent ruin even if formula says 90%
            if selected_kelly > 0.50:
                selected_kelly = 0.50

            # 3. Fractional Scaling (Component 6.2)
            fraction = self.base_fraction

            # Adapt to Confidence (PSND Score / AI Confidence)
            # If confidence > 70%, increase fraction
            if confidence_score > 0.7:
                fraction += 0.10 # 0.35
            elif confidence_score < 0.4:
                fraction -= 0.10 # 0.15

            # 4. Drawdown Adjustment (Component 6.4)
            # Access RiskOracle state
            # We assume risk_oracle has updated metrics
            # We can't easily access internal state if not exposed, but we can query DB or assume passed param
            # Or use risk_oracle public methods.
            # RiskOracle stores state in DB.

            # Approximation based on Oracle Status
            if self.risk_oracle.is_recovery_mode():
                fraction *= 0.5 # Reduce by half in recovery

            # 5. Final Calculation
            kelly_pct = selected_kelly * fraction
            position_size_usd = capital * kelly_pct

            # Volatility Adjustment (Safety)
            position_size_usd *= volatility_score

            # Min/Max Limits
            if position_size_usd < 10: position_size_usd = 0.0 # Min dust

            # Log decision
            # logging.info(f"[{ticker}] Kelly Sizer ({source}): Raw={selected_kelly:.2f}, Frac={fraction:.2f}, FinalUSD={position_size_usd:.2f}")

            return position_size_usd

        except Exception as e:
            logging.error(f"PositionSizer Error: {e}")
            # Fallback safe size
            return min(capital * 0.05, 100.0)
