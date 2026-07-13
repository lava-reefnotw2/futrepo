import joblib
import pandas as pd
import numpy as np
import os
import streamlit as st
from db import get_team_stats, get_pitcher_stats
from keras.models import load_model

@st.cache_resource
def load_scaler_and_pkl(sport):
    sport = sport.lower()
    
    model_path_pkl = os.path.join('models', f'best_model_{sport}.pkl')
    model_path_h = os.path.join('models', f'best_model_{sport}.h')
    scaler_path = os.path.join('models', f'scaler_{sport}.pkl')
    
    if os.path.exists(model_path_pkl):
        model = joblib.load(model_path_pkl)
    else:
        model = joblib.load(model_path_h)
        
    scaler = joblib.load(scaler_path)
    return model, scaler

def load_resources(sport):
    sport = sport.lower()
    model_path_keras = os.path.join('models', f'best_model_{sport}.keras')
    
    if os.path.exists(model_path_keras):
        model = load_model(model_path_keras)
        scaler = joblib.load(os.path.join('models', f'scaler_{sport}.pkl'))
        return model, scaler
    
    return load_scaler_and_pkl(sport)

def build_features(scaler, h_stats, a_stats):
    if not hasattr(scaler, 'feature_names_in_'):
        return {
            'HomeElo': h_stats.get('Elo', 1500),
            'AwayElo': a_stats.get('Elo', 1500),
            'HomeWinPct': h_stats.get('WinRate', 0),
            'AwayWinPct': a_stats.get('WinRate', 0),
            'HomeGoalsScored': h_stats.get('AvgGoalsScored', 0),
            'AwayGoalsScored': a_stats.get('AvgGoalsScored', 0),
            'HomeGoalsConceded': h_stats.get('AvgGoalsConceded', 0),
            'AwayGoalsConceded': a_stats.get('AvgGoalsConceded', 0),
            'HomeStreak': h_stats.get('CurrentStreak', 0),
            'AwayStreak': a_stats.get('CurrentStreak', 0)
        }
    
    feature_dict = {}
    for feature in scaler.feature_names_in_:
        val = 0
        if feature.startswith('Home'):
            stat = feature.replace('Home', '')
            if stat == 'Elo': val = h_stats.get('Elo', 1500)
            elif stat == 'WinPct': val = h_stats.get('WinRate', 0)
            elif stat == 'Streak': val = h_stats.get('CurrentStreak', 0)
            else: val = h_stats.get(stat, h_stats.get('Avg' + stat, h_stats.get('Avg' + stat + 'Scored', 0)))
        elif feature.startswith('Away'):
            stat = feature.replace('Away', '')
            if stat == 'Elo': val = a_stats.get('Elo', 1500)
            elif stat == 'WinPct': val = a_stats.get('WinRate', 0)
            elif stat == 'Streak': val = a_stats.get('CurrentStreak', 0)
            else: val = a_stats.get(stat, a_stats.get('Avg' + stat, a_stats.get('Avg' + stat + 'Scored', 0)))
        feature_dict[feature] = val
    return feature_dict

def predict_football(home_team, away_team):
    model, scaler = load_resources('futbol')
    h_stats = get_team_stats('Futbol', home_team) or {}
    a_stats = get_team_stats('Futbol', away_team) or {}
    
    feature_dict = build_features(scaler, h_stats, a_stats)
    
    df_features = pd.DataFrame([feature_dict])
    X_scaled = scaler.transform(df_features)
    
    # Manejar salida keras o sklearn
    if hasattr(model, 'predict_proba'):
        probs = model.predict_proba(X_scaled)[0]
    else:
        probs = model.predict(X_scaled)[0]
        # Si la salida es binaria (1 neurona)
        if len(probs) == 1:
            p = probs[0]
            probs = [1 - p, p] # Asumimos 0=Visita, 1=Local. Ajustar segun modelo real.
    
    return {
        'Local': float(probs[1]) if len(probs) > 1 else float(probs[0]),
        'Visitante': float(probs[0]) if len(probs) > 1 else 1 - float(probs[0]),
        'Empate': 0.0 # Simplificado
    }

