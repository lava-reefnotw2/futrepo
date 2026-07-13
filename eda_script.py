import pandas as pd
import numpy as np

print("=== ANALISIS DE NBA ===")
nba = pd.read_csv('datasets/NBA_cleaned.csv')
nba['gameDate'] = pd.to_datetime(nba['gameDate'])
print(f"Total partidos NBA: {len(nba)}")
print(f"Rango de fechas: {nba['gameDate'].min()} a {nba['gameDate'].max()}")
print(f"Equipos unicos: {nba['hometeamName'].nunique()}")
print(nba.head())

print("\n=== ANALISIS DE MLB ===")
mlb = pd.read_csv('datasets/mlb_elo_cleaned.csv')
mlb['date'] = pd.to_datetime(mlb['date'])
print(f"Total partidos MLB: {len(mlb)}")
print(f"Rango de fechas: {mlb['date'].min()} a {mlb['date'].max()}")
print(f"Equipos unicos: {mlb['team1'].nunique()}")
print(f"Lanzadores (Pitcher 1) unicos: {mlb['pitcher1'].nunique()}")
print(f"Lanzadores (Pitcher 2) unicos: {mlb['pitcher2'].nunique()}")
print(mlb.head())

