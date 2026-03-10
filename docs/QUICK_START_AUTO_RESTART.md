# 🚀 Quick Start - Auto-Restart & Checkpoints

## ⚡ TL;DR

**System automatycznie zapisuje model co 10k kroków i wznawia trening po crash'u.**

Nic nie musisz robić - po prostu uruchom:

```bash
docker-compose up -d
```

---

## 📦 Co Dostałeś?

### ✅ **1. Automatyczne Checkpointy**
Model PPO zapisywany **co 10,000 kroków**:
```
models/checkpoints/
├── ppo_checkpoint_10000.zip  ← Postęp: 5%
├── ppo_checkpoint_20000.zip  ← Postęp: 10%
└── ppo_checkpoint_30000.zip  ← Postęp: 15%
```

### ✅ **2. Auto-Restart Po OOM**
Jeśli trening crash'uje (brak pamięci):
- System automatycznie wykrywa crash
- Wznawia od ostatniego checkpointu
- Kontynuuje trening tam gdzie skończył

### ✅ **3. Szczegółowe Logi**
Wszystkie detale w pliku `logs/PPO.log`:
```
[INFO] 💾 Checkpoint saved: 10000/200000 (5%) | Win Rate: 54.2%
[INFO] 💾 Checkpoint saved: 20000/200000 (10%) | Win Rate: 56.8%
[ERROR] 💀 ZOMBIE DETECTED! Auto-restarting...
[INFO] 🔄 Resuming from checkpoint: ppo_checkpoint_20000
[SUCCESS] ✅ Checkpoint loaded: 20000 steps completed
```

---

## 🎯 Podstawowe Użycie

### **Scenariusz 1: Normalny Trening (Automatyczny)**

Bot robi wszystko sam:
```bash
# Uruchom bota
docker-compose up -d

# Monitoruj logi
docker exec -it pilot_bot tail -f logs/PPO.log
```

Supervisor automatycznie:
1. Uruchamia trening PPO co 7 dni
2. Zapisuje checkpointy co 10k kroków
3. Wznawia po crash'u od ostatniego checkpointu

---

### **Scenariusz 2: Ręczny Trening**

Chcesz ręcznie wytrenować model:

```bash
# Wejdź do kontenera
docker exec -it pilot_bot bash

# Uruchom trening (200k kroków, 180 dni danych)
python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --data-days 180
```

Trening automatycznie:
- Zapisuje checkpoint co 10k kroków
- Można przerwać (Ctrl+C) i wznowić później

---

### **Scenariusz 3: Wznowienie Po Przerwaniu**

Przerwałeś trening i chcesz kontynuować:

```bash
# 1. Sprawdź dostępne checkpointy
ls -lh models/checkpoints/

# Output:
# ppo_checkpoint_10000.zip
# ppo_checkpoint_20000.zip
# ppo_checkpoint_30000.zip  ← Ostatni checkpoint

# 2. Wznów od ostatniego checkpointu
python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --resume ./models/checkpoints/ppo_checkpoint_30000
```

Model wznowi trening od 30k kroków i będzie kontynuował do 200k.

---

## 📊 Jak Sprawdzić Postęp?

### **Opcja 1: Dashboard (Najłatwiej)**

1. Otwórz: `http://localhost/index.php`
2. Przewiń do **"System Logs"**
3. Kliknij zakładkę **"PPO Logs"**
4. Zobacz real-time progress!

### **Opcja 2: Logi (Terminal)**

```bash
# Real-time monitoring
docker exec -it pilot_bot tail -f logs/PPO.log

# Ostatnie 50 linii
docker exec -it pilot_bot tail -n 50 logs/PPO.log | grep "Checkpoint\|Progress\|Win Rate"
```

### **Opcja 3: Checkpointy (Pliki)**

```bash
# Lista checkpointów
docker exec -it pilot_bot ls -lh models/checkpoints/

# Metadata ostatniego checkpointu
docker exec -it pilot_bot cat models/checkpoints/ppo_checkpoint_30000_metadata.json
```

**Przykładowy output:**
```json
{
  "timesteps": 30000,
  "total_timesteps": 200000,
  "progress_pct": 15.0,
  "win_rate": 58.3,
  "episodes": 142
}
```

---

## 🔧 Konfiguracja (Opcjonalnie)

