import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json
import requests
from prisma_db import authenticate_user, create_user, save_prediction as prisma_save_prediction, get_user_predictions as prisma_get_user_predictions, get_user_notifications
import prisma_db
import matplotlib.pyplot as plt
import seaborn as sns
from fpdf import FPDF
import base64
from io import BytesIO
import time
from typing import List, Dict, Optional
import hashlib
import hmac
from scipy import stats
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

from db import init_db, get_teams_by_sport, get_pitchers, save_future_match, get_future_matches
from predict import predict_football, predict_nba, predict_mlb
# ============================================================================
# CONFIGURACIÓN DE LA PÁGINA
# ============================================================================

st.set_page_config(
    page_title="SportsPredict Pro - Predicciones Deportivas",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://www.example.com/help",
        "Report a bug": "https://www.example.com/bug",
        "About": "# SportsPredict Pro v1.0\nPlataforma de predicciones deportivas con IA"
    }
)

# Estilos CSS personalizados
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
    }
    .prediction-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
    }
    .premium-badge {
        background: linear-gradient(135deg, #ffd89b 0%, #19547b 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# INICIALIZACIÓN Y CONFIGURACIÓN
# ============================================================================

@st.cache_resource
def init_api_keys():
    """Obtiene las claves de API de los secretos (Solo APIs Gratuitas)"""
    return {
        'api_football': st.secrets.get("API_FOOTBALL_KEY", ""),
        'google_studio': st.secrets.get("GOOGLE_STUDIO_KEY", "")
    }

api_keys = init_api_keys()

@st.cache_resource
def init_storage():
    """Asegura que las bases locales existan antes de usarlas."""
    init_db()
    prisma_db.init_prisma_db()

init_storage()

# Estado de sesión
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

if 'user_tier' not in st.session_state:
    st.session_state.user_tier = "free"

if 'user_role' not in st.session_state:
    st.session_state.user_role = "USER"

if 'favorite_teams' not in st.session_state:
    st.session_state.favorite_teams = []

if 'selected_competitions' not in st.session_state:
    st.session_state.selected_competitions = []

# ============================================================================
# CLASES Y UTILIDADES
# ============================================================================

class PDFReport(FPDF):
    """Generador de reportes PDF"""

    def header(self):
        self.set_font('Arial', 'B', 16)
        self.image(None, 10, 8, 33)  # Placeholder para logo
        self.cell(0, 10, 'SportsPredict Pro - Reporte de Predicciones', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 10, title, 0, 1, 'L', True)
        self.ln(5)

    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 10, body)
        self.ln()

class APIClient:
    """Cliente para consultar APIs de deportes"""

    def __init__(self, api_keys: Dict):
        self.api_keys = api_keys
        self.football_base_url = "https://v3.football.api-sports.io"
        self.session = requests.Session()

    def get_matches_by_date(self, target_date: str) -> List[Dict]:
        """Obtiene partidos de una fecha específica de API-Football"""
        try:
            if not self.api_keys.get('api_football'):
                return self._get_mock_matches()

            headers = {"x-apisports-key": self.api_keys['api_football']}
            response = self.session.get(
                f"{self.football_base_url}/fixtures",
                headers=headers,
                params={"date": target_date, "status": "NS"}  # NS = Not Started
            )
            
            if response.status_code == 200:
                data = response.json()
                errors = data.get('errors')
                if errors:
                    if isinstance(errors, dict) and any(errors.values()):
                        err_msg = ", ".join([f"{k}: {v}" for k, v in errors.items()])
                        raise ValueError(err_msg)
                    elif isinstance(errors, list) and len(errors) > 0:
                        raise ValueError(str(errors))
                
                if 'response' in data:
                    allowed_countries = {'italy', 'spain', 'france', 'germany', 'england'}
                    return [
                        m for m in data['response']
                        if m.get('league', {}).get('country', '').lower() in allowed_countries
                    ]
            else:
                raise ValueError(f"HTTP Status {response.status_code}")
            return self._get_mock_matches()
        except Exception as e:
            st.warning(f"Error obteniendo partidos de API-Football: {e}. Se mostrarán partidos de prueba.")
            return self._get_mock_matches()

    def get_upcoming_matches(self, days: int = 7) -> List[Dict]:
        """Obtiene partidos próximos de API-Football"""
        try:
            if not self.api_keys.get('api_football'):
                return self._get_mock_matches()

            headers = {"x-apisports-key": self.api_keys['api_football']}

            # Obtener partidos de los próximos días
            matches = []
            allowed_countries = {'italy', 'spain', 'france', 'germany', 'england'}
            for i in range(days):
                date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
                response = self.session.get(
                    f"{self.football_base_url}/fixtures",
                    headers=headers,
                    params={"date": date, "status": "NS"}  # NS = Not Started
                )

                if response.status_code == 200:
                    data = response.json()
                    errors = data.get('errors')
                    if errors:
                        if isinstance(errors, dict) and any(errors.values()):
                            err_msg = ", ".join([f"{k}: {v}" for k, v in errors.items()])
                            raise ValueError(err_msg)
                        elif isinstance(errors, list) and len(errors) > 0:
                            raise ValueError(str(errors))
                    if 'response' in data:
                        filtered_day = [
                            m for m in data['response']
                            if m.get('league', {}).get('country', '').lower() in allowed_countries
                        ]
                        matches.extend(filtered_day[:5])  # Limitar a 5 por día
                else:
                    raise ValueError(f"HTTP Status {response.status_code}")

            return matches[:10]
        except Exception as e:
            st.warning(f"Error obteniendo partidos de API-Football: {e}. Se mostrarán partidos de prueba.")
            return self._get_mock_matches()

    def get_team_stats(self, team_id: int) -> Dict:
        """Obtiene estadísticas de un equipo"""
        try:
            if not self.api_keys.get('api_football'):
                return self._get_mock_team_stats()

            headers = {"x-apisports-key": self.api_keys['api_football']}
            response = self.session.get(
                f"{self.football_base_url}/teams/statistics",
                headers=headers,
                params={"team": team_id, "season": datetime.now().year}
            )

            if response.status_code == 200:
                data = response.json()
                errors = data.get('errors')
                if errors:
                    if isinstance(errors, dict) and any(errors.values()):
                        err_msg = ", ".join([f"{k}: {v}" for k, v in errors.items()])
                        raise ValueError(err_msg)
                    elif isinstance(errors, list) and len(errors) > 0:
                        raise ValueError(str(errors))
                return data.get('response', {})
            else:
                raise ValueError(f"HTTP Status {response.status_code}")
            return self._get_mock_team_stats()
        except Exception as e:
            st.warning(f"Error obteniendo estadísticas: {e}. Se mostrarán estadísticas de prueba.")
            return self._get_mock_team_stats()

    def get_predictions(self, fixture_id: int) -> Dict:
        """Obtiene predicciones para un partido"""
        try:
            if not self.api_keys.get('api_football'):
                return self._get_mock_prediction()

            headers = {"x-apisports-key": self.api_keys['api_football']}
            response = self.session.get(
                f"{self.football_base_url}/predictions",
                headers=headers,
                params={"fixture": fixture_id}
            )

            if response.status_code == 200:
                data = response.json()
                errors = data.get('errors')
                if errors:
                    if isinstance(errors, dict) and any(errors.values()):
                        err_msg = ", ".join([f"{k}: {v}" for k, v in errors.items()])
                        raise ValueError(err_msg)
                    elif isinstance(errors, list) and len(errors) > 0:
                        raise ValueError(str(errors))
                return data.get('response', [{}])[0]
            else:
                raise ValueError(f"HTTP Status {response.status_code}")
            return self._get_mock_prediction()
        except Exception as e:
            st.warning(f"Error obteniendo predicciones: {e}. Se mostrarán predicciones de prueba.")
            return self._get_mock_prediction()

    def get_head_to_head(self, team1_id: int, team2_id: int) -> List[Dict]:
        """Obtiene historial H2H entre dos equipos"""
        try:
            if not self.api_keys.get('api_football'):
                return self._get_mock_h2h()

            headers = {"x-apisports-key": self.api_keys['api_football']}
            response = self.session.get(
                f"{self.football_base_url}/fixtures/headtohead",
                headers=headers,
                params={"h2h": f"{team1_id}-{team2_id}", "last": 10}
            )

            if response.status_code == 200:
                data = response.json()
                errors = data.get('errors')
                if errors:
                    if isinstance(errors, dict) and any(errors.values()):
                        err_msg = ", ".join([f"{k}: {v}" for k, v in errors.items()])
                        raise ValueError(err_msg)
                    elif isinstance(errors, list) and len(errors) > 0:
                        raise ValueError(str(errors))
                return data.get('response', [])
            else:
                raise ValueError(f"HTTP Status {response.status_code}")
            return self._get_mock_h2h()
        except Exception as e:
            st.warning(f"Error obteniendo H2H: {e}. Se mostrarán partidos de prueba.")
            return self._get_mock_h2h()

    # ==================== DATOS MOCK ====================

    @staticmethod
    def _get_mock_matches() -> List[Dict]:
        """Retorna datos de ejemplo para partidos"""
        return [
            {
                'fixture': {'id': 1001, 'date': '2026-07-13T20:00:00+00:00', 'status': 'NS'},
                'league': {'name': 'La Liga', 'country': 'Spain', 'logo': ''},
                'teams': {
                    'home': {'id': 541, 'name': 'Real Madrid', 'logo': ''},
                    'away': {'id': 529, 'name': 'Barcelona', 'logo': ''}
                },
                'goals': {'home': None, 'away': None}
            },
            {
                'fixture': {'id': 1002, 'date': '2026-07-13T15:00:00+00:00', 'status': 'NS'},
                'league': {'name': 'Premier League', 'country': 'England', 'logo': ''},
                'teams': {
                    'home': {'id': 42, 'name': 'Manchester City', 'logo': ''},
                    'away': {'id': 40, 'name': 'Liverpool', 'logo': ''}
                },
                'goals': {'home': None, 'away': None}
            },
            {
                'fixture': {'id': 1003, 'date': '2026-07-13T19:30:00+00:00', 'status': 'NS'},
                'league': {'name': 'Bundesliga', 'country': 'Germany', 'logo': ''},
                'teams': {
                    'home': {'id': 25, 'name': 'Bayern Munich', 'logo': ''},
                    'away': {'id': 165, 'name': 'Borussia Dortmund', 'logo': ''}
                },
                'goals': {'home': None, 'away': None}
            },
            {
                'fixture': {'id': 1004, 'date': '2026-07-13T18:00:00+00:00', 'status': 'NS'},
                'league': {'name': 'La Liga', 'country': 'Spain', 'logo': ''},
                'teams': {
                    'home': {'id': 542, 'name': 'Atletico Madrid', 'logo': ''},
                    'away': {'id': 529, 'name': 'Barcelona', 'logo': ''}
                },
                'goals': {'home': None, 'away': None}
            },
            {
                'fixture': {'id': 1005, 'date': '2026-07-13T21:00:00+00:00', 'status': 'NS'},
                'league': {'name': 'La Liga', 'country': 'Spain', 'logo': ''},
                'teams': {
                    'home': {'id': 548, 'name': 'Real Sociedad', 'logo': ''},
                    'away': {'id': 541, 'name': 'Real Madrid', 'logo': ''}
                },
                'goals': {'home': None, 'away': None}
            },
            {
                'fixture': {'id': 1006, 'date': '2026-07-13T17:30:00+00:00', 'status': 'NS'},
                'league': {'name': 'Premier League', 'country': 'England', 'logo': ''},
                'teams': {
                    'home': {'id': 49, 'name': 'Arsenal', 'logo': ''},
                    'away': {'id': 45, 'name': 'Chelsea', 'logo': ''}
                },
                'goals': {'home': None, 'away': None}
            },
            {
                'fixture': {'id': 1007, 'date': '2026-07-13T20:00:00+00:00', 'status': 'NS'},
                'league': {'name': 'Premier League', 'country': 'England', 'logo': ''},
                'teams': {
                    'home': {'id': 33, 'name': 'Manchester United', 'logo': ''},
                    'away': {'id': 47, 'name': 'Tottenham', 'logo': ''}
                },
                'goals': {'home': None, 'away': None}
            },
            {
                'fixture': {'id': 1008, 'date': '2026-07-13T15:30:00+00:00', 'status': 'NS'},
                'league': {'name': 'Bundesliga', 'country': 'Germany', 'logo': ''},
                'teams': {
                    'home': {'id': 168, 'name': 'Bayer Leverkusen', 'logo': ''},
                    'away': {'id': 25, 'name': 'Bayern Munich', 'logo': ''}
                },
                'goals': {'home': None, 'away': None}
            },
            {
                'fixture': {'id': 1009, 'date': '2026-07-13T18:30:00+00:00', 'status': 'NS'},
                'league': {'name': 'Bundesliga', 'country': 'Germany', 'logo': ''},
                'teams': {
                    'home': {'id': 173, 'name': 'RB Leipzig', 'logo': ''},
                    'away': {'id': 165, 'name': 'Borussia Dortmund', 'logo': ''}
                },
                'goals': {'home': None, 'away': None}
            }
        ]

    @staticmethod
    def _get_mock_prediction() -> Dict:
        """Retorna predicción de ejemplo"""
        return {
            'predictions': {
                'winner': {'name': 'home', 'comment': 'The home team is likely to win'},
                'win_or_draw': 95,
                'win_home_or_draw': 88,
                'goals': {'home': 2.1, 'away': 1.2},
                'goals_more_less': 'over',
                'advice': 'Home team is in better form'
            },
            'comparison': {
                'form': {'home': '5W-2D-1L', 'away': '3W-4D-3L'},
                'att': {'home': 85, 'away': 72},
                'def': {'home': 92, 'away': 78},
                'poisson_distribution': {
                    'home': {'0': 8, '1': 21, '2': 35, '3': 30},
                    'away': {'0': 15, '1': 34, '2': 28, '3': 16}
                }
            }
        }

    @staticmethod
    def _get_mock_team_stats() -> Dict:
        """Retorna estadísticas de equipo de ejemplo"""
        return {
            'team': {'id': 541, 'name': 'Real Madrid'},
            'statistics': [
                {'type': 'Wins home', 'value': 12},
                {'type': 'Wins away', 'value': 8},
                {'type': 'Draws', 'value': 4},
                {'type': 'Goals for', 'value': 65},
                {'type': 'Goals against', 'value': 18},
                {'type': 'Goals for home', 'value': 35},
                {'type': 'Goals for away', 'value': 30},
                {'type': 'Goals against home', 'value': 8},
                {'type': 'Goals against away', 'value': 10}
            ]
        }

    @staticmethod
    def _get_mock_h2h() -> List[Dict]:
        """Retorna historial H2H de ejemplo"""
        return [
            {
                'fixture': {'id': 900, 'date': '2023-12-10T19:00:00+00:00'},
                'teams': {'home': {'name': 'Real Madrid'}, 'away': {'name': 'Barcelona'}},
                'goals': {'home': 2, 'away': 1},
                'score': {'fulltime': {'home': 2, 'away': 1}}
            },
            {
                'fixture': {'id': 901, 'date': '2023-10-28T20:00:00+00:00'},
                'teams': {'home': {'name': 'Barcelona'}, 'away': {'name': 'Real Madrid'}},
                'goals': {'home': 1, 'away': 1},
                'score': {'fulltime': {'home': 1, 'away': 1}}
            },
            {
                'fixture': {'id': 902, 'date': '2023-08-15T19:30:00+00:00'},
                'teams': {'home': {'name': 'Real Madrid'}, 'away': {'name': 'Barcelona'}},
                'goals': {'home': 3, 'away': 2},
                'score': {'fulltime': {'home': 3, 'away': 2}}
            }
        ]

api_client = APIClient(api_keys)

# ============================================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================================

def save_prediction(user_id: str, match_data: Dict, prediction: Dict, confidence: float):
    """Guarda una predicción en la base de datos"""
    try:
        match_id = match_data.get('fixture', {}).get('id', 0)
        # Using prisma to save
        prisma_save_prediction(
            user_id=user_id,
            match_id=match_id,
            predicted_winner=prediction.get('winner', {}).get('name', 'Unknown'),
            confidence=confidence,
            is_manual=False,
            ai_data=json.dumps(prediction)
        )
        return True
    except Exception as e:
        st.error(f"Error guardando predicción: {e}")
        return False

def get_user_predictions(user_id: str, limit: int = 50) -> List[Dict]:
    """Obtiene las predicciones de un usuario"""
    try:
        if not user_id: return []
        preds = prisma_get_user_predictions(user_id, limit)
        # Map back to dict format expected by the app
        mapped = []
        for p in preds:
            mapped.append({
                'match_id': p.get('matchId'),
                'predicted_home_score': p.get('predictedHomeScore', 0),
                'predicted_away_score': p.get('predictedAwayScore', 0),
                'confidence_level': p.get('confidenceLevel', 0),
                'created_at': p.get('createdAt').isoformat() if p.get('createdAt') else "",
                'is_manual': p.get('isManual', False),
                'predicted_winner': p.get('predictedWinner', '')
            })
        return mapped
    except Exception as e:
        st.warning(f"Error obteniendo predicciones: {e}")
        return []

def get_user_stats(user_id: str) -> Dict:
    """Calcula estadísticas del usuario"""
    predictions = get_user_predictions(user_id)

    if not predictions:
        return {
            'total_predictions': 0,
            'correct_predictions': 0,
            'accuracy_rate': 0,
            'avg_confidence': 0,
            'total_earnings': 0,
            'rank': 'N/A'
        }

    df = pd.DataFrame(predictions)

    total_preds = len(df)
    correct_preds = len(df[df['confidence_level'] > 0.7]) if 'confidence_level' in df.columns else 0
    avg_conf = df['confidence_level'].mean() if 'confidence_level' in df.columns else 0

    return {
        'total_predictions': total_preds,
        'correct_predictions': correct_preds,
        'accuracy_rate': (correct_preds / total_preds * 100) if total_preds > 0 else 0,
        'avg_confidence': float(avg_conf),
        'total_earnings': 0,
        'rank': f'Top {np.random.randint(5, 25)}%'
    }

def get_competitions() -> List[Dict]:
    """Obtiene las competencias activas"""
    return []


def is_admin() -> bool:
    """Indica si el usuario autenticado tiene rol de administrador."""
    return st.session_state.get('user_role', 'USER') == 'ADMIN'

# ============================================================================
# COMPONENTES REUTILIZABLES
# ============================================================================

def render_metric_card(label: str, value: str, delta: str = "", icon: str = ""):
    """Renderiza una tarjeta de métrica"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        st.markdown(f"<h3>{icon}</h3>", unsafe_allow_html=True)
    with col2:
        st.metric(label, value, delta=delta)
    with col3:
        pass

def render_match_card(match: Dict):
    """Renderiza una tarjeta de partido"""
    try:
        fixture = match.get('fixture', {})
        teams = match.get('teams', {})
        league = match.get('league', {})

        home_team = teams.get('home', {})
        away_team = teams.get('away', {})

        match_date = fixture.get('date', '')
        if match_date:
            match_date = datetime.fromisoformat(match_date.replace('Z', '+00:00')).strftime("%d/%m/%Y %H:%M")

        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

        with col1:
            st.write(f"🏆 **{league.get('name', 'Liga')}**")
            st.write(f"📅 {match_date}")

        with col2:
            st.write(f"🏠 **{home_team.get('name', 'Equipo 1')}**")

        with col3:
            st.write("vs")

        with col4:
            st.write(f"✈️ **{away_team.get('name', 'Equipo 2')}**")

        return True
    except Exception as e:
        st.error(f"Error renderizando partido: {e}")
        return False

# ============================================================================
# GENERADOR DE REPORTES - PDF Y EXCEL
# ============================================================================

def generate_predictions_report_pdf(predictions: List[Dict]) -> bytes:
    """Genera reporte PDF de predicciones"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 15, "📊 REPORTE DE PREDICCIONES", ln=True, align="C")

    pdf.set_font("Arial", "", 11)
    pdf.ln(5)

    df = pd.DataFrame(predictions) if predictions else pd.DataFrame()

    if not df.empty:
        total = len(df)
        correct = len(df[df.get('prediction_status') == 'won']) if 'prediction_status' in df.columns else 0
        accuracy = (correct / total * 100) if total > 0 else 0

        pdf.cell(0, 8, f"Total de Predicciones: {total}", ln=True)
        pdf.cell(0, 8, f"Predicciones Correctas: {correct}", ln=True)
        pdf.cell(0, 8, f"Tasa de Precisión: {accuracy:.2f}%", ln=True)

        if 'confidence_level' in df.columns:
            avg_conf = df['confidence_level'].mean()
            pdf.cell(0, 8, f"Confianza Promedio: {avg_conf:.2f}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "I", 8)
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pdf.cell(0, 10, f"Generado: {timestamp}", align="R")

    return pdf.output()


def generate_predictions_report_excel(predictions: List[Dict]) -> bytes:
    """Genera reporte Excel de predicciones"""
    df = pd.DataFrame(predictions) if predictions else pd.DataFrame()

    wb = Workbook()
    ws = wb.active
    ws.title = "Predicciones"

    # Headers
    if not df.empty:
        for col_idx, col_name in enumerate(df.columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.value = col_name
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="667EEA", end_color="667EEA", fill_type="solid")

        # Datos
        for row_idx, row_data in enumerate(dataframe_to_rows(df, index=False, header=False), 2):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.value = value

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# ============================================================================
# ESTADÍSTICAS DESCRIPTIVAS - GRÁFICOS Y ANÁLISIS
# ============================================================================

def create_distribution_plot(data: List[float], title: str = "Distribución") -> go.Figure:
    """Crea gráfico de distribución con curva normal"""
    if not data:
        return go.Figure()

    df = pd.DataFrame({'value': data})

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=df['value'],
        name='Frecuencia',
        nbinsx=30,
        marker_color='rgba(102, 126, 234, 0.7)'
    ))

    mu, sigma = np.mean(data), np.std(data)
    x = np.linspace(min(data), max(data), 100)
    y = stats.norm.pdf(x, mu, sigma)
    y_scaled = y * len(data) * (max(data) - min(data)) / 30

    fig.add_trace(go.Scatter(
        x=x, y=y_scaled,
        name='Curva Normal',
        mode='lines',
        line=dict(color='red', width=3)
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Valor",
        yaxis_title="Frecuencia",
        hovermode='x unified',
        height=400
    )

    return fig


def create_boxplot(data_dict: Dict[str, List[float]], title: str = "Comparación") -> go.Figure:
    """Crea gráfico de caja (boxplot)"""
    fig = go.Figure()

    for label, values in data_dict.items():
        fig.add_trace(go.Box(y=values, name=label, boxmean='sd'))

    fig.update_layout(
        title=title,
        yaxis_title="Valor",
        height=400
    )

    return fig


def create_time_series_plot(dates: List[datetime], values: List[float], title: str = "Serie Temporal") -> go.Figure:
    """Crea gráfico de serie temporal"""
    df = pd.DataFrame({'date': dates, 'value': values})
    df = df.sort_values('date')

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['value'],
        mode='lines+markers',
        name='Valor',
        line=dict(color='#667EEA', width=2)
    ))

    if len(df) > 7:
        df['ma_7'] = df['value'].rolling(window=7).mean()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['ma_7'],
            mode='lines',
            name='Media Móvil (7 días)',
            line=dict(color='red', dash='dash')
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Fecha",
        yaxis_title="Valor",
        height=400
    )

    return fig


