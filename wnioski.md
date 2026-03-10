# Audyt Strategii i Zachowania AI Tradera

Na podstawie analizy kodu źródłowego (`src/process_trader.py`, `src/ai/rl_agent.py`, `src/ai/models.py`, `config.json`), oto szczegółowy raport dotyczący strategii inwestycyjnej, zachowania sztucznej inteligencji oraz systemów zarządzania ryzykiem.

## 1. Strategia Ogólna: Titan Adaptive Defense

System działa w oparciu o architekturę hybrydową, łączącą predykcje techniczne (Ensemble Model) z decyzjami strategicznymi (RL Agent) oraz sztywnymi regułami bezpieczeństwa (Execution Manager).

### Kluczowe Cechy:
*   **Timeframe**: 1 minuta (`1m`) - agresywny scalping/day-trading.
*   **Dźwignia**: 20x (Futures).
*   **Alokacja**: 10% kapitału na transakcję.
*   **Tryb Pracy**: Sequential Relay (jeden ticker trenowany na raz) + Futures Sniper (egzekucja).

---

## 2. Zachowanie AI (Sygnały Wejścia)

Decyzja o otwarciu pozycji jest wieloetapowa:

1.  **Analiza Techniczna (Ensemble Model)**:
    *   Model przetwarza 19 wskaźników (RSI, MACD, Bollinger Bands, Funding Rates, Market Breadth).
    *   Generuje sygnał `LONG`/`SHORT` oraz `Confidence Score` (0-100%).
2.  **Filtr Pewności (Confidence Threshold)**:
    *   Pozycja jest otwierana **tylko**, gdy `Confidence > 60%`.
    *   Poniżej tego progu sygnał jest ignorowany (`WAITING`).
3.  **Veto System (Matrix Bias)**:
    *   Sprawdzany jest ogólny sentyment rynku (`global_bias`) na podstawie Market Breadth (Bulls vs Bears).
    *   Jeśli sygnał jest sprzeczny z rynkiem (np. LONG podczas BEARISH bias), transakcja jest blokowana.
    *   **Wyjątek**: Jeśli `Confidence > 85%`, system ignoruje bias rynku ("High Confidence Override").
4.  **RL Agent (Warstwa Decyzyjna - Opcjonalna)**:
    *   Jeśli aktywny, Agent PPO otrzymuje stan portfela i predykcję LSTM.
    *   Może nadpisać sygnał: zmienić na `HOLD` lub wymusić `CLOSE`.

---

## 3. Zarządzanie Ryzykiem (Zamykanie Pozycji)

System posiada zaawansowany moduł "Profit Guardian" i "Recovery Mode".

### Scenariusze Wyjścia (Zysk):
1.  **Profit Snatcher**:
    *   Aktywacja przy **ROI > 6%**.
    *   Zamyka pozycję, jeśli AI wykryje słabnące momentum (nawet jeśli cena wciąż rośnie).
2.  **Trailing Stop**:
    *   Aktywacja po przekroczeniu **ROI > 3%**.
    *   Śledzi najwyższy punkt zysku (`highest_pnl`).
    *   Zamyka pozycję przy cofnięciu o **1.5%** od szczytu.
3.  **Anti-Spike**:
    *   Chroni zysk, jeśli cena gwałtownie spadnie z poziomu >3% do 0.5%.
4.  **Take Profit (TP)**:
    *   Sztywny poziom: Cena wejścia ± (4 × ATR).

### Scenariusze Wyjścia (Strata) i Obrona:
1.  **Stop Loss (SL)**:
    *   Sztywny poziom: Cena wejścia ± (2 × ATR).
2.  **Recovery Mode (Inteligentne Uśrednianie/Hold)**:
    *   Aktywuje się, gdy strata przekroczy **-3%**.
    *   AI ocenia szansę na odbicie w ciągu 30 minut.
    *   Jeśli szansa jest wysoka (`Conf > 75%`): Trzyma pozycję (do max -85% ROI - Hard Liquidation Buffer).
    *   Jeśli szansa jest mała: Natychmiast zamyka pozycję ("Emergency Exit").
3.  **AI Reversal**:
    *   Natychmiastowe odwrócenie pozycji, jeśli AI zmieni zdanie (np. z LONG na SHORT) z pewnością > 70%.

---

## 4. Architektura Modeli AI

System wykorzystuje dwa główne silniki predykcyjne:

### A. Ensemble Model v3.4 (Kierunek Ceny)
Jest to stos (stacking) czterech modeli, zarządzany przez Meta-Learnera (Regresja Logistyczna):
1.  **LSTM z Attention**: Analizuje sekwencje czasowe i zależności długoterminowe.
2.  **Random Forest**: Wykrywa nieliniowe wzorce i ważność cech.
3.  **XGBoost**: Gradient boosting dla złożonych interakcji.
4.  **LightGBM**: Szybki boosting, odporny na szum.

*Cel*: Przewidywanie kierunku ceny (UP/DOWN) na 30 minut w przód.

### B. RL Agent (PPO - Proximal Policy Optimization)
Agent uczenia ze wzmocnieniem, który "gra" na giełdzie.
*   **Obserwacja**: 28 zmiennych (wskaźniki techniczne + stan portfela + predykcje LSTM).
*   **Nagrody**:
    *   +200 pkt za ROI > 5%.
    *   -500 pkt za Drawdown > 30%.
    *   Kara za czas trwania pozycji (wymusza szybkie decyzje).

---

## 5. Konfiguracja (`config.json`)

*   **Risk Management**:
    *   `sl_atr_mult`: 2.0 (Mnożnik ATR dla Stop Loss)
    *   `tp_atr_mult`: 4.0 (Mnożnik ATR dla Take Profit)
    *   `min_profit_to_lock`: 6.0% (Próg Profit Snatcher)
    *   `recovery_mode`: true (Włączony tryb ratunkowy)
*   **Training**:
    *   `lookback_days`: 180 (Dane treningowe: 6 miesięcy)
    *   `prediction_horizon`: 30 (30 minut w przód)

## Podsumowanie
AI Trader zachowuje się jak **agresywny snajper**. Czeka na bardzo pewne sygnały (>60%), wchodzi z dużą dźwignią (20x) i szybko realizuje zyski (Profit Snatcher), jednocześnie posiadając wielowarstwowy system obrony przed głębokimi stratami (Recovery Mode, Veto). Jest to strategia typu "High Probability Scalping".
