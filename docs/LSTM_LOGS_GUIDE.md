# 📊 LSTM Logs - Complete Training Visibility

## 🎯 Overview

**LSTM Logs** provides detailed insights into the LSTM (Long Short-Term Memory) model training process, analogous to PPO Logs for reinforcement learning.

All LSTM training details are logged to: **`logs/LSTM.log`**

---

## 🔍 What's Logged?

### **1. Data Source & Quantity**
```
[INFO] ✅ LSTM Data Source: Database
[INFO] 📊 LSTM Training Dataset: 259,200 candles = 180 days of 1-min data
```

**Details:**
- Where data comes from (Database or API fallback)
- Exact number of candles used for training
- Duration in days (1-min intervals)

---

### **2. Feature Engineering**
```
[INFO] 🔧 LSTM Features Created:
[INFO]    - Technical Indicators: RSI, MACD, Bollinger, ATR
[INFO]    - Macro Context: 4h/24h trends, volatility regime
[INFO]    - Target: 30-minute lookahead (Micro-Input/Macro-Output)
[INFO]    - Final Dataset: 259,170 samples × 23 features
```

**Details:**
- Complete list of technical indicators
- Macro context features (multi-timeframe)
- Target prediction window (30-minute lookahead)
- Final feature count

---

### **3. Dataset Split**
```
[INFO] 📊 LSTM Dataset Split:
[INFO]    - Training Set: 207,336 samples (144 days)
[INFO]    - Test Set: 51,834 samples (36 days)
[INFO]    - Split Ratio: 80% train / 20% test
```

**Details:**
- Exact sample counts for train/test
- Duration in days for each set
- Split ratio (80/20)

---

### **4. Class Distribution**
```
[INFO] 📊 LSTM Target Distribution:
[INFO]    - Class 0 (DOWN): 103,668 samples (50.0%)
[INFO]    - Class 1 (UP): 103,668 samples (50.0%)
```

**Details:**
- Balanced vs imbalanced dataset
- SMOTE applied if imbalance detected (>70%)

---

### **5. Training Progress**
```
[INFO] 🚀 Starting LSTM Ensemble Training...
[INFO]    - Architecture: Bidirectional LSTM + Multi-Head Attention
[INFO]    - Ensemble: RandomForest + XGBoost + LSTM
[INFO] 🔄 Training RandomForest...
[INFO] 🔄 Training XGBoost...
[INFO] 🔄 Training LSTM with Attention...
[SUCCESS] ✅ LSTM Ensemble Training Complete!
```

**Details:**
- Architecture type (Bidirectional LSTM + Attention)
- Ensemble components (RF + XGBoost + LSTM)
- Training phases for each model

---

### **6. Test Results**
```
[SUCCESS] 📊 LSTM Test Results:
[SUCCESS]    - Overall Accuracy: 58.42%
[INFO]    - DOWN (Class 0): Precision=59.1%, Recall=56.8%
[INFO]    - UP (Class 1): Precision=57.8%, Recall=60.1%
[INFO]    - Test Samples: 51,834 predictions
```

**Details:**
- Overall model accuracy
- Per-class precision & recall (DOWN/UP)
- Number of test predictions

---

### **7. Training Summary**
```
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

**Details:**
- Complete training summary
- Ticker symbol
- Total data used
- Final accuracy
- Model filename
- Lookback period

---

## 📍 Where to Find LSTM Logs?

### **Option 1: Dashboard (Easiest)**

1. Open: `http://localhost/index.php`
2. Scroll to **"System Logs"** section
3. Click **"LSTM Logs"** tab
4. View real-time training progress

**Screenshot:**
```
┌─────────────────────────────────────────┐
│ System Logs                             │
├─────────────────────────────────────────┤
│ [System] [PPO Logs] [LSTM Logs] ← Click│
├─────────────────────────────────────────┤
│ [2026-01-24 14:30:15] [SUCCESS] ✅ LSTM│
│ Training Complete! Accuracy: 58.42%     │
│ ...                                     │
└─────────────────────────────────────────┘
```

---

### **Option 2: Docker Terminal (Real-time)**

```bash
# Real-time monitoring
docker exec -it pilot_bot tail -f logs/LSTM.log

# Last 50 lines
docker exec -it pilot_bot tail -n 50 logs/LSTM.log

# Search for specific keywords
docker exec -it pilot_bot grep "Accuracy" logs/LSTM.log
```

---

### **Option 3: Direct File Access**

```bash
# Read entire file
cat logs/LSTM.log

# Search for training summaries
grep "Training Summary" logs/LSTM.log -A 10
```

---

## 🔧 Configuration

### **Automatic Logging**

LSTM Logs are **automatically enabled** - no configuration needed!

The logger automatically routes messages containing these keywords to `LSTM.log`:
- `LSTM`
- `Ensemble`
- `Epoch`
- `Training samples`
- `candles`
- `Feature Engineering`
- `Model trained`

---

### **Manual Logging (Development)**

If you want to add custom LSTM logs:

```python
from src.utils.logger import log

# Log only to LSTM.log (not system.log)
log("Custom LSTM message", "INFO", lstm_only=True)

# Log to both system.log and LSTM.log
log("LSTM model accuracy: 58%", "SUCCESS")  # Auto-routed due to "LSTM" keyword
```

---

## 📊 Typical Training Flow

### **Example: 180-day Training**

