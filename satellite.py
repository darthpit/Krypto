import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import time
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from scipy.optimize import curve_fit

# PLIK WYNIKOWY
DATA_FILE = 'api/satellite_data.json'
UPDATE_INTERVAL_SECONDS = 1 * 24 * 60 * 60  # 1 Dzien (aktualizacja codzienna o 1:00 AM)

# DATY HALVINGÓW (Kluczowe dla cykli)
HALVING_DATES = ['2016-07-09', '2020-05-11', '2024-04-20']

def log_func(x, a, b):
    return a + b * np.log(x)

def run_satellite_analysis():
    print("[SATELITA] Uruchamianie procedury Satelita Crypto...")
    
    # 1. POBIERANIE DANYCH (1D)
    try:
        df = yf.download('BTC-USD', start='2015-01-01', interval='1d', progress=False)
        df = df.reset_index()
        # Fix dla yfinance multi-index
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
    except Exception as e:
        print(f"[ERROR] Blad pobierania danych: {e}")
        return

    # 2. OBLICZANIE TĘCZOWEGO WYKRESU (Regresja)
    df = df[df['Close'] > 0].copy()
    df['DayNr'] = np.arange(len(df)) + 1
    
    # Dopasowanie krzywej logarytmicznej
    popt, _ = curve_fit(log_func, df['DayNr'], np.log(df['Close']))
    df['FairValue'] = np.exp(log_func(df['DayNr'], *popt))
    
    # Bandy Tęczy
    df['Band_Blue'] = df['FairValue'] * 0.5   # Wyprzedaż
    df['Band_Green'] = df['FairValue'] * 0.8  # Akumulacja
    df['Band_Red'] = df['FairValue'] * 3.0    # Bańka Spekulacyjna

    # 3. AI FEATURE ENGINEERING (Przygotowanie danych dla modelu)
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['Mayer_Multiple'] = df['Close'] / df['SMA_200']
    
    # Obliczanie dni do/od Halvingu
    df['DaysFromHalving'] = 0
    for i, date in enumerate(df['Date']):
        deltas = [(date - datetime.strptime(h, '%Y-%m-%d')).days for h in HALVING_DATES]
        # Wybierz najbliższy (może być ujemny jeśli przed halvingiem)
        closest = min(deltas, key=abs)
        df.loc[i, 'DaysFromHalving'] = closest

    df = df.dropna()

    # 4. TRENING MODELU (Random Forest)
    # Definiujemy historyczne etykiety (Uczymy AI na przeszłości)
    conditions = [
        (df['Mayer_Multiple'] > 2.4),      # Historyczne szczyty
        (df['Mayer_Multiple'] < 0.6),      # Historyczne dołki
        (df['Close'] > df['SMA_200']),     # Trend wzrostowy
        (df['Close'] <= df['SMA_200'])     # Trend spadkowy
    ]
    choices = ['EUFORIA (Top)', 'DEPRESJA (Bottom)', 'HOSSA (Bull)', 'BESSA (Bear)']
    df['Phase'] = np.select(conditions, choices, default='KONSOLIDACJA')

    features = ['Mayer_Multiple', 'DaysFromHalving', 'Close', 'Band_Red']
    X = df[features]
    y = df['Phase']

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    # 5. PREDYKCJA DLA OSTATNIEGO DNIA
    latest_row = X.iloc[[-1]]
    current_phase = model.predict(latest_row)[0]
    probs = model.predict_proba(latest_row)[0]
    
    # Konwersja pewności AI na słownik
    confidence = {model.classes_[i]: round(probs[i]*100, 1) for i in range(len(probs))}

    # 6. ZAPIS DANYCH
    # Redukcja danych do wykresu (bierzemy co 7 dzień, żeby nie zapchać przeglądarki)
    chart_data = []
    df_mini = df.iloc[::7].copy()
    
    # WAŻNE: Zawsze dołączaj ostatni (najnowszy) dzień
    if df.iloc[-1]['Date'] != df_mini.iloc[-1]['Date']:
        df_mini = pd.concat([df_mini, df.iloc[[-1]]], ignore_index=True)
    
    for _, row in df_mini.iterrows():
        chart_data.append({
            'date': row['Date'].strftime('%Y-%m-%d'),
            'price': round(row['Close'], 2),
            'rainbow_top': round(row['Band_Red'], 2),
            'rainbow_bot': round(row['Band_Blue'], 2),
            'phase_marker': row['Phase'], # Do kolorowania tła wykresu
            'is_projection': False
        })

    next_update = datetime.now() + timedelta(seconds=UPDATE_INTERVAL_SECONDS)

    # Obliczamy szacunkowe okno szczytu (średnio 700 dni po halvingu)
    last_halving = datetime.strptime(HALVING_DATES[-1], '%Y-%m-%d')
    estimated_peak = last_halving + timedelta(days=700)
    days_to_peak = (estimated_peak - datetime.now()).days

    output = {
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'next_update_ts': int(next_update.timestamp() * 1000), # Timestamp dla JS
        'current_price': round(df.iloc[-1]['Close'], 2),
        'current_phase': current_phase,
        'ai_confidence': confidence,
        'mayer_multiple': round(df.iloc[-1]['Mayer_Multiple'], 2),
        'days_from_halving': int(df.iloc[-1]['DaysFromHalving']),
        'chart_history': chart_data,
        'halving_dates': HALVING_DATES,
        'days_to_statistical_peak': days_to_peak,
        'recommended_mode': 'SPOT' if days_to_peak > 0 else 'FUTURES_SHORT'
    }

    # Upewnij się, że katalog istnieje
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    
    with open(DATA_FILE, 'w') as f:
        json.dump(output, f)
    
    print(f"[SUCCESS] Satelita zaktualizowany! Faza: {current_phase}")

def check_and_run():
    should_run = True
    if os.path.exists(DATA_FILE):
        file_time = os.path.getmtime(DATA_FILE)
        age = time.time() - file_time
        
        # Check if data inside file is stale (not just file modification time)
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                last_update_str = data.get('last_update', '')
                if last_update_str:
                    last_update = datetime.strptime(last_update_str, '%Y-%m-%d %H:%M:%S')
                    data_age = (datetime.now() - last_update).total_seconds()
                    
                    if data_age > UPDATE_INTERVAL_SECONDS:
                        print(f"[WARNING] Dane w pliku przestarzale ({data_age/86400:.1f} dni). Aktualizacja...")
                        should_run = True
                    elif age < UPDATE_INTERVAL_SECONDS:
                        print(f"[INFO] Dane sa swieze. Nastepna aktualizacja za: {int((UPDATE_INTERVAL_SECONDS - age)/3600)}h")
                        should_run = False
        except Exception as e:
            print(f"[WARNING] Nie mozna sprawdzic danych w pliku: {e}. Wymuszenie aktualizacji...")
            should_run = True
    
    if should_run:
        run_satellite_analysis()

if __name__ == "__main__":
    check_and_run()
