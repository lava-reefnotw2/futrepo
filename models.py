import os
import time
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, KFold, cross_val_score, RandomizedSearchCV, StratifiedKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
import xgboost as xgb
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_curve, auc
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, Dropout, LayerNormalization, MultiHeadAttention, Flatten, Reshape
from scipy import stats

try:
    from catboost import CatBoostClassifier
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False


def prepare_data(df: pd.DataFrame, target_col: str):
    """
    Realiza limpieza básica y preprocesamiento del dataset.
    """
    df = df.dropna()
    X = df.drop(columns=[target_col])
    y = df[target_col]
    
    encoders = {}
    for col in X.select_dtypes(include=['object', 'category']).columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col])
        encoders[col] = le
        
    if y.dtype == 'object' or str(y.dtype) == 'category':
        le_y = LabelEncoder()
        y = le_y.fit_transform(y)
        encoders['target'] = le_y
        
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_scaled = pd.DataFrame(X_scaled, columns=X.columns)
    
    # Asegurar que y siempre sea numpy array para evitar problemas de indices
    y = np.array(y)
    
    return X_scaled, y, encoders, scaler

def build_tabular_attention_nn(input_dim: int, num_classes: int = 2):
    """
    Construye una Red Neuronal Tabular con mecanismo de atención usando Keras.
    """
    inputs = Input(shape=(input_dim,))
    
    x = Dense(128, activation='relu')(inputs)
    x = LayerNormalization()(x)
    x = Dropout(0.3)(x)
    
    x_reshaped = Reshape((1, 128))(x)
    attention_output = MultiHeadAttention(num_heads=4, key_dim=32)(x_reshaped, x_reshaped)
    attention_output = LayerNormalization()(attention_output + x_reshaped)
    
    x = Flatten()(attention_output)
    x = Dense(64, activation='relu')(x)
    x = Dropout(0.2)(x)
    
    if num_classes == 2:
        outputs = Dense(1, activation='sigmoid')(x)
        loss = 'binary_crossentropy'
    else:
        outputs = Dense(num_classes, activation='softmax')(x)
        loss = 'sparse_categorical_crossentropy'
        
    model = Model(inputs=inputs, outputs=outputs)
    model.compile(optimizer='adam', loss=loss, metrics=['accuracy'])
    
    return model

