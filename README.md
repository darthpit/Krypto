# 🚀 AI Crypto Pilot - Titan Stack v5.0 (Full Cockpit)

**AI Crypto Pilot** to zaawansowany, w pełni autonomiczny system handlu algorytmicznego (Quantitative Trading) oparty na sztucznej inteligencji. System został zaprojektowany do działania na rynku kryptowalut (Futures/Spot) w architekturze mikroserwisowej opartej na Dockerze.

Wersja **v5.0** wprowadza **Reinforcement Learning (RL)**, zaawansowany **Ensemble (XGBoost + LightGBM)** oraz integrację **Funding Rates**, celując w trafność predykcji na poziomie 90%.

---

## 🧠 Kluczowe Funkcje i Logika Systemu

System nie opiera się na prostych wskaźnikach (jak RSI < 30), lecz na wielowarstwowym procesie decyzyjnym, który naśladuje pracę funduszu hedgingowego.

### 1. Hybrydowy Silnik AI (Ensemble Stack)
Decyzje podejmuje "komitet" modeli AI, ważony przez Meta-Learnera:
*   **LSTM z Attention:** Sieć neuronowa analizująca sekwencje czasowe (trendy).
*   **XGBoost & LightGBM:** Modele oparte na drzewach decyzyjnych (Gradient Boosting) do analizy nieliniowych zależności między wskaźnikami.
*   **Random Forest:** Las losowy dla stabilizacji wyników.
*   **RL Agent (PPO):** Agent uczenia ze wzmocnieniem, który podejmuje ostateczną decyzję (HOLD/LONG/SHORT/CLOSE) uwzględniając stan portfela i zarządzanie ryzykiem.

### 2. Strategia "Micro-Input / Macro-Output"
Unikalne podejście do analizy rynku wprowadzone w wersji 3.4.0:
*   **Input (Micro):** Analiza świec 1-minutowych, aby wykrywać "Liquidity Grabs" i nagłe skoki wolumenu.
*   **Target (Macro):** Predykcja trendu na 30 minut do przodu, co filtruje szum rynkowy i ignoruje drobne fluktuacje.

### 3. Holistic Guardian (Globalny Strażnik Ryzyka)
Moduł bezpieczeństwa analizujący cały rynek:
*   **Market Matrix:** Analiza korelacji Bitcoina z Top 50 Altcoinami.
*   **Market Breadth:** Stosunek byków do niedźwiedzi (Bulls/Bears Ratio).
*   **Veto System:** Jeśli AI sugeruje LONG, a rynek jest globalnie BEARISH, Strażnik blokuje transakcję (chyba że pewność AI przekracza 85%).

### 4. Titan Adaptive Defense (Zaawansowane Zarządzanie Pozycją)
System posiada adaptacyjny moduł obronny, który dynamicznie reaguje na sytuację rynkową:

#### Moduł 1: Profit Guardian (Inteligentne Wyjście)
*   **Profit Snatcher:** Aktywuje się przy ROI > 6%. Konsultuje się z AI – jeśli momentum słabnie, zamyka pozycję natychmiast ("Lock Profit").
*   **Anti-Spike Protection:** Monitoruje pozycje z zyskiem 0.5% - 3%. Jeśli wykryje nagły spadek zysku, zamyka pozycję, by uniknąć straty.
*   **Trailing Stop:** Aktywuje się przy +3% ROI. Zamyka pozycję przy cofnięciu o 1.5%.

#### Moduł 2: Recovery Mode (Tryb Ratunkowy)
*   Aktywuje się, gdy strata przekroczy -3%.
*   **Scenariusz A (Nadzieja):** Jeśli AI (confidence > 75%) przewiduje powrót ceny, system trzyma pozycję (Hard Stop dopiero przy -85% ROI, aby uniknąć likwidacji).
*   **Scenariusz B (Potwierdzenie błędu):** Jeśli AI potwierdza zły kierunek, system tnie stratę natychmiast przy -3%.

---

## 🏗 Architektura Techniczna (Titan Stack)

System działa w izolowanych kontenerach Docker:

1.  **`pilot_bot` (Python 3.12 + GPU):**
    *   **Core:** TensorFlow/Keras (LSTM), PyTorch (RL Agent), XGBoost/LightGBM.
    *   **Logic:** `process_trader.py` (cykl 1-min), `process_trainer.py` (trening modeli), `process_rl_trainer.py` (trening RL).
    *   **AI Control Center:** Backendowy monitor (`model_monitor.py`) automatycznie sprawdza wiek modeli co 5 sekund. Jeśli model LSTM jest starszy niż 6 dni, automatycznie uruchamia re-trening.
2.  **`pilot_postgres` (PostgreSQL 15):** Baza danych dla historii świec, transakcji i logów.
3.  **`pilot_redis` (Redis):** Pamięć podręczna do komunikacji między procesami.

---

## 📜 Historia Zmian i Aktualizacji (Changelog)

