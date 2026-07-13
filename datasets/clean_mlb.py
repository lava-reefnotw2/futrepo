import pandas as pd
import os

def clean_mlb_data(input_path="mlb_elo.csv", output_path="mlb_elo_cleaned.csv"):
    print(f"Limpiando {input_path}...")
    try:
        # Cargar dataset
        df = pd.read_csv(input_path)
        print(f"Forma original: {df.shape}")
        
        # Seleccionar columnas relevantes para ML
        # Evitamos 'post' elos/ratings para evitar Data Leakage (fuga de datos)
        cols_to_keep = [
            'date', 'season', 'team1', 'team2', 
            'elo1_pre', 'elo2_pre', 'elo_prob1', 'elo_prob2', 
            'rating1_pre', 'rating2_pre', 'rating_prob1', 'rating_prob2',
            'pitcher1', 'pitcher2', 
            'score1', 'score2'
        ]
        
        cols_available = [col for col in cols_to_keep if col in df.columns]
        df_clean = df[cols_available].copy()
        
        # Eliminar filas con valores nulos
        df_clean = df_clean.dropna()
        
        # Guardar dataset limpio
        df_clean.to_csv(output_path, index=False)
        print(f"Limpieza completada. Forma final: {df_clean.shape}")
        print(f"Guardado en {output_path}")
        
    except Exception as e:
        print(f"Error al limpiar {input_path}: {e}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, "mlb_elo.csv")
    output_file = os.path.join(script_dir, "mlb_elo_cleaned.csv")
    
    clean_mlb_data(input_file, output_file)
