import os
import joblib
import datetime
import logging

MODELS_DIR = "models"

def ensure_models_dir():
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)

def get_model_filename(ticker, strategy_name):
    """
    Generates a standardized filename for the model.
    Format: model_{ticker}_{strategy}_{timestamp}.pkl
    """
    # Clean ticker name (e.g. BTC/USDT -> BTC_USDT)
    clean_ticker = ticker.replace("/", "_")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"model_{clean_ticker}_{strategy_name}_{timestamp}.pkl"

def save_model(model, ticker, strategy_name):
    """
    Saves the model to disk.
    Returns the absolute path of the saved model.
    """
    ensure_models_dir()
    filename = get_model_filename(ticker, strategy_name)
    filepath = os.path.join(MODELS_DIR, filename)

    try:
        if hasattr(model, 'save_custom'):
            model.save_custom(filepath)
        else:
            joblib.dump(model, filepath)

        logging.info(f"Model saved to {filepath}")
        return os.path.abspath(filepath)
    except Exception as e:
        logging.error(f"Failed to save model: {e}")
        raise

def load_model(filepath):
    """
    Loads a model from disk.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Model file not found: {filepath}")

    try:
        model = joblib.load(filepath)
        if hasattr(model, 'rehydrate'):
            model.rehydrate(filepath)

        logging.info(f"Model loaded from {filepath}")
        return model
    except Exception as e:
        logging.error(f"Failed to load model from {filepath}: {e}")
        raise
