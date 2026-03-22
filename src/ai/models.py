import numpy as np
import os
import joblib
import logging
from sklearn.ensemble import RandomForestClassifier

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AI_Models")

# Try importing XGBoost and LightGBM
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not found. Install with: pip install xgboost")

try:
    from lightgbm import LGBMClassifier
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logger.warning("LightGBM not found. Install with: pip install lightgbm")

# Try importing TensorFlow
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, Model, load_model as keras_load_model
    from tensorflow.keras.layers import (
        LSTM, Dense, Dropout, Input, Bidirectional,
        MultiHeadAttention, GlobalAveragePooling1D, LayerNormalization
    )
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not found. LSTM will fall back to MLP (Sklearn).")
    from sklearn.neural_network import MLPClassifier

class LSTMAdapter:
    """
    LSTM with Multi-Head Attention Mechanism (FAZA 2.2)
    
    Architecture:
    - Bidirectional LSTM layers for capturing patterns in both directions
    - Multi-Head Attention to focus on important time steps
    - Layer Normalization for stable training
    - Dropout for regularization
    
    Expected Accuracy Gain: +4-7%
    """
    def __init__(self, input_shape=None, use_attention=True):
        self.model = None
        self.input_shape = input_shape
        self.is_tf = TF_AVAILABLE
        self.lstm_path = None
        self.use_attention = use_attention and TF_AVAILABLE

    def build_model(self, input_dim):
        if self.is_tf and self.use_attention:
            logger.info(f"🧠 Building LSTM with Multi-Head Attention (features: {input_dim})")
            
            # Input layer
            inputs = Input(shape=(1, input_dim), name='input_layer')
            
            # Bidirectional LSTM layers
            lstm1 = Bidirectional(LSTM(128, return_sequences=True, name='lstm1'))(inputs)
            lstm1_norm = LayerNormalization()(lstm1)
            
            lstm2 = Bidirectional(LSTM(64, return_sequences=True, name='lstm2'))(lstm1_norm)
            lstm2_norm = LayerNormalization()(lstm2)
            
            # Multi-Head Attention
            attention = MultiHeadAttention(
                num_heads=4,
                key_dim=32,
                name='attention'
            )(lstm2_norm, lstm2_norm)
            
            attention_norm = LayerNormalization()(attention)
            
            # Global pooling
            pooled = GlobalAveragePooling1D()(attention_norm)
            
            # Dense layers
            dense1 = Dense(32, activation='relu', name='dense1')(pooled)
            dropout1 = Dropout(0.3)(dense1)
            
            dense2 = Dense(16, activation='relu', name='dense2')(dropout1)
            dropout2 = Dropout(0.2)(dense2)
            
            # Output
            output = Dense(1, activation='sigmoid', name='output')(dropout2)
            
            # Build model
            model = Model(inputs=inputs, outputs=output)
            model.compile(
                optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                loss='binary_crossentropy',
                metrics=['accuracy']
            )
            
            self.model = model
            logger.info(f"✅ LSTM with Attention built successfully ({model.count_params()} parameters)")
            
        elif self.is_tf:
            # Basic LSTM (fallback)
            logger.info(f"Building Basic LSTM (features: {input_dim})")
            model = Sequential()
            model.add(Input(shape=(1, input_dim)))
            model.add(LSTM(50, return_sequences=False))
            model.add(Dropout(0.2))
            model.add(Dense(1, activation='sigmoid'))
            model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
            self.model = model
        else:
            # Fallback to MLP
            logger.info("Using MLP fallback (TensorFlow not available)")
            self.model = MLPClassifier(hidden_layer_sizes=(50, 30), max_iter=500, random_state=42)

    def fit(self, X, y):
        if self.model is None:
            self.build_model(X.shape[1])

        if self.is_tf:
            # ═══════════════════════════════════════════════════════════════════
            # MEMORY OPTIMIZATION for 180-day datasets (259,200 samples)
            # ═══════════════════════════════════════════════════════════════════
            # Enable memory growth (prevents TensorFlow from allocating all GPU memory)
            try:
                gpus = tf.config.list_physical_devices('GPU')
                if gpus:
                    for gpu in gpus:
                        tf.config.experimental.set_memory_growth(gpu, True)
                    logger.info(f"✅ GPU Memory Growth enabled for {len(gpus)} GPU(s)")
            except Exception as e:
                logger.warning(f"Could not enable GPU memory growth: {e}")
            
            # Reshape for LSTM: (Samples, TimeSteps, Features)
            X_reshaped = np.array(X).reshape((X.shape[0], 1, X.shape[1]))
            # Convert y to numpy
            y_np = np.array(y)
            
            # Train with more epochs if using attention (more complex model)
            epochs = 10 if self.use_attention else 5
            
            # ADAPTIVE BATCH SIZE for large datasets (180 days = 259,200 samples)
            # Larger batch = faster training, less memory fragmentation
            batch_size = 64 if len(X) > 100000 else 32
            logger.info(f"Using batch_size={batch_size} for {len(X)} samples")
            
            # Early stopping to prevent overfitting
            early_stop = tf.keras.callbacks.EarlyStopping(
                monitor='loss',
                patience=3,
                restore_best_weights=True,
                verbose=0
            )
            
            # MEMORY CLEANUP CALLBACK (clear session after each epoch)
            import gc
            class MemoryCleanupCallback(tf.keras.callbacks.Callback):
                def on_epoch_end(self, epoch, logs=None):
                    gc.collect()  # Force garbage collection
                    tf.keras.backend.clear_session()  # Clear TF session cache
            
            from sklearn.utils.class_weight import compute_class_weight
            classes = np.unique(y_np)
            class_weights_array = compute_class_weight(class_weight='balanced', classes=classes, y=y_np)
            class_weights_dict = dict(zip(classes, class_weights_array))

            logger.info(f"Training LSTM for {epochs} epochs with memory optimization and balanced class weights...")
            self.model.fit(
                X_reshaped, y_np,
                epochs=epochs,
                batch_size=batch_size,
                verbose=0,
                callbacks=[early_stop, MemoryCleanupCallback()],
                class_weight=class_weights_dict
            )
            
            # Final cleanup after training
            gc.collect()
            logger.info(f"✅ LSTM training complete, memory cleanup done")
        else:
            self.model.fit(X, y)

    def predict(self, X):
        if self.model is None:
            return np.zeros(len(X))

        if self.is_tf:
            X_reshaped = np.array(X).reshape((X.shape[0], 1, X.shape[1]))
            # Predict returns (N, 1)
            return self.model.predict(X_reshaped, verbose=0).flatten()
        else:
            # MLP predict_proba returns (N, 2)
            return self.model.predict_proba(X)[:, 1]

    def save(self, filepath):
        if self.is_tf and self.model:
            # Save Keras model to H5
            h5_path = filepath.replace('.pkl', '.h5')
            if not h5_path.endswith('.h5'): h5_path += '.h5'
            self.model.save(h5_path)
            return h5_path
        elif not self.is_tf and self.model:
             # Sklearn model pickles fine, handled by parent
             pass
        return None

    def load(self, filepath):
        if self.is_tf:
            h5_path = filepath.replace('.pkl', '.h5')
            if not h5_path.endswith('.h5'): h5_path += '.h5'
            # Also try the stored path if different
            if not os.path.exists(h5_path) and self.lstm_path and os.path.exists(self.lstm_path):
                h5_path = self.lstm_path

            if os.path.exists(h5_path):
                try:
                    self.model = keras_load_model(h5_path)
                    logger.info(f"Loaded LSTM from {h5_path}")
                except Exception as e:
                    logger.error(f"Failed to load LSTM h5: {e}")
        else:
            # Sklearn loaded by parent
            pass

