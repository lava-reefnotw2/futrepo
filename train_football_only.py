import pandas as pd
import time
import json
from train_and_evaluate import get_chronological_split, train_sport, load_dataset

def main():
    start_total = time.time()
    
    print("=" * 60)
    print("  ENTRENAMIENTO LOCAL (SOLO FUTBOL - GPU MX450)")
    print("=" * 60)
    
    all_results = {}
    
    print("\nCargando dataset optimizado Footballnew.csv...")
    try:
        df_football = load_dataset("Footballnew.csv")
    except FileNotFoundError:
        df_football = pd.read_csv("datasets/Footballnew.csv")
        
    df_football = df_football.dropna(subset=['FTResult', 'MatchDate'])
    
    df_football, split_idx_fb = get_chronological_split(df_football, 'MatchDate')
    print(f"Registros totales tras limpieza cronologica: {len(df_football)}")
    
    # Ya se borraron HomeTeam, AwayTeam, FTHome y FTAway en Footballnew.csv
    cols_to_drop = ['MatchDate']
    df_football_ml = df_football.drop(columns=cols_to_drop)
    
    all_results['futbol'] = train_sport('futbol', df_football_ml, 'FTResult', split_idx_fb)
    
    # Guardar resultados
    with open('model_results_futbol.json', 'w') as f:
        json.dump(all_results, f, indent=4)
        
    elapsed = time.time() - start_total
    print("\n" + "=" * 60)
    print("  RESUMEN FINAL - FUTBOL")
    print("=" * 60)
    
    best = all_results['futbol']['best_model']
    acc = all_results['futbol']['model_details'][best]['accuracy']
    f1 = all_results['futbol']['model_details'][best]['f1']
    print(f"\n    Mejor modelo: {best}")
    print(f"    Accuracy:     {acc:.4f}")
    print(f"    F1 Score:     {f1:.4f}")
    ext = '.keras' if best == 'nn' else '.pkl'
    print(f"    Archivo:      models/best_model_futbol{ext}")
    
    print(f"\nTiempo total: {elapsed:.1f} segundos ({elapsed/60:.1f} minutos)")
    print("\nProceso completado exitosamente.")

if __name__ == '__main__':
    main()
