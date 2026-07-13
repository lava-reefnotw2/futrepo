import pandas as pd
import time
import json
from train_and_evaluate import get_chronological_split, train_sport, load_dataset

def main():
    start_total = time.time()
    
    print("=" * 60)
    print("  ENTRENAMIENTO LOCAL (EXTRAS FUTBOL - GPU MX450)")
    print("=" * 60)
    
    all_results = {}
    
    print("\nCargando dataset optimizado Footballnew.csv...")
    try:
        df_football = load_dataset("Footballnew.csv")
    except FileNotFoundError:
        df_football = pd.read_csv("datasets/Footballnew.csv")
        
    df_football = df_football.dropna(subset=['MatchDate'])
    
    # 1. ENTRENAR MODELO OVER 2.5
    print("\n--- Preparando Modelo Over 2.5 ---")
    df_over25 = df_football.copy().dropna(subset=['Over25'])
    df_over25, split_idx_over = get_chronological_split(df_over25, 'MatchDate')
    
    # Eliminar las otras columnas objetivo para no hacer data leakage
    cols_to_drop_over = ['MatchDate', 'FTResult', 'BTTS']
    # Ignorar errores si no existen
    df_over_ml = df_over25.drop(columns=cols_to_drop_over, errors='ignore')
    
    all_results['futbol_over25'] = train_sport('futbol_over25', df_over_ml, 'Over25', split_idx_over)
    
    # 2. ENTRENAR MODELO BTTS (Ambos Anotan)
    print("\n--- Preparando Modelo BTTS ---")
    df_btts = df_football.copy().dropna(subset=['BTTS'])
    df_btts, split_idx_btts = get_chronological_split(df_btts, 'MatchDate')
    
    cols_to_drop_btts = ['MatchDate', 'FTResult', 'Over25']
    df_btts_ml = df_btts.drop(columns=cols_to_drop_btts, errors='ignore')
    
    all_results['futbol_btts'] = train_sport('futbol_btts', df_btts_ml, 'BTTS', split_idx_btts)
    
    # Guardar resultados
    with open('model_results_futbol_extras.json', 'w') as f:
        json.dump(all_results, f, indent=4)
        
    elapsed = time.time() - start_total
    print("\n" + "=" * 60)
    print("  RESUMEN FINAL - EXTRAS FUTBOL")
    print("=" * 60)
    
    for extra_name in ['futbol_over25', 'futbol_btts']:
        best = all_results[extra_name]['best_model']
        acc = all_results[extra_name]['model_details'][best]['accuracy']
        f1 = all_results[extra_name]['model_details'][best]['f1']
        print(f"\n[{extra_name.upper()}]")
        print(f"    Mejor modelo: {best}")
        print(f"    Accuracy:     {acc:.4f}")
        print(f"    F1 Score:     {f1:.4f}")
        ext = '.keras' if best == 'nn' else '.pkl'
        print(f"    Archivo:      models/best_model_{extra_name}{ext}")
    
    print(f"\nTiempo total: {elapsed:.1f} segundos ({elapsed/60:.1f} minutos)")
    print("\nProceso de extras completado exitosamente.")

if __name__ == '__main__':
    main()
