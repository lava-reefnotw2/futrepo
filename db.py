import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'sports_predict.db')

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de equipos con sus ultimas estadisticas conocidas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deporte TEXT NOT NULL,
            nombre TEXT NOT NULL,
            stats_json TEXT,
            UNIQUE(deporte, nombre)
        )
    ''')
    
    # Tabla de lanzadores de beisbol
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lanzadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            win_rate REAL,
            exp INTEGER
        )
    ''')
    
    # Tabla de partidos futuros ingresados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partidos_futuros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deporte TEXT NOT NULL,
            fecha TEXT NOT NULL,
            local TEXT NOT NULL,
            visitante TEXT NOT NULL,
            pitcher1 TEXT,
            pitcher2 TEXT,
            prob_local REAL,
            prob_empate REAL,
            prob_visitante REAL,
            prediccion_ia TEXT,
            resultado_real TEXT
        )
    ''')
    
    # Historial de predicciones del usuario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predicciones_usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partido_id INTEGER,
            usuario TEXT,
            prediccion TEXT,
            fecha_prediccion TEXT,
            FOREIGN KEY (partido_id) REFERENCES partidos_futuros(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_teams_by_sport(sport):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT nombre FROM equipos WHERE deporte = ? ORDER BY nombre', (sport,))
    teams = [row[0] for row in cursor.fetchall()]
    conn.close()
    return teams

def get_team_stats(sport, team_name):
    import json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT stats_json FROM equipos WHERE deporte = ? AND nombre = ?', (sport, team_name))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return json.loads(row[0])
    return None

def get_pitchers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT nombre FROM lanzadores ORDER BY nombre')
    pitchers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return pitchers

def get_pitcher_stats(pitcher_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT win_rate, exp FROM lanzadores WHERE nombre = ?', (pitcher_name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"win_rate": row[0], "exp": row[1]}
    return {"win_rate": 0.5, "exp": 0}

def save_future_match(deporte, fecha, local, visitante, pitcher1, pitcher2, probs, prediccion):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO partidos_futuros 
        (deporte, fecha, local, visitante, pitcher1, pitcher2, prob_local, prob_empate, prob_visitante, prediccion_ia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (deporte, fecha, local, visitante, pitcher1, pitcher2, 
          probs.get('local', 0), probs.get('empate', None), probs.get('visitante', 0), prediccion))
    conn.commit()
    conn.close()

def get_future_matches(deporte=None):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if deporte and deporte != 'Todos':
        cursor.execute('SELECT * FROM partidos_futuros WHERE deporte = ? AND resultado_real IS NULL ORDER BY fecha DESC', (deporte,))
    else:
        cursor.execute('SELECT * FROM partidos_futuros WHERE resultado_real IS NULL ORDER BY fecha DESC')
        
    matches = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return matches

if __name__ == '__main__':
    init_db()
    print("Base de datos SQLite inicializada exitosamente.")
