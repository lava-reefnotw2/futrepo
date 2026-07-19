import pandas as pd
import numpy as np
import time
import json
import os
import sys

# Importar funciones de train_and_evaluate
from train_and_evaluate import get_chronological_split, train_sport, load_dataset

def main():
    start_total = time.time()
    
    print("=" * 60)
    print("  ENTRENAMIENTO 1X2 FUTBOL CON FUTBOLMATCHES.CSV")
    print("=" * 60)
    
    # 1. Cargar datasets
    print("Cargando datasets...")
    try:
        df_futbol = pd.read_csv("datasets/FutbolMatches2.csv")
    except FileNotFoundError:
        try:
            df_futbol = pd.read_csv("datasets/FutbolMatches.csv")
            print("Cargado fallback datasets/FutbolMatches.csv")
        except FileNotFoundError:
            print("Error: No se encontró datasets/FutbolMatches2.csv ni datasets/FutbolMatches.csv")
            sys.exit(1)
        
    date_col = None
    if 'MatchDate' in df_futbol.columns:
        date_col = 'MatchDate'
    else:
        # Intentar recuperar MatchDate de FootballMatches2.csv o FootballMatches.csv
        df_dates = None
        for filename in ["FootballMatches2.csv", "FootballMatches.csv"]:
            try:
                df_dates = pd.read_csv(f"datasets/{filename}", usecols=["MatchDate"])
                print(f"Fechas leídas desde datasets/{filename}")
                break
            except Exception:
                continue
                
        if df_dates is not None:
            try:
                idx_col = df_futbol.columns[0]
                print(f"Recuperando fechas usando la columna de índice: '{idx_col}'...")
                df_futbol['MatchDate'] = df_dates.loc[df_futbol[idx_col], 'MatchDate'].values
                date_col = 'MatchDate'
            except Exception as e:
                print(f"No se pudo recuperar MatchDate mediante la columna de índice: {e}")
        else:
            print("No se encontraron archivos de fechas para recuperar MatchDate.")
            
    if date_col:
        print("MatchDate recuperado/detectado exitosamente.")
    else:
        print("Advertencia: No se dispone de columna de fecha. Se usará división cronológica por índice.")
    
    # 3. Seleccionar columnas requeridas para entrenamiento y alinear nombres para la inferencia
    features_to_keep = [
        'HomeElo', 'AwayElo', 
        'Form3Home', 'Form5Home', 
        'Form3Away', 'Form5Away'
    ]
    target_col = 'FTResult'
    
    all_cols = features_to_keep + [target_col]
    if date_col:
        all_cols.append(date_col)
    
    print(f"Filas originales: {len(df_futbol)}")
    available_cols = [c for c in all_cols if c in df_futbol.columns]
    df_cleaned = df_futbol[available_cols].dropna()
    print(f"Filas tras eliminar valores nulos: {len(df_cleaned)}")
    
    # Renombrar columnas de forma para compatibilidad directa con build_features() en predict.py
    df_cleaned = df_cleaned.rename(columns={
        'Form3Home': 'HomeForm3',
        'Form5Home': 'HomeForm5',
        'Form3Away': 'AwayForm3',
        'Form5Away': 'AwayForm5'
    })
    
    # 4. Partición cronológica (último año para validación / prueba)
    df_cleaned, split_idx = get_chronological_split(df_cleaned, date_col)
    print(f"Registros totales ordenados cronológicamente: {len(df_cleaned)}")
    
    # Excluir la columna de fecha para entrenamiento si existe
    if date_col and date_col in df_cleaned.columns:
        df_ready = df_cleaned.drop(columns=[date_col])
    else:
        df_ready = df_cleaned.copy()
    
    # 5. Entrenar y evaluar modelos (incluye Regresión Logística, Random Forest, XGBoost, Stacking y CatBoost si está instalado)
    results = train_sport('futbol', df_ready, target_col, split_idx)
    
    # 6. Actualizar y guardar los resultados en JSON preservando otros deportes
    for json_file in ['model_results.json', 'model_results_futbol.json']:
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
            except Exception:
                data = {}
        else:
            data = {}
            
        data['futbol'] = results
        
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Resultados guardados exitosamente en: {json_file}")
        
    elapsed = time.time() - start_total
    print("\n" + "=" * 60)
    print(f"  PROCESO COMPLETADO EN {elapsed:.1f} SEGUNDOS ({elapsed/60:.1f} MINUTOS)")
    print("=" * 60)
    
    best = results['best_model']
    acc = results['model_details'][best]['accuracy']
    f1 = results['model_details'][best]['f1']
    print(f"  Mejor Modelo: {best.upper()}")
    print(f"  Accuracy:     {acc:.4f}")
    print(f"  F1 Score:     {f1:.4f}")
    
    ext = '.keras' if best == 'nn' else '.pkl'
    print(f"  Modelo guardado como: models/best_model_futbol{ext}")

if __name__ == '__main__':
    main()
