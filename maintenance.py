"""
📋 MANTENIMIENTO DE TABLAS - Backend
Gestión de CRUD completo para todas las tablas de la base de datos
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import streamlit as st
from supabase import create_client, Client
import json

# ============================================================================
# CLASE MANAGER DE TABLAS
# ============================================================================

class TableManager:
    """
    Gestor centralizado para todas las operaciones CRUD de la base de datos.
    Proporciona métodos para crear, leer, actualizar y eliminar registros
    en cualquier tabla.
    """

    def __init__(self, supabase_client: Client):
        self.db = supabase_client

    # ========== USUARIOS ==========

    def create_user(self, email: str, username: str, full_name: str = None) -> bool:
        """Crea un nuevo usuario"""
        try:
            data = {
                'email': email,
                'username': username,
                'full_name': full_name,
                'subscription_tier': 'free',
                'created_at': datetime.now().isoformat()
            }
            self.db.table('users').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error creando usuario: {e}")
            return False

    def get_user(self, user_id: str) -> Optional[Dict]:
        """Obtiene información del usuario"""
        try:
            response = self.db.table('users').select('*').eq('id', user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Error obteniendo usuario: {e}")
            return None

    def update_user(self, user_id: str, updates: Dict) -> bool:
        """Actualiza datos del usuario"""
        try:
            updates['updated_at'] = datetime.now().isoformat()
            self.db.table('users').update(updates).eq('id', user_id).execute()
            return True
        except Exception as e:
            st.error(f"Error actualizando usuario: {e}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """Elimina un usuario"""
        try:
            self.db.table('users').delete().eq('id', user_id).execute()
            return True
        except Exception as e:
            st.error(f"Error eliminando usuario: {e}")
            return False

    def get_all_users(self) -> List[Dict]:
        """Obtiene todos los usuarios"""
        try:
            response = self.db.table('users').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo usuarios: {e}")
            return []

    # ========== EQUIPOS ==========

    def create_team(self, name: str, country: str = None, sport_type: str = 'football') -> bool:
        """Crea un nuevo equipo"""
        try:
            data = {
                'name': name,
                'country': country,
                'sport_type': sport_type,
                'created_at': datetime.now().isoformat()
            }
            self.db.table('teams').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error creando equipo: {e}")
            return False

    def get_team(self, team_id: str) -> Optional[Dict]:
        """Obtiene información del equipo"""
        try:
            response = self.db.table('teams').select('*').eq('id', team_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Error obteniendo equipo: {e}")
            return None

    def get_teams_by_sport(self, sport_type: str) -> List[Dict]:
        """Obtiene equipos por deporte"""
        try:
            response = self.db.table('teams').select('*').eq('sport_type', sport_type).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo equipos: {e}")
            return []

    def update_team(self, team_id: str, updates: Dict) -> bool:
        """Actualiza datos del equipo"""
        try:
            updates['updated_at'] = datetime.now().isoformat()
            self.db.table('teams').update(updates).eq('id', team_id).execute()
            return True
        except Exception as e:
            st.error(f"Error actualizando equipo: {e}")
            return False

    def get_all_teams(self) -> List[Dict]:
        """Obtiene todos los equipos"""
        try:
            response = self.db.table('teams').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo equipos: {e}")
            return []

    # ========== PARTIDOS ==========

    def create_match(self, home_team_id: str, away_team_id: str, match_date: datetime,
                     league: str = None, sport_type: str = 'football') -> bool:
        """Crea un nuevo partido"""
        try:
            data = {
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'match_date': match_date.isoformat(),
                'league': league,
                'sport_type': sport_type,
                'status': 'scheduled',
                'created_at': datetime.now().isoformat()
            }
            self.db.table('matches').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error creando partido: {e}")
            return False

    def get_match(self, match_id: str) -> Optional[Dict]:
        """Obtiene información del partido"""
        try:
            response = self.db.table('matches').select('*').eq('id', match_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Error obteniendo partido: {e}")
            return None

    def update_match(self, match_id: str, updates: Dict) -> bool:
        """Actualiza datos del partido"""
        try:
            updates['updated_at'] = datetime.now().isoformat()
            self.db.table('matches').update(updates).eq('id', match_id).execute()
            return True
        except Exception as e:
            st.error(f"Error actualizando partido: {e}")
            return False

    def get_upcoming_matches(self, days: int = 7) -> List[Dict]:
        """Obtiene partidos próximos"""
        try:
            from_date = datetime.now().isoformat()
            to_date = (datetime.now() + timedelta(days=days)).isoformat()
            response = self.db.table('matches').select('*').gte('match_date', from_date).lte('match_date', to_date).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo partidos: {e}")
            return []

    def get_finished_matches(self) -> List[Dict]:
        """Obtiene partidos finalizados"""
        try:
            response = self.db.table('matches').select('*').eq('status', 'finished').execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo partidos finalizados: {e}")
            return []

    # ========== PREDICCIONES DE USUARIOS ==========

    def create_prediction(self, user_id: str, match_id: str, home_score: int,
                         away_score: int, confidence: float) -> bool:
        """Crea una nueva predicción"""
        try:
            data = {
                'user_id': user_id,
                'match_id': match_id,
                'predicted_home_score': home_score,
                'predicted_away_score': away_score,
                'confidence_level': confidence,
                'prediction_status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            self.db.table('user_predictions').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error creando predicción: {e}")
            return False

    def get_user_predictions(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Obtiene predicciones del usuario"""
        try:
            response = self.db.table('user_predictions').select('*').eq('user_id', user_id).limit(limit).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo predicciones: {e}")
            return []

    def update_prediction_status(self, prediction_id: str, status: str, points: int = 0) -> bool:
        """Actualiza estado de predicción después del partido"""
        try:
            data = {
                'prediction_status': status,
                'points_earned': points,
                'updated_at': datetime.now().isoformat()
            }
            self.db.table('user_predictions').update(data).eq('id', prediction_id).execute()
            return True
        except Exception as e:
            st.error(f"Error actualizando predicción: {e}")
            return False

    # ========== PREDICCIONES IA ==========

    def create_ai_prediction(self, match_id: str, winner: str, home_score: float,
                            away_score: float, confidence: float, analysis: str = None) -> bool:
        """Crea una predicción de IA"""
        try:
            data = {
                'match_id': match_id,
                'predicted_winner': winner,
                'predicted_home_score': home_score,
                'predicted_away_score': away_score,
                'ai_confidence': confidence,
                'analysis_text': analysis,
                'created_at': datetime.now().isoformat()
            }
            self.db.table('ai_predictions').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error creando predicción IA: {e}")
            return False

    def get_ai_prediction(self, match_id: str) -> Optional[Dict]:
        """Obtiene predicción IA de un partido"""
        try:
            response = self.db.table('ai_predictions').select('*').eq('match_id', match_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Error obteniendo predicción IA: {e}")
            return None

    # ========== COMPETENCIAS ==========

    def create_competition(self, name: str, description: str = None,
                          start_date: datetime = None, end_date: datetime = None,
                          prize_pool: float = 0) -> bool:
        """Crea una nueva competencia"""
        try:
            data = {
                'name': name,
                'description': description,
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'prize_pool': prize_pool,
                'status': 'active',
                'created_at': datetime.now().isoformat()
            }
            self.db.table('competitions').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error creando competencia: {e}")
            return False

    def get_active_competitions(self) -> List[Dict]:
        """Obtiene competencias activas"""
        try:
            response = self.db.table('competitions').select('*').eq('status', 'active').execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo competencias: {e}")
            return []

    def add_competitor(self, competition_id: str, user_id: str) -> bool:
        """Agrega un participante a una competencia"""
        try:
            data = {
                'competition_id': competition_id,
                'user_id': user_id,
                'score': 0,
                'joined_at': datetime.now().isoformat()
            }
            self.db.table('competition_participants').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error agregando participante: {e}")
            return False

    def get_competition_ranking(self, competition_id: str) -> List[Dict]:
        """Obtiene ranking de una competencia"""
        try:
            response = self.db.table('competition_participants').select(
                '*, users(username)'
            ).eq('competition_id', competition_id).order('score', ascending=False).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo ranking: {e}")
            return []

    # ========== APUESTAS ==========

    def create_bet(self, user_id: str, match_id: str, amount: float,
                   bet_type: str, selection: str = None, odds: float = 1.0) -> bool:
        """Crea una nueva apuesta"""
        try:
            data = {
                'user_id': user_id,
                'match_id': match_id,
                'amount': amount,
                'bet_type': bet_type,
                'selection': selection,
                'odds': odds,
                'potential_payout': amount * odds,
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            self.db.table('bets').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error creando apuesta: {e}")
            return False

    def get_user_bets(self, user_id: str) -> List[Dict]:
        """Obtiene apuestas del usuario"""
        try:
            response = self.db.table('bets').select('*').eq('user_id', user_id).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo apuestas: {e}")
            return []

    def settle_bet(self, bet_id: str, status: str, payout: float = 0) -> bool:
        """Cierra una apuesta después del partido"""
        try:
            data = {
                'status': status,
                'actual_payout': payout,
                'settled_at': datetime.now().isoformat()
            }
            self.db.table('bets').update(data).eq('id', bet_id).execute()
            return True
        except Exception as e:
            st.error(f"Error cerrando apuesta: {e}")
            return False

    # ========== ALERTAS ==========

    def create_alert(self, user_id: str, alert_type: str, message: str,
                     match_id: str = None, priority: str = 'normal') -> bool:
        """Crea una nueva alerta"""
        try:
            data = {
                'user_id': user_id,
                'alert_type': alert_type,
                'message': message,
                'match_id': match_id,
                'priority': priority,
                'is_read': False,
                'created_at': datetime.now().isoformat()
            }
            self.db.table('alerts').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error creando alerta: {e}")
            return False

    def get_user_alerts(self, user_id: str, unread_only: bool = False) -> List[Dict]:
        """Obtiene alertas del usuario"""
        try:
            query = self.db.table('alerts').select('*').eq('user_id', user_id)
            if unread_only:
                query = query.eq('is_read', False)
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo alertas: {e}")
            return []

    def mark_alert_as_read(self, alert_id: str) -> bool:
        """Marca una alerta como leída"""
        try:
            data = {'is_read': True, 'read_at': datetime.now().isoformat()}
            self.db.table('alerts').update(data).eq('id', alert_id).execute()
            return True
        except Exception as e:
            st.error(f"Error marcando alerta: {e}")
            return False

    # ========== MÉTODOS GENERALES ==========

    def get_table_data(self, table_name: str, limit: int = 1000) -> List[Dict]:
        """Obtiene todos los datos de una tabla"""
        try:
            response = self.db.table(table_name).select('*').limit(limit).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error obteniendo datos de {table_name}: {e}")
            return []

    def get_table_count(self, table_name: str) -> int:
        """Obtiene la cantidad de registros en una tabla"""
        try:
            response = self.db.table(table_name).select('id', count='exact').execute()
            return len(response.data) if response.data else 0
        except Exception as e:
            st.error(f"Error contando registros: {e}")
            return 0

    def export_table_to_dataframe(self, table_name: str) -> pd.DataFrame:
        """Exporta tabla a DataFrame"""
        try:
            data = self.get_table_data(table_name)
            return pd.DataFrame(data) if data else pd.DataFrame()
        except Exception as e:
            st.error(f"Error exportando tabla: {e}")
            return pd.DataFrame()

    def get_database_stats(self) -> Dict:
        """Obtiene estadísticas generales de la BD"""
        try:
            stats = {
                'total_users': self.get_table_count('users'),
                'total_teams': self.get_table_count('teams'),
                'total_matches': self.get_table_count('matches'),
                'total_predictions': self.get_table_count('user_predictions'),
                'total_competitions': self.get_table_count('competitions'),
                'total_bets': self.get_table_count('bets'),
                'total_alerts': self.get_table_count('alerts'),
            }
            return stats
        except Exception as e:
            st.error(f"Error obteniendo estadísticas: {e}")
            return {}


# ============================================================================
# INTERFAZ DE ADMINISTRACIÓN
# ============================================================================

def show_table_manager_ui(supabase_client: Client):
    """Interfaz Streamlit para el gestor de tablas"""

    manager = TableManager(supabase_client)

    st.title("📋 Administración de Base de Datos")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Estadísticas", "👥 Usuarios", "⚽ Equipos", "🎯 Partidos"]
    )

    # TAB 1: ESTADÍSTICAS
    with tab1:
        st.subheader("Estadísticas de Base de Datos")

        stats = manager.get_database_stats()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Usuarios", stats.get('total_users', 0))
        with col2:
            st.metric("Total Equipos", stats.get('total_teams', 0))
        with col3:
            st.metric("Total Partidos", stats.get('total_matches', 0))
        with col4:
            st.metric("Total Predicciones", stats.get('total_predictions', 0))

        col5, col6, col7 = st.columns(3)
        with col5:
            st.metric("Competencias", stats.get('total_competitions', 0))
        with col6:
            st.metric("Apuestas", stats.get('total_bets', 0))
        with col7:
            st.metric("Alertas", stats.get('total_alerts', 0))

    # TAB 2: USUARIOS
    with tab2:
        st.subheader("Gestión de Usuarios")

        subcol1, subcol2 = st.columns(2)

        with subcol1:
            st.write("**Crear Nuevo Usuario**")
            email = st.text_input("Email")
            username = st.text_input("Username")
            full_name = st.text_input("Nombre Completo")

            if st.button("Crear Usuario"):
                if manager.create_user(email, username, full_name):
                    st.success("✅ Usuario creado correctamente")
                else:
                    st.error("❌ Error creando usuario")

        with subcol2:
            st.write("**Listar Usuarios**")
            users = manager.get_all_users()
            if users:
                df_users = pd.DataFrame(users)
                st.dataframe(df_users[['id', 'email', 'username', 'subscription_tier', 'created_at']])
            else:
                st.info("No hay usuarios en la base de datos")

    # TAB 3: EQUIPOS
    with tab3:
        st.subheader("Gestión de Equipos")

        subcol1, subcol2 = st.columns(2)

        with subcol1:
            st.write("**Crear Nuevo Equipo**")
            team_name = st.text_input("Nombre del Equipo")
            team_country = st.text_input("País")
            team_sport = st.selectbox("Deporte", ["football", "basketball", "tennis", "baseball"])

            if st.button("Crear Equipo"):
                if manager.create_team(team_name, team_country, team_sport):
                    st.success("✅ Equipo creado correctamente")
                else:
                    st.error("❌ Error creando equipo")

        with subcol2:
            st.write("**Listar Equipos**")
            teams = manager.get_all_teams()
            if teams:
                df_teams = pd.DataFrame(teams)
                st.dataframe(df_teams[['id', 'name', 'country', 'sport_type']])
            else:
                st.info("No hay equipos en la base de datos")

    # TAB 4: PARTIDOS
    with tab4:
        st.subheader("Gestión de Partidos")

        st.write("**Próximos Partidos**")
        upcoming = manager.get_upcoming_matches(7)

        if upcoming:
            df_matches = pd.DataFrame(upcoming)
            st.dataframe(df_matches[['id', 'home_team_name', 'away_team_name', 'match_date', 'league', 'status']])
        else:
            st.info("No hay partidos próximos programados")

        st.write("**Partidos Finalizados**")
        finished = manager.get_finished_matches()

        if finished:
            df_finished = pd.DataFrame(finished)
            st.dataframe(df_finished[['id', 'home_team_name', 'away_team_name', 'home_score', 'away_score', 'league']])
        else:
            st.info("No hay partidos finalizados")


if __name__ == "__main__":
    from supabase import create_client

    # Ejemplo de uso
    supabase_url = "tu-url"
    supabase_key = "tu-key"

    supabase = create_client(supabase_url, supabase_key)
    show_table_manager_ui(supabase)
