"""
📊 ESTADÍSTICAS DESCRIPTIVAS - Cuadros y Gráficos Avanzados
Análisis visual para toma de decisiones
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from scipy import stats
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

# ============================================================================
# FUNCIONES DE ANÁLISIS ESTADÍSTICO
# ============================================================================

def calculate_descriptive_stats(data: List[float]) -> Dict:
    """Calcula estadísticas descriptivas básicas"""
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
        'q3': float(np.percentile(data_array, 75)),
        'iqr': float(np.percentile(data_array, 75) - np.percentile(data_array, 25)),
        'skewness': float(stats.skew(data_array)) if len(data_array) > 2 else 0,
        'kurtosis': float(stats.kurtosis(data_array)) if len(data_array) > 3 else 0
    }


def calculate_correlation_matrix(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    """Calcula matriz de correlación"""
    numeric_df = df[numeric_cols].select_dtypes(include=[np.number])
    return numeric_df.corr()


def perform_hypothesis_test(group1: List[float], group2: List[float]) -> Dict:
    """Realiza prueba t de Student independiente entre dos grupos"""
    if len(group1) < 2 or len(group2) < 2:
        return {'t_statistic': 0, 'p_value': 1, 'significant': False}

    t_stat, p_value = stats.ttest_ind(group1, group2)

    return {
        't_statistic': float(t_stat),
        'p_value': float(p_value),
        'significant': p_value < 0.05
    }

def perform_paired_ttest(group1: List[float], group2: List[float]) -> Dict:
    """Realiza prueba t de Student pareada (útil para comparar scores de CV de modelos)"""
    if len(group1) < 2 or len(group2) < 2 or len(group1) != len(group2):
        return {'t_statistic': 0, 'p_value': 1, 'significant': False}

    t_stat, p_value = stats.ttest_rel(group1, group2)

    return {
        't_statistic': float(t_stat),
        'p_value': float(p_value),
        'significant': p_value < 0.05
    }


# ============================================================================
# GENERADORES DE GRÁFICOS
# ============================================================================

class StatisticsVisualizer:
    """Genera visualizaciones estadísticas avanzadas"""

    @staticmethod
    def create_distribution_plot(data: List[float], title: str = "Distribución de Datos") -> go.Figure:
        """Crea gráfico de distribución (histograma + curva normal)"""
        df = pd.DataFrame({'value': data})

        fig = go.Figure()

        # Histograma
        fig.add_trace(go.Histogram(
            x=df['value'],
            name='Frecuencia',
            nbinsx=30,
            marker_color='rgba(102, 126, 234, 0.7)'
        ))

        # Curva normal teórica
        mu, sigma = np.mean(data), np.std(data)
        x = np.linspace(min(data), max(data), 100)
        y = stats.norm.pdf(x, mu, sigma)
        y_scaled = y * len(data) * (max(data) - min(data)) / 30

        fig.add_trace(go.Scatter(
            x=x, y=y_scaled,
            name='Distribución Normal',
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

    @staticmethod
    def create_boxplot(data: Dict[str, List[float]], title: str = "Comparación de Distribuciones") -> go.Figure:
        """Crea gráfico de caja (boxplot) para comparar distribuciones"""
        fig = go.Figure()

        for label, values in data.items():
            fig.add_trace(go.Box(
                y=values,
                name=label,
                boxmean='sd'
            ))

        fig.update_layout(
            title=title,
            yaxis_title="Valor",
            hovermode='y unified',
            height=400
        )

        return fig

    @staticmethod
    def create_correlation_heatmap(df: pd.DataFrame, numeric_cols: List[str], title: str = "Matriz de Correlación") -> go.Figure:
        """Crea mapa de calor de correlaciones"""
        corr_matrix = calculate_correlation_matrix(df, numeric_cols)

        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.columns,
            colorscale='RdBu',
            zmid=0,
            text=np.round(corr_matrix.values, 2),
            texttemplate='%{text:.2f}',
            textfont={"size": 10},
            colorbar=dict(title="Correlación")
        ))

        fig.update_layout(
            title=title,
            height=500,
            width=600
        )

        return fig

    @staticmethod
    def create_time_series_plot(dates: List[datetime], values: List[float],
                                title: str = "Serie Temporal") -> go.Figure:
        """Crea gráfico de serie temporal con tendencia"""
        df = pd.DataFrame({'date': dates, 'value': values})
        df = df.sort_values('date')

        fig = go.Figure()

        # Línea principal
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['value'],
            mode='lines+markers',
            name='Valor',
            line=dict(color='#667EEA', width=2),
            marker=dict(size=6)
        ))

        # Línea de tendencia (moving average)
        if len(df) > 7:
            df['ma_7'] = df['value'].rolling(window=7).mean()
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['ma_7'],
                mode='lines',
                name='Media Móvil (7 días)',
                line=dict(color='red', width=2, dash='dash')
            ))

        fig.update_layout(
            title=title,
            xaxis_title="Fecha",
            yaxis_title="Valor",
            hovermode='x unified',
            height=400
        )

        return fig

    @staticmethod
    def create_scatter_plot(x_data: List[float], y_data: List[float],
                           title: str = "Análisis de Relación",
                           x_label: str = "X", y_label: str = "Y") -> go.Figure:
        """Crea gráfico de dispersión con línea de regresión"""
        df = pd.DataFrame({'x': x_data, 'y': y_data})

        fig = px.scatter(df, x='x', y='y', title=title,
                         labels={'x': x_label, 'y': y_label})

        # Línea de regresión
        z = np.polyfit(x_data, y_data, 1)
        p = np.poly1d(z)
        x_line = np.linspace(min(x_data), max(x_data), 100)

        fig.add_trace(go.Scatter(
            x=x_line,
            y=p(x_line),
            mode='lines',
            name='Regresión Lineal',
            line=dict(color='red', width=2, dash='dash')
        ))

        fig.update_layout(height=400)

        return fig

    @staticmethod
    def create_comparison_bar_chart(categories: List[str], values: List[float],
                                    title: str = "Comparación") -> go.Figure:
        """Crea gráfico de barras para comparación"""
        fig = go.Figure()

        colors = ['#667EEA' if v >= np.mean(values) else '#FF6B6B' for v in values]

        fig.add_trace(go.Bar(
            x=categories,
            y=values,
            marker=dict(color=colors),
            text=np.round(values, 2),
            textposition='auto'
        ))

        fig.update_layout(
            title=title,
            yaxis_title="Valor",
            hovermode='x unified',
            height=400
        )

        return fig

    @staticmethod
    def create_violin_plot(data: Dict[str, List[float]], title: str = "Distribución Detallada") -> go.Figure:
        """Crea gráfico de violín para comparar distribuciones"""
        fig = go.Figure()

        for label, values in data.items():
            fig.add_trace(go.Violin(
                y=values,
                name=label,
                box_visible=True,
                meanline_visible=True
            ))

        fig.update_layout(
            title=title,
            yaxis_title="Valor",
            height=400
        )

        return fig

    @staticmethod
    def create_cumulative_distribution(data: List[float], title: str = "Distribución Acumulada") -> go.Figure:
        """Crea función de distribución acumulada"""
        sorted_data = np.sort(data)
        cumulative = np.arange(1, len(sorted_data) + 1) / len(sorted_data)

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=sorted_data,
            y=cumulative,
            mode='lines',
            name='CDF',
            line=dict(color='#667EEA', width=3)
        ))

        fig.update_layout(
            title=title,
            xaxis_title="Valor",
            yaxis_title="Probabilidad Acumulada",
            height=400
        )

        return fig


# ============================================================================
# TABLAS ESTADÍSTICAS
# ============================================================================

def create_descriptive_stats_table(predictions: List[Dict]) -> pd.DataFrame:
    """Crea tabla de estadísticas descriptivas"""
    if not predictions:
        return pd.DataFrame()

    df = pd.DataFrame(predictions)

    # Seleccionar columnas numéricas
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
            'Máx': round(col_stats.get('max', 0), 2),
            'Q1': round(col_stats.get('q1', 0), 2),
            'Q3': round(col_stats.get('q3', 0), 2),
        })

    return pd.DataFrame(stats_data)


def create_summary_statistics_table(user_stats: Dict) -> pd.DataFrame:
    """Crea tabla de resumen de estadísticas del usuario"""
    summary_data = {
        'Métrica': [
            'Total de Predicciones',
            'Predicciones Correctas',
            'Predicciones Incorrectas',
            'Tasa de Precisión (%)',
            'Confianza Promedio',
            'Ranking Global'
        ],
        'Valor': [
            user_stats.get('total_predictions', 0),
            user_stats.get('correct_predictions', 0),
            user_stats.get('total_predictions', 0) - user_stats.get('correct_predictions', 0),
            f"{user_stats.get('accuracy_rate', 0):.2f}%",
            f"{user_stats.get('avg_confidence', 0):.2f}",
            str(user_stats.get('rank', 'N/A'))
        ]
    }

    return pd.DataFrame(summary_data)


def create_performance_breakdown_table(predictions: List[Dict]) -> pd.DataFrame:
    """Crea tabla desglosando rendimiento por categoría"""
    if not predictions:
        return pd.DataFrame()

    df = pd.DataFrame(predictions)

    breakdown_data = []

    # Por estado de predicción
    if 'prediction_status' in df.columns:
        for status in df['prediction_status'].unique():
            status_data = df[df['prediction_status'] == status]
            breakdown_data.append({
                'Categoría': f'Status: {status}',
                'Cantidad': len(status_data),
                'Confianza Promedio': round(status_data['confidence_level'].mean(), 2) if 'confidence_level' in df.columns else 0
            })

    return pd.DataFrame(breakdown_data) if breakdown_data else pd.DataFrame()


# ============================================================================
# INTERFAZ DE STREAMLIT
# ============================================================================

def show_statistics_dashboard(user_stats: Dict, predictions: List[Dict]):
    """Muestra dashboard de estadísticas descriptivas"""

    st.title("📊 ESTADÍSTICAS DESCRIPTIVAS")

    # SECCIÓN 1: RESUMEN
    st.header("📈 Resumen General")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Predicciones",
            user_stats.get('total_predictions', 0),
            delta=f"+{user_stats.get('total_predictions', 0) % 10}"
        )

    with col2:
        st.metric(
            "Tasa de Precisión",
            f"{user_stats.get('accuracy_rate', 0):.1f}%",
            delta=f"+{user_stats.get('accuracy_rate', 0) - 55:.1f}%"
        )

    with col3:
        st.metric(
            "Confianza Promedio",
            f"{user_stats.get('avg_confidence', 0):.2f}",
            delta="+0.05"
        )

    with col4:
        st.metric(
            "Ranking",
            str(user_stats.get('rank', 'N/A')),
            delta="+5 posiciones"
        )

    st.divider()

    # SECCIÓN 2: TABLAS ESTADÍSTICAS
    st.header("📋 Tablas Estadísticas")

    tab1, tab2, tab3 = st.tabs(["Resumen", "Estadísticas Descriptivas", "Desglose de Rendimiento"])

    with tab1:
        st.subheader("Resumen de Estadísticas")
        summary_table = create_summary_statistics_table(user_stats)
        st.dataframe(summary_table, use_container_width=True)

    with tab2:
        st.subheader("Estadísticas Descriptivas de Predicciones")
        descriptive_table = create_descriptive_stats_table(predictions)
        if not descriptive_table.empty:
            st.dataframe(descriptive_table, use_container_width=True)
        else:
            st.info("No hay datos numéricos disponibles")

    with tab3:
        st.subheader("Desglose de Rendimiento")
        breakdown_table = create_performance_breakdown_table(predictions)
        if not breakdown_table.empty:
            st.dataframe(breakdown_table, use_container_width=True)
        else:
            st.info("No hay datos disponibles")

    st.divider()

    # SECCIÓN 3: GRÁFICOS
    st.header("📊 Visualizaciones")

    if predictions and len(predictions) > 0:
        df = pd.DataFrame(predictions)
        visualizer = StatisticsVisualizer()

        # Distribuciónde confianza
        if 'confidence_level' in df.columns:
            col1, col2 = st.columns(2)

            with col1:
                confidence_data = df['confidence_level'].dropna().tolist()
                fig_dist = visualizer.create_distribution_plot(
                    confidence_data,
                    "Distribución de Confianza"
                )
                st.plotly_chart(fig_dist, use_container_width=True)

            with col2:
                fig_cdf = visualizer.create_cumulative_distribution(
                    confidence_data,
                    "CDF de Confianza"
                )
                st.plotly_chart(fig_cdf, use_container_width=True)

        # Gráfico temporal
        if 'created_at' in df.columns:
            st.subheader("Evolución Temporal")

            df['created_at'] = pd.to_datetime(df['created_at'])
            df_sorted = df.sort_values('created_at')

            dates = df_sorted['created_at'].tolist()
            values = df_sorted.get('confidence_level', pd.Series(range(len(df_sorted)))).tolist()

            fig_time = visualizer.create_time_series_plot(
                dates, values,
                "Evolución de Confianza en el Tiempo"
            )
            st.plotly_chart(fig_time, use_container_width=True)

        # Comparación por status
        if 'prediction_status' in df.columns:
            st.subheader("Análisis por Status")

            status_counts = df['prediction_status'].value_counts()
            fig_status = visualizer.create_comparison_bar_chart(
                status_counts.index.tolist(),
                status_counts.values.tolist(),
                "Predicciones por Status"
            )
            st.plotly_chart(fig_status, use_container_width=True)

    else:
        st.info("No hay suficientes datos para mostrar gráficos avanzados")

    st.divider()

    # SECCIÓN 4: INSIGHTS
    st.header("💡 Insights")

    insights_text = f"""
    ### Análisis de Rendimiento

    Based on {user_stats.get('total_predictions', 0)} predicciones:

    - **Tasa de Precisión**: {user_stats.get('accuracy_rate', 0):.1f}%
      - {'✅ Excelente desempeño' if user_stats.get('accuracy_rate', 0) > 70 else '⚠️ Oportunidad de mejora' if user_stats.get('accuracy_rate', 0) > 55 else '❌ Bajo rendimiento'}

    - **Confianza Promedio**: {user_stats.get('avg_confidence', 0):.2f}
      - {'✅ Confianza bien calibrada' if user_stats.get('avg_confidence', 0) > 0.7 else '⚠️ Considera revisar confianza'}

    - **Ranking Global**: {user_stats.get('rank', 'N/A')}
      - Estás en el {'top 10%' if 'Top 10' in str(user_stats.get('rank', '')) else 'ranking competitivo'}

    ### Recomendaciones
    1. Analiza tus predicciones incorrectas para identificar patrones
    2. Aumenta confianza solo cuando tengas datos sólidos
    3. Diversifica predicciones entre diferentes deportes
    4. Revisa regularmente tu rendimiento
    """

    st.markdown(insights_text)


if __name__ == "__main__":
    # Datos de ejemplo
    sample_stats = {
        'total_predictions': 50,
        'correct_predictions': 35,
        'accuracy_rate': 70.0,
        'avg_confidence': 0.72,
        'rank': 'Top 15%'
    }

    sample_predictions = [
        {'match_id': f'00{i}', 'confidence_level': np.random.uniform(0.4, 0.95), 'prediction_status': np.random.choice(['won', 'lost'])}
        for i in range(50)
    ]

    show_statistics_dashboard(sample_stats, sample_predictions)
