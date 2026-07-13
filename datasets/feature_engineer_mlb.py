import pandas as pd
import numpy as np
import os
import time

def engineer_mlb_features(input_path, output_path, drop_initial_rows=2000):
    print(f"Generando Features para MLB desde {input_path}...")
    start_time = time.time()
    
    df = pd.read_csv(input_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # Variable objetivo: 1 si team1 gana, 0 si team2 gana
    df['team1_wins'] = (df['score1'] > df['score2']).astype(int)
    
    # Diccionarios para estadisticas de lanzadores
    pitcher_wins = {}
    pitcher_games = {}
    
    features = []
    
    for idx, row in df.iterrows():
        p1 = row['pitcher1']
        p2 = row['pitcher2']
        date = row['date']
        
        # Inicializar lanzadores
        for p in [p1, p2]:
            if pd.isna(p): continue
            if p not in pitcher_wins:
                pitcher_wins[p] = 0
                pitcher_games[p] = 0
                
        p1_games = max(pitcher_games.get(p1, 0), 1)
        p2_games = max(pitcher_games.get(p2, 0), 1)
        
        p1_win_rate = pitcher_wins.get(p1, 0) / p1_games if pd.notna(p1) else 0.5
        p2_win_rate = pitcher_wins.get(p2, 0) / p2_games if pd.notna(p2) else 0.5
        
        feat = {
            'date': date,
            'team1': row['team1'],
            'team2': row['team2'],
            'elo1_pre': row['elo1_pre'],
            'elo2_pre': row['elo2_pre'],
            'elo_diff': row['elo1_pre'] - row['elo2_pre'],
            'elo_prob1': row['elo_prob1'],
            'elo_prob2': row['elo_prob2'],
            'rating1_pre': row['rating1_pre'],
            'rating2_pre': row['rating2_pre'],
            'rating_diff': row['rating1_pre'] - row['rating2_pre'],
            'rating_prob1': row['rating_prob1'],
            'rating_prob2': row['rating_prob2'],
            'pitcher1': row['pitcher1'],
            'pitcher2': row['pitcher2'],
            'pitcher1_win_rate': p1_win_rate,
            'pitcher2_win_rate': p2_win_rate,
            'pitcher1_exp': pitcher_games.get(p1, 0),
            'pitcher2_exp': pitcher_games.get(p2, 0),
            'team1_wins': row['team1_wins']
        }
        features.append(feat)
        
        # Actualizar despues del partido
        team1_won = row['team1_wins'] == 1
        
        if pd.notna(p1):
            pitcher_games[p1] += 1
            pitcher_wins[p1] += int(team1_won)
            
        if pd.notna(p2):
            pitcher_games[p2] += 1
            pitcher_wins[p2] += int(not team1_won)
            
    df_features = pd.DataFrame(features)
    
    # Descartar filas iniciales
    if drop_initial_rows > 0:
        print(f"Descartando los primeros {drop_initial_rows} partidos por historial de lanzadores incompleto...")
        df_features = df_features.iloc[drop_initial_rows:].reset_index(drop=True)
        
    df_features.fillna(0, inplace=True)
    df_features.to_csv(output_path, index=False)
    
    elapsed = time.time() - start_time
    print(f"✅ Terminado en {elapsed:.2f}s. Archivo guardado en {output_path}")
    print(f"Registros finales: {len(df_features)}")
    print(df_features.head(3))

if __name__ == '__main__':
    input_file = os.path.join('datasets', 'mlb_elo_cleaned.csv')
    output_file = os.path.join('datasets', 'MLB_featured.csv')
    engineer_mlb_features(input_file, output_file, drop_initial_rows=3000)
