# 🎯 PPO QUICK REFERENCE CARD

**Szybki przewodnik po nowym systemie nagród**

---

## 💰 BUDŻET & POSITION SIZING

```
Balance: $1000
Per Trade: 10% = $100
Leverage: 20x
Position Size: $100 × 20 = $2000

Możliwych transakcji: 10 (teoretycznie)
Praktycznie: max_open_positions = 1
```

---

## 🎁 SYSTEM NAGRÓD

### 1️⃣ OTWARCIE (Action 1 lub 2)
```
Nagroda: 0 punktów
(Samo otwarcie nie jest karane/nagradzane)
```

### 2️⃣ PIERWSZY KROK PO OTWARCIU
```
✅ PnL > 0:   +10 punktów  (dobry timing!)
❌ PnL ≤ 0:   -5 punktów   (zły timing)
```

### 3️⃣ ZAMKNIĘCIE (Action 3)
```
🎉 Zysk > +2.5%:        +150 punktów  (DUŻA NAGRODA!)
😐 Zysk 0% do +2.5%:    0 punktów     (za mało)
💔 Strata 0% to -2%:    -30 punktów
💥 Strata -2% to -5%:   -80 punktów
☠️  Strata > -5%:       -150 punktów  (DUŻA KARA!)
```

### 4️⃣ DRAWDOWN (per step)
```
DD > 40%:  -2.0 punktów/krok  (bardzo źle!)
DD > 30%:  -1.0 punktów/krok  (źle!)
DD > 20%:  -0.3 punktów/krok  (uwaga!)
DD > 10%:  -0.05 punktów/krok (ostrzeżenie)
```

### 5️⃣ BONUSY
```
🎉 Nowy szczyt kapitału:  +2.0 punktów
💀 Bankruptcy (≤$0):       -200 punktów (GAME OVER)
```

---

## 📊 MATEMATYKA

### Przy 55% LSTM Accuracy:
```
55% trades: +2.5% × +150 pkt = +82.5 pkt
45% trades: -2.0% × -30 pkt = -13.5 pkt
────────────────────────────────────────
Expected Value: +69 punktów/trade ✅
```

### Przy 90% LSTM Accuracy (Cel):
```
90% trades: +2.5% × +150 pkt = +135 pkt
10% trades: -2.0% × -30 pkt = -3 pkt
────────────────────────────────────────
Expected Value: +132 punkty/trade 🚀
```

---

## 🚀 QUICK START

```bash
# 1. RESET
rm models/ppo_trading_agent.zip
rm -rf models/checkpoints/*.zip

# 2. TRAIN
python3.12 src/process_rl_trainer.py \
    --timesteps 200000 \
    --data-days 180 \
    --balance 1000

# 3. MONITOR
tail -f logs/PPO.log

# 4. CHECK RESULTS
cat models/rl_training_results.json
```

---

## ✅ SUCCESS CRITERIA

```
Win Rate:      > 50% (55%+ doskonale)
Total Return:  > 20% (na validacji)
Max Drawdown:  < 20%
Episodes:      > 100 (nie 0!)
```

---

## 🆚 PRZED vs PO

| Metryka | Przed | Po |
|---------|-------|-----|
| Win Rate | 0% | 55%+ |
| Episodes | 0 | 500+ |
| Reward >2.5% | +100 | +150 |
| Penalty Loss | -20 | -30/-80/-150 |
| Drawdown Penalty | Agresywne | Umiarkowane |
| Data Days | 4 | 180 |

---

**ZMIANY GOTOWE!** Czas na nowy trening 🔥