Domyślne ustawienia działają świetnie, ale możesz dostosować:

### **Zmień Częstotliwość Checkpointów**

Chcesz zapisywać **co 5k kroków** zamiast 10k?

```bash
python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --checkpoint-interval 5000  # ← Zapisuj częściej
```

---

### **Zmień Ilość Danych Treningowych**

Domyślnie: **180 dni** (6 miesięcy)

Użyj **90 dni** (mniej RAM):
```bash
python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --data-days 90  # ← Mniej danych = mniej pamięci
```

---

## 🆘 Najczęstsze Problemy

### **Problem: "Out of Memory (OOM)" po każdym restart'ie**

**Rozwiązanie:**
1. Zwiększ pamięć Docker w `docker-compose.yml`:
   ```yaml
   mem_limit: 56g  # Było: 48g
   ```
2. Lub zmniejsz dane:
   ```bash
   --data-days 90  # Zamiast 180
   ```

---

### **Problem: "No checkpoints found"**

**Przyczyna:** Trening crash'ował przed 10k kroków

**Rozwiązanie:**
```bash
# Zapisuj checkpoint co 5k kroków
--checkpoint-interval 5000
```

---

### **Problem: "Training stuck at 0%"**

**Przyczyna:** Brak danych w bazie

**Rozwiązanie:**
```bash
# Zsynchronizuj dane
docker exec -it pilot_bot python3.12 src/process_trainer.py
```

---

## 📌 Kluczowe Pliki

| Plik | Opis |
|------|------|
| `logs/PPO.log` | Szczegółowe logi treningu PPO |
| `models/checkpoints/ppo_checkpoint_*.zip` | Zapisane modele |
| `models/checkpoints/*_metadata.json` | Metadata (win rate, progress) |
| `models/rl_training_info.json` | Status treningu (PID, restart count) |
| `models/.rl_training.lock` | Lockfile (trening w toku) |

---

## 🎓 Zaawansowane

### **Ręczne Czyszczenie Checkpointów**

Zbyt wiele checkpointów (zużycie dysku)?

```bash
# Usuń stare checkpointy (zostaw ostatni)
docker exec -it pilot_bot bash -c "cd models/checkpoints && ls -t ppo_checkpoint_*.zip | tail -n +4 | xargs rm -f"
```

To usunie wszystkie checkpointy oprócz 3 najnowszych.

---

### **Export Checkpointu Na Dysk**

Chcesz zabezpieczyć checkpoint?

```bash
# Skopiuj checkpoint z Dockera na host
docker cp pilot_bot:/app/models/checkpoints/ppo_checkpoint_30000.zip ./backup/
docker cp pilot_bot:/app/models/checkpoints/ppo_checkpoint_30000_metadata.json ./backup/
```

---

### **Import Checkpointu Z Dysku**

Chcesz przywrócić stary checkpoint?

```bash
# Skopiuj z hosta do Dockera
docker cp ./backup/ppo_checkpoint_30000.zip pilot_bot:/app/models/checkpoints/
docker cp ./backup/ppo_checkpoint_30000_metadata.json pilot_bot:/app/models/checkpoints/

# Wznów trening
docker exec -it pilot_bot python3.12 src/process_rl_trainer.py \
  --timesteps 200000 \
  --resume ./models/checkpoints/ppo_checkpoint_30000
```

---

## ✅ Checklist - Czy Wszystko Działa?

Sprawdź czy system jest poprawnie skonfigurowany:

```bash
# 1. ✅ Logi PPO istnieją i są aktualizowane
docker exec -it pilot_bot ls -lh logs/PPO.log

# 2. ✅ Folder checkpointów istnieje
docker exec -it pilot_bot ls -d models/checkpoints/

# 3. ✅ Bot działa
docker ps | grep pilot_bot

# 4. ✅ Dashboard odpowiada
curl -I http://localhost/index.php
```

Jeśli wszystkie komendy zwracają OK → **System gotowy!** 🎉

---

## 📚 Więcej Informacji

Szczegółowa dokumentacja: [`docs/RL_AUTO_RESTART_CHECKPOINTS.md`](./RL_AUTO_RESTART_CHECKPOINTS.md)

---

**Pytania? Problem?** Sprawdź logi:
```bash
docker exec -it pilot_bot tail -f logs/PPO.log
```
