import pandas as pd
import os

def clean_football_data(input_path="FootballMatches.csv", output_path="FootballMatches_cleaned.csv"):
    print(f"Limpiando {input_path}...")
    try:
        # Cargar dataset
        df = pd.read_csv(input_path)
        print(f"Forma original: {df.shape}")
        
        # Seleccionar columnas relevantes para ML
        cols_to_keep = [
            'MatchDate', 'HomeTeam', 'AwayTeam', 
            'HomeElo', 'AwayElo', 'Form3Home', 'Form5Home', 'Form3Away', 'Form5Away',
            'HomeShots', 'AwayShots', 'HomeTarget', 'AwayTarget', 
            'HomeFouls', 'AwayFouls', 'HomeCorners', 'AwayCorners', 
            'HomeYellow', 'AwayYellow', 'HomeRed', 'AwayRed', 
            'OddHome', 'OddDraw', 'OddAway', 
            'FTHome', 'FTAway', 'FTResult'  # Targets
        ]
        
        # Mantener solo las columnas que existan en el dataframe
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
    # Ajustar rutas relativas si se corre desde la raíz
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, "FootballMatches.csv")
    output_file = os.path.join(script_dir, "FootballMatches_cleaned.csv")
    
    clean_football_data(input_file, output_file)
