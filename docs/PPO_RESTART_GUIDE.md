# 🚀 INSTRUKCJA RESTARTU TRENINGU PPO

**Data:** 26 stycznia 2026  
**Status:** ✅ System naprawiony, gotowy do nowego treningu

---

## ⚠️ WAŻNE: RESTART WYMAGANY

Obecny model PPO ma **0% win rate** i trenował się na **błędnej logice nagród**. Musisz zrestartować trening od zera z nowym systemem.

---

## 📋 KROK PO KROKU

### 1. ZATRZYMAJ Obecny Trening

```bash
# Znajdź proces PPO training
ps aux | grep process_rl_trainer

# Zabij proces (zastąp PID numerem procesu)
kill -9 <PID>

# Alternatywnie: Ctrl+C w terminalu gdzie trening się odbywa
```

### 2. USUŃ Stare Modele (RESET)

```bash
# Przejdź do katalogu projektu
cd /c/xampp/htdocs/CryptoSniperFutures

# Usuń stary model PPO
rm -f models/ppo_trading_agent.zip

# Usuń wszystkie checkpointy (opcjonalne, ale zalecane)
rm -rf models/checkpoints/ppo_checkpoint_*.zip

# Usuń stare wyniki
rm -f models/rl_training_results.json

# Zweryfikuj usunięcie
ls -lh models/
```

### 3. UPEWNIJ SIĘ, ŻE MASZ 180 DNI DANYCH

```bash
# Sprawdź bazę danych - ile dni danych masz?
# Powinno być ~259,200 candles (180 dni × 1440 minut)

# Jeśli nie, uruchom synchronizację:
python3.12 src/process_trainer.py

# Poczekaj aż zsynchronizuje pełne 180 dni (może zająć 30-60 minut)
# Monitoruj: tail -f logs/system.log
```

### 4. URUCHOM NOWY TRENING

```bash
# Podstawowy trening (200k steps, ~3-4 godziny)
python3.12 src/process_rl_trainer.py \
    --timesteps 200000 \
    --data-days 180 \
    --balance 1000 \
    --leverage 20 \
    --checkpoint-interval 10000

# Jeśli chcesz dłuższy trening (500k steps, ~8-10 godzin):
python3.12 src/process_rl_trainer.py \
    --timesteps 500000 \
    --data-days 180 \
    --balance 1000 \
    --leverage 20 \
    --checkpoint-interval 10000
```

### 5. MONITORUJ TRENING

**Terminal 1: Logi PPO**
```bash
tail -f logs/PPO.log
```

**Co powinieneś zobaczyć:**
```
✅ Good Signs (PO ZMIANACH):
- Win Rate powinien zacząć rosnąć już po 20k-50k steps
- Episodes powinny się kończyć (nie 0 jak teraz)
- Cumulative Reward powinien rosnąć (nie 0.00 jak teraz)
- Checkpoints zapisywane co 10k steps

❌ Bad Signs (jeśli widzisz):
- Win Rate = 0% po 100k steps → coś jest nie tak
- Balance spada do 0 zbyt często → kary za drawdown zbyt wysokie
- Episodes = 0 po 50k steps → agent nie kończy epizodów
```

**Terminal 2: Monitoring systemu**
```bash
# CPU/RAM usage
watch -n 5 'free -h && ps aux | grep process_rl_trainer | grep -v grep'
```

### 6. PRZERWANIE I WZNOWIENIE (OPTIONAL)

**Jeśli musisz przerwać trening:**
```bash
# Ctrl+C (graceful shutdown - zapisze checkpoint)

# Wznów od ostatniego checkpointa:
python3.12 src/process_rl_trainer.py \
    --timesteps 200000 \
    --data-days 180 \
    --resume ppo_checkpoint_120000
```

**System automatycznie:**
- Załaduje checkpoint
- Obliczy remaining timesteps
- Kontynuuje trening

### 7. PO ZAKOŃCZENIU TRENINGU

**Sprawdź wyniki:**
```bash
# Pokaż wyniki walidacji
cat models/rl_training_results.json

# Wyniki backtestingu (na końcu logów)
tail -100 logs/PPO.log
```

**Kluczowe metryki:**
```json
{
  "validation_results": {
    "win_rate": 55.0,           // Cel: > 50%
    "total_return_pct": 25.5,   // Cel: > 20%
    "max_drawdown_pct": 15.2,   // Cel: < 20%
    "total_trades": 120,
    "winning_trades": 66
  }
}
```

