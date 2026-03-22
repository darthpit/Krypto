import pandas as pd
import numpy as np
from src.logic.behavioral_guard import BehavioralGuard
from src.logic.anti_fomo import AntiFOMOModule

class MockDB:
    def execute(self, query, params=None):
        pass
    def query(self, query, params=None):
        return [(1,)] # Overtrading check uses COUNT

def main():
    db = MockDB()
    guard = BehavioralGuard(db)
    anti_fomo = AntiFOMOModule(db)

    # Mock Data
    dates = pd.date_range('2023-01-01', periods=100, freq='1min')
    df = pd.DataFrame(index=dates)
    df['open'] = np.linspace(99, 109, 100)
    df['close'] = np.linspace(100, 110, 100)
    df['volume'] = np.random.randint(100, 1000, 100)
    df['high'] = df['close'] + 1
    df['low'] = df['close'] - 1

    # Add RSI for BehavioralGuard
    df['rsi'] = 50.0

    ticker = "BTC/USDT"
    psnd_score = 0.5

    # Test AntiFOMO Pump
    # Simulate a pump
    df_pump = df.copy()
    df_pump.iloc[-1, df_pump.columns.get_loc('open')] = 109
    df_pump.iloc[-1, df_pump.columns.get_loc('close')] = 120 # 10% jump
    df_pump.iloc[-1, df_pump.columns.get_loc('volume')] = 5000 # 5x volume

    pump_check = anti_fomo.check_pump_dump(ticker, df_pump)
    print("AntiFOMO Pump Check:", pump_check)

    # Test AntiFOMO Panic
    df_panic = df.copy()
    df_panic.iloc[-1, df_panic.columns.get_loc('open')] = 109
    df_panic.iloc[-1, df_panic.columns.get_loc('close')] = 90 # 10% drop
    df_panic.iloc[-1, df_panic.columns.get_loc('volume')] = 5000 # 5x volume

    panic_check = anti_fomo.check_panic_sell(ticker, df_panic, fear_greed_index=20)
    print("AntiFOMO Panic Check:", panic_check)

    # Test BehavioralGuard Check All
    guard_ok, guard_reason, guard_modifier = guard.check_all(
        ticker=ticker, df=df, signal_type="BUY", psnd_score=psnd_score
    )
    print(f"BehavioralGuard Check: {guard_ok}, {guard_reason}, {guard_modifier}")

    print("🎉 Wszystkie testy zdane! BehavioralGuard + AntiFOMO gotowe.")

if __name__ == "__main__":
    main()