def create_correlation_heatmap(df: pd.DataFrame, numeric_cols: List[str]) -> go.Figure:
    """Crea mapa de calor de correlaciones"""
    numeric_df = df[numeric_cols].select_dtypes(include=[np.number])
    corr_matrix = numeric_df.corr()

    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.columns,
        colorscale='RdBu',
        zmid=0,
        text=np.round(corr_matrix.values, 2),
        texttemplate='%{text:.2f}'
    ))

    fig.update_layout(title="Matriz de Correlación", height=500, width=600)
    return fig


def calculate_descriptive_stats(data: List[float]) -> Dict:
    """Calcula estadísticas descriptivas"""
    if not data or len(data) == 0:
        return {}

    data_array = np.array(data)

    return {
        'count': len(data),
        'mean': float(np.mean(data_array)),
        'median': float(np.median(data_array)),
        'std': float(np.std(data_array)),
        'min': float(np.min(data_array)),
        'max': float(np.max(data_array)),
        'q1': float(np.percentile(data_array, 25)),
        'q3': float(np.percentile(data_array, 75))
    }


def create_descriptive_stats_table(predictions: List[Dict]) -> pd.DataFrame:
    """Crea tabla de estadísticas descriptivas"""
    if not predictions:
        return pd.DataFrame()

    df = pd.DataFrame(predictions)
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    stats_data = []

    for col in numeric_cols:
        col_stats = calculate_descriptive_stats(df[col].dropna().tolist())
        stats_data.append({
            'Variable': col,
            'N': col_stats.get('count', 0),
            'Media': round(col_stats.get('mean', 0), 2),
            'Mediana': round(col_stats.get('median', 0), 2),
            'Desv. Est.': round(col_stats.get('std', 0), 2),
            'Mín': round(col_stats.get('min', 0), 2),
            'Máx': round(col_stats.get('max', 0), 2)
        })

    return pd.DataFrame(stats_data)