### ✅ V5.0 - Funding Rates & Advanced Ensemble (2026-01-22)
*Skupienie na integracji danych Futures i zaawansowanych modeli drzewiastych.*
*   **XGBoost & LightGBM:** Dodano dwa potężne modele gradient boosting do komitetu decyzyjnego, zwiększając trafność o ~10-15%.
*   **Funding Rates:** Integracja stóp finansowania z giełdy. Wysoki funding rate (>0.01%) sygnalizuje potencjalny SHORT (overcrowded longs).
*   **Feature Expansion:** Liczba wskaźników wejściowych wzrosła z 4 do 19 (m.in. Volume Profile, OBV, Volatility).

### ✅ V4.5 - Titan Stack & Adaptive Defense
*Fundament obecnej architektury oraz zaawansowana obrona.*
*   **Titan Adaptive Defense:** Wdrożenie modułów Profit Guardian i Recovery Mode.
*   **AI Control Center:** Automatyzacja treningu i monitoring wieku modeli.
*   **PostgreSQL:** Migracja z SQLite na PostgreSQL dla wydajności.
*   **Dashboard:** Interfejs webowy w PHP pokazujący status AI, paski postępu treningu i wykresy na żywo.

### ✅ V3.4.0 - Micro-Macro Strategy
*Rewolucja w sposobie postrzegania czasu przez AI.*
*   **Zmiana Targetu:** Zamiast przewidywać następną minutę (szum), AI przewiduje trend za 30 minut.
*   **Input 1-min:** Zachowano precyzyjne dane wejściowe 1-minutowe, aby widzieć strukturę rynku.
*   **Wynik:** Drastyczna redukcja fałszywych sygnałów (overtrading).

### ✅ V3.0.0 - RL Enhanced (Reinforcement Learning)
*Wprowadzenie agenta, który "rozumie" kontekst.*
*   **RL Agent (PPO):** Agent uczy się nie tylko przewidywać cenę, ale maksymalizować zysk (Reward Function).
*   **Context Aware:** Agent widzi PnL otwartej pozycji. Jeśli masz duży zysk, może zdecydować o wcześniejszym wyjściu (CLOSE), czego zwykły model predykcyjny nie potrafi.
*   **Veto Fix:** Ulepszono logikę VETO, pozwalając na "High Confidence Override" (>85%).

---

## 🖥 Dashboard i Interfejs

Interfejs użytkownika (`index.php`) dostępny pod `http://localhost:3000` (lub `http://localhost/CryptoSniperFutures/`).

### Główne Elementy:
1.  **AI Trader Performance:** Statystyki skuteczności (Win Rate, PnL, Sharpe Ratio).
2.  **Market Watch:** Pasek postępu "Condition Score" (Zgoda modeli AI) oraz historia (30 dni).
3.  **AI Training Center:** Panel w lewej kolumnie pokazujący status treningu modeli, paski postępu oraz czas do następnego automatycznego treningu.
4.  **System Logs:** Podgląd procesu myślowego bota (dlaczego otworzył/odrzucił pozycję, logi treningu).
5.  **AI Command Center:** Czat z modelem LLM (opcjonalnie z Ollama).

---

## 🛠 Instalacja i Uruchomienie

### Wymagania
*   Docker Desktop & Docker Compose
*   NVIDIA GPU (Zalecane dla treningu)
*   Python 3.10+ (do lokalnych skryptów pomocniczych)

### Instrukcja Szybkiego Startu
1.  **Przygotowanie:**
    ```bash
    git clone <repo_url>
    cd CryptoSniperFutures
    ```
2.  **Uruchomienie:**
    Uruchom `start.bat` (Windows) lub:
    ```bash
    docker-compose up --build -d
    ```
3.  **Automatyzacja:**
    System automatycznie wykryje brak modeli i rozpocznie ich trening (może to zająć kilka godzin dla RL). Status widoczny w Dashboardzie.

4.  **Dostęp:**
    Otwórz przeglądarkę i wejdź na `http://localhost` (lub port skonfigurowany w docker-compose).

---

## ⚠️ Rozwiązywanie Problemów

### Trening RL (Błędy modułów)
System działa w Dockerze. Jeśli widzisz błędy typu `ModuleNotFoundError: No module named 'ccxt'`, oznacza to, że próbujesz uruchomić skrypt na swoim komputerze, a nie w kontenerze.

**Poprawne uruchomienie treningu ręcznego:**
```bash
docker exec -it pilot_bot python src/process_rl_trainer.py --timesteps 200000
```

### Inne problemy
*   **Brak transakcji:** Sprawdź `Risk Score` w dashboardzie. Jeśli rynek jest `BEARISH` lub `Risk > 50`, bot czeka na bezpieczniejsze warunki.
*   **Puste wykresy:** Bot potrzebuje około 15-30 minut na pobranie historii i synchronizację danych po pierwszym uruchomieniu (`Cold Start`).
*   **Błędy bibliotek:** Jeśli widzisz błędy `xgboost not found`, upewnij się, że obraz Docker został przebudowany (`docker-compose build --no-cache`).

---

**Autor:** Projekt Titan Stack v5.0 (AI Implementation System)