```
1. Data Synchronization (10%)
   ✅ LSTM Data Source: Database
   📊 Fetched 259,200 candles (180 days)

2. Feature Engineering (30%)
   🔧 Created 23 features
   ✅ Final Dataset: 259,170 samples

3. Dataset Split (50%)
   📊 Training: 207,336 samples (80%)
   📊 Test: 51,834 samples (20%)

4. Training (50-85%)
   🔄 Training RandomForest...
   🔄 Training XGBoost...
   🔄 Training LSTM with Attention...
   ✅ Training Complete!

5. Evaluation (85-95%)
   📊 Overall Accuracy: 58.42%
   📊 DOWN: Precision=59.1%, Recall=56.8%
   📊 UP: Precision=57.8%, Recall=60.1%

6. Saving (95-100%)
   💾 Model saved: model_BTC_USDT_*.pkl
   ✅ Training Cycle Complete!
```

---

## 🆚 Comparison: LSTM Logs vs PPO Logs

| Feature | LSTM Logs | PPO Logs |
|---------|-----------|----------|
| **Log File** | `logs/LSTM.log` | `logs/PPO.log` |
| **Model Type** | Ensemble (RF + XGBoost + LSTM) | Reinforcement Learning (PPO) |
| **Training Data** | Historical candles (180 days) | Simulated trading episodes |
| **Progress Metrics** | Accuracy, Precision, Recall | Win Rate, Cumulative Reward |
| **Training Frequency** | Every 30 minutes (supervisor) | Every 7 days |
| **Dashboard Tab** | "LSTM Logs" | "PPO Logs" |
| **Typical Duration** | 5-15 minutes | 2-6 hours |

---

## 🐛 Troubleshooting

### **Problem: "Waiting for LSTM training logs..."**

**Cause:** No LSTM training has run yet, or log file is empty.

**Solution:**
```bash
# Trigger LSTM training manually
docker exec -it pilot_bot python3.12 src/process_trainer.py

# Check if log file exists
docker exec -it pilot_bot ls -lh logs/LSTM.log
```

---

### **Problem: "LSTM Data Source: API (fallback)"**

**Cause:** Database has insufficient historical data (<1440 candles).

**Solution:**
```bash
# Synchronize full history to database
docker exec -it pilot_bot python3.12 -c "
from src.utils.data_provider import MarketDataProvider
from datetime import datetime, timedelta
dp = MarketDataProvider()
start = datetime.now() - timedelta(days=180)
dp.fetch_full_history('BTC/USDT', timeframe='1m', start_date=start, limit=500)
"
```

---

### **Problem: Low Accuracy (<50%)**

**Cause:** Insufficient data, class imbalance, or market conditions.

**Check:**
```bash
# Check class distribution in logs
docker exec -it pilot_bot grep "Class Balance" logs/LSTM.log

# Check data quantity
docker exec -it pilot_bot grep "Training Dataset" logs/LSTM.log
```

**Solution:**
- Ensure 180 days of data (259,200 candles)
- Verify SMOTE is applied for imbalance
- Increase lookback period in `config.json`

---

## 📈 Performance Benchmarks

### **Expected Metrics**

| Metric | Good | Excellent |
|--------|------|-----------|
| **Overall Accuracy** | >55% | >60% |
| **Precision (DOWN)** | >55% | >65% |
| **Precision (UP)** | >55% | >65% |
| **Training Time** | <10 min | <5 min |
| **Data Used** | 180 days | 180 days |

---

## 📝 Log File Rotation

LSTM logs can grow large over time. To prevent disk issues:

### **Auto-Rotation (Recommended)**

Create a logrotate config:

```bash
# /etc/logrotate.d/lstm-logs
/app/logs/LSTM.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 0644 root root
}
```

### **Manual Cleanup**

```bash
# Archive old logs
docker exec -it pilot_bot bash -c "
cd logs && \
cp LSTM.log LSTM_$(date +%Y%m%d).log && \
gzip LSTM_$(date +%Y%m%d).log && \
> LSTM.log
"
```

---

## 🎓 Advanced Usage

### **Compare Training Runs**

```bash
# Extract all training summaries
docker exec -it pilot_bot grep -A 7 "Training Summary" logs/LSTM.log

# Compare accuracy over time
docker exec -it pilot_bot grep "Model Accuracy" logs/LSTM.log | tail -10
```

### **Monitor Training in Real-time**

```bash
# Watch for specific events
docker exec -it pilot_bot tail -f logs/LSTM.log | grep --line-buffered "Accuracy\|Complete\|ERROR"
```

---

## ✅ Quick Checklist

Before troubleshooting, verify:

- [x] LSTM.log file exists: `ls logs/LSTM.log`
- [x] Dashboard tab "LSTM Logs" is visible
- [x] Data source is "Database" (not API fallback)
- [x] Training dataset has 180 days of data
- [x] Accuracy is >50%
- [x] No errors in log file: `grep ERROR logs/LSTM.log`

---

## 🔗 Related Documentation

- **PPO Logs Guide:** `docs/RL_AUTO_RESTART_CHECKPOINTS.md`
- **Dashboard Guide:** `README.md` (section "Monitoring")
- **Configuration:** `config.json` (lookback_days, training settings)

---

**Questions?** Check the logs:
```bash
docker exec -it pilot_bot tail -f logs/LSTM.log
```
