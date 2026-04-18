import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.utils.logger import log

class MarketMemory:
    def __init__(self, db, lookback_days=180, lookahead=30, atr_period=14, risk_multiplier=2.0):
        self.db = db
        self.lookback_days = lookback_days
        self.lookahead = lookahead
        self.atr_period = atr_period
        self.risk_multiplier = risk_multiplier
        self.last_update = None
        self.memory_df = None

    def _fetch_data(self, ticker, timeframe):
        date_threshold = (datetime.utcnow() - timedelta(days=self.lookback_days)).strftime('%Y-%m-%d %H:%M:%S')
        tables_to_try = ['candles', 'market_data']
        df = None

        for table in tables_to_try:
            query = f"""
                SELECT timestamp, open, high, low, close
                FROM {table}
                WHERE ticker = '{ticker}'
                AND timeframe = '{timeframe}'
                AND timestamp >= '{date_threshold}'
                ORDER BY timestamp ASC
            """
            try:
                rows = self.db.query(query)
                if rows and len(rows) > 0:
                    df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close'])
                    break
            except Exception:
                continue

        if df is None or df.empty:
            log(f"MarketMemory: No historical data found for {ticker} ({timeframe})", "WARNING")
            return None

        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    def _calculate_memory(self, df):
        df['prev_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=self.atr_period).mean()

        # Oczekiwane MAE to najgłębsze cofnięcie PRZED osiągnięciem MFE
        # Do tego musimy najpierw znaleźć indeks MFE

        # Funkcja pomocnicza do obliczania MAE i MFE na przód
        def calc_excursions(series):
            # Zwracamy tablicę z Max_Long_Move, Max_Short_Move, Max_Long_Adverse, Max_Short_Adverse
            res = np.full((len(series), 4), np.nan)
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values

            for i in range(len(series) - self.lookahead):
                future_highs = highs[i+1 : i+1+self.lookahead]
                future_lows = lows[i+1 : i+1+self.lookahead]

                # MFE/MAE dla LONG
                max_high_idx = np.argmax(future_highs)
                # Szukamy najniższego punktu przed osiągnięciem maksymalnego szczytu
                if max_high_idx > 0:
                    min_before_max = np.min(future_lows[:max_high_idx+1])
                else:
                    min_before_max = future_lows[0]

                res[i, 0] = future_highs[max_high_idx] - closes[i] # Max_Long_Move
                res[i, 2] = closes[i] - min_before_max # Max_Long_Adverse (ile cofnęło PRZED szczytem)

                # MFE/MAE dla SHORT
                min_low_idx = np.argmin(future_lows)
                if min_low_idx > 0:
                    max_before_min = np.max(future_highs[:min_low_idx+1])
                else:
                    max_before_min = future_highs[0]

                res[i, 1] = closes[i] - future_lows[min_low_idx] # Max_Short_Move
                res[i, 3] = max_before_min - closes[i] # Max_Short_Adverse (ile cofnęło PRZED dołkiem)

            return res

        excursions = calc_excursions(df)
        df['Max_Long_Move'] = excursions[:, 0]
        df['Max_Short_Move'] = excursions[:, 1]
        df['Max_Long_Adverse'] = excursions[:, 2]
        df['Max_Short_Adverse'] = excursions[:, 3]

        # Obliczenie momentum (ROC - Rate of Change) do filtrowania podobnych środowisk
        df['ROC_14'] = df['close'].pct_change(periods=14) * 100

        # Obliczenie pseudo-wolumenu SMA
        if 'volume' in df.columns:
            df['Volume_SMA'] = df['volume'].rolling(window=14).mean()
            df['Volume_Ratio'] = df['volume'] / df['Volume_SMA']
        else:
            df['Volume_Ratio'] = 1.0

        return df.dropna().copy()

    def update_memory(self, ticker, timeframe):
        now = datetime.utcnow()
        if self.last_update and self.memory_df is not None and (now - self.last_update) < timedelta(hours=6):
            return self.memory_df

        log(f"MarketMemory: Syncing 180-day market memory for {ticker} ({timeframe})...", "INFO")
        df = self._fetch_data(ticker, timeframe)
        if df is not None:
            self.memory_df = self._calculate_memory(df)
            self.last_update = now
            log(f"MarketMemory: Memory synced successfully. Analyzed {len(self.memory_df)} candles.", "INFO")
        return self.memory_df

    def get_expected_excursions(self, ticker, timeframe, current_atr, signal, current_roc=None, current_vol_ratio=None):
        """
        Zwraca MFE (Średni Zysk) i MAE (Średnia Strata) na podstawie historii.
        Poszukuje momentów w historii, gdzie ATR było podobne (np. +/- 20%).
        Dodatkowo filtruje po zbliżonym momentum (ROC) i strukturze wolumenu (Volume Ratio).
        """
        self.update_memory(ticker, timeframe)
        if self.memory_df is None or self.memory_df.empty:
            return None, None

        df = self.memory_df

        # Filtracja wielowymiarowa
        mask = (df['ATR'] >= current_atr * 0.8) & (df['ATR'] <= current_atr * 1.2)

        if current_roc is not None and not np.isnan(current_roc):
            roc_std = df['ROC_14'].std() or 1.0
            # Odchylenie ROC w granicach 1 odchylenia standardowego
            mask &= (df['ROC_14'] >= current_roc - roc_std) & (df['ROC_14'] <= current_roc + roc_std)

        if current_vol_ratio is not None and not np.isnan(current_vol_ratio):
            # Volume ratio w granicach +/- 30%
            mask &= (df['Volume_Ratio'] >= current_vol_ratio * 0.7) & (df['Volume_Ratio'] <= current_vol_ratio * 1.3)

        similar_env = df[mask]

        if similar_env.empty:
            # Fallback to all data if no exact match
            similar_env = df

        if signal == "LONG":
            mfe = similar_env['Max_Long_Move'].mean()
            # Prawdziwe, historyczne MAE
            historical_mae = similar_env['Max_Long_Adverse'].mean()
            # Mniejsza wartość - rynek albo utnie stratę (SL), albo rynek cofnął się mniej
            mae = min(historical_mae, current_atr * self.risk_multiplier)
        elif signal == "SHORT":
            mfe = similar_env['Max_Short_Move'].mean()
            # Prawdziwe, historyczne MAE
            historical_mae = similar_env['Max_Short_Adverse'].mean()
            # Mniejsza wartość - rynek albo utnie stratę (SL), albo rynek cofnął się mniej
            mae = min(historical_mae, current_atr * self.risk_multiplier)
        else:
            return 0.0, 0.0

        return mfe, mae
