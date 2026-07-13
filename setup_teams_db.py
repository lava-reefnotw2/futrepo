import pandas as pd
import sqlite3
import json
import os
from db import init_db, get_connection

def setup_football():
    print("Poblando equipos de Fútbol...")
    df = pd.read_csv('datasets/FootballMatches_cleaned.csv')
    df['MatchDate'] = pd.to_datetime(df['MatchDate'])
    df = df.sort_values('MatchDate')
    
    teams = {}
    for _, row in df.iterrows():
        home, away = row['HomeTeam'], row['AwayTeam']
        teams[home] = {
            'Elo': row['HomeElo'],
            'Form3': row['Form3Home'],
            'Form5': row['Form5Home'],
            'Shots': row['HomeShots'],
            'Target': row['HomeTarget'],
            'Corners': row['HomeCorners'],
            'Fouls': row['HomeFouls']
        }
        teams[away] = {
            'Elo': row['AwayElo'],
            'Form3': row['Form3Away'],
            'Form5': row['Form5Away'],
            'Shots': row['AwayShots'],
            'Target': row['AwayTarget'],
            'Corners': row['AwayCorners'],
            'Fouls': row['AwayFouls']
        }
        
    conn = get_connection()
    cursor = conn.cursor()
    for team, stats in teams.items():
        cursor.execute('''
            INSERT OR REPLACE INTO equipos (deporte, nombre, stats_json)
            VALUES (?, ?, ?)
        ''', ('Futbol', team, json.dumps(stats)))
    conn.commit()
    conn.close()
    print(f"Terminado. {len(teams)} equipos de Futbol insertados.")

def setup_nba():
    print("Poblando equipos de NBA...")
    df = pd.read_csv('datasets/NBA_cleaned.csv')
    df['gameDate'] = pd.to_datetime(df['gameDate'])
    df = df.sort_values('gameDate')
    
    # Leemos el df con features para sacar las ultimas stats calculadas
    df_feat = pd.read_csv('datasets/NBA_featured.csv')
    
    # Extraer ultimas stats para cada equipo desde la perspectiva de local o visitante
    teams = {}
    for _, row in df_feat.iterrows():
        teams[row['hometeamName']] = {
            'win_pct': row['home_win_pct'],
            'avg_pts': row['home_avg_pts'],
            'avg_pts_against': row['home_avg_pts_against'],
            'streak': row['home_streak'],
            'local_pct': row['home_local_pct']
        }
        teams[row['awayteamName']] = {
            'win_pct': row['away_win_pct'],
            'avg_pts': row['away_avg_pts'],
            'avg_pts_against': row['away_avg_pts_against'],
            'streak': row['away_streak'],
            'local_pct': row['home_local_pct'] # aproximacion
        }
        
    conn = get_connection()
    cursor = conn.cursor()
    for team, stats in teams.items():
        cursor.execute('''
            INSERT OR REPLACE INTO equipos (deporte, nombre, stats_json)
            VALUES (?, ?, ?)
        ''', ('NBA', team, json.dumps(stats)))
    conn.commit()
    conn.close()
    print(f"Terminado. {len(teams)} equipos de NBA insertados.")

def setup_mlb():
    print("Poblando equipos y lanzadores de MLB...")
    df = pd.read_csv('datasets/MLB_featured.csv')
    
    teams = {}
    pitchers = {}
    
    for _, row in df.iterrows():
        t1, t2 = row['team1'], row['team2']
        teams[t1] = {'elo_pre': row['elo1_pre'], 'rating_pre': row['rating1_pre']}
        teams[t2] = {'elo_pre': row['elo2_pre'], 'rating_pre': row['rating2_pre']}
        
        p1, p2 = row['pitcher1'], row['pitcher2']
        if pd.notna(p1) and p1 != '0': # 0 vino de fillna
            pitchers[p1] = {'win_rate': row['pitcher1_win_rate'], 'exp': row['pitcher1_exp']}
        if pd.notna(p2) and p2 != '0':
            pitchers[p2] = {'win_rate': row['pitcher2_win_rate'], 'exp': row['pitcher2_exp']}
            
    conn = get_connection()
    cursor = conn.cursor()
    for team, stats in teams.items():
        cursor.execute('''
            INSERT OR REPLACE INTO equipos (deporte, nombre, stats_json)
            VALUES (?, ?, ?)
        ''', ('MLB', team, json.dumps(stats)))
        
    for p_name, p_stats in pitchers.items():
        cursor.execute('''
            INSERT OR REPLACE INTO lanzadores (nombre, win_rate, exp)
            VALUES (?, ?, ?)
        ''', (p_name, p_stats['win_rate'], p_stats['exp']))
        
    conn.commit()
    conn.close()
    print(f"Terminado. {len(teams)} equipos y {len(pitchers)} lanzadores de MLB insertados.")

if __name__ == '__main__':
    init_db()
    setup_football()
    setup_nba()
    setup_mlb()
    print("=======================================")
    print("Base de datos de equipos completamente inicializada.")
