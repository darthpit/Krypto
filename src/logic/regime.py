import pandas as pd
import pandas_ta as ta

class MarketRegime:
    def __init__(self):
        self.adx_threshold = 25

    def get_market_regime(self, df):
        """
        Determines market regime using ADX.
        Returns: 'TREND' or 'RANGE'.
        """
        if df.empty or len(df) < 14:
            return 'RANGE'

        try:
            # Check if ADX is already calculated
            if 'adx' not in df.columns:
                # Calculate ADX
                adx = ta.adx(df['high'], df['low'], df['close'], length=14)
                if adx is not None and not adx.empty:
                    # pandas_ta returns a DF with columns like ADX_14, DMP_14, DMN_14
                    # We need to find the ADX column
                    adx_col = [c for c in adx.columns if c.startswith('ADX')][0]
                    current_adx = adx[adx_col].iloc[-1]
                else:
                    current_adx = 0
            else:
                current_adx = df['adx'].iloc[-1]

            if current_adx > self.adx_threshold:
                return 'TREND'
            else:
                return 'RANGE'

        except Exception as e:
            # Default to RANGE on error
            return 'RANGE'
