import sqlite3
import hashlib
import uuid
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "prisma", "dev.db")

class ModelWrapper:
    def __init__(self, **entries):
        self.__dict__.update(entries)
    
    def model_dump(self):
        return self.__dict__

def parse_dates(row_dict):
    for key in ['createdAt', 'updatedAt']:
        if key in row_dict and isinstance(row_dict[key], str):
            try:
                row_dict[key] = datetime.strptime(row_dict[key], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            except ValueError:
                row_dict[key] = datetime.now(timezone.utc)
        elif key in row_dict and isinstance(row_dict[key], (int, float)):
             row_dict[key] = datetime.fromtimestamp(row_dict[key]/1000, tz=timezone.utc)
    return row_dict

def execute_query(query, params=(), fetch=None):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch == "one":
            row = cur.fetchone()
            return ModelWrapper(**parse_dates(dict(row))) if row else None
        elif fetch == "all":
            rows = cur.fetchall()
            return [ModelWrapper(**parse_dates(dict(row))) for row in rows]
        conn.commit()
        return True

def create_user(username: str, password_raw: str, plan: str = "free"):
    password_hash = hashlib.sha256(password_raw.encode()).hexdigest()
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    execute_query(
        'INSERT INTO "User" (id, username, password_hash, plan, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, username, password_hash, plan, now, now)
    )
    return get_user_by_id(user_id)

def authenticate_user(username: str, password_raw: str):
    password_hash = hashlib.sha256(password_raw.encode()).hexdigest()
    user = execute_query('SELECT * FROM "User" WHERE username = ?', (username,), fetch="one")
    if user and user.password_hash == password_hash:
        return user
    return None

def get_user_by_id(user_id: str):
    return execute_query('SELECT * FROM "User" WHERE id = ?', (user_id,), fetch="one")

def save_prediction(user_id: str, match_id: int, predicted_winner: str, confidence: float, is_manual: bool = False, ai_data: str = ""):
    pred_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    execute_query(
        '''INSERT INTO "Prediction" (id, userId, matchId, predictedWinner, confidenceLevel, isManual, aiPredictionData, createdAt) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (pred_id, user_id, match_id, predicted_winner, confidence, is_manual, ai_data, now)
    )
    return True

def get_user_predictions(user_id: str, limit: int = 50):
    preds = execute_query(
        'SELECT * FROM "Prediction" WHERE userId = ? ORDER BY createdAt DESC LIMIT ?', 
        (user_id, limit), 
        fetch="all"
    )
    return [p.model_dump() for p in preds]

def create_notification(user_id: str, subject: str, description: str):
    notif_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    execute_query(
        'INSERT INTO "Notification" (id, userId, subject, description, createdAt) VALUES (?, ?, ?, ?, ?)',
        (notif_id, user_id, subject, description, now)
    )
    return True

def get_user_notifications(user_id: str):
    nots = execute_query(
        'SELECT * FROM "Notification" WHERE userId = ? ORDER BY createdAt DESC', 
        (user_id,), 
        fetch="all"
    )
    return [n.model_dump() for n in nots]
