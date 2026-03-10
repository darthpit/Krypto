import logging
import pandas as pd
import numpy as np

class PerformanceTracker:
    """
    Component 6.1: Performance Tracker
    Tracks trade statistics to feed the Kelly Criterion Position Sizer.
    """

    def __init__(self, db):
        self.db = db

    def get_kelly_metrics(self, ticker, strategy):
        """
        Calculates Win Rate, Avg Win, Avg Loss for Kelly Criterion.
        Returns a dictionary with metrics.
        """
        try:
            # Fetch completed trades (SELLs) which have PnL recorded
            # We assume PnL is stored in 'pnl' column (absolute value) or we calculate it?
            # User specified: pnl_percent, outcome (WIN/LOSS)

            # We need pnl_percent. If 'trades' table has 'pnl' (absolute), we need cost to get percent.
            # trades table: action, amount, cost, pnl
            # pnl_percent = pnl / cost (approx for the sold portion)

            query = """
                SELECT pnl, cost, strategy, ticker
                FROM trades
                WHERE action = 'SELL' AND pnl != 0
            """
            rows = self.db.query(query)

            if not rows:
                return self._default_metrics()

            df = pd.DataFrame(rows, columns=['pnl', 'cost', 'strategy_col', 'ticker_col'])

            # Calculate PnL Percent
            # 'cost' in trades table for SELL is the Total Sale Value (Revenue).
            # We need Return on Investment (ROI) = PnL / Initial Investment.
            # Initial Investment = Sale Value - PnL (Gross).
            # Example: Buy 100, Sell 105, PnL 5. Cost(SellRow) = 105. Inv = 105 - 5 = 100. ROI = 5/100.

            def calculate_roi(row):
                investment = row['cost'] - row['pnl']
                if investment <= 0: return 0.0
                return row['pnl'] / investment

            df['pnl_percent'] = df.apply(calculate_roi, axis=1)

            # Filter for specific context
            # 1. Overall
            overall_stats = self._calculate_stats(df)

            # 2. Per Strategy
            strategy_stats = self._calculate_stats(df[df['strategy_col'] == strategy])

            # 3. Per Ticker
            ticker_stats = self._calculate_stats(df[df['ticker_col'] == ticker])

            return {
                "overall": overall_stats,
                "strategy": strategy_stats,
                "ticker": ticker_stats
            }

        except Exception as e:
            logging.error(f"PerformanceTracker Error: {e}")
            return self._default_metrics()

    def _calculate_stats(self, df):
        if df.empty:
            return None

        # Win/Loss
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        total_trades = len(df)
        win_count = len(wins)
        loss_count = len(losses)

        win_rate = win_count / total_trades if total_trades > 0 else 0
        loss_rate = 1.0 - win_rate

        # Avg Win % (e.g. 0.04 for 4%)
        avg_win = wins['pnl_percent'].mean() if not wins.empty else 0.0
        # Avg Loss % (should be positive number for formula? Formula: Kelly = W - (1-W)/R where R = AvgWin/AvgLoss)
        # User Formula: (Win Rate * Avg Win - Loss Rate * Avg Loss) / Avg Win
        # Here Avg Loss is likely absolute value in the formula context or negative?
        # User example: Avg Loss = -2%. Formula: (0.6 * 4 - 0.4 * 2) -> subtacting the loss part.
        # So Avg Loss should be treated as positive magnitude in the user's explicit formula structure:
        # Kelly % = (Win Rate × Avg Win - Loss Rate × Avg Loss) / Avg Win
        # If Avg Loss is 2% (0.02), then 0.4 * 0.02.

        avg_loss = abs(losses['pnl_percent'].mean()) if not losses.empty else 0.0

        # Kelly Calculation
        # Avoid division by zero
        kelly = 0.0
        if avg_win > 0:
             kelly = (win_rate * avg_win - loss_rate * avg_loss) / avg_win

        return {
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "kelly": kelly,
            "count": total_trades
        }

    def _default_metrics(self):
        return {
            "overall": None,
            "strategy": None,
            "ticker": None
        }
