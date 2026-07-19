"""
Script unificado de entrenamiento multi-deporte.
Entrena modelos para Futbol, NBA y MLB con hiperparametros optimizados,
validacion cruzada de 5 folds, pruebas estadisticas y reportes.
"""
import pandas as pd
import numpy as np
import json
import os
import time
import joblib
import warnings
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from models import prepare_data, SportsModelTrainer
from reports import generate_model_evaluation_report

warnings.filterwarnings('ignore')

def load_dataset(filename):
    """Carga CSV verificando ruta local o en subcarpeta datasets/ y optimiza memoria a float32."""
    path = os.path.join("datasets", filename)
    if not os.path.exists(path):
        path = filename
        if not os.path.exists(path):
            raise FileNotFoundError(f"No se encontró el dataset {filename} en /datasets ni en el directorio raíz.")
            
    df = pd.read_csv(path)
    # Optimización de memoria (float64 -> float32)
    float_cols = df.select_dtypes(include=['float64']).columns
    df[float_cols] = df[float_cols].astype('float32')
    return df


# ============================================================================
# PIPELINE DE ENTRENAMIENTO POR DEPORTE
# ============================================================================

def train_sport(sport_name, df_ready, target_col, split_index):
    """Pipeline completo de entrenamiento para un deporte usando validacion cronologica."""
    separator = "=" * 60
    print(f"\n{separator}")
    print(f"  ENTRENANDO: {sport_name.upper()}")
    print(f"{separator}")
    
    # Preparar datos
    X, y, encoders, scaler = prepare_data(df_ready, target_col)
    is_multiclass = len(np.unique(y)) > 2
    num_classes = len(np.unique(y))
    
    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]
    y_train = y[:split_index]
    y_test = y[split_index:]
    
    print(f"Train (Pasado): {len(X_train)} | Test (Último Año): {len(X_test)} | Classes: {num_classes}")
    
    # Entrenar
    trainer = SportsModelTrainer(random_state=42)
    trainer.train_and_tune_classic_models(X_train, y_train, cv_folds=5)
    trainer.train_hybrid_models(
        X_train, y_train, 
        input_dim=X_train.shape[1], 
        num_classes=num_classes, 
        cv_folds=5
    )
    
    # Evaluar
    eval_results = trainer.evaluate_models(X_test, y_test, is_multiclass=is_multiclass)
    
    # Pruebas estadisticas
    stats_results = trainer.perform_statistical_tests()
    
    # Guardar modelo + scaler + encoders
    best_name = trainer.save_best_model(
        output_dir='models', 
        sport_name=sport_name,
        scaler=scaler,
        encoders=encoders
    )
    
    # Generar reportes
    print(f"\nGenerando reportes para {sport_name}...")
    for fmt, ext in [('pdf', 'pdf'), ('word', 'docx'), ('excel', 'xlsx')]:
        report_bytes = generate_model_evaluation_report(eval_results, stats_results, report_type=fmt)
        filename = f'evaluacion_{sport_name}.{ext}'
        with open(filename, 'wb') as f:
            f.write(report_bytes)
    
    print(f"Reportes guardados: evaluacion_{sport_name}.pdf/.docx/.xlsx")
    
    # Extraer mejores params y tiempos para el JSON
    model_details = {}
    for m_name, metrics in eval_results.items():
        params = {}
        estimator = trainer.best_estimators.get(m_name)
        if estimator and hasattr(estimator, 'get_params'):
            all_p = estimator.get_params()
            if m_name == 'xgb':
                params = {k: all_p[k] for k in ['learning_rate', 'max_depth', 'n_estimators'] if k in all_p}
            elif m_name == 'rf':
                params = {k: all_p[k] for k in ['max_depth', 'n_estimators', 'min_samples_split'] if k in all_p}
            elif m_name == 'logreg':
                params = {k: all_p[k] for k in ['C', 'penalty', 'solver'] if k in all_p}
            elif m_name == 'cb':
                params = {k: all_p[k] for k in ['learning_rate', 'depth', 'iterations'] if k in all_p}

                
        model_details[m_name] = {
            'accuracy': float(metrics['accuracy']),
            'f1': float(metrics['f1']),
            'time_s': float(metrics['time']),
            'params': params
        }
    
    return {
        'sport': sport_name,
        'best_model': best_name,
        'model_details': model_details,
        'num_classes': num_classes
    }

# ============================================================================
# MAIN
# ============================================================================

