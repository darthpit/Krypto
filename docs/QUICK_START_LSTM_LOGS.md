# 🚀 Quick Start - LSTM Logs

## ⚡ TL;DR

**LSTM Logs show detailed training progress for the LSTM model** (candles used, features, accuracy, test results).

View logs in: **Dashboard → System Logs → LSTM Logs tab**

---

## 📦 What You Get

### ✅ **Detailed Training Visibility**

Every time LSTM trains, you see:

1. **Data Source**: Database or API
2. **Candles Used**: Exact count (e.g., 259,200 candles = 180 days)
3. **Features**: Technical indicators, macro context
4. **Dataset Split**: 80% train / 20% test
5. **Class Balance**: UP vs DOWN distribution
6. **Training Progress**: RandomForest, XGBoost, LSTM
7. **Test Results**: Accuracy, Precision, Recall per class
8. **Summary**: Complete training overview

---

## 🎯 How to View LSTM Logs

### **Option 1: Dashboard (Easiest)**

1. Open: `http://localhost/index.php`
2. Scroll to **"System Logs"**
3. Click **"LSTM Logs"** tab
4. Done! Real-time training logs displayed

### **Option 2: Terminal (Real-time)**

```bash
# Monitor live
docker exec -it pilot_bot tail -f logs/LSTM.log

# Last 50 lines
docker exec -it pilot_bot tail -n 50 logs/LSTM.log
```

---

## 📊 Example Log Output

```
[INFO] ═══════════════════════════════════════════════════════════════════════════════
[SUCCESS] 🚀 LSTM TRAINING CYCLE START - BTC/USDT
[INFO] ═══════════════════════════════════════════════════════════════════════════════

[INFO] 📥 Step 1: Data Synchronization
[SUCCESS] ✅ LSTM Data Source: Database
[INFO] 📊 LSTM Training Dataset: 259,200 candles = 180 days of 1-min data

[INFO] 🔧 Step 2: Feature Engineering
[INFO] 🔧 LSTM Features Created:
[INFO]    - Technical Indicators: RSI, MACD, Bollinger, ATR
[INFO]    - Macro Context: 4h/24h trends, volatility regime
[INFO]    - Target: 30-minute lookahead (Micro-Input/Macro-Output)
[INFO]    - Final Dataset: 259,170 samples × 23 features

[INFO] 📊 Step 3: Dataset Split
[INFO] 📊 LSTM Dataset Split:
[INFO]    - Training Set: 207,336 samples (144 days)
[INFO]    - Test Set: 51,834 samples (36 days)
[INFO]    - Split Ratio: 80% train / 20% test

[INFO] 📊 LSTM Target Distribution:
[INFO]    - Class 0 (DOWN): 103,668 samples (50.0%)
[INFO]    - Class 1 (UP): 103,668 samples (50.0%)

[INFO] 🧠 Step 4: LSTM Model Training
[INFO] 🚀 Starting LSTM Ensemble Training...
[INFO]    - Architecture: Bidirectional LSTM + Multi-Head Attention
[INFO]    - Ensemble: RandomForest + XGBoost + LSTM
[INFO] 🔄 Training RandomForest...
[INFO] 🔄 Training XGBoost...
[INFO] 🔄 Training LSTM with Attention...
[SUCCESS] ✅ LSTM Ensemble Training Complete!

[INFO] 📊 Evaluating model on test set...
[SUCCESS] 📊 LSTM Test Results:
[SUCCESS]    - Overall Accuracy: 58.42%
[INFO]    - DOWN (Class 0): Precision=59.1%, Recall=56.8%
[INFO]    - UP (Class 1): Precision=57.8%, Recall=60.1%
[INFO]    - Test Samples: 51,834 predictions

[INFO] 💾 Step 5: Saving Model & Stats
[SUCCESS] ✅ Model Training Complete: Accuracy=58.42% (23 features)
[SUCCESS] 🎯 LSTM Model Ready for Deployment!

[INFO] ═══════════════════════════════════════════════════════════════════════════════
[SUCCESS] ✅ LSTM TRAINING CYCLE COMPLETE!
[INFO] ═══════════════════════════════════════════════════════════════════════════════
[INFO] 📊 Training Summary:
[INFO]    - Ticker: BTC/USDT
[INFO]    - Data Used: 259,200 candles (180 days)
[INFO]    - Model Accuracy: 58.42%
[INFO]    - Model Saved: model_BTC_USDT_Ensemble_RF_LSTM_Futures_20260124_143015.pkl
[INFO]    - Lookback Period: 180 days
[INFO] ═══════════════════════════════════════════════════════════════════════════════
```

---

## 🔄 Training Frequency

LSTM trains automatically **every 30 minutes** via supervisor.

Or trigger manually:
```bash
docker exec -it pilot_bot python3.12 src/process_trainer.py
```

---

## 📌 Key Files

| File | Purpose |
|------|---------|
| `logs/LSTM.log` | Detailed LSTM training logs |
| `logs/system.log` | General system logs |
| `logs/PPO.log` | RL training logs |

---

## 🎓 Compare: LSTM vs PPO Logs

| Aspect | LSTM Logs | PPO Logs |
|--------|-----------|----------|
| **Model** | Supervised Learning | Reinforcement Learning |
| **Training Data** | Historical candles (180 days) | Simulated episodes |
| **Metrics** | Accuracy, Precision, Recall | Win Rate, Cumulative Reward |
| **Frequency** | Every 30 min | Every 7 days |
| **Duration** | 5-15 minutes | 2-6 hours |
| **Dashboard Tab** | "LSTM Logs" | "PPO Logs" |

---

## ✅ Quick Check

Is everything working?

```bash
# 1. Check log file exists
docker exec -it pilot_bot ls -lh logs/LSTM.log

# 2. View last training
docker exec -it pilot_bot tail -n 50 logs/LSTM.log

# 3. Check accuracy
docker exec -it pilot_bot grep "Overall Accuracy" logs/LSTM.log | tail -1
```

---

## 🆘 Common Issues

### **"Waiting for LSTM training logs..."**

**Cause:** No training has run yet.

**Fix:**
```bash
docker exec -it pilot_bot python3.12 src/process_trainer.py
```

---

### **"LSTM Data Source: API (fallback)"**

**Cause:** Database has insufficient data.

**Fix:** Wait for supervisor to sync history (automatic), or manually:
```bash
docker exec -it pilot_bot python3.12 -c "
from src.utils.data_provider import MarketDataProvider
from datetime import datetime, timedelta
dp = MarketDataProvider()
start = datetime.now() - timedelta(days=180)
dp.fetch_full_history('BTC/USDT', timeframe='1m', start_date=start)
"
```

---

## 📚 More Information

Detailed guide: [`docs/LSTM_LOGS_GUIDE.md`](./LSTM_LOGS_GUIDE.md)

---

**Questions?** Check the logs:
```bash
docker exec -it pilot_bot tail -f logs/LSTM.log
```
