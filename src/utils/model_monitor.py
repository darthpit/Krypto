"""
AI Model Monitor & Auto-Retraining Watchdog
============================================
System automatycznego monitorowania i zarządzania treningiem modeli AI.

Funkcje:
- Śledzenie statusu treningu (TRAINING, IDLE, ERROR)
- Automatyczne wykrywanie modeli starszych niż 6 dni
- Pask postępu treningu w czasie rzeczywistym
- Statystyki skuteczności modeli
- Dashboard-ready JSON export
"""

import json
import os
import time
from datetime import datetime, timedelta

# Ścieżka do pliku statusu (widoczny z PHP Dashboard)
STATUS_FILE = 'models/ai_status.json'

class ModelMonitor:
    """
    Centralna klasa zarządzająca statusem wszystkich modeli AI w systemie.
    
    Modele:
    - lstm: LSTM Ensemble (Predykcje ceny)
    - rl_agent: PPO Reinforcement Learning Agent (Decyzje tradingowe)
    """
    
    def __init__(self):
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Tworzy domyślny plik statusu jeśli nie istnieje"""
        if not os.path.exists(STATUS_FILE):
            # Upewnij się, że folder models/ istnieje
            os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
            
            default_data = {
                "lstm": {
                    "name": "LSTM Ensemble v3.4",
                    "status": "IDLE",  # TRAINING, IDLE, ERROR
                    "progress": 0,
                    "last_trained": None,
                    "next_training": None,
                    "accuracy": 0.0,
                    "data_days": 180,  # Ilość dni historii używanych do treningu
                    "message": "Oczekuje na inicjalizację...",
                    "model_type": "predictor",  # predictor / decision_maker
                    "training_duration_avg": "30-45 min"
                },
                "rl_agent": {
                    "name": "PPO Agent (Sniper Mode)",
                    "status": "IDLE",
                    "progress": 0,
                    "last_trained": None,
                    "next_training": None,
                    "accuracy": 0.0,
                    "data_days": 180,
                    "message": "Oczekuje na inicjalizację...",
                    "model_type": "decision_maker",
                    "training_duration_avg": "2-6 hours"
                }
            }
            self._save(default_data)

    def _load(self):
        """Wczytuje aktualny status z pliku JSON"""
        try:
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading model status: {e}")
            return {}

    def _save(self, data):
        """Zapisuje status do pliku JSON (atomically)"""
        try:
            # Zapis atomowy (najpierw do .tmp, potem rename)
            temp_file = STATUS_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            # Replace atomically
            if os.path.exists(STATUS_FILE):
                os.remove(STATUS_FILE)
            os.rename(temp_file, STATUS_FILE)
            
        except Exception as e:
            print(f"⚠️ Error saving model status: {e}")

    def update_start(self, model_key, message="Rozpoczynam trening..."):
        """
        Oznacza start treningu modelu.
        
        Args:
            model_key: 'lstm' lub 'rl_agent'
            message: Wiadomość opisująca fazę treningu
        """
        data = self._load()
        if model_key in data:
            data[model_key]["status"] = "TRAINING"
            data[model_key]["progress"] = 0
            data[model_key]["message"] = message
            data[model_key]["training_started_at"] = datetime.now().isoformat()
            self._save(data)
            print(f"🚀 [{model_key}] Training started: {message}")

    def update_progress(self, model_key, percent, message):
        """
        Aktualizuje postęp treningu.
        
        Args:
            model_key: 'lstm' lub 'rl_agent'
            percent: Postęp 0-100
            message: Wiadomość opisująca aktualną fazę (np. "Epoch 5/10")
        """
        data = self._load()
        if model_key in data:
            data[model_key]["status"] = "TRAINING"
            data[model_key]["progress"] = min(100, max(0, percent))
            data[model_key]["message"] = message
            self._save(data)
            # Log tylko co 10% (redukuje spam)
            if percent % 10 == 0 or percent >= 95:
                print(f"📊 [{model_key}] Progress: {percent}% - {message}")

    def update_finish(self, model_key, accuracy, data_days=180):
        """
        Oznacza zakończenie treningu.
        
        Args:
            model_key: 'lstm' lub 'rl_agent'
            accuracy: Skuteczność modelu (0.0 - 1.0)
            data_days: Ilość dni danych użytych do treningu
        """
        data = self._load()
        if model_key in data:
            now = datetime.now()
            next_run = now + timedelta(days=7)
            
            data[model_key]["status"] = "IDLE"
            data[model_key]["progress"] = 100
            data[model_key]["last_trained"] = now.strftime("%Y-%m-%d %H:%M:%S")
            data[model_key]["next_training"] = next_run.strftime("%Y-%m-%d %H:%M:%S")
            data[model_key]["accuracy"] = round(accuracy * 100, 2)  # Convert to percentage
            data[model_key]["data_days"] = data_days
            data[model_key]["message"] = "Model aktywny i gotowy"
            
            # Remove temporary fields
            if "training_started_at" in data[model_key]:
                del data[model_key]["training_started_at"]
            
            self._save(data)
            print(f"✅ [{model_key}] Training completed! Accuracy: {accuracy:.1%}, Next training: {next_run.strftime('%Y-%m-%d %H:%M')}")

    def update_error(self, model_key, error_message):
        """
        Oznacza błąd treningu.
        
        Args:
            model_key: 'lstm' lub 'rl_agent'
            error_message: Treść błędu
        """
        data = self._load()
        if model_key in data:
            data[model_key]["status"] = "ERROR"
            data[model_key]["progress"] = 0
            data[model_key]["message"] = f"❌ Błąd: {error_message[:100]}"
            self._save(data)
            print(f"❌ [{model_key}] Training error: {error_message}")

    def check_needs_training(self, model_key, max_age_days=6):
        """
        Sprawdza czy model wymaga ponownego treningu.
        
        Args:
            model_key: 'lstm' lub 'rl_agent'
            max_age_days: Maksymalny wiek modelu w dniach (domyślnie 6)
            
        Returns:
            bool: True jeśli model jest starszy niż max_age_days lub nigdy nie był trenowany
        """
        data = self._load()
        if model_key not in data:
            return True  # Model nie istnieje - wymaga treningu
        
        last = data[model_key].get("last_trained")
        if not last:
            print(f"⚠️ [{model_key}] Never trained - needs training")
            return True  # Nigdy nie trenowany
        
        try:
            last_date = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
            age_days = (datetime.now() - last_date).days
            
            if age_days >= max_age_days:
                print(f"⚠️ [{model_key}] Model is {age_days} days old (>{max_age_days} days) - needs retraining")
                return True
            else:
                print(f"✅ [{model_key}] Model is fresh ({age_days} days old)")
                return False
                
        except Exception as e:
            print(f"⚠️ [{model_key}] Error parsing last_trained date: {e} - forcing training")
            return True

    def get_status(self, model_key):
        """
        Pobiera aktualny status konkretnego modelu.
        
        Args:
            model_key: 'lstm' lub 'rl_agent'
            
        Returns:
            dict: Status modelu lub None jeśli nie istnieje
        """
        data = self._load()
        return data.get(model_key)

    def get_all_status(self):
        """
        Pobiera status wszystkich modeli.
        
        Returns:
            dict: Pełny słownik statusów
        """
        return self._load()

    def is_training_active(self, model_key):
        """
        Sprawdza czy trening jest aktualnie w toku.
        
        Args:
            model_key: 'lstm' lub 'rl_agent'
            
        Returns:
            bool: True jeśli model jest w trakcie treningu
        """
        data = self._load()
        if model_key not in data:
            return False
        return data[model_key].get("status") == "TRAINING"

    def get_time_to_next_training(self, model_key):
        """
        Oblicza czas do następnego zaplanowanego treningu.
        
        Args:
            model_key: 'lstm' lub 'rl_agent'
            
        Returns:
            timedelta or None: Czas do następnego treningu lub None jeśli nie zaplanowano
        """
        data = self._load()
        if model_key not in data:
            return None
        
        next_training = data[model_key].get("next_training")
        if not next_training:
            return None
        
        try:
            next_date = datetime.strptime(next_training, "%Y-%m-%d %H:%M:%S")
            return next_date - datetime.now()
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS (Quick Access)
# ═══════════════════════════════════════════════════════════════════

def get_monitor():
    """Zwraca instancję ModelMonitor (singleton pattern)"""
    global _monitor_instance
    if '_monitor_instance' not in globals():
        _monitor_instance = ModelMonitor()
    return _monitor_instance


# Quick access functions (dla ułatwienia integracji)
def start_training(model_key, message="Rozpoczynam trening..."):
    """Szybki dostęp: Oznacz start treningu"""
    get_monitor().update_start(model_key, message)

def update_progress(model_key, percent, message):
    """Szybki dostęp: Zaktualizuj postęp"""
    get_monitor().update_progress(model_key, percent, message)

def finish_training(model_key, accuracy, data_days=180):
    """Szybki dostęp: Oznacz zakończenie treningu"""
    get_monitor().update_finish(model_key, accuracy, data_days)

def mark_error(model_key, error_message):
    """Szybki dostęp: Oznacz błąd"""
    get_monitor().update_error(model_key, error_message)

def needs_training(model_key, max_age_days=6):
    """Szybki dostęp: Sprawdź czy wymaga treningu"""
    return get_monitor().check_needs_training(model_key, max_age_days)


# ═══════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing Model Monitor...")
    
    monitor = ModelMonitor()
    
    # Test 1: Start training
    print("\n1. Starting LSTM training...")
    monitor.update_start("lstm", "Pobieranie danych...")
    time.sleep(1)
    
    # Test 2: Progress updates
    for i in range(0, 101, 20):
        monitor.update_progress("lstm", i, f"Training epoch {i//10}/10")
        time.sleep(0.5)
    
    # Test 3: Finish training
    monitor.update_finish("lstm", accuracy=0.88, data_days=180)
    
    # Test 4: Check if needs training
    print("\n2. Checking if model needs training...")
    needs_retrain = monitor.check_needs_training("lstm", max_age_days=6)
    print(f"Needs retraining: {needs_retrain}")
    
    # Test 5: Get status
    print("\n3. Getting all status...")
    status = monitor.get_all_status()
    print(json.dumps(status, indent=2))
    
    print("\n✅ Model Monitor test complete!")
