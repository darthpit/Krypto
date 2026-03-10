#!/usr/bin/env python3
import psycopg2
import time
import sys
import json
from datetime import datetime

def get_db_connection():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            db_conf = config['database']

        conn = psycopg2.connect(
            host=db_conf['host'],
            port=db_conf['port'],
            user=db_conf['user'],
            password=db_conf['password'],
            dbname=db_conf['dbname']
        )
        return conn
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

def check_status():
    conn = get_db_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()

        print("\n" + "="*60)
        print(f"  Bot Status Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")

        # Check system status
        try:
            cursor.execute("SELECT key, value FROM system_status WHERE key IN ('pulse_1m', 'pulse_5m', 'pulse_30m')")
            pulses = cursor.fetchall()

            if pulses:
                for key, value in pulses:
                    # Value might be None if not set
                    val_str = str(value) if value is not None else "N/A"
                    print(f"  {key}: {val_str[:100]}...")
            else:
                 print("  No system pulse data found.")
        except psycopg2.Error as e:
            print(f"  Error reading system_status: {e}")

        # Check recent trades
        try:
            cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp > NOW() - INTERVAL '1 day'")
            trade_count = cursor.fetchone()[0]
            print(f"\n  Trades (last 24h): {trade_count}")
        except psycopg2.Error as e:
             print(f"\n  Error reading trades: {e}")

        # Check wallet
        try:
            cursor.execute("SELECT currency, amount FROM wallet_balances")
            balances = cursor.fetchall()
            print(f"\n  Wallet Balances:")
            if balances:
                for curr, amt in balances:
                    print(f"    {curr}: {float(amt):.4f}")
            else:
                print("    No balances found.")
        except psycopg2.Error as e:
             print(f"\n  Error reading wallet_balances: {e}")

        # Check for active queries (locking indicator equivalent)
        try:
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            active_queries = cursor.fetchone()[0]
            print(f"\n  Active DB Connections: {active_queries}")
        except psycopg2.Error:
            pass

        conn.close()
        print("\n" + "="*60 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        while True:
            check_status()
            time.sleep(10)
    else:
        check_status()
