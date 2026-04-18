import logging
import pandas as pd
from src.logic.performance_tracker import PerformanceTracker

class PositionSizer:
    """
    Risk-Based Position Sizer.
    Calculates exact trade size strictly risking 2% of the base capital.
    Stop Loss (SL) is always calculated dynamically as 2 * ATR.
    """

    def __init__(self, db, risk_oracle=None):
        self.db = db
        self.risk_oracle = risk_oracle
        self.tracker = PerformanceTracker(db)
        self.risk_percentage = 0.02  # Exact 2% Risk

    def calculate_size(self, ticker, capital, current_price, atr, side, confidence_score=0.5, volatility_score=1.0):
        """
        Returns the safe trade amount in USD.
        Wielkość pozycji obliczaj wzorem: Position Size = (Portfel * 0.02) / (Cena Wejścia - Cena SL)
        """
        try:
            risk_amount = capital * self.risk_percentage
            
            # SL is strictly 2 * ATR
            sl_distance = 2.0 * atr

            if side == "LONG":
                sl_price = current_price - sl_distance
                price_diff = current_price - sl_price
            elif side == "SHORT":
                sl_price = current_price + sl_distance
                price_diff = sl_price - current_price
            else:
                logging.warning(f"[{ticker}] Unknown side {side}. Skipping.")
                return 0.0

            if price_diff <= 0:
                 logging.warning(f"[{ticker}] Invalid price diff for Risk-Based Sizing. SL distance is {sl_distance}.")
                 return 0.0
                 
            # Calculating Position Size (Base Asset Amount)
            position_amount_asset = risk_amount / price_diff
            
            # Position Size in USD (Notional Value)
            position_size_usd = position_amount_asset * current_price

            if position_size_usd < 10: 
                position_size_usd = 0.0 # Min dust

            return position_size_usd

        except Exception as e:
            logging.error(f"PositionSizer Error: {e}")
            return 0.0