class SportsModelTrainer:
    def __init__(self, random_state=42):
        self.random_state = random_state
        self.models = {
            'logreg': LogisticRegression(random_state=self.random_state, max_iter=1000),
            'rf': RandomForestClassifier(random_state=self.random_state),
            'xgb': xgb.XGBClassifier(
                random_state=self.random_state, 
                eval_metric='logloss',
                tree_method='hist'
            ),
        }
        if HAS_CATBOOST:
            self.models['cb'] = CatBoostClassifier(
                random_state=self.random_state,
                verbose=0,
                task_type='CPU'
            )


        self.best_estimators = {}
        self.cv_scores = {}
        self.training_times = {}
        self.eval_results = {}
        
    def _extract_cv_scores(self, grid_search, cv_folds):
        scores = []
        best_index = grid_search.best_index_
        for i in range(cv_folds):
            key = f'split{i}_test_score'
            scores.append(grid_search.cv_results_[key][best_index])
        return np.array(scores)

    def train_and_tune_classic_models(self, X_train, y_train, cv_folds=5):
        """Entrena modelos clásicos con RandomizedSearchCV para mayor velocidad"""
        print(f"Entrenando Regresion Logistica (CV={cv_folds})...")
        start_time = time.time()
        param_grid_lr = {
            'C': [0.01, 0.1, 1.0, 10.0, 100.0],
            'solver': ['lbfgs', 'liblinear'],
            'penalty': ['l2']
        }
        grid_lr = RandomizedSearchCV(self.models['logreg'], param_grid_lr, n_iter=10, cv=cv_folds, scoring='accuracy', n_jobs=-1, random_state=self.random_state)
        grid_lr.fit(X_train, y_train)
        self.best_estimators['logreg'] = grid_lr.best_estimator_
        self.cv_scores['logreg'] = self._extract_cv_scores(grid_lr, cv_folds)
        self.training_times['logreg'] = time.time() - start_time
        print(f"  Mejor: {grid_lr.best_params_}")
        
        print(f"Entrenando Random Forest (CV={cv_folds})...")
        start_time = time.time()
        param_grid_rf = {
            'n_estimators': [100, 200, 300],
            'max_depth': [None, 10, 20, 30],
            'min_samples_split': [2, 5],
            'min_samples_leaf': [1, 2]
        }
        grid_rf = RandomizedSearchCV(self.models['rf'], param_grid_rf, n_iter=15, cv=cv_folds, scoring='accuracy', n_jobs=-1, random_state=self.random_state)
        grid_rf.fit(X_train, y_train)
        self.best_estimators['rf'] = grid_rf.best_estimator_
        self.cv_scores['rf'] = self._extract_cv_scores(grid_rf, cv_folds)
        self.training_times['rf'] = time.time() - start_time
        print(f"  Mejor: {grid_rf.best_params_}")
        
        print(f"Entrenando XGBoost (CV={cv_folds})...")
        start_time = time.time()
        
        # Test if CUDA is available for XGBoost
        try:
            test_xgb = xgb.XGBClassifier(tree_method='hist', device='cuda', n_estimators=1)
            test_xgb.fit(X_train[:10], y_train[:10])
            self.models['xgb'].set_params(device='cuda')
            print("  (Aceleración por GPU CUDA activada para XGBoost)")
        except Exception:
            print("  (CUDA no disponible para XGBoost, usando CPU con Multi-threading)")

        param_grid_xgb = {
            'n_estimators': [100, 200, 300],
            'learning_rate': [0.01, 0.05, 0.1, 0.2],
            'max_depth': [3, 5, 7],
            'subsample': [0.8, 1.0],
            'colsample_bytree': [0.8, 1.0]
        }
        grid_xgb = RandomizedSearchCV(self.models['xgb'], param_grid_xgb, n_iter=15, cv=cv_folds, scoring='accuracy', n_jobs=-1, random_state=self.random_state)
        grid_xgb.fit(X_train, y_train)
        self.best_estimators['xgb'] = grid_xgb.best_estimator_
        self.cv_scores['xgb'] = self._extract_cv_scores(grid_xgb, cv_folds)
        self.training_times['xgb'] = time.time() - start_time
        print(f"  Mejor: {grid_xgb.best_params_}")
        
        if HAS_CATBOOST:
            print(f"Entrenando CatBoost (CV={cv_folds})...")
            start_time = time.time()
            
            # Test if GPU is available for CatBoost
            try:
                test_cb = CatBoostClassifier(iterations=1, task_type='GPU', verbose=0)
                test_cb.fit(np.random.rand(10, 2), np.array([0, 1] * 5))
                self.models['cb'].set_params(task_type='GPU')
                print("  (Aceleración por GPU activada para CatBoost)")
            except Exception:
                print("  (GPU no disponible para CatBoost, usando CPU)")

            param_grid_cb = {
                'iterations': [100, 200, 300],
                'learning_rate': [0.01, 0.05, 0.1],
                'depth': [4, 6, 8]
            }
            grid_cb = RandomizedSearchCV(self.models['cb'], param_grid_cb, n_iter=10, cv=cv_folds, scoring='accuracy', n_jobs=-1, random_state=self.random_state)
            grid_cb.fit(X_train, y_train)
            self.best_estimators['cb'] = grid_cb.best_estimator_
            self.cv_scores['cb'] = self._extract_cv_scores(grid_cb, cv_folds)
            self.training_times['cb'] = time.time() - start_time
            print(f"  Mejor: {grid_cb.best_params_}")

        
    def train_hybrid_models(self, X_train, y_train, input_dim: int, num_classes: int=2, cv_folds=5):
        """Entrena modelos híbridos"""
        print(f"Entrenando Stacking Classifier (CV={cv_folds})...")
        start_time = time.time()
        estimators = [
            ('rf', self.best_estimators['rf']),
            ('xgb', self.best_estimators['xgb'])
        ]
        if HAS_CATBOOST:
            estimators.append(('cb', self.best_estimators['cb']))

        
        # Reducir cv a 3 para acelerar el Stacking final
        stacking_clf = StackingClassifier(
            estimators=estimators, 
            final_estimator=LogisticRegression(max_iter=1000),
            cv=3,
            n_jobs=-1
        )
        stacking_clf.fit(X_train, y_train)
        self.best_estimators['stacking'] = stacking_clf
        
        kf = KFold(n_splits=cv_folds, shuffle=True, random_state=self.random_state)
        scores = cross_val_score(stacking_clf, X_train, y_train, cv=kf, scoring='accuracy')
        self.cv_scores['stacking'] = scores
        self.training_times['stacking'] = time.time() - start_time
        
        print(f"Entrenando Red Neuronal Tabular con Atención (CV={cv_folds})...")
        start_time = time.time()
        nn_model = build_tabular_attention_nn(input_dim, num_classes)
        
        nn_cv_scores = []
        for train_idx, val_idx in kf.split(X_train):
            X_t, X_v = X_train.iloc[train_idx], X_train.iloc[val_idx]
            y_t, y_v = y_train[train_idx], y_train[val_idx]
            
            temp_model = build_tabular_attention_nn(input_dim, num_classes)
            temp_model.fit(X_t, y_t, epochs=10, batch_size=32, verbose=0)
            val_loss, val_acc = temp_model.evaluate(X_v, y_v, verbose=0)
            nn_cv_scores.append(val_acc)
            
        # Entrenar el modelo final en todo X_train
        nn_model.fit(X_train, y_train, epochs=20, batch_size=32, verbose=0)
        self.best_estimators['nn'] = nn_model
        self.cv_scores['nn'] = np.array(nn_cv_scores)
        self.training_times['nn'] = time.time() - start_time

    def evaluate_models(self, X_test, y_test, is_multiclass=False):
        """Evalúa los modelos y extrae métricas extendidas"""
        self.eval_results = {}
        print("\n--- Evaluación de Modelos ---")
        for name, model in self.best_estimators.items():
            res = {}
            if name == 'nn':
                y_pred_prob = model.predict(X_test)
                if not is_multiclass:
                    y_pred = (y_pred_prob > 0.5).astype(int).ravel()
                    y_pred_prob = y_pred_prob.ravel()
                else:
                    y_pred = np.argmax(y_pred_prob, axis=1)
            else:
                y_pred = model.predict(X_test)
                if hasattr(model, "predict_proba"):
                    y_pred_prob = model.predict_proba(X_test)
                    if not is_multiclass:
                        y_pred_prob = y_pred_prob[:, 1]
                else:
                    y_pred_prob = None
                    
            avg_mode = 'weighted' if is_multiclass else 'binary'
            
            res['accuracy'] = accuracy_score(y_test, y_pred)
            res['precision'] = precision_score(y_test, y_pred, average=avg_mode, zero_division=0)
            res['recall'] = recall_score(y_test, y_pred, average=avg_mode, zero_division=0)
            res['f1'] = f1_score(y_test, y_pred, average=avg_mode, zero_division=0)
            res['confusion_matrix'] = confusion_matrix(y_test, y_pred).tolist()
            res['time'] = self.training_times.get(name, 0)
            
            # ROC / AUC sólo para clasificación binaria
            if not is_multiclass and y_pred_prob is not None:
                fpr, tpr, _ = roc_curve(y_test, y_pred_prob)
                res['roc_auc'] = auc(fpr, tpr)
                res['fpr'] = fpr.tolist()
                res['tpr'] = tpr.tolist()
            else:
                res['roc_auc'] = None
                
            self.eval_results[name] = res
            print(f"[{name}] Acc: {res['accuracy']:.4f} | F1: {res['f1']:.4f} | Time: {res['time']:.2f}s")
            
        return self.eval_results
        
    def perform_statistical_tests(self):
        """Realiza pruebas T pareadas de validación cruzada frente al mejor modelo"""
        if not self.cv_scores:
            return {}
            
        # Encontrar el mejor modelo según media de CV scores
        mean_cv = {k: np.mean(v) for k, v in self.cv_scores.items()}
        best_model_name = max(mean_cv, key=mean_cv.get)
        best_scores = self.cv_scores[best_model_name]
        
        stats_results = {'best_model': best_model_name}
        print(f"\nMejor modelo en CV: {best_model_name} (Acc Media: {mean_cv[best_model_name]:.4f})")
        
        for name, scores in self.cv_scores.items():
            if name == best_model_name:
                continue
            
            t_stat, p_value = stats.ttest_rel(best_scores, scores)
            stats_results[name] = {
                't_stat': t_stat,
                'p_value': p_value,
                'is_significant': p_value < 0.05
            }
            sig_text = "Significativo" if p_value < 0.05 else "No Significativo"
            print(f"  vs {name}: p-value = {p_value:.4f} ({sig_text})")
            
        return stats_results

    def save_best_model(self, output_dir: str = 'models', sport_name: str = 'futbol', scaler=None, encoders=None):
        """Guarda el mejor modelo, scaler y encoders para un deporte"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        best_name = max(self.eval_results, key=lambda k: self.eval_results[k]['accuracy'])
        best_model = self.best_estimators[best_name]
        
        if best_name == 'nn':
            model_path = os.path.join(output_dir, f'best_model_{sport_name}.keras')
            best_model.save(model_path)
        else:
            model_path = os.path.join(output_dir, f'best_model_{sport_name}.pkl')
            joblib.dump(best_model, model_path)
        
        # Guardar scaler y encoders para usar en prediccion
        if scaler is not None:
            scaler_path = os.path.join(output_dir, f'scaler_{sport_name}.pkl')
            joblib.dump(scaler, scaler_path)
            
        if encoders is not None:
            encoders_path = os.path.join(output_dir, f'encoders_{sport_name}.pkl')
            joblib.dump(encoders, encoders_path)
            
        print(f"\nEl mejor modelo ({best_name}) guardado como: {model_path}")
        return best_name
