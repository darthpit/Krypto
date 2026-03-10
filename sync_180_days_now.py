"""
EMERGENCY SCRIPT: Force 180-day database sync NOW
Poprawiona wersja z obsługą stref czasowych (timezone-aware fix)
"""
import sys
import os
import pandas as pd
import datetime
from datetime import timezone

# Dodanie ścieżki projektu
sys.path.insert(0, os.path.dirname(__file__))

from src.utils.data_provider import MarketDataProvider
from src.database import Database

def main():
    print("=" * 80)
    print("🚀 EMERGENCY: Syncing 180 days of BTC/USDT 1m data to database")
    print("=" * 80)
    
    # Initialize
    provider = MarketDataProvider()
    db = Database()
    ticker = "BTC/USDT"
    
    # Check current database status
    try:
        rows = db.query(
            "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM candles WHERE ticker = ? AND timeframe = '1m'",
            (ticker,)
        )
        if rows and rows[0]:
            current_candles = rows[0][0] or 0
            oldest = rows[0][1]
            newest = rows[0][2]
            
            # FIX: Konwersja na Timestamp z obsługą stref czasowych, aby uniknąć błędów obliczeń
            if oldest and newest:
                # Upewniamy się, że oba obiekty są w tej samej strefie (UTC)
                ts_new = pd.to_datetime(newest).tz_localize(None) if hasattr(pd.to_datetime(newest), 'tz_node') else pd.to_datetime(newest).replace(tzinfo=None)
                ts_old = pd.to_datetime(oldest).tz_localize(None) if hasattr(pd.to_datetime(oldest), 'tz_node') else pd.to_datetime(oldest).replace(tzinfo=None)
                current_days = (ts_new - ts_old).days
            else:
                current_days = 0
            
            print(f"\n📊 Current database status:")
            print(f"   Candles: {current_candles:,}")
            print(f"   Days: {current_days}")
            print(f"   Range: {oldest} to {newest}")
    except Exception as e:
        print(f"⚠️ Error checking database: {e}")
        current_candles = 0
    
    # Confirm action
    if current_candles > 200000:
        print(f"\n⚠️ WARNING: Database already has {current_candles:,} candles")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Aborted by user")
            return
    
    print(f"\n📥 Fetching 180 days using DUAL-EXCHANGE strategy...")
    print(f"   - Binance: Historical data (31-180 days ago)")
    print(f"   - MEXC: Current data (last 30 days)")
    print(f"   - This will take 15-30 minutes due to API rate limits")
    print()
    
    # Callback to save chunks
    saved_chunks = 0
    total_candles_saved = 0
    
    def save_callback(df, progress_info):
        nonlocal saved_chunks, total_candles_saved
        
        try:
            if df.empty:
                return

            # Save to database
            data = []
            for index, row in df.iterrows():
                # FIX: Usuwamy strefę czasową z indeksu przed zapisem do bazy
                if hasattr(index, 'tzinfo') and index.tzinfo is not None:
                    ts = index.replace(tzinfo=None).isoformat()
                else:
                    ts = index.isoformat()

                data.append((
                    ticker,
                    ts,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume']),
                    '1m'
                ))
            
            # Zapytanie PostgreSQL (używamy %s dla psycopg2)
            query = """
                INSERT INTO candles (ticker, timestamp, open, high, low, close, volume, timeframe)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, timestamp, timeframe) DO NOTHING
            """
            db.execute_many(query, data)
            
            saved_chunks += 1
            total_candles_saved += len(df)
            
            # Progress
            source = progress_info.get('source', 'unknown')
            current_date = progress_info.get('current_date', 'N/A')
            days_fetched = progress_info.get('days_fetched', 0)
            
            print(f"✅ Chunk #{saved_chunks}: Saved {len(df)} candles from {source} | Date: {current_date} | Total days: {days_fetched}")
            
        except Exception as e:
            print(f"❌ Error saving chunk: {e}")
    
    # Fetch with dual-exchange
    try:
        # Metoda fetch_dual_exchange_history musi mieć wewnątrz poprawkę tz-naive/aware 
        # którą Jules wprowadził do data_provider.py
        df = provider.fetch_dual_exchange_history(
            ticker=ticker,
            timeframe='1m',
            target_days=180,
            limit=1000,
            callback=save_callback
        )
        
        print(f"\n" + "=" * 80)
        print(f"✅ SYNC COMPLETE!")
        print(f"=" * 80)
        print(f"📊 Saved {saved_chunks} chunks ({total_candles_saved:,} candles)")
        
        # Verify database po synchronizacji
        rows = db.query(
            "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM candles WHERE ticker = %s AND timeframe = '1m'",
            (ticker,)
        )
        if rows and rows[0]:
            final_candles = rows[0][0] or 0
            oldest = rows[0][1]
            newest = rows[0][2]
            
            # FIX: Ponowna konwersja bezpieczna
            ts_new = pd.to_datetime(newest).replace(tzinfo=None) if newest else None
            ts_old = pd.to_datetime(oldest).replace(tzinfo=None) if oldest else None
            final_days = (ts_new - ts_old).days if ts_new and ts_old else 0
            
            print(f"\n📊 Final database status:")
            print(f"   Candles: {final_candles:,}")
            print(f"   Days: {final_days}")
            print(f"   Range: {oldest} to {newest}")
            
            if final_days >= 170: # Tolerancja dla małych przerw
                print(f"\n🎉 SUCCESS! Database now has {final_days} days of data!")
            else:
                print(f"\n⚠️ WARNING: Only {final_days} days synced (target: 180)")
    
    except Exception as e:
        print(f"\n❌ SYNC FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()