class EnsembleModel:
    """
    Enhanced Hybrid Ensemble:
    - LSTM: Sequential patterns and temporal dependencies
    - RandomForest: Feature importance and non-linear patterns
    - XGBoost: Gradient boosting for complex interactions
    - LightGBM: Fast, robust gradient boosting
    - Meta-Learner: Stacking ensemble for optimal combination
    
    Version: 2.0 (FAZA 2.1)
    Expected Accuracy Gain: +8-12%
    """
    def __init__(self, use_advanced=True):
        self.use_advanced = use_advanced and XGBOOST_AVAILABLE and LIGHTGBM_AVAILABLE
        
        # Core models
        self.rf = RandomForestClassifier(
            n_estimators=100, 
            max_depth=5, 
            random_state=42,
            class_weight='balanced'  # CRITICAL FIX: Handle class imbalance
        )
        self.lstm = LSTMAdapter()
        
        # Advanced models (FAZA 2.1)
        if self.use_advanced:
            logger.info("🚀 Initializing Advanced Ensemble (LSTM + RF + XGBoost + LightGBM)")
            
            self.xgb = XGBClassifier(
                n_estimators=500,
                max_depth=7,
                learning_rate=0.01,
                subsample=0.8,
                colsample_bytree=0.8,
                use_label_encoder=False,
                eval_metric='logloss',
                random_state=42,
                verbosity=0,
                scale_pos_weight=1  # Will be updated in fit() based on class ratio
            )
            
            self.lgbm = LGBMClassifier(
                n_estimators=500,
                max_depth=7,
                learning_rate=0.01,
                num_leaves=127,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbosity=-1,
                class_weight='balanced'  # CRITICAL FIX: Handle class imbalance
            )
            
            # Meta-learner for stacking
            from sklearn.linear_model import LogisticRegression
            self.meta_model = LogisticRegression(random_state=42, max_iter=1000)
            
            self.ensemble_version = "2.0_ADVANCED"
        else:
            logger.warning("⚠️ Using Basic Ensemble (LSTM + RF only). Install XGBoost/LightGBM for better accuracy.")
            self.ensemble_version = "1.0_BASIC"

    def fit(self, X, y):
        """
        Train all models in the ensemble
        """
        logger.info(f"Training Ensemble v{self.ensemble_version} on {len(X)} samples...")
        
        # Calculate scale_pos_weight for XGBoost (for class imbalance)
        if self.use_advanced:
            class_counts = np.bincount(y.astype(int))
            if len(class_counts) == 2 and class_counts[1] > 0:
                scale_pos_weight = class_counts[0] / class_counts[1]
                logger.info(f"📊 XGBoost scale_pos_weight={scale_pos_weight:.2f} (class 0: {class_counts[0]}, class 1: {class_counts[1]})")
                self.xgb.set_params(scale_pos_weight=scale_pos_weight)
        
        # Train core models
        self.rf.fit(X, y)
        self.lstm.fit(X, y)
        
        if self.use_advanced:
            # Train advanced models
            logger.info("Training XGBoost...")
            self.xgb.fit(X, y)
            
            logger.info("Training LightGBM...")
            self.lgbm.fit(X, y)
            
            # Train meta-model on stacked predictions
            logger.info("Training Meta-Learner (Stacking)...")
            rf_pred = self.rf.predict_proba(X)
            lstm_pred = self.lstm.predict(X)
            xgb_pred = self.xgb.predict_proba(X)
            lgbm_pred = self.lgbm.predict_proba(X)
            
            # Stack predictions
            meta_X = np.column_stack([
                rf_pred[:, 1],      # RF probability for class 1
                lstm_pred,          # LSTM probability for class 1
                xgb_pred[:, 1],     # XGBoost probability for class 1
                lgbm_pred[:, 1]     # LightGBM probability for class 1
            ])
            
            self.meta_model.fit(meta_X, y)
            logger.info("✅ Advanced Ensemble Training Complete!")
        else:
            logger.info("✅ Basic Ensemble Training Complete!")

    def predict(self, X):
        # Returns class 0 or 1
        probs = self.predict_proba(X)
        return (probs[:, 1] > 0.5).astype(int)

    def predict_proba(self, X):
        """
        Predict probabilities using ensemble
        
        Returns: [[p0, p1], ...] where p1 = probability of UP (class 1)
        """
        if self.use_advanced:
            # Get predictions from all models
            rf_probs = self.rf.predict_proba(X)
            lstm_prob = self.lstm.predict(X)
            xgb_probs = self.xgb.predict_proba(X)
            lgbm_probs = self.lgbm.predict_proba(X)
            
            # Stack predictions
            meta_X = np.column_stack([
                rf_probs[:, 1],
                lstm_prob,
                xgb_probs[:, 1],
                lgbm_probs[:, 1]
            ])
            
            # Meta-model prediction
            final_probs = self.meta_model.predict_proba(meta_X)
            return final_probs
        else:
            # Basic ensemble (original implementation)
            rf_probs = self.rf.predict_proba(X)
            lstm_prob = self.lstm.predict(X)
            
            combined_p1 = (rf_probs[:, 1] + lstm_prob) / 2
            combined_p0 = 1.0 - combined_p1
            
            return np.column_stack((combined_p0, combined_p1))
    
    def get_feature_importance(self):
        """
        Get feature importance from tree-based models
        Useful for understanding which features drive predictions
        """
        if not self.use_advanced:
            return self.rf.feature_importances_
        
        # Average importance across tree models
        rf_importance = self.rf.feature_importances_
        xgb_importance = self.xgb.feature_importances_
        lgbm_importance = self.lgbm.feature_importances_
        
        avg_importance = (rf_importance + xgb_importance + lgbm_importance) / 3
        return avg_importance

    def save_custom(self, filepath):
        # 1. Save LSTM part to sidecar file if needed
        lstm_path = self.lstm.save(filepath)
        if lstm_path:
             self.lstm.lstm_path = lstm_path

        # 2. Remove LSTM Keras model from object before pickling to avoid errors
        # (Only if TF)
        temp_model = None
        if self.lstm.is_tf:
            temp_model = self.lstm.model
            self.lstm.model = None # Detach

        # 3. Save Ensemble (RF + LSTM wrapper + XGBoost + LightGBM + Meta)
        joblib.dump(self, filepath)
        logger.info(f"Ensemble v{self.ensemble_version} saved to {filepath}")

        # 4. Restore
        if self.lstm.is_tf:
            self.lstm.model = temp_model

        return filepath

    def rehydrate(self, filepath):
        # Called after joblib load
        if self.lstm.is_tf:
             # Look for sidecar
             # First try filepath replacement
             h5_path = filepath.replace('.pkl', '.h5')
             self.lstm.load(h5_path)
