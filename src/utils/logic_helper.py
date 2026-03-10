import pandas as pd

def calculate_condition_score(current_price, sma20, regime, fvg_equilibrium=None):
    """
    Calculates a 0-100 score representing how close the asset is to a transaction condition.
    """
    score = 0
    try:
        if regime == 'TREND':
            # Trend Condition: Price > SMA20
            # If Price == SMA20, score = 50.
            # If Price > SMA20 by 1%, score = 75.
            # If Price > SMA20 by 2%, score = 100.
            if sma20 > 0:
                diff_pct = (current_price - sma20) / sma20
                # Scale: -1% -> 25, 0% -> 50, +1% -> 75, +2% -> 100
                score = 50 + (diff_pct * 100 * 25)

        elif regime == 'RANGE':
            # Range Condition: Price close to Equilibrium
            if fvg_equilibrium and fvg_equilibrium > 0:
                # Distance from Eq
                dist_pct = abs(current_price - fvg_equilibrium) / fvg_equilibrium
                # If dist = 0, score = 100.
                # If dist = 1%, score = 50.
                # If dist = 2%, score = 0.
                score = 100 - (dist_pct * 100 * 50)
            else:
                score = 50 # Neutral if no FVG

        else:
            score = 0 # Unknown regime

        # Clamp 0-100
        return int(max(0, min(100, score)))

    except Exception:
        return 0
