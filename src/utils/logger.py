import os
import datetime
import threading
import sys

# Color codes for console output
COLOR_CODES = {
    "INFO": "",
    "SUCCESS": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",    # Red
    "CRITICAL": "\033[35m", # Magenta
    "PULS": "\033[36m"      # Cyan
}

RESET_CODE = "\033[0m"

class Logger:
    _instance = None
    _lock = threading.Lock()
    _file_lock = threading.Lock()

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.log_dir = os.path.join(self.base_dir, 'logs')
        self.log_file = os.path.join(self.log_dir, 'system.log')
        self.ppo_log_file = os.path.join(self.log_dir, 'PPO.log')  # Dedicated PPO log file
        self.lstm_log_file = os.path.join(self.log_dir, 'LSTM.log')  # Dedicated LSTM log file

        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)

    @classmethod
    def get_logger(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = Logger()
        return cls._instance

    def log(self, msg, level="INFO", ppo_only=False, lstm_only=False):
        """
        Logs to console (VISIBLE) and file with thread safety.
        
        Args:
            msg: Message to log
            level: Log level (INFO, SUCCESS, WARNING, ERROR, CRITICAL)
            ppo_only: If True, only log to PPO.log (not system.log)
            lstm_only: If True, only log to LSTM.log (not system.log)
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        color = COLOR_CODES.get(level, "")
        formatted_msg = f"[{timestamp}] [{level}] {msg}"
        colored_msg = f"{color}{formatted_msg}{RESET_CODE}" if color else formatted_msg

        # 1. Print to Console
        try:
            print(colored_msg)
        except Exception:
            pass # Ignore console encoding errors

        # 2. Write to File (Thread-Safe)
        try:
            with self._file_lock:
                # Always write to system.log unless ppo_only=True or lstm_only=True
                if not ppo_only and not lstm_only:
                    with open(self.log_file, "a", encoding='utf-8') as f:
                        f.write(formatted_msg + "\n")
                
                # If message is PPO-related (contains 'PPO', 'RL', 'Episode', 'Bankructwo'),
                # also write to PPO.log
                ppo_keywords = ['PPO', 'RL', 'Episode', 'TERMINATED', 'Bankructwo', 'Agent', 'timesteps']
                if ppo_only or any(keyword in msg for keyword in ppo_keywords):
                    with open(self.ppo_log_file, "a", encoding='utf-8') as f:
                        f.write(formatted_msg + "\n")
                
                # If message is LSTM-related (contains 'LSTM', 'Ensemble', 'Epoch', 'Accuracy'),
                # also write to LSTM.log
                lstm_keywords = ['LSTM', 'Ensemble', 'Epoch', 'Training samples', 'candles', 'Feature Engineering', 'Model trained']
                if lstm_only or any(keyword in msg for keyword in lstm_keywords):
                    with open(self.lstm_log_file, "a", encoding='utf-8') as f:
                        f.write(formatted_msg + "\n")
        except Exception as e:
            print(f"[ERROR] Logging to file failed: {e}")

# Global Accessor
def log(msg, level="INFO", ppo_only=False, lstm_only=False):
    """
    Global log function.
    
    Args:
        msg: Message to log
        level: Log level (INFO, SUCCESS, WARNING, ERROR, CRITICAL)
        ppo_only: If True, only log to PPO.log (not system.log) - useful for detailed PPO training stats
        lstm_only: If True, only log to LSTM.log (not system.log) - useful for detailed LSTM training stats
    """
    Logger.get_logger().log(msg, level, ppo_only=ppo_only, lstm_only=lstm_only)
