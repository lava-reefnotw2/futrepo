import pandas as pd

def optimize_football_csv():
    print("Cargando FootballMatches_cleaned.csv...")
    df = pd.read_csv("datasets/FootballMatches_cleaned.csv")
    
    print(f"Filas originales: {len(df)}")
    
    # Asegurar que MatchDate es datetime
    df['MatchDate'] = pd.to_datetime(df['MatchDate'])
    
    # Filtrar desde 2006 en adelante (borrar 2005 hacia atrás)
    df = df[df['MatchDate'] >= '2006-01-01']
    
    # Crear columnas objetivo para los modelos extra
    # Over25: Verdadero si la suma de goles es mayor a 2.5
    if 'FTHome' in df.columns and 'FTAway' in df.columns:
        df['Over25'] = ((df['FTHome'] + df['FTAway']) > 2.5).astype(int)
        # BTTS: Verdadero si ambos equipos marcan
        df['BTTS'] = ((df['FTHome'] > 0) & (df['FTAway'] > 0)).astype(int)
    
    # Eliminar columnas innecesarias para el modelo
    # HomeTeam y AwayTeam son strings categoricos que causan cardinalidad excesiva.
    # FTHome y FTAway son goles finales (data leakage).
    cols_to_drop = ['HomeTeam', 'AwayTeam', 'FTHome', 'FTAway']
    df = df.drop(columns=cols_to_drop, errors='ignore')
    
    print(f"Filas resultantes: {len(df)}")
    print(f"Columnas resultantes: {len(df.columns)}")
    
    df.to_csv("datasets/Footballnew.csv", index=False)
    print("Guardado en datasets/Footballnew.csv exitosamente.")

if __name__ == '__main__':
    optimize_football_csv()
