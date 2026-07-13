import hashlib
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    import streamlit as st
except Exception:
    st = None

try:
    import tomllib
except ImportError:
    import tomli as tomllib

BASE_DIR = os.path.dirname(__file__)
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")


class ModelWrapper:
    def __init__(self, **entries):
        self.__dict__.update(entries)

    def model_dump(self):
        return self.__dict__


def _load_secrets():
    if st is not None:
        try:
            return dict(st.secrets)
        except Exception:
            pass

    if os.path.exists(SECRETS_PATH):
        with open(SECRETS_PATH, "rb") as fh:
            return tomllib.load(fh)

    return {}


def get_db_config():
    secrets = _load_secrets()
    return {
        "host": secrets.get("POSTGRES_HOST", os.getenv("POSTGRES_HOST", "localhost")),
        "port": int(secrets.get("POSTGRES_PORT", os.getenv("POSTGRES_PORT", 5432))),
        "dbname": secrets.get("POSTGRES_DB", os.getenv("POSTGRES_DB", "futdb")),
        "user": secrets.get("POSTGRES_USER", os.getenv("POSTGRES_USER", "postgres")),
        "password": secrets.get("POSTGRES_PASSWORD", os.getenv("POSTGRES_PASSWORD", "")),
    }


@contextmanager
def get_connection(dbname=None):
    config = get_db_config()
    conn = psycopg2.connect(
        host=config["host"],
        port=config["port"],
        dbname=dbname or config["dbname"],
        user=config["user"],
        password=config["password"],
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_dates(row_dict):
    for key in ["createdAt", "updatedAt"]:
        if key in row_dict and isinstance(row_dict[key], str):
            try:
                row_dict[key] = datetime.fromisoformat(row_dict[key])
            except ValueError:
                row_dict[key] = datetime.now(timezone.utc)
    return row_dict


def ensure_database_exists():
    config = get_db_config()
    with get_connection("postgres") as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (config["dbname"],))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{config["dbname"]}"')


def init_prisma_db():
    ensure_database_exists()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                '''
                CREATE TABLE IF NOT EXISTS "User" (
                    id TEXT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    plan VARCHAR(20) NOT NULL DEFAULT 'free',
                    role VARCHAR(20) NOT NULL DEFAULT 'USER',
                    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                '''
            )
            cur.execute(
                '''
                CREATE TABLE IF NOT EXISTS "Prediction" (
                    id TEXT PRIMARY KEY,
                    "userId" TEXT NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                    "matchId" INTEGER NOT NULL,
                    "predictedHomeScore" INTEGER,
                    "predictedAwayScore" INTEGER,
                    "predictedWinner" TEXT,
                    "confidenceLevel" DOUBLE PRECISION,
                    "isManual" BOOLEAN NOT NULL DEFAULT FALSE,
                    "aiPredictionData" TEXT,
                    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                '''
            )
            cur.execute(
                '''
                CREATE TABLE IF NOT EXISTS "Notification" (
                    id TEXT PRIMARY KEY,
                    "userId" TEXT NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                    subject TEXT NOT NULL,
                    description TEXT NOT NULL,
                    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                '''
            )
            cur.execute(
                '''
                INSERT INTO "User" (id, username, password_hash, plan, role, "createdAt", "updatedAt")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    plan = EXCLUDED.plan,
                    role = EXCLUDED.role,
                    "updatedAt" = EXCLUDED."updatedAt"
                ''',
                (
                    str(uuid.uuid4()),
                    "admin",
                    hashlib.sha256("admin".encode()).hexdigest(),
                    "elite",
                    "ADMIN",
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                ),
            )


def execute_query(query, params=(), fetch=None):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch == "one":
                row = cur.fetchone()
                return ModelWrapper(**parse_dates(dict(row))) if row else None
            if fetch == "all":
                rows = cur.fetchall()
                return [ModelWrapper(**parse_dates(dict(row))) for row in rows]
            return True


def create_user(username: str, password_raw: str, plan: str = "free", role: str = "USER"):
    password_hash = hashlib.sha256(password_raw.encode()).hexdigest()
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    execute_query(
        'INSERT INTO "User" (id, username, password_hash, plan, role, "createdAt", "updatedAt") VALUES (%s, %s, %s, %s, %s, %s, %s)',
        (user_id, username, password_hash, plan, role.upper(), now, now),
    )
    return get_user_by_id(user_id)


def authenticate_user(username: str, password_raw: str):
    password_hash = hashlib.sha256(password_raw.encode()).hexdigest()
    user = execute_query('SELECT * FROM "User" WHERE username = %s', (username,), fetch="one")
    if user and user.password_hash == password_hash:
        return user
    return None


def get_user_by_id(user_id: str):
    return execute_query('SELECT * FROM "User" WHERE id = %s', (user_id,), fetch="one")


def save_prediction(user_id: str, match_id: int, predicted_winner: str, confidence: float, is_manual: bool = False, ai_data: str = ""):
    pred_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    execute_query(
        '''INSERT INTO "Prediction" (id, "userId", "matchId", "predictedWinner", "confidenceLevel", "isManual", "aiPredictionData", "createdAt")
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
        (pred_id, user_id, match_id, predicted_winner, confidence, is_manual, ai_data, now),
    )
    return True


def get_user_predictions(user_id: str, limit: int = 50):
    preds = execute_query(
        'SELECT * FROM "Prediction" WHERE "userId" = %s ORDER BY "createdAt" DESC LIMIT %s',
        (user_id, limit),
        fetch="all",
    )
    return [p.model_dump() for p in preds]


def create_notification(user_id: str, subject: str, description: str):
    notif_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    execute_query(
        'INSERT INTO "Notification" (id, "userId", subject, description, "createdAt") VALUES (%s, %s, %s, %s, %s)',
        (notif_id, user_id, subject, description, now),
    )
    return True


def get_user_notifications(user_id: str):
    nots = execute_query(
        'SELECT * FROM "Notification" WHERE "userId" = %s ORDER BY "createdAt" DESC',
        (user_id,),
        fetch="all",
    )
    return [n.model_dump() for n in nots]

