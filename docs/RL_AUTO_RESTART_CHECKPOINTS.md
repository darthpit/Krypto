# 🔄 Auto-Restart & Model Checkpoints - Dokumentacja

## 📋 Przegląd Funkcjonalności

System treningu RL (PPO) został rozszerzony o dwie kluczowe funkcjonalności:

### 1️⃣ **Model Checkpoints** - Automatyczne Zapisywanie Postępu
- ✅ Automatyczne zapisywanie modelu co **10,000 kroków** (konfigurowalne)
- ✅ Pełna metadata: timesteps, win rate, accuracy, episodes
- ✅ Możliwość wznowienia treningu od dowolnego checkpointu
- ✅ Lokalizacja: `models/checkpoints/`

### 2️⃣ **Auto-Restart** - Automatyczne Wznowienie Po OOM
- ✅ Automatyczne wykrywanie crash'u procesu (OOM, zombie)
- ✅ Wznowienie treningu od ostatniego checkpointu
- ✅ Limit 3 prób auto-restart (zapobieganie nieskończonej pętli)
- ✅ Integracja z supervisor (main.py)

---

## 🎯 Jak to Działa?

### **Checkpoints - Automatyczne Zapisywanie**

Podczas treningu PPO, model jest automatycznie zapisywany co **10,000 kroków**:

```
models/checkpoints/
├── ppo_checkpoint_10000.zip
├── ppo_checkpoint_10000_metadata.json
├── ppo_checkpoint_20000.zip
├── ppo_checkpoint_20000_metadata.json
├── ppo_checkpoint_30000.zip
└── ppo_checkpoint_30000_metadata.json
```

**Metadata zawiera:**
```json
{
  "timesteps": 10000,
  "total_timesteps": 200000,
  "progress_pct": 5.0,
  "episodes": 48,
  "winning_episodes": 26,
  "win_rate": 54.2,
  "cumulative_reward": 1245.67,
  "saved_at": "2026-01-24T14:30:15.123456",
  "checkpoint_file": "ppo_checkpoint_10000.zip"
}
```

### **Auto-Restart - Automatyczne Wznowienie**

Gdy supervisor wykryje crash procesu PPO:

1. **Wykrywanie zombie** - Sprawdza czy proces żyje (PID check)
2. **Sprawdzenie checkpointów** - Czy istnieją zapisane modele?
3. **Limit prób** - Czy nie przekroczono 3 prób restart?
4. **Wznowienie** - Automatyczne uruchomienie z flagą `--resume`

**Logi z PPO.log:**
```
[2026-01-24 14:30:15] [ERROR] 💀 ZOMBIE LOCK DETECTED! Process 1234 is dead but lockfile exists. Cleaning up...
[2026-01-24 14:30:16] [INFO] 🔄 AUTO-RESTART: Attempting to resume training from last checkpoint...
[2026-01-24 14:30:17] [INFO] 🔄 Resuming from checkpoint: ppo_checkpoint_30000
[2026-01-24 14:30:20] [SUCCESS] ✅ Checkpoint loaded: 30000 steps completed
[2026-01-24 14:30:20] [INFO] 🎯 Remaining training: 170000 steps
```

---

## 🚀 Użycie

### **Automatyczny Trening (Supervisor)**

Supervisor automatycznie zarządza auto-restart. Nic nie musisz robić!

```bash
# Uruchom bota w Dockerze
docker-compose up -d
```

Supervisor:
- Monitoruje proces PPO co 60 sekund
- Wykrywa zombie lockfile
- Automatycznie wznawia od ostatniego checkpointu

---

### **Ręczne Uruchomienie Treningu**

#### **Nowy Trening (od zera)**
```bash
python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --data-days 180 \
  --checkpoint-interval 10000
```

**Parametry:**
- `--timesteps 200000` - Liczba kroków treningowych
- `--data-days 180` - Ilość dni danych historycznych
- `--checkpoint-interval 10000` - Zapisuj co 10k kroków

---

#### **Wznowienie Od Checkpointu**
```bash
python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --data-days 180 \
  --resume ./models/checkpoints/ppo_checkpoint_30000
```

**Parametry:**
- `--resume <path>` - Ścieżka do checkpointu (bez .zip)

**Przykład:**
```bash
# Wyświetl dostępne checkpointy
ls -lh models/checkpoints/

# Wznów od checkpointu 30000
python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --resume ./models/checkpoints/ppo_checkpoint_30000
```

---

#### **Zmiana Częstotliwości Checkpointów**

Domyślnie: co **10,000 kroków**

Zapisuj co **5,000 kroków** (częściej):
```bash
python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --checkpoint-interval 5000
```

Zapisuj co **20,000 kroków** (rzadziej):
```bash
python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --checkpoint-interval 20000
```

---

## 📊 Monitoring

### **1. Logi PPO**
```bash
# Docker
docker exec -it pilot_bot tail -f logs/PPO.log

# Lokalnie
tail -f logs/PPO.log
```

**Przykładowe logi:**
```
[2026-01-24 14:30:15] [SUCCESS] 💾 Checkpoint saved: ppo_checkpoint_10000.zip | Steps: 10000/200000 (5.0%) | Win Rate: 54.2%
[2026-01-24 14:35:20] [SUCCESS] 💾 Checkpoint saved: ppo_checkpoint_20000.zip | Steps: 20000/200000 (10.0%) | Win Rate: 56.8%
```

---

### **2. Dashboard - Zakładka "PPO Logs"**

Otwórz dashboard:
```
http://localhost/index.php
```

1. Przewiń do sekcji **"System Logs"**
2. Kliknij zakładkę **"PPO Logs"**
3. Zobacz real-time progress checkpointów i auto-restart

