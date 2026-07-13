import pandas as pd
import numpy as np
import os
import time

def engineer_nba_features(input_path, output_path, drop_initial_rows=1000):
    print(f"Generando Features para NBA desde {input_path}...")
    start_time = time.time()
    
    df = pd.read_csv(input_path)
    df['gameDate'] = pd.to_datetime(df['gameDate'])
    df = df.sort_values('gameDate').reset_index(drop=True)
    
    # Crear variable objetivo: 1 si gana el local, 0 si gana el visitante
    df['homeWin'] = (df['homeScore'] > df['awayScore']).astype(int)
    
    # Diccionarios de seguimiento
    team_wins = {}
    team_games = {}
    team_points_for = {}
    team_points_against = {}
    team_home_wins = {}
    team_home_games = {}
    team_last5 = {}
    team_last_match_date = {}
    
    # Seguimiento H2H: (equipo1, equipo2) -> victorias de equipo1 (orden alfabetico)
    h2h_history = {}
    
    features = []
    
    for idx, row in df.iterrows():
        home = row['hometeamName']
        away = row['awayteamName']
        date = row['gameDate']
        
        # Inicializar si es la primera vez
        for team in [home, away]:
            if team not in team_wins:
                team_wins[team] = 0
                team_games[team] = 0
                team_points_for[team] = []
                team_points_against[team] = []
                team_home_wins[team] = 0
                team_home_games[team] = 0
                team_last5[team] = []
                team_last_match_date[team] = pd.NaT
                
        h2h_key = tuple(sorted([home, away]))
        if h2h_key not in h2h_history:
            h2h_history[h2h_key] = {home: 0, away: 0}
            
        # 1. Dias de descanso y B2B
        home_rest = (date - team_last_match_date[home]).days if not pd.isna(team_last_match_date[home]) else 10
        away_rest = (date - team_last_match_date[away]).days if not pd.isna(team_last_match_date[away]) else 10
        
        # 2. H2H Win Rate
        h2h_total = h2h_history[h2h_key][home] + h2h_history[h2h_key][away]
        home_h2h_win_pct = h2h_history[h2h_key][home] / max(h2h_total, 1)
        
        # Calcular features ANTES de actualizar
        home_games = max(team_games[home], 1)
        away_games = max(team_games[away], 1)
        
        home_avg_pts = np.mean(team_points_for[home][-10:]) if team_points_for[home] else 100
        away_avg_pts = np.mean(team_points_for[away][-10:]) if team_points_for[away] else 100
        home_avg_pts_against = np.mean(team_points_against[home][-10:]) if team_points_against[home] else 100
        away_avg_pts_against = np.mean(team_points_against[away][-10:]) if team_points_against[away] else 100
        
        feat = {
            'gameDate': date,
            'hometeamName': home,
            'awayteamName': away,
            'home_win_pct': team_wins[home] / home_games,
            'away_win_pct': team_wins[away] / away_games,
            'home_avg_pts': home_avg_pts,
            'away_avg_pts': away_avg_pts,
            'home_avg_pts_against': home_avg_pts_against,
            'away_avg_pts_against': away_avg_pts_against,
            'home_point_diff': home_avg_pts - home_avg_pts_against,
            'away_point_diff': away_avg_pts - away_avg_pts_against,
            'home_local_pct': team_home_wins[home] / max(team_home_games[home], 1),
            'home_streak': sum(team_last5[home][-5:]) if team_last5[home] else 0,
            'away_streak': sum(team_last5[away][-5:]) if team_last5[away] else 0,
            'home_rest_days': home_rest,
            'away_rest_days': away_rest,
            'home_b2b': int(home_rest <= 1),
            'away_b2b': int(away_rest <= 1),
            'home_h2h_win_pct': home_h2h_win_pct,
            'homeWin': row['homeWin']
        }
        features.append(feat)
        
        # Actualizar stats DESPUES
        home_won = row['homeWin'] == 1
        team_games[home] += 1
        team_games[away] += 1
        team_wins[home] += int(home_won)
        team_wins[away] += int(not home_won)
        team_points_for[home].append(row['homeScore'])
        team_points_for[away].append(row['awayScore'])
        team_points_against[home].append(row['awayScore'])
        team_points_against[away].append(row['homeScore'])
        team_home_games[home] += 1
        team_home_wins[home] += int(home_won)
        team_last5[home].append(int(home_won))
        team_last5[away].append(int(not home_won))
        team_last_match_date[home] = date
        team_last_match_date[away] = date
        h2h_history[h2h_key][home] += int(home_won)
        h2h_history[h2h_key][away] += int(not home_won)
    
    df_features = pd.DataFrame(features)
    
    # Descartar las filas iniciales donde el historial es insuficiente
    if drop_initial_rows > 0:
        print(f"Descartando los primeros {drop_initial_rows} partidos por historial incompleto...")
        df_features = df_features.iloc[drop_initial_rows:].reset_index(drop=True)
    
    # Rellenar cualquier NaN que pudiera haber quedado (poco probable)
    df_features.fillna(0, inplace=True)
    
    df_features.to_csv(output_path, index=False)
    
    elapsed = time.time() - start_time
    print(f"✅ Terminado en {elapsed:.2f}s. Archivo guardado en {output_path}")
    print(f"Registros finales: {len(df_features)}")
    print(df_features.head(3))

if __name__ == '__main__':
    input_file = os.path.join('datasets', 'NBA_cleaned.csv')
    output_file = os.path.join('datasets', 'NBA_featured.csv')
    engineer_nba_features(input_file, output_file, drop_initial_rows=1500)