### 8. DEPLOYMENT (Po Successful Training)

**JEŚLI win_rate > 50% i total_return > 20%:**

```bash
# Wdróż na PAPER trading (tryb testowy)
# Edytuj config.json
nano config.json
# Upewnij się że: "mode": "PAPER"

# Restart tradingowego procesu
supervisorctl restart process_trader
# LUB
pkill -f process_trader
python3.12 src/process_trader.py &

# Monitoruj przez 24-48h
tail -f logs/system.log
```

**JEŚLI wszystko działa dobrze po 48h PAPER:**
```bash
# Przełącz na LIVE (OSTROŻNIE!)
# Edytuj config.json
nano config.json
# Zmień: "mode": "LIVE"

# Restart z mniejszym kapitałem (test)
# Edytuj balance w config lub trader setup
```

---

## 📊 OCZEKIWANE CZASY

| Etap | Czas | Notatki |
|------|------|---------|
| **Synchronizacja danych (180 dni)** | 30-60 min | Jednorazowo, jeśli baza pusta |
| **Trening 200k steps** | 3-4h | Zależy od CPU/RAM |
| **Trening 500k steps** | 8-10h | Zalecane dla lepszej konwergencji |
| **Walidacja** | 5-10 min | Automatyczna po treningu |

---

## 🔧 TROUBLESHOOTING

### Problem: "Out of Memory (OOM)"
```bash
# Zmniejsz data_days
python3.12 src/process_rl_trainer.py --data-days 90  # Zamiast 180

# LUB zwiększ swap
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Problem: "Win Rate = 0% po 100k steps"
```bash
# Sprawdź logi czy są błędy
grep ERROR logs/PPO.log

# Sprawdź czy LSTM model działa
ls -lh models/model_BTC_USDT_*

# Jeśli problem persystuje, sprawdź czy zmiany zostały zapisane:
grep "NOWA ZDROWA LOGIKA" src/ai/rl_agent.py
```

### Problem: "Agent ciągle bankrutuje"
```bash
# Zwiększ initial balance (więcej kapitału na uczenie się)
python3.12 src/process_rl_trainer.py --balance 5000  # Zamiast 1000

# LUB zmniejsz leverage
python3.12 src/process_rl_trainer.py --leverage 10  # Zamiast 20
```

### Problem: "Trening trwa zbyt długo"
```bash
# Użyj mniejszej liczby timesteps (szybszy test)
python3.12 src/process_rl_trainer.py --timesteps 50000

# Ale pamiętaj: PPO potrzebuje czasu do konwergencji
# Minimum 100k steps zalecane, 200k-500k optymalne
```

---

## 📝 CHECKLIST PRZED URUCHOMIENIEM

- [ ] Zatrzymany stary trening PPO
- [ ] Usunięte stare modele (`rm models/ppo_trading_agent.zip`)
- [ ] Usunięte checkpointy (`rm models/checkpoints/*.zip`)
- [ ] Baza ma ≥ 180 dni danych (sprawdź `logs/system.log`)
- [ ] Wystarczająco RAM (min 10GB free)
- [ ] Wystarczająco miejsca na dysku (min 5GB free)
- [ ] Terminal otwarty dla logów (`tail -f logs/PPO.log`)
- [ ] Zmiany w `src/ai/rl_agent.py` zapisane i zweryfikowane

---

## 🎯 OCZEKIWANE REZULTATY

### Po Nowym Treningu (200k steps):

```
✅ Win Rate: 50-60% (było 0%)
✅ Episodes: 500-1000+ completed (było 0)
✅ Cumulative Reward: Positive growing (było 0.00)
✅ Total Return: +20-40% na validacji
✅ Max Drawdown: <20%
✅ Agent nauczy się:
   - Otwierać pozycje w dobrych momentach
   - Zamykać zyski przy +2.5%+
   - Zamykać straty wcześnie (SL)
   - Zarządzać ryzykiem (max 10% per trade)
```

---

**Powodzenia!** 🚀

Jeśli masz problemy, sprawdź:
1. `logs/PPO.log` - szczegóły treningu
2. `logs/system.log` - ogólne błędy systemu
3. `docs/PPO_LOGIC_ANALYSIS.md` - pełna analiza zmian