---

### **3. Sprawdź Checkpointy**

```bash
# Docker
docker exec -it pilot_bot ls -lh models/checkpoints/

# Lokalnie
ls -lh models/checkpoints/
```

**Przykładowy output:**
```
-rw-r--r-- 1 root root 15M Jan 24 14:30 ppo_checkpoint_10000.zip
-rw-r--r-- 1 root root 456 Jan 24 14:30 ppo_checkpoint_10000_metadata.json
-rw-r--r-- 1 root root 15M Jan 24 14:35 ppo_checkpoint_20000.zip
-rw-r--r-- 1 root root 458 Jan 24 14:35 ppo_checkpoint_20000_metadata.json
```

---

### **4. Przeczytaj Metadata Checkpointu**

```bash
# Docker
docker exec -it pilot_bot cat models/checkpoints/ppo_checkpoint_10000_metadata.json

# Lokalnie
cat models/checkpoints/ppo_checkpoint_10000_metadata.json
```

**Output:**
```json
{
  "timesteps": 10000,
  "total_timesteps": 200000,
  "progress_pct": 5.0,
  "episodes": 48,
  "winning_episodes": 26,
  "win_rate": 54.2,
  "cumulative_reward": 1245.67,
  "saved_at": "2026-01-24T14:30:15.123456"
}
```

---

## 🔧 Konfiguracja

### **Zmiana Interwału Checkpointów w Supervisorze**

Edytuj `main.py` (linia ~588):
```python
cmd = [
    python_cmd, 
    self.rl_trainer_file,
    '--timesteps', '200000',
    '--data-days', str(data_days),
    '--checkpoint-interval', '5000',  # ← ZMIEŃ TUTAJ (domyślnie 10000)
    '--balance', '1000',
    '--leverage', '20'
]
```

---

### **Zmiana Limitu Auto-Restart**

Edytuj `main.py` (linia ~387):
```python
# Check restart count (prevent infinite loop)
restart_count = training_info.get('restart_count', 0)
if restart_count >= 5:  # ← ZMIEŃ TUTAJ (domyślnie 3)
    logger.error(f"❌ Auto-restart limit reached ({restart_count}/5 attempts)")
    return False
```

---

## 🛡️ Bezpieczeństwo i Best Practices

### ✅ **Zalecenia**
1. **Checkpoint interval**: 10,000 steps (optymalna częstotliwość)
2. **Auto-restart limit**: 3 próby (zapobiega pętli)
3. **Backup checkpointów**: Regularnie kopiuj `models/checkpoints/` na dysk
4. **Monitoruj pamięć**: Sprawdzaj `docker stats` podczas treningu

### ⚠️ **Ostrzeżenia**
- Checkpointy zajmują ~15MB każdy
- Nie usuwaj checkpointów podczas aktywnego treningu
- Auto-restart może nie pomóc jeśli OOM jest spowodowany brakiem RAM (zwiększ `mem_limit` w docker-compose.yml)

---

## 🐛 Troubleshooting

### **Problem: "No checkpoints found for auto-restart"**

**Przyczyna:** Trening crash'ował przed pierwszym checkpointem (< 10k kroków)

**Rozwiązanie:**
- Zmniejsz `--checkpoint-interval` do 5000 lub 2000
- Zwiększ pamięć Docker (`mem_limit` w docker-compose.yml)

---

### **Problem: "Auto-restart limit reached (3/3 attempts)"**

**Przyczyna:** OOM występuje nawet po auto-restart (zbyt mało RAM)

**Rozwiązanie:**
1. Zwiększ pamięć Docker do 56GB:
   ```yaml
   mem_limit: 56g
   ```
2. Zmniejsz `--data-days` z 180 na 90
3. Zmniejsz `--timesteps` z 200000 na 100000

---

### **Problem: "Checkpoint loaded but training fails immediately"**

**Przyczyna:** Uszkodzony checkpoint lub zmieniona struktura danych

**Rozwiązanie:**
- Usuń uszkodzony checkpoint
- Wznów od wcześniejszego checkpointu
- Rozpocznij trening od zera (usuń wszystkie checkpointy)

---

## 📈 Przykładowy Workflow

### **Scenariusz: Trening 200k kroków z auto-restart**

```bash
# 1. Uruchom trening
python3.12 src/process_rl_trainer.py --timesteps 200000 --data-days 180

# Checkpoint zapisany: 10000 steps (5%)
# Checkpoint zapisany: 20000 steps (10%)
# Checkpoint zapisany: 30000 steps (15%)
# [CRASH! OOM]

# 2. Auto-restart wykrywa crash
# [Auto-restart] Resuming from ppo_checkpoint_30000...

# Checkpoint zapisany: 40000 steps (20%)
# Checkpoint zapisany: 50000 steps (25%)
# ... continues ...
# ✅ Training completed successfully!
```

---

## 📝 Podsumowanie

| Funkcja | Domyślna Wartość | Konfiguracja |
|---------|------------------|--------------|
| Checkpoint interval | 10,000 kroków | `--checkpoint-interval` |
| Auto-restart limit | 3 próby | `main.py` linia ~387 |
| Checkpoint lokalizacja | `models/checkpoints/` | `src/ai/rl_agent.py` |
| Logi | `logs/PPO.log` | `src/utils/logger.py` |

---

## 🎉 Gotowe!

System automatycznie:
- ✅ Zapisuje checkpointy co 10k kroków
- ✅ Wznawia trening po crash'u (OOM)
- ✅ Loguje szczegółowy progress do `PPO.log`
- ✅ Pokazuje status w dashboard (zakładka "PPO Logs")

**Żadnej dodatkowej konfiguracji nie trzeba!** 🚀