def predict_football_extras(home_team, away_team):
    # Intentar cargar modelos extra
    try:
        model_over, scaler_over = load_resources('futbol_over25')
        model_btts, scaler_btts = load_resources('futbol_btts')
        
        h_stats = get_team_stats('Futbol', home_team) or {}
        a_stats = get_team_stats('Futbol', away_team) or {}
        
        feature_dict_over = build_features(scaler_over, h_stats, a_stats)
        df_features_over = pd.DataFrame([feature_dict_over])
        
        X_over = scaler_over.transform(df_features_over)
        if hasattr(model_over, 'predict_proba'):
            prob_over = model_over.predict_proba(X_over)[0][1]
        else:
            prob_over = model_over.predict(X_over)[0][0]
            
        feature_dict_btts = build_features(scaler_btts, h_stats, a_stats)
        df_features_btts = pd.DataFrame([feature_dict_btts])
        
        X_btts = scaler_btts.transform(df_features_btts)
        if hasattr(model_btts, 'predict_proba'):
            prob_btts = model_btts.predict_proba(X_btts)[0][1]
        else:
            prob_btts = model_btts.predict(X_btts)[0][0]
            
        return float(prob_over), float(prob_btts)
    except Exception as e:
        print(f"Error loading extra models: {e}")
        return 0.5, 0.5


def predict_nba(home_team, away_team):
    model, scaler = load_resources('nba')
    h_stats = get_team_stats('NBA', home_team) or {}
    a_stats = get_team_stats('NBA', away_team) or {}
    
    feature_dict = {
        'homeElo': h_stats.get('Elo', 1500),
        'awayElo': a_stats.get('Elo', 1500),
        'homeWinRate': h_stats.get('WinRate', 0),
        'awayWinRate': a_stats.get('WinRate', 0),
        'homeAvgPoints': h_stats.get('AvgPointsScored', 0),
        'awayAvgPoints': a_stats.get('AvgPointsScored', 0),
        'homeAvgPointsAllowed': h_stats.get('AvgPointsConceded', 0),
        'awayAvgPointsAllowed': a_stats.get('AvgPointsConceded', 0),
        'homeStreak': h_stats.get('CurrentStreak', 0),
        'awayStreak': a_stats.get('CurrentStreak', 0)
    }
    
    df_features = pd.DataFrame([feature_dict])
    X_scaled = scaler.transform(df_features)
    
    if hasattr(model, 'predict_proba'):
        probs = model.predict_proba(X_scaled)[0]
    else:
        probs = model.predict(X_scaled)[0]
        if len(probs) == 1:
            p = probs[0]
            probs = [1 - p, p]
            
    return {
        'Local': float(probs[1]) if len(probs) > 1 else float(probs[0]),
        'Visitante': float(probs[0]) if len(probs) > 1 else 1 - float(probs[0])
    }

def predict_mlb(home_team, away_team, home_pitcher=None, away_pitcher=None):
    model, scaler = load_resources('mlb')
    h_stats = get_team_stats('MLB', home_team) or {}
    a_stats = get_team_stats('MLB', away_team) or {}
    
    hp_stats = get_pitcher_stats(home_pitcher) if home_pitcher else {}
    ap_stats = get_pitcher_stats(away_pitcher) if away_pitcher else {}
    
    feature_dict = {
        'homeElo': h_stats.get('Elo', 1500),
        'awayElo': a_stats.get('Elo', 1500),
        'homeWinRate': h_stats.get('WinRate', 0),
        'awayWinRate': a_stats.get('WinRate', 0),
        'homeERA': hp_stats.get('ERA', 4.5),
        'awayERA': ap_stats.get('ERA', 4.5),
        'homeWHIP': hp_stats.get('WHIP', 1.3),
        'awayWHIP': ap_stats.get('WHIP', 1.3),
        'homeStreak': h_stats.get('CurrentStreak', 0),
        'awayStreak': a_stats.get('CurrentStreak', 0)
    }
    
    df_features = pd.DataFrame([feature_dict])
    X_scaled = scaler.transform(df_features)
    
    if hasattr(model, 'predict_proba'):
        probs = model.predict_proba(X_scaled)[0]
    else:
        probs = model.predict(X_scaled)[0]
        if len(probs) == 1:
            p = probs[0]
            probs = [1 - p, p]
            
    return {
        'Local': float(probs[1]) if len(probs) > 1 else float(probs[0]),
        'Visitante': float(probs[0]) if len(probs) > 1 else 1 - float(probs[0])
    }
