import pandas as pd

class SMCAnalyzer:
    def __init__(self):
        pass

    def scan_fvgs(self, df, lookback=10):
        """
        Scans for Bullish and Bearish Fair Value Gaps (FVG) in the last N candles.
        Returns a list of FVG dictionaries.
        """
        if len(df) < lookback + 3:
            return []

        # We look at completed candles mostly, but user might pass live data.
        # Assuming df includes the current (potentially developing) candle at -1.
        # We scan history up to the previous completed candle to find *formed* FVGs.

        fvgs = []

        # Iterate backwards
        # i is the index of the middle candle of the 3-candle pattern
        # Range: from len(df)-2 (last closed candle as C3) down to ...

        # Let's verify indices:
        # i = current candle index.
        # Pattern: [i-2, i-1, i] -> Gap is between i-2 and i.

        # Iterating `i` as the 3rd candle (the one that confirms the gap or not)
        # We need `i-2` to exist.

        for i in range(len(df) - 1, 2, -1):
            if len(fvgs) >= 5: # Limit to recent ones
                break

            c1 = df.iloc[i-2] # Left
            c2 = df.iloc[i-1] # Middle (Impulse)
            c3 = df.iloc[i]   # Right (Confirmation/Current)

            # Skip if older than lookback
            if (len(df) - i) > lookback:
                break

            # Bullish FVG
            # C2 is Green (mostly). Gap: C1 High < C3 Low
            if c1['high'] < c3['low']:
                # The gap is the empty space
                gap_size = c3['low'] - c1['high']
                # Filter tiny gaps? For now, no.
                fvgs.append({
                    "type": "BULLISH",
                    "top": c3['low'],
                    "bottom": c1['high'],
                    "equilibrium": (c3['low'] + c1['high']) / 2,
                    "index": i-1,
                    "timestamp": c2.name if hasattr(c2, 'name') else None
                })

            # Bearish FVG
            # Gap: C1 Low > C3 High
            elif c1['low'] > c3['high']:
                gap_size = c1['low'] - c3['high']
                fvgs.append({
                    "type": "BEARISH",
                    "top": c1['low'],
                    "bottom": c3['high'],
                    "equilibrium": (c1['low'] + c3['high']) / 2,
                    "index": i-1,
                    "timestamp": c2.name if hasattr(c2, 'name') else None
                })

        return fvgs

    def get_fvg_equilibrium(self, fvg_data):
        """
        Helper to get the middle price of a gap.
        Accepts an FVG dictionary.
        """
        if not fvg_data:
            return 0.0
        return fvg_data.get('equilibrium', (fvg_data['top'] + fvg_data['bottom']) / 2)