def get_chronological_split(df, date_col=None, test_ratio=0.2):
    """
    Filtra juegos futuros, ordena por fecha si existe columna y devuelve el índice de corte.
    Si no existe la columna de fecha, realiza división por índice asumiendo orden cronológico preexistente.
    """
    if date_col and date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
        # Filtrar partidos que están en el futuro y no tienen resultado
        df = df[df[date_col] < datetime.now()].copy()
        df = df.sort_values(date_col).reset_index(drop=True)
        
        max_date = df[date_col].max()
        test_start_date = max_date - timedelta(days=365)
        
        split_index = df[df[date_col] >= test_start_date].index.min()
        return df, split_index
    else:
        # Partición cronológica por índice directo (asume pre-ordenado)
        split_index = int(len(df) * (1 - test_ratio))
        return df, split_index

def main():
    start_total = time.time()
    
    print("=" * 60)
    print("  PIPELINE MULTI-DEPORTE (TIME-BASED SPLIT)")
    print("=" * 60)
    
    all_results = {}
    
    # ---- FUTBOL ----
    print("\nCargando dataset de Futbol...")
    df_football = load_dataset("FootballMatches_cleaned.csv")
    date_col_fb = 'MatchDate' if 'MatchDate' in df_football.columns else None
    
    subset_drop = ['FTResult']
    if date_col_fb:
        subset_drop.append(date_col_fb)
    df_football = df_football.dropna(subset=subset_drop)
    
    df_football, split_idx_fb = get_chronological_split(df_football, date_col_fb)
    print(f"Registros totales pasados: {len(df_football)}")
    
    cols_to_drop = [c for c in ['MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway'] if c in df_football.columns]
    df_football_ml = df_football.drop(columns=cols_to_drop)
    all_results['futbol'] = train_sport('futbol', df_football_ml, 'FTResult', split_idx_fb)
    
    # ---- NBA ----
    print("\nCargando dataset de NBA...")
    df_nba_ml = load_dataset("NBA_featured.csv")
    date_col_nba = 'gameDate' if 'gameDate' in df_nba_ml.columns else None
    
    subset_drop_nba = ['homeWin']
    if date_col_nba:
        subset_drop_nba.append(date_col_nba)
    df_nba_ml = df_nba_ml.dropna(subset=subset_drop_nba)
    
    df_nba_ml, split_idx_nba = get_chronological_split(df_nba_ml, date_col_nba)
    print(f"Registros totales pasados: {len(df_nba_ml)}")
    
    cols_to_drop_nba = [c for c in ['gameDate', 'hometeamName', 'awayteamName'] if c in df_nba_ml.columns]
    df_nba_ml = df_nba_ml.drop(columns=cols_to_drop_nba)
    all_results['nba'] = train_sport('nba', df_nba_ml, 'homeWin', split_idx_nba)
    
    # ---- MLB ----
    print("\nCargando dataset de MLB...")
    df_mlb_ml = load_dataset("MLB_featured.csv")
    date_col_mlb = 'date' if 'date' in df_mlb_ml.columns else None
    
    subset_drop_mlb = ['team1_wins']
    if date_col_mlb:
        subset_drop_mlb.append(date_col_mlb)
    df_mlb_ml = df_mlb_ml.dropna(subset=subset_drop_mlb)
    
    df_mlb_ml, split_idx_mlb = get_chronological_split(df_mlb_ml, date_col_mlb)
    print(f"Registros totales pasados: {len(df_mlb_ml)}")
    
    cols_to_drop_mlb = [c for c in ['date', 'team1', 'team2', 'pitcher1', 'pitcher2'] if c in df_mlb_ml.columns]
    df_mlb_ml = df_mlb_ml.drop(columns=cols_to_drop_mlb)
    all_results['mlb'] = train_sport('mlb', df_mlb_ml, 'team1_wins', split_idx_mlb)
    
    # Guardar resultados en JSON para la UI
    with open('model_results.json', 'w') as f:
        json.dump(all_results, f, indent=4)
    
    # ---- RESUMEN FINAL ----
    elapsed = time.time() - start_total
    print("\n" + "=" * 60)
    print("  RESUMEN FINAL - MEJORES MODELOS POR DEPORTE")
    print("=" * 60)
    
    for sport, result in all_results.items():
        best = result['best_model']
        acc = result['model_details'][best]['accuracy']
        f1 = result['model_details'][best]['f1']
        print(f"\n  {sport.upper()}:")
        print(f"    Mejor modelo: {best}")
        print(f"    Accuracy:     {acc:.4f}")
        ext = '.keras' if best == 'nn' else '.pkl'
        print(f"    Archivo:      models/best_model_{sport}{ext}")
    
    print(f"\nTiempo total: {elapsed:.1f} segundos ({elapsed/60:.1f} minutos)")
    print("\nArchivos generados:")
    for sport in all_results:
        print(f"  models/best_model_{sport}.pkl/keras  +  scaler_{sport}.pkl  +  encoders_{sport}.pkl")
        print(f"  evaluacion_{sport}.pdf  /  .docx  /  .xlsx")
    
    print("\nProceso completado exitosamente.")

if __name__ == '__main__':
    main()
