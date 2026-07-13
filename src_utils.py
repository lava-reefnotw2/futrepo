"""
Utilidades para la plataforma de predicciones deportivas
"""

import json
import hashlib
import hmac
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from enum import Enum

# ============================================================================
# ENUMERACIONES
# ============================================================================

class SubscriptionTier(str, Enum):
    """Niveles de suscripción"""
    FREE = "free"
    PRO = "pro"
    ELITE = "elite"

class PredictionStatus(str, Enum):
    """Estados de una predicción"""
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    DRAW = "draw"
    CANCELLED = "cancelled"

class BetType(str, Enum):
    """Tipos de apuestas"""
    ONE_X_TWO = "1x2"
    OVER_UNDER = "over_under"
    ASIAN_HANDICAP = "asian_handicap"
    BOTH_TEAMS_TO_SCORE = "btts"
    CORRECT_SCORE = "correct_score"

class SportType(str, Enum):
    """Tipos de deportes soportados"""
    FOOTBALL = "football"
    BASKETBALL = "basketball"
    TENNIS = "tennis"
    BASEBALL = "baseball"

# ============================================================================
# FUNCIONES DE VALIDACIÓN
# ============================================================================

def validate_email(email: str) -> bool:
    """Valida formato de email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_username(username: str) -> bool:
    """Valida formato de username"""
    return 3 <= len(username) <= 50 and username.isalnum()

def validate_confidence(confidence: float) -> bool:
    """Valida que la confianza esté entre 0 y 1"""
    return 0.0 <= confidence <= 1.0

def validate_prediction_scores(home: int, away: int) -> bool:
    """Valida que los scores sean válidos"""
    return isinstance(home, int) and isinstance(away, int) and home >= 0 and away >= 0

def validate_bet_amount(amount: float) -> bool:
    """Valida que el monto de la apuesta sea válido"""
    return isinstance(amount, (int, float)) and amount > 0

# ============================================================================
# FUNCIONES DE CÁLCULO
# ============================================================================

def calculate_accuracy(correct_predictions: int, total_predictions: int) -> float:
    """Calcula el porcentaje de precisión"""
    if total_predictions == 0:
        return 0.0
    return (correct_predictions / total_predictions) * 100

def calculate_expected_value(odds: float, probability: float) -> float:
    """Calcula el valor esperado de una apuesta"""
    return (odds * probability) - 1

def calculate_kelly_criterion(odds: float, probability: float) -> float:
    """
    Calcula el Kelly Criterion (fracción óptima a apostar)
    Fórmula: f = (bp - q) / b
    donde: b = odds - 1, p = probability, q = 1 - p
    """
    if probability <= 0 or probability >= 1:
        return 0.0

    b = odds - 1
    p = probability
    q = 1 - p

    return (b * p - q) / b

def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """Calcula el ratio de Sharpe de una serie de retornos"""
    if len(returns) < 2:
        return 0.0

    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate

    if np.std(excess_returns) == 0:
        return 0.0

    return np.mean(excess_returns) / np.std(excess_returns)

def calculate_rank_change(current_rank: int, previous_rank: int) -> int:
    """Calcula el cambio de posición en el ranking"""
    return previous_rank - current_rank

# ============================================================================
# FUNCIONES DE ANÁLISIS DE PREDICCIONES
# ============================================================================

def analyze_prediction_confidence(prediction_data: Dict) -> Dict:
    """
    Analiza la confianza de una predicción basada en múltiples factores

    Args:
        prediction_data: Datos de la predicción con factores

    Returns:
        Dict con análisis de confianza
    """
    factors = prediction_data.get('factors', {})

    weights = {
        'form': 0.25,
        'head_to_head': 0.20,
        'team_strength': 0.20,
        'injuries': 0.15,
        'weather': 0.10,
        'home_advantage': 0.10
    }

    total_confidence = 0.0
    analyzed_factors = {}

    for factor, weight in weights.items():
        factor_value = factors.get(factor, 0.5)
        weighted_value = factor_value * weight
        total_confidence += weighted_value
        analyzed_factors[factor] = {
            'value': factor_value,
            'weight': weight,
            'contribution': weighted_value
        }

    return {
        'overall_confidence': min(total_confidence, 1.0),
        'factor_analysis': analyzed_factors,
        'recommendation': get_confidence_recommendation(total_confidence)
    }

def get_confidence_recommendation(confidence: float) -> str:
    """Obtiene recomendación basada en nivel de confianza"""
    if confidence >= 0.85:
        return "Muy Alta - Apuesta segura"
    elif confidence >= 0.70:
        return "Alta - Recomendado"
    elif confidence >= 0.55:
        return "Media - Considerar cuidadosamente"
    elif confidence >= 0.40:
        return "Baja - Evitar"
    else:
        return "Muy Baja - No recomendado"

def compare_odds(actual_probability: float, offered_odds: float) -> Dict:
    """
    Compara probabilidad actual con odds ofrecidas
    Identifica value bets
    """
    implied_probability = 1 / offered_odds
    ev = calculate_expected_value(offered_odds, actual_probability)

    return {
        'actual_probability': actual_probability,
        'implied_probability': implied_probability,
        'expected_value': ev,
        'is_value_bet': ev > 0,
        'advantage': actual_probability - implied_probability
    }

# ============================================================================
# FUNCIONES DE FORMATO Y CONVERSIÓN
# ============================================================================

def format_currency(amount: float, currency: str = "USD") -> str:
    """Formatea cantidad como moneda"""
    symbols = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'MXN': '$',
        'ARS': '$'
    }
    symbol = symbols.get(currency, '$')
    return f"{symbol}{amount:,.2f}"

def format_percentage(value: float, decimals: int = 2) -> str:
    """Formatea valor como porcentaje"""
    return f"{value * 100:.{decimals}f}%"

def format_date(date: datetime, format_str: str = "%d/%m/%Y %H:%M") -> str:
    """Formatea fecha"""
    return date.strftime(format_str)

def format_odds(odds: float, format_type: str = "decimal") -> str:
    """
    Formatea odds en diferentes formatos

    Soporta:
    - decimal: 2.50
    - fractional: 3/2
    - american: +250 o -250
    """
    if format_type == "decimal":
        return f"{odds:.2f}"
    elif format_type == "fractional":
        numerator = int((odds - 1) * 100)
        return f"{numerator}/100"
    elif format_type == "american":
        if odds >= 2:
            return f"+{int((odds - 1) * 100)}"
        else:
            return f"{int(-100 / (odds - 1))}"
    return f"{odds:.2f}"

def format_score(home: int, away: int) -> str:
    """Formatea resultado de partido"""
    return f"{home}-{away}"

def time_until_match(match_date: datetime) -> str:
    """Calcula tiempo restante hasta el partido"""
    now = datetime.now()
    delta = match_date - now

    if delta.days > 0:
        return f"En {delta.days} días"
    elif delta.seconds > 3600:
        hours = delta.seconds // 3600
        return f"En {hours} horas"
    elif delta.seconds > 60:
        minutes = delta.seconds // 60
        return f"En {minutes} minutos"
    else:
        return "En vivo"

# ============================================================================
# FUNCIONES DE SEGURIDAD
# ============================================================================

def hash_password(password: str, salt: str = "") -> str:
    """Hash seguro de contraseña"""
    if not salt:
        salt = hashlib.sha256(str(datetime.now()).encode()).hexdigest()

    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt.encode(),
        100000
    ).hex()

def generate_api_key() -> str:
    """Genera una API key aleatoria"""
    import secrets
    return secrets.token_urlsafe(32)

def verify_signature(message: str, signature: str, secret: str) -> bool:
    """Verifica firma HMAC (para webhooks)"""
    expected_signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)

def encode_token(data: Dict, secret: str) -> str:
    """Codifica datos en un token"""
    json_data = json.dumps(data)
    encoded = base64.b64encode(json_data.encode()).decode()
    signature = hashlib.sha256(f"{encoded}{secret}".encode()).hexdigest()
    return f"{encoded}.{signature}"

def decode_token(token: str, secret: str) -> Optional[Dict]:
    """Decodifica un token"""
    try:
        encoded, signature = token.split('.')
        expected_sig = hashlib.sha256(f"{encoded}{secret}".encode()).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        json_data = base64.b64decode(encoded).decode()
        return json.loads(json_data)
    except:
        return None

# ============================================================================
# FUNCIONES DE ESTADÍSTICAS
# ============================================================================

def calculate_statistics(predictions: List[Dict]) -> Dict:
    """Calcula estadísticas generales de predicciones"""
    if not predictions:
        return {
            'total': 0,
            'won': 0,
            'lost': 0,
            'draw': 0,
            'accuracy': 0,
            'average_confidence': 0,
            'total_earnings': 0
        }

    df = pd.DataFrame(predictions)

    total = len(df)
    won = len(df[df['prediction_status'] == PredictionStatus.WON.value])
    lost = len(df[df['prediction_status'] == PredictionStatus.LOST.value])
    draw = len(df[df['prediction_status'] == PredictionStatus.DRAW.value])

    accuracy = (won / total * 100) if total > 0 else 0
    avg_confidence = df['confidence_level'].mean() if 'confidence_level' in df.columns else 0
    total_earnings = df['payout_amount'].sum() if 'payout_amount' in df.columns else 0

    return {
        'total': int(total),
        'won': int(won),
        'lost': int(lost),
        'draw': int(draw),
        'accuracy': float(accuracy),
        'average_confidence': float(avg_confidence),
        'total_earnings': float(total_earnings),
        'win_rate': float(won / total * 100) if total > 0 else 0
    }

def calculate_monthly_stats(predictions: List[Dict]) -> pd.DataFrame:
    """Calcula estadísticas mensuales"""
    df = pd.DataFrame(predictions)

    if df.empty:
        return pd.DataFrame()

    df['created_at'] = pd.to_datetime(df['created_at'])
    df['month'] = df['created_at'].dt.to_period('M')

    monthly = df.groupby('month').agg({
        'id': 'count',
        'confidence_level': 'mean',
        'prediction_status': lambda x: (x == PredictionStatus.WON.value).sum() / len(x) * 100
    }).rename(columns={
        'id': 'total_predictions',
        'confidence_level': 'avg_confidence',
        'prediction_status': 'accuracy'
    })

    return monthly

def get_best_performing_sport(predictions: List[Dict]) -> Dict:
    """Identifica el deporte con mejor desempeño"""
    df = pd.DataFrame(predictions)

    if df.empty or 'sport_type' not in df.columns:
        return {'sport': 'N/A', 'accuracy': 0}

    sport_accuracy = df.groupby('sport_type').apply(
        lambda x: (x['prediction_status'] == PredictionStatus.WON.value).sum() / len(x) * 100
    ).sort_values(ascending=False)

    if len(sport_accuracy) == 0:
        return {'sport': 'N/A', 'accuracy': 0}

    return {
        'sport': sport_accuracy.index[0],
        'accuracy': float(sport_accuracy.iloc[0])
    }

# ============================================================================
# FUNCIONES DE RECOMENDACIONES
# ============================================================================

def get_betting_recommendations(user_stats: Dict) -> List[str]:
    """Genera recomendaciones basadas en estadísticas del usuario"""
    recommendations = []

    accuracy = user_stats.get('accuracy', 0)
    confidence = user_stats.get('average_confidence', 0)

    if accuracy < 50:
        recommendations.append("Tu precisión está por debajo del 50%. Considera revisar tu estrategia.")

    if accuracy > 70:
        recommendations.append("¡Excelente desempeño! Tu precisión es superior al 70%.")

    if confidence < 0.5:
        recommendations.append("Aumenta tu confianza cuando estés seguro de una predicción.")

    if user_stats.get('total', 0) < 10:
        recommendations.append("Realiza más predicciones para obtener mejores estadísticas.")

    return recommendations if recommendations else ["Continúa con tu estrategia actual."]

# ============================================================================
# FUNCIONES DE UTILIDAD GENERAL
# ============================================================================

def get_sport_icon(sport: str) -> str:
    """Retorna emoji para cada deporte"""
    icons = {
        'football': '⚽',
        'basketball': '🏀',
        'tennis': '🎾',
        'baseball': '⚾',
        'hockey': '🏒',
        'american_football': '🏈'
    }
    return icons.get(sport, '🏆')

def get_status_emoji(status: str) -> str:
    """Retorna emoji para estado de predicción"""
    emojis = {
        'pending': '⏳',
        'won': '✅',
        'lost': '❌',
        'draw': '🔄',
        'cancelled': '⛔'
    }
    return emojis.get(status, '❓')

def get_tier_info(tier: str) -> Dict:
    """Obtiene información del plan de suscripción"""
    tiers = {
        'free': {
            'name': 'Free',
            'price': 'Gratis',
            'max_predictions_month': 50,
            'features': ['Predicciones básicas', 'Competencias gratuitas', 'Estadísticas básicas']
        },
        'pro': {
            'name': 'Pro',
            'price': '$4.99/mes',
            'max_predictions_month': 500,
            'features': ['Predicciones avanzadas', 'Análisis detallados', 'Reportes PDF', 'Sin límite de alertas']
        },
        'elite': {
            'name': 'Elite',
            'price': '$9.99/mes',
            'max_predictions_month': float('inf'),
            'features': ['Análisis en tiempo real', 'Consulta con expertos', 'Datos históricos completos', 'Prioridad total']
        }
    }
    return tiers.get(tier, tiers['free'])

def truncate_text(text: str, max_length: int = 100) -> str:
    """Trunca texto con puntos suspensivos"""
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text

def paginate_results(results: List, page: int = 1, per_page: int = 10) -> Tuple[List, Dict]:
    """Pagina resultados"""
    total = len(results)
    total_pages = (total + per_page - 1) // per_page

    start = (page - 1) * per_page
    end = start + per_page

    paginated = results[start:end]

    pagination_info = {
        'current_page': page,
        'total_pages': total_pages,
        'total_items': total,
        'items_per_page': per_page,
        'has_next': page < total_pages,
        'has_prev': page > 1
    }

    return paginated, pagination_info

if __name__ == "__main__":
    # Pruebas rápidas
    print("Validaciones:")
    print(f"Email válido: {validate_email('test@example.com')}")
    print(f"Username válido: {validate_username('testuser')}")
    print(f"Confianza válida: {validate_confidence(0.75)}")

    print("\nCálculos:")
    print(f"Precisión: {calculate_accuracy(75, 100)}%")
    print(f"Kelly Criterion: {calculate_kelly_criterion(2.5, 0.55):.4f}")
    print(f"Sharpe Ratio: {calculate_sharpe_ratio([0.01, 0.02, -0.01, 0.03]):.4f}")

    print("\nFormatos:")
    print(f"Moneda: {format_currency(1000.50)}")
    print(f"Porcentaje: {format_percentage(0.7525)}")
    print(f"Odds decimal: {format_odds(2.50)}")
    print(f"Odds americana: {format_odds(2.50, 'american')}")
