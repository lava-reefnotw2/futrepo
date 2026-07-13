import pandas as pd
import os

def clean_nba_data(input_path="NBA.csv", output_path="NBA_cleaned.csv"):
    print(f"Limpiando {input_path}...")
    try:
        # Cargar dataset
        df = pd.read_csv(input_path)
        print(f"Forma original: {df.shape}")
        
        # Seleccionar columnas relevantes para ML (evitando IDs e info de arena innecesaria)
        cols_to_keep = [
            'gameDate', 'hometeamName', 'awayteamName', 
            'hometeamId', 'awayteamId', 'homeScore', 'awayScore', 'winner'
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
    input_file = os.path.join(script_dir, "NBA.csv")
    output_file = os.path.join(script_dir, "NBA_cleaned.csv")
    
    clean_nba_data(input_file, output_file)