# ============================================================================
# PÁGINAS PRINCIPALES
# ============================================================================

def page_dashboard():
    """Página principal - Dashboard"""
    st.title("⚽ Dashboard de Predicciones Deportivas")

    # Métricas principales
    st.subheader("Tus Estadísticas")

    user_stats = get_user_stats(st.session_state.user_id)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Predicciones",
            user_stats['total_predictions'],
            delta=f"{np.random.randint(1, 5)} hoy"
        )

    with col2:
        st.metric(
            "Tasa de Precisión",
            f"{user_stats['accuracy_rate']:.1f}%",
            delta=f"+{np.random.randint(1, 5)}%" if user_stats['accuracy_rate'] > 0 else "0%"
        )

    with col3:
        st.metric(
            "Confianza Promedio",
            f"{user_stats['avg_confidence']:.2f}",
            delta="+0.05" if user_stats['avg_confidence'] > 0 else "0.00"
        )

    with col4:
        st.metric(
            "Ranking Global",
            user_stats['rank'],
            delta="+5 posiciones"
        )

    st.divider()

    # Próximos partidos creados por el usuario
    st.subheader("📋 Próximos Partidos Guardados")
    st.markdown("Partidos analizados y listos para tu predicción personal.")

    with st.spinner("Cargando partidos desde la base de datos..."):
        matches = get_future_matches()

    if matches:
        for i, match in enumerate(matches):
            with st.expander(f"[{match['deporte']}] 👥 {match['local']} vs {match['visitante']} - {match['fecha']}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write("**Predicción de nuestra IA:**")
                    st.info(f"Ganador sugerido: **{match['prediccion_ia'].upper()}**")
                    if match['deporte'] == 'Futbol':
                        st.write(f"V: {match['prob_visitante']*100:.1f}% | E: {match['prob_empate']*100:.1f}% | L: {match['prob_local']*100:.1f}%")
                    else:
                        st.write(f"Visita: {match['prob_visitante']*100:.1f}% | Local: {match['prob_local']*100:.1f}%")

                with col2:
                    st.write("**Tu Predicción:**")
                    opciones = ['Local', 'Empate', 'Visitante'] if match['deporte'] == 'Futbol' else ['Local', 'Visitante']
                    tu_pred = st.selectbox("¿Quién crees que ganará?", opciones, key=f"user_pred_{i}")

                with col3:
                    st.write("**Confianza:**")
                    confidence = st.slider("Nivel de confianza", 0.0, 1.0, 0.5, step=0.1, key=f"conf_{i}")

                    if st.button("🎯 Guardar mi predicción", key=f"btn_{i}"):
                        try:
                            prisma_save_prediction(
                                user_id=st.session_state.user_id,
                                match_id=match.get('id', 0),
                                predicted_winner=tu_pred,
                                confidence=confidence,
                                is_manual=True,
                                ai_data=json.dumps({"prediccion_ia": match.get('prediccion_ia')})
                            )
                            st.success("✅ Predicción guardada en tu perfil exitosamente")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error guardando predicción: {e}")
    else:
        st.info("No hay partidos futuros guardados. Ve a 'Crear Predicción' para añadir uno.")

    st.divider()

    # Gráfico de rendimiento
    st.subheader("📈 Tu Rendimiento Reciente")

    # Datos simulados
    days = pd.date_range(end=datetime.now(), periods=30)
    df_performance = pd.DataFrame({
        'fecha': days,
        'precisión': np.random.uniform(0.4, 0.85, 30),
        'predicciones': np.random.randint(1, 8, 30)
    })

    col1, col2 = st.columns(2)

    with col1:
        fig_precision = px.line(
            df_performance,
            x='fecha',
            y='precisión',
            title='Evolución de Precisión (30 días)',
            markers=True,
            color_discrete_sequence=['#FF4B4B']
        )
        fig_precision.update_layout(hovermode='x unified')
        st.plotly_chart(fig_precision, use_container_width=True)

    with col2:
        fig_volume = px.bar(
            df_performance,
            x='fecha',
            y='predicciones',
            title='Volumen de Predicciones',
            color_discrete_sequence=['#00CC96']
        )
        st.plotly_chart(fig_volume, use_container_width=True)

def page_my_predictions():
    """Página de mis predicciones"""
    st.title("📊 Mis Predicciones")

    predictions = get_user_predictions(st.session_state.user_id)

    if predictions:
        df = pd.DataFrame(predictions)

        # Resumen
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de predicciones", len(df))
        with col2:
            high_conf = len(df[df['confidence_level'] > 0.7])
            st.metric("Alta confianza (>70%)", high_conf)
        with col3:
            avg_conf = df['confidence_level'].mean()
            st.metric("Confianza promedio", f"{avg_conf:.2f}")

        st.divider()

        # Tabla de predicciones
        st.subheader("Historial de Predicciones")

        display_df = df[['match_id', 'predicted_home_score', 'predicted_away_score', 'confidence_level', 'created_at']].copy()
        display_df.columns = ['ID Partido', 'Goles Local', 'Goles Visitante', 'Confianza', 'Fecha']

        st.dataframe(display_df, use_container_width=True)

        # Análisis
        st.subheader("📈 Análisis de Confianza")

        fig = px.histogram(
            df,
            x='confidence_level',
            nbins=20,
            title='Distribución de Niveles de Confianza',
            color_discrete_sequence=['#FF4B4B']
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aún no has realizado predicciones. ¡Comienza ahora!")

import json
from reports import generate_consolidated_report

def page_ai_predictions():
    """Página de predicciones con IA"""
    st.title("🤖 Predicciones con Inteligencia Artificial")

    st.markdown("""
    Nuestra inteligencia artificial se somete a una rigurosa evaluación de validación cruzada.
    Se utiliza el **historial histórico completo** para entrenamiento, reservando estrictamente los 
    **últimos 365 días** de resultados reales para evaluar la precisión del modelo en escenarios no vistos.
    """)

    st.divider()

    # Inicializar el estado de la predicción activa
    if 'active_prediction' not in st.session_state:
        st.session_state.active_prediction = None

    # Mostrar la última predicción realizada si está activa
    if st.session_state.active_prediction:
        act = st.session_state.active_prediction
        st.markdown("<div style='border: 2px solid #667eea; padding: 20px; border-radius: 12px; margin-bottom: 20px; background-color: #1e1e1e;'>", unsafe_allow_html=True)
        st.subheader("🔮 Último Análisis de IA Generado")
        col_m_left, col_m_right = st.columns([3, 2])
        with col_m_left:
            st.write(f"### {act['home_team']} vs {act['away_team']}")
            st.success(f"Favorito: **{act['pred_label'].upper()}**")
            st.info(f"📈 **Confianza:** {act['confidence']*100:.1f}%")
        with col_m_right:
            labels = ['Visitante', 'Empate', 'Local']
            values = [act['probs']['visitante']*100, act['probs']['empate']*100, act['probs']['local']*100]
            fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.5, marker_colors=['#f5576c', '#aaaaaa', '#667eea'])])
            fig.update_layout(height=220, margin=dict(t=20, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
        
        if st.button("❌ Cerrar Análisis", use_container_width=True):
            st.session_state.active_prediction = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("📅 Partidos Futuros (Mundial)")
    st.write("Selecciona una fecha (hasta 4 días en el futuro) para ver los próximos partidos de fútbol y obtener una predicción de nuestra IA.")
    
    if 'api_matches' not in st.session_state:
        st.session_state.api_matches = []
        st.session_state.last_api_date = None
        
    col_date, col_empty = st.columns([1, 3])
    with col_date:
        selected_date = st.date_input(
            "Fecha de los partidos",
            value=datetime.now().date(),
            min_value=datetime.now().date(),
            max_value=(datetime.now() + timedelta(days=4)).date()
        )
    
    date_str = selected_date.strftime("%Y-%m-%d")
    
    if st.session_state.last_api_date != date_str:
        with st.spinner("Conectando con API-Football..."):
            st.session_state.api_matches = api_client.get_matches_by_date(date_str)
            st.session_state.last_api_date = date_str

    # Obtener IDs de partidos ya predichos por el usuario
    user_preds = get_user_predictions(st.session_state.user_id)
    predicted_match_ids = {int(p['match_id']) for p in user_preds if p.get('match_id') is not None}
            
    if st.session_state.api_matches:
        # Filtrar partidos que ya fueron predichos
        matches = [m for m in st.session_state.api_matches if m.get('fixture', {}).get('id') not in predicted_match_ids]
        
        if matches:
            st.success(f"Se encontraron {len(matches)} partidos programados para el {st.session_state.last_api_date} (excluyendo tus predicciones).")
            
            for i, match in enumerate(matches[:15]): 
                fixture = match.get('fixture', {})
                teams = match.get('teams', {})
                league = match.get('league', {})
                
                home_team = teams.get('home', {}).get('name', 'Local')
                away_team = teams.get('away', {}).get('name', 'Visitante')
                match_time = fixture.get('date', '').split('T')[1][:5] if 'T' in fixture.get('date', '') else ''
                
                with st.container():
                    st.markdown(f"<div style='border:1px solid #333; padding: 15px; border-radius: 8px; margin-bottom: 10px; background-color: #1e1e1e;'>", unsafe_allow_html=True)
                    col1, col2, col3 = st.columns([2, 3, 2])
                    with col1:
                        st.write(f"🏆 **{league.get('name', 'Liga')}**")
                        st.write(f"⏱️ {match_time}")
                    with col2:
                        st.write(f"🏠 **{home_team}**")
                        st.write(f"✈️ **{away_team}**")
                    
                    with col3:
                        # Usar el ID del fixture en la clave del botón para evitar colisiones
                        btn_key = f"pred_api_{fixture.get('id', i)}"
                        if st.button(f"🔮 Predecir", key=btn_key, use_container_width=True):
                            with st.spinner("Analizando historial..."):
                                try:
                                    probs = predict_football(home_team, away_team)
                                    pred_label = max(probs, key=probs.get)
                                    
                                    # Guardar en la base de datos de Prisma del usuario
                                    fid = fixture.get('id') if fixture.get('id') else int(time.time())
                                    prisma_save_prediction(
                                        user_id=st.session_state.user_id,
                                        match_id=fid,
                                        predicted_winner=pred_label.upper(),
                                        confidence=max(probs.values()),
                                        is_manual=False,
                                        ai_data=json.dumps({"prediccion_ia": pred_label, "probs": probs})
                                    )
                                    
                                    # Guardar en session state para el banner
                                    st.session_state.active_prediction = {
                                        'home_team': home_team,
                                        'away_team': away_team,
                                        'pred_label': pred_label,
                                        'probs': probs,
                                        'confidence': max(probs.values())
                                    }
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
                    st.markdown("</div>", unsafe_allow_html=True)
            
            if len(matches) > 15:
                st.info(f"... y {len(matches) - 15} partidos más. (Se muestran los primeros 15).")
        else:
            st.info("Ya has realizado predicciones para todos los partidos disponibles en esta fecha.")
            
    st.divider()

    if not is_admin():
        st.info("Los resultados detallados del modelo y la exportación consolidada están restringidos al rol ADMIN.")
        return

    try:
        with open('model_results.json', 'r') as f:
            model_results = json.load(f)
    except FileNotFoundError:
        st.warning("⏳ Los modelos se están entrenando en este momento (Time-Based Split). Por favor, regresa más tarde para ver los resultados.")
        return

    st.subheader("📊 Resultados de Validación Cronológica (Último Año)")
    
    # Selector de deporte
    deportes = list(model_results.keys())
    sport = st.selectbox("Deporte a visualizar", deportes, format_func=lambda x: x.upper())
    
    result = model_results[sport]
    best_model = result['best_model']
    model_details = result['model_details']

    st.info(f"🏆 El modelo **{best_model.upper()}** fue seleccionado como el mejor y es el utilizado para inferencias en vivo.")

    # Convertir JSON a DataFrame para mostrar
    records = []
    for m_name, details in model_details.items():
        records.append({
            'Modelo': f"⭐ {m_name.upper()}" if m_name == best_model else m_name.upper(),
            'Accuracy': f"{details.get('accuracy', 0)*100:.2f}%",
            'F1 Score': f"{details.get('f1', 0):.4f}",
            'Tiempo de Entr. (s)': f"{details.get('time_s', 0):.1f}"
        })
    df_eval = pd.DataFrame(records)
    
    st.dataframe(df_eval, use_container_width=True)

    with st.expander("Ver Hiperparámetros Óptimos"):
        for m_name, details in model_details.items():
            params = details.get('params', {})
            if params:
                st.write(f"**{m_name.upper()}**:")
                st.code(json.dumps(params, indent=2))
            else:
                st.write(f"**{m_name.upper()}**: Default")

    st.divider()
    
    st.write("### 📄 Exportar Reporte Consolidado")
    st.write("Descarga un informe detallado con las métricas y configuraciones de todos los modelos entrenados.")
    
    report_bytes = generate_consolidated_report('model_results.json')
    if report_bytes:
        st.download_button(
            label="⬇️ Descargar Reporte Completo (Word)",
            data=report_bytes,
            file_name=f"Reporte_Definitivo_Modelos_{datetime.now().strftime('%Y%m%d')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

def page_competitions():
    """Página de competencias"""
    st.title("🏆 Competencias y Torneos")

    # Datos de ejemplo
    competitions_data = [
        {
            'id': 1,
            'name': 'Liga Predictor Enero',
            'description': 'Predice correctamente y gana premios semanales',
            'participants': 245,
            'prize': '$1,000',
            'entry_fee': 'Gratis',
            'deadline': '2024-01-31',
            'status': 'active',
            'prize_pool': 1000
        },
        {
            'id': 2,
            'name': 'Torneo Premium Elite',
            'description': 'Exclusivo para suscriptores premium - Grandes premios',
            'participants': 89,
            'prize': '$2,500',
            'entry_fee': '$10',
            'deadline': '2024-01-25',
            'status': 'active',
            'prize_pool': 2500
        },
        {
            'id': 3,
            'name': 'Desafío de 100 Predicciones',
            'description': 'Realiza 100 predicciones precisas y gana jackpot',
            'participants': 156,
            'prize': '$500',
            'entry_fee': 'Gratis',
            'deadline': '2024-02-15',
            'status': 'active',
            'prize_pool': 500
        }
    ]

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Competencias Disponibles")

        for comp in competitions_data:
            with st.expander(f"🏆 {comp['name']}"):
                st.write(f"**Descripción:** {comp['description']}")

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    st.metric("Participantes", comp['participants'])

                with col_b:
                    st.metric("Premio Total", comp['prize'])

                with col_c:
                    st.metric("Entrada", comp['entry_fee'])

                st.write(f"📅 **Cierra:** {comp['deadline']}")

                col_x, col_y = st.columns(2)

                with col_x:
                    if comp['entry_fee'] == 'Gratis':
                        if st.button("✅ Unirse", key=f"join_{comp['id']}"):
                            st.session_state.selected_competitions.append(comp['id'])
                            st.success(f"¡Te has unido a {comp['name']}!")
                            st.balloons()
                    else:
                        if st.session_state.user_tier == 'premium':
                            if st.button("✅ Unirse", key=f"join_{comp['id']}"):
                                st.session_state.selected_competitions.append(comp['id'])
                                st.success(f"¡Te has unido a {comp['name']}!")
                                st.balloons()
                        else:
                            st.warning("💎 Requiere suscripción Premium")

                with col_y:
                    st.write(f"Status: ✅ Activa")

    with col2:
        st.subheader("📊 Tu Ranking")

        ranking_positions = [
            {'pos': 1, 'user': 'PredictorPro', 'score': 1850, 'acc': '78%'},
            {'pos': 2, 'user': 'SportGenius', 'score': 1820, 'acc': '76%'},
            {'pos': 3, 'user': 'BetMaster', 'score': 1780, 'acc': '74%'},
            {'pos': 4, 'user': 'DataAnalyst', 'score': 1750, 'acc': '72%'},
            {'pos': 5, 'user': 'GoldenPredictor', 'score': 1720, 'acc': '71%'},
            {'pos': 15, 'user': '👤 Tú', 'score': 1520, 'acc': '68%'},
        ]

        for rank in ranking_positions:
            if rank['user'] == '👤 Tú':
                st.markdown(
                    f"<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); "
                    f"color: white; padding: 10px; border-radius: 5px; margin: 5px 0;'>"
                    f"<b>🎯 {rank['pos']}. {rank['user']}</b> - {rank['score']} pts ({rank['acc']})"
                    f"</div>",
                    unsafe_allow_html=True
                )
            else:
                st.write(f"{rank['pos']}. {rank['user']} - {rank['score']} pts ({rank['acc']})")

def page_statistics():
    """Página de estadísticas avanzadas con gráficos y reportes"""
    st.title("📊 ESTADÍSTICAS DESCRIPTIVAS Y ANÁLISIS")

    user_stats = get_user_stats(st.session_state.user_id)
    predictions = get_user_predictions(st.session_state.user_id)

    # ============ TAB 1: RESUMEN ============
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📈 Resumen", "📋 Tablas", "📊 Gráficos Avanzados", "📥 Reportes", "💡 Insights"]
    )

    with tab1:
        st.subheader("Resumen General")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Predicciones",
                user_stats['total_predictions'],
                delta=f"+{user_stats['total_predictions'] % 10}"
            )

        with col2:
            st.metric(
                "Tasa de Precisión",
                f"{user_stats['accuracy_rate']:.1f}%",
                delta=f"+{user_stats['accuracy_rate'] - 55:.1f}%" if user_stats['accuracy_rate'] > 55 else "-2%"
            )

        with col3:
            st.metric(
                "Confianza Promedio",
                f"{user_stats['avg_confidence']:.2f}",
                delta="+0.05"
            )

        with col4:
            st.metric(
                "Ranking Global",
                str(user_stats['rank']),
                delta="+5 posiciones"
            )

    # ============ TAB 2: TABLAS ESTADÍSTICAS ============
    with tab2:
        st.subheader("Estadísticas Descriptivas")

        # Tabla de resumen
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Resumen de Desempeño**")
            summary_table = pd.DataFrame({
                'Métrica': ['Total', 'Correctas', 'Incorrectas', 'Precisión', 'Confianza Prom.', 'Ranking'],
                'Valor': [
                    str(user_stats['total_predictions']),
                    str(user_stats['correct_predictions']),
                    str(user_stats['total_predictions'] - user_stats['correct_predictions']),
                    f"{user_stats['accuracy_rate']:.2f}%",
                    f"{user_stats['avg_confidence']:.2f}",
                    str(user_stats['rank'])
                ]
            })
            st.dataframe(summary_table, use_container_width=True)

        with col2:
            st.write("**Estadísticas Descriptivas de Predicciones**")
            stats_table = create_descriptive_stats_table(predictions)
            if not stats_table.empty:
                st.dataframe(stats_table, use_container_width=True)
            else:
                st.info("No hay datos numéricos disponibles")

    # ============ TAB 3: GRÁFICOS AVANZADOS ============
    with tab3:
        st.subheader("Visualizaciones Avanzadas")

        if predictions and len(predictions) > 0:
            df = pd.DataFrame(predictions)

            # Gráfico 1: Distribución de Confianza
            if 'confidence_level' in df.columns:
                col1, col2 = st.columns(2)

                with col1:
                    confidence_data = df['confidence_level'].dropna().tolist()
                    fig_dist = create_distribution_plot(
                        confidence_data,
                        "Distribución de Confianza (Histograma + Curva Normal)"
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)

                with col2:
                    # Gráfico de CDF (Función de Distribución Acumulada)
                    sorted_data = np.sort(confidence_data)
                    cumulative = np.arange(1, len(sorted_data) + 1) / len(sorted_data)

                    fig_cdf = go.Figure()
                    fig_cdf.add_trace(go.Scatter(
                        x=sorted_data, y=cumulative,
                        mode='lines',
                        name='CDF',
                        line=dict(color='#667EEA', width=3)
                    ))
                    fig_cdf.update_layout(
                        title="Función de Distribución Acumulada (CDF)",
                        xaxis_title="Confianza",
                        yaxis_title="Probabilidad",
                        height=400
                    )
                    st.plotly_chart(fig_cdf, use_container_width=True)

            # Gráfico 2: Serie Temporal
            if 'created_at' in df.columns:
                st.subheader("Evolución en el Tiempo")

                df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
                df_sorted = df.sort_values('created_at').dropna(subset=['created_at'])

                if len(df_sorted) > 0:
                    dates = df_sorted['created_at'].tolist()
                    values = df_sorted.get('confidence_level', pd.Series(range(len(df_sorted)))).tolist()

                    fig_time = create_time_series_plot(
                        dates, values,
                        "Evolución de Confianza en el Tiempo"
                    )
                    st.plotly_chart(fig_time, use_container_width=True)

            # Gráfico 3: Por Status
            if 'prediction_status' in df.columns:
                st.subheader("Análisis por Status")

                status_counts = df['prediction_status'].value_counts()
                fig_status = px.bar(
                    x=status_counts.index,
                    y=status_counts.values,
                    title="Distribución por Status",
                    labels={'x': 'Status', 'y': 'Cantidad'},
                    color_discrete_sequence=['#667EEA']
                )
                fig_status.update_layout(height=400)
                st.plotly_chart(fig_status, use_container_width=True)

        else:
            st.info("No hay suficientes datos para mostrar gráficos")

    # ============ TAB 4: REPORTES ============
    with tab4:
        st.subheader("📥 Generar Reportes")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Reporte en PDF**")
            if st.button("📄 Descargar PDF"):
                pdf_bytes = generate_predictions_report_pdf(predictions)
                st.download_button(
                    label="Descargar PDF",
                    data=pdf_bytes,
                    file_name=f"predicciones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                )

        with col2:
            st.write("**Reporte en Excel**")
            if st.button("📊 Descargar Excel"):
                excel_bytes = generate_predictions_report_excel(predictions)
                st.download_button(
                    label="Descargar Excel",
                    data=excel_bytes,
                    file_name=f"predicciones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    # ============ TAB 5: INSIGHTS ============
    with tab5:
        st.subheader("💡 Insights y Recomendaciones")

        accuracy = user_stats.get('accuracy_rate', 0)
        confidence = user_stats.get('avg_confidence', 0)

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Análisis de Rendimiento**")

            if accuracy >= 75:
                st.success("✅ **EXCELENTE** - Tu precisión es superior al 75%")
                insight1 = "Mantén tu estrategia actual, has encontrado un buen patrón."
            elif accuracy >= 60:
                st.info("⚠️ **BUENO** - Tu precisión está sobre el promedio")
                insight1 = "Continúa mejorando, hay espacio para optimizar."
            else:
                st.warning("⚠️ **DESARROLLO** - Tu precisión está por debajo del 60%")
                insight1 = "Revisa tu metodología de análisis."

            st.write(insight1)

        with col2:
            st.write("**Análisis de Confianza**")

            if confidence >= 0.75:
                st.success("✅ Confianza bien calibrada (>0.75)")
                insight2 = "Tu confianza es realista con tu precisión."
            elif confidence >= 0.6:
                st.info("⚠️ Confianza moderada (0.60-0.75)")
                insight2 = "Considera si tu confianza refleja tu precisión."
            else:
                st.warning("⚠️ Confianza baja (<0.60)")
                insight2 = "Aumenta confianza cuando tengas análisis sólidos."

            st.write(insight2)

        st.divider()

        st.write("**Recomendaciones Personalizadas**")
        recommendations = [
            "🔍 Analiza tus predicciones incorrectas para identificar patrones",
            "📚 Aumenta confianza solo cuando tengas datos sólidos de respaldo",
            "🎯 Diversifica tus predicciones entre diferentes deportes y ligas",
            "📊 Mantén un registro detallado de tus análisis y resultados",
            "⏱️ Revisa tu rendimiento regularmente (semanal/mensual)",
            "💡 Considera variables externas: lesiones, clima, forma del equipo"
        ]

        for rec in recommendations:
            st.write(rec)

def page_alerts():
    """Página de alertas"""
    st.title("🔔 Alertas y Notificaciones")

    alerts_data = [
        {
            'type': 'partido',
            'icon': '⚽',
            'title': 'Nuevo partido disponible',
            'message': 'Real Madrid vs Barcelona - Predicción IA lista',
            'time': 'Hace 2 horas',
            'read': False
        },
        {
            'type': 'prediccion',
            'icon': '🤖',
            'title': 'Actualización de predicción IA',
            'message': 'Nueva predicción para Manchester City vs Liverpool',
            'time': 'Hace 5 horas',
            'read': True
        },
        {
            'type': 'competencia',
            'icon': '🏆',
            'title': 'Competencia finaliza pronto',
            'message': 'Liga Predictor Enero cierra en 2 días',
            'time': 'Hace 1 día',
            'read': False
        },
        {
            'type': 'ranking',
            'icon': '📈',
            'title': 'Cambio en tu ranking',
            'message': 'Subiste 5 posiciones en el ranking global',
            'time': 'Hace 1 día',
            'read': True
        }
    ]

    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("Notificaciones Recientes")

        for alert in alerts_data:
            status_icon = "📬" if alert['read'] else "📭"
            bg_color = "#f0f0f0" if alert['read'] else "#fff3cd"

            col_alert = st.columns([1, 10, 1])

            with col_alert[0]:
                st.write(alert['icon'])

            with col_alert[1]:
                st.markdown(
                    f"<div style='background: {bg_color}; padding: 15px; border-radius: 5px;'>"
                    f"<b>{alert['title']}</b><br>"
                    f"{alert['message']}<br>"
                    f"<small>{alert['time']}</small>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with col_alert[2]:
                st.write(status_icon)

    with col2:
        st.subheader("Configurar Alertas")

        st.checkbox("⚽ Nuevos partidos", value=True)
        st.checkbox("🤖 Predicciones IA", value=True)
        st.checkbox("🏆 Competencias", value=True)
        st.checkbox("📈 Cambios ranking", value=True)
        st.checkbox("💎 Ofertas Premium", value=False)

        if st.button("Guardar configuración"):
            st.success("✅ Configuración guardada")

def page_premium():
    """Página de suscripción premium"""
    st.title("💎 SportsPredict Pro Premium")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("📦 Plan Free")

        st.markdown("""
        ✅ Predicciones IA básicas
        ✅ Competencias gratuitas
        ✅ Estadísticas básicas
        ✅ Hasta 50 predicciones/mes

        ---

        **Precio:** Gratis
        """)

        if st.session_state.user_tier != "free":
            st.info("Tu plan actual: Premium")
        else:
            st.success("Tu plan actual")

    with col2:
        st.subheader("🌟 Plan Pro")

        st.markdown("""
        ✅ Todas las del plan Free
        ✅ Predicciones IA avanzadas
        ✅ Acceso a competencias premium
        ✅ Análisis detallados
        ✅ Reportes PDF personalizados
        ✅ Alertas ilimitadas
        ✅ Hasta 500 predicciones/mes

        ---

        **Precio:** $4.99/mes
        *(o $49.99/año)*
        """)

        if st.button("🚀 Suscribirse a Pro", key="btn_pro"):
            st.session_state.user_tier = "pro"
            st.success("¡Bienvenido a SportsPredict Pro!")
            st.balloons()

    with col3:
        st.subheader("👑 Plan Elite")

        st.markdown("""
        ✅ Todas las del plan Pro
        ✅ Acceso a análisis IA en tiempo real
        ✅ Consultas personalizadas con expertos
        ✅ Datos históricos completos
        ✅ Predicciones ilimitadas
        ✅ Prioridad en competencias
        ✅ Descuentos en apuestas

        ---

        **Precio:** $9.99/mes
        *(o $99.99/año)*
        """)

        if st.button("👑 Suscribirse a Elite", key="btn_elite"):
            st.session_state.user_tier = "elite"
            st.success("¡Bienvenido a SportsPredict Elite!")
            st.balloons()

    st.divider()

    st.subheader("Beneficios Adicionales")

    benefits = pd.DataFrame({
        'Característica': [
            'Predicciones IA básicas',
            'Predicciones IA avanzadas',
            'Acceso a competencias',
            'Reportes PDF',
            'Alertas personalizadas',
            'Análisis histórico',
            'Soporte prioritario',
            'Consulta con expertos'
        ],
        'Free': ['✅', '❌', '✅', '❌', '❌', '❌', '❌', '❌'],
        'Pro': ['✅', '✅', '✅', '✅', '✅', '✅', '❌', '❌'],
        'Elite': ['✅', '✅', '✅', '✅', '✅', '✅', '✅', '✅']
    })

    st.dataframe(benefits, use_container_width=True)

# ============================================================================
# MENÚ PRINCIPAL Y NAVEGACIÓN
# ============================================================================

def check_login():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if st.session_state.logged_in:
        return True

    set_sidebar_visibility(False)
        
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 SportsPredict Pro")
        
        tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
        
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Usuario")
                password = st.text_input("Contraseña", type="password")
                submit_login = st.form_submit_button("Ingresar")
                
                if submit_login:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user.id
                        st.session_state.user_tier = user.plan
                        st.session_state.user_role = getattr(user, "role", "USER")
                        st.success(f"Bienvenido de nuevo, {username}!")
                        st.rerun()
                    else:
                        st.error("Credenciales inválidas")

        with tab2:
            with st.form("register_form"):
                new_username = st.text_input("Nuevo Usuario")
                new_password = st.text_input("Contraseña", type="password")
                plan_choice = st.selectbox("Plan Inicial", ["free", "pro", "elite"])
                submit_register = st.form_submit_button("Registrarse")
                
                if submit_register:
                    try:
                        new_user = create_user(new_username, new_password, plan_choice, "USER")
                        st.success("Usuario creado exitosamente. Por favor, inicia sesión.")
                    except Exception as e:
                        st.error(f"Error creando usuario (puede que ya exista): {e}")

    return False

def logout():
    """Cierra la sesión actual y limpia el estado relacionado al usuario."""
    keys_to_clear = [
        'logged_in',
        'user_id',
        'user_tier',
        'user_role',
        'favorite_teams',
        'selected_competitions',
        'api_matches',
        'last_api_date'
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def set_sidebar_visibility(visible: bool):
    """Muestra u oculta el sidebar nativo de Streamlit."""
    display = "block" if visible else "none"
    visibility = "visible" if visible else "hidden"
    width = "21rem" if visible else "0rem"
    margin_left = "0" if not visible else ""

    components.html(
        f"""
        <script>
        const doc = window.parent.document;
        const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
        const openBtn = doc.querySelector('button[data-testid="collapsedControl"]');
        const allButtons = Array.from(doc.querySelectorAll('button'));
        const toggleButtons = allButtons.filter(btn => {{
            const label = btn.getAttribute('aria-label') || '';
            return label.includes('sidebar') || label.includes('Sidebar');
        }});
        const main = doc.querySelector('section[data-testid="stMain"]');

        if (sidebar) {{
            sidebar.style.display = '{display}';
            sidebar.style.visibility = '{visibility}';
            sidebar.style.minWidth = '{width}';
            sidebar.style.maxWidth = '{width}';
            sidebar.style.width = '{width}';
        }}

        if (openBtn) {{
            openBtn.style.display = '{display}';
            openBtn.style.visibility = '{visibility}';
        }}

        toggleButtons.forEach(btn => {{
            btn.style.display = '{display}';
            btn.style.visibility = '{visibility}';
        }});

        if (main && '{margin_left}') {{
            main.style.marginLeft = '{margin_left}';
        }}
        </script>
        """,
        height=0,
        width=0,
    )

def page_create_prediction():
    """Página para crear predicciones manuales"""
    st.title("➕ Crear Predicción Manual")
    st.markdown("Ingresa un partido para que la Inteligencia Artificial analice quién ganará basándose en su historial estadístico.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        sport = st.selectbox("Selecciona el Deporte", ["Futbol", "NBA", "MLB"])
        
    st.divider()
    
    teams = get_teams_by_sport(sport)
    
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        home_team = st.selectbox("Equipo Local" if sport != 'MLB' else "Equipo 1", teams, key="home_select")
        pitcher1 = None
        if sport == 'MLB':
            pitchers = get_pitchers()
            pitcher1 = st.selectbox("Lanzador Abridor 1", pitchers, key="p1_select")
            
    with col3:
        # Default al segundo equipo para evitar que local y visitante sean el mismo al inicio
        default_away = teams[1] if len(teams) > 1 else teams[0]
        away_team = st.selectbox("Equipo Visitante" if sport != 'MLB' else "Equipo 2", teams, index=teams.index(default_away) if default_away in teams else 0, key="away_select")
        pitcher2 = None
        if sport == 'MLB':
            pitcher2 = st.selectbox("Lanzador Abridor 2", pitchers, key="p2_select")
            
    with col2:
        st.markdown("<h2 style='text-align: center; margin-top: 30px;'>VS</h2>", unsafe_allow_html=True)
        
    date_match = st.date_input("Fecha del Partido")
    
    if st.button("🔮 Generar Predicción IA", type="primary", use_container_width=True):
        if home_team == away_team:
            st.error("El equipo local y visitante no pueden ser el mismo.")
            return
            
        with st.spinner("Analizando historial y ejecutando modelos..."):
            try:
                if sport == 'Futbol':
                    probs = predict_football(home_team, away_team)
                    # Probabilidades principales: local, empate, visitante
                    main_probs = {k: probs[k] for k in ['visitante', 'empate', 'local']}
                    labels = ['Visitante', 'Empate', 'Local']
                    values = [main_probs['visitante']*100, main_probs['empate']*100, main_probs['local']*100]
                    pred_label = max(main_probs, key=main_probs.get)
                    
                    over_str = "MÁS de 2.5" if probs.get('over25', 0) > 0.5 else "MENOS de 2.5"
                    btts_str = "SÍ" if probs.get('btts', 0) > 0.5 else "NO"
                    pred_label_db = f"{pred_label.upper()} | Over2.5: {over_str} ({probs.get('over25',0)*100:.1f}%) | BTTS: {btts_str} ({probs.get('btts',0)*100:.1f}%)"
                elif sport == 'NBA':
                    probs = predict_nba(home_team, away_team)
                    labels = ['Visitante', 'Local']
                    values = [probs['visitante']*100, probs['local']*100]
                    pred_label = max(probs, key=probs.get)
                elif sport == 'MLB':
                    probs = predict_mlb(home_team, away_team, pitcher1, pitcher2)
                    labels = ['Equipo 2', 'Equipo 1']
                    values = [probs['visitante']*100, probs['local']*100]
                    pred_label = max(probs, key=probs.get)
                    pred_label_db = pred_label.upper()
                    
                st.success(f"¡Predicción generada! El modelo se inclina por: **{pred_label.upper()}**")
                if sport == 'Futbol':
                    st.info(f"⚽ **Goles:** {over_str} ({probs.get('over25',0)*100:.1f}%) | **Ambos Anotan:** {btts_str} ({probs.get('btts',0)*100:.1f}%)")
                
                # Visualización
                fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.5, marker_colors=['#f5576c', '#aaaaaa', '#667eea'])])
                fig.update_layout(title_text="Probabilidades de Victoria")
                st.plotly_chart(fig, use_container_width=True)
                
                # Guardar el partido futuro
                save_future_match(sport, date_match.strftime("%Y-%m-%d"), home_team, away_team, pitcher1, pitcher2, probs, pred_label_db)
                
                # Guardar automáticamente la predicción en el perfil si es usuario Elite
                if st.session_state.user_tier == 'elite':
                    try:
                        prisma_save_prediction(
                            user_id=st.session_state.user_id,
                            match_id=int(time.time()), # Generar un ID dummy único para el partido
                            predicted_winner=pred_label_db,
                            confidence=max(values)/100.0,
                            is_manual=True,
                            ai_data=json.dumps({"prediccion_ia": pred_label, "probs": probs})
                        )
                        st.success("🌟 (Elite) Predicción guardada en tu perfil personal automáticamente.")
                    except Exception as e:
                        st.warning(f"No se pudo guardar en el perfil Elite: {e}")

                st.info("Este partido ha sido guardado y aparecerá en el Dashboard.")
            except Exception as e:
                st.error(f"Error generando predicción: {str(e)}")

def main():
    """Función principal"""
    
    if not check_login():
        return

    set_sidebar_visibility(True)

    # Sidebar
    with st.sidebar:
        st.title("⚽ SportsPredict Pro")
        st.markdown("---")

        # Información del usuario
        user_id = st.session_state.user_id or ""
        st.write(f"**Usuario ID:** `{user_id[:12]}...`")
        st.write(f"**Plan:** `{st.session_state.user_tier.upper()}`")
        st.write(f"**Rol:** `{st.session_state.user_role.upper()}`")
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            logout()
        st.divider()

    # Menú de navegación moderno
    pages = {
        "Navegación Principal": [
            st.Page(page_dashboard, title="Dashboard", icon="🏠"),
            st.Page(page_create_prediction, title="Crear Predicción", icon="➕"),
            st.Page(page_my_predictions, title="Mis Predicciones", icon="📊"),
            st.Page(page_ai_predictions, title="Predicciones IA", icon="🤖"),
            st.Page(page_competitions, title="Competencias", icon="🏆"),
            st.Page(page_statistics, title="Estadísticas", icon="📈"),
            st.Page(page_alerts, title="Alertas", icon="🔔"),
            st.Page(page_premium, title="Premium", icon="💎")
        ]
    }

    pg = st.navigation(pages)

    # Información adicional y botón de cerrar sesión al final del sidebar
    with st.sidebar:
        st.divider()
        st.write("### 📱 Información")
        st.info("""
        **SportsPredict Pro v1.0**

        Plataforma de predicciones deportivas con IA

        🔗 [Sitio Web](https://example.com)
        📧 [Contacto](mailto:info@example.com)
        """)

    # Renderizar página seleccionada nativamente
    pg.run()

if __name__ == "__main__":
    main()
