import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import fastf1
from fastf1 import utils
import random

# Application Configuration
st.set_page_config(
    page_title="F1 Telemetry & Network IDS",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants & Mapping
YEARS = list(range(2026, 2017, -1))
SESSION_MAP = {
    "Practice 1 (FP1)": "FP1",
    "Practice 2 (FP2)": "FP2",
    "Practice 3 (FP3)": "FP3",
    "Qualifying (Q)": "Q",
    "Sprint Shootout (SQ)": "SQ",
    "Sprint (S)": "S",
    "Race (R)": "R"
}

def setup_environment() -> None:
    if not os.path.exists('cache'):
        os.makedirs('cache')
    fastf1.Cache.enable_cache('cache')

@st.cache_resource(show_spinner="Fetching F1 calendar...")
def get_event_schedule(year: int) -> list:
    try:
        schedule = fastf1.get_event_schedule(year)
        events = schedule[schedule['EventFormat'] != 'testing']
        return events['EventName'].tolist()
    except Exception:
        return []

@st.cache_resource(show_spinner="Downloading session data...")
def load_session_data(year: int, gp: str, session_type: str):
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=True, weather=False, messages=False)
    return session

@st.cache_data(show_spinner="Processing telemetry for selected drivers...")
def get_driver_lap(_session, cache_key: str, driver: str):
    lap = _session.laps.pick_driver(driver).pick_fastest()
    return lap

def format_lap_time(lap_time) -> str:
    if pd.isnull(lap_time):
        return "No Time"
    c = lap_time.components
    return f"{c.minutes}:{c.seconds:02d}.{c.milliseconds:03d}"

def extract_driver_color(session, driver_id: str, default_hex: str) -> str:
    try:
        color = session.get_driver(driver_id)['TeamColor']
        if pd.isna(color) or str(color).strip() == "":
            return default_hex
        return f"#{color}"
    except Exception:
        return default_hex

def render_telemetry_dashboard(lap1, lap2, driver1: str, driver2: str, c1: str, c2: str, gp: str, year: int) -> None:
    display_location = gp
    if year == 2026 and "Bahrain" in gp:
        display_location = f"{gp} (Sepang International Circuit, Malaysia)"
        
    st.title("COMPARATIVE PERFORMANCE ANALYSIS")
    
    st.markdown(f"**Event:** {display_location} | **Reference:** {driver1} | **Comparator:** {driver2}")
    st.divider()

    tel1 = lap1.get_telemetry().add_distance()
    tel2 = lap2.get_telemetry().add_distance()

    if driver1 == driver2:
        tel1['Delta'] = 0.0
    else:
        try:
            delta = utils.delta_time(lap1, lap2)
            
            delta_sec = delta.dt.total_seconds()
            
            if len(delta_sec) == len(tel1):
                tel1['Delta'] = delta_sec
            else:
                tel1['Delta'] = 0.0
        except Exception:
            tel1['Delta'] = 0.0

    tel_merged = pd.merge_asof(
        tel1[['Distance', 'X', 'Y', 'Time', 'Speed', 'nGear', 'Throttle', 'Brake']],
        tel2[['Distance', 'Speed', 'nGear', 'Throttle', 'Brake']],
        on='Distance',
        suffixes=(f'_{driver1}', f'_{driver2}')
    )
    
    # Tolerance filter: Driver must be at least 1 km/h faster to claim the micro-sector
    speed_diff = tel_merged[f'Speed_{driver1}'] - tel_merged[f'Speed_{driver2}']
    conditions = [
        speed_diff >= 1.0,
        speed_diff <= -1.0
    ]
    choices = [driver1, driver2]
    tel_merged['Fastest_Driver'] = np.select(conditions, choices, default="Equal")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric(f"{driver1} Lap Time", format_lap_time(lap1['LapTime']))
    with col2:
        st.metric(f"{driver2} Lap Time", format_lap_time(lap2['LapTime']))

    st.markdown("### Micro-Sector Dominance Map")
    
    color_map = {driver1: c1, driver2: c2, "Equal": "#555555"}
    
    fig_map = px.scatter(
        tel_merged, x="X", y="Y", color="Fastest_Driver",
        color_discrete_map=color_map,
        hover_data={
            "X": False, "Y": False, "Distance": ":.0f",
            f"Speed_{driver1}": True, f"Speed_{driver2}": True,
            "Fastest_Driver": True
        }
    )
    
    # Graphic override: Make points larger to form a continuous neon line
    fig_map.update_traces(marker=dict(size=8, opacity=0.9, line=dict(width=0)))
    
    fig_map.update_yaxes(scaleanchor="x", scaleratio=1)
    fig_map.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        )
    )
    st.plotly_chart(fig_map, use_container_width=True)

    st.markdown("### Telemetry Dynamics & Delta")

    fig_dynamics = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.5, 0.2, 0.3]
    )

    fig_dynamics.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Speed'], name=f'{driver1} Speed', line=dict(color=c1, width=2)), row=1, col=1)
    fig_dynamics.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Speed'], name=f'{driver2} Speed', line=dict(color=c2, width=2)), row=1, col=1)

    fig_dynamics.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Delta'], name='Delta Time (Ref: D1)', line=dict(color='#ffffff', width=1.5)), row=2, col=1)

    fig_dynamics.add_trace(go.Scatter(x=tel1['Distance'], y=tel1['Throttle'], name=f'{driver1} Throttle', line=dict(color=c1, width=1.5, dash='dot')), row=3, col=1)
    fig_dynamics.add_trace(go.Scatter(x=tel2['Distance'], y=tel2['Throttle'], name=f'{driver2} Throttle', line=dict(color=c2, width=1.5, dash='dot')), row=3, col=1)

    fig_dynamics.update_layout(
        hovermode='x unified',
        plot_bgcolor="rgba(0,0,0,0)",
        height=700,
        margin=dict(l=0, r=0, t=30, b=0)
    )
    
    fig_dynamics.update_yaxes(title_text="Speed (km/h)", row=1, col=1)
    fig_dynamics.update_yaxes(title_text="Delta (s)", row=2, col=1)
    fig_dynamics.update_yaxes(title_text="Throttle (%)", row=3, col=1)
    fig_dynamics.update_xaxes(title_text="Distance (m)", row=3, col=1)
    fig_dynamics.update_xaxes(showgrid=False)
    fig_dynamics.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.1)')

    st.plotly_chart(fig_dynamics, use_container_width=True)

def render_cyber_dashboard(lap1) -> None:
    st.title("SECURITY OPERATIONS CENTER (SOC) - LIVE CTF")
    st.markdown("Analyze the incoming telemetry stream. Detect anomalies injected via CAN bus spoofing or sensor failures.")
    st.divider()

    # Initialisation
    if 'cyber_scenario' not in st.session_state:
        st.session_state.cyber_scenario = random.choice(['Safe', 'Engine_Spoof', 'Brake_Failure', 'Gear_Drop'])
        st.session_state.diagnosis_submitted = False

    telemetry = lap1.get_telemetry()
    df_network = telemetry.copy()

    # Injection dynamique de l'anomalie 
    scenario = st.session_state.cyber_scenario
    injection_idx = int(len(df_network) * 0.6) # On injecte l'anomalie à 60% du tour
#mise en place de différent sénarios d'attaque pour le CTF
    if scenario == 'Engine_Spoof':
        # Le moteur s'emballe à 22 000 tours/min sur quelques paquets réseau
        df_network.loc[injection_idx:injection_idx+20, 'RPM'] = 22000 
    elif scenario == 'Brake_Failure':
        # Les freins s'activent à 100% de manière anormale
        df_network.loc[injection_idx:injection_idx+30, 'Brake'] = 100
    elif scenario == 'Gear_Drop':
        # La boîte tombe au point mort
        df_network.loc[injection_idx:injection_idx+15, 'nGear'] = 0

    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### Live Telemetry Stream")
        
        # Création du moniteur de surveillance réseau
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                            subplot_titles=("Engine Speed (RPM)", "Brake Pressure (%)", "Gear Selection"))
        
        fig.add_trace(go.Scatter(x=df_network['Distance'], y=df_network['RPM'], name='RPM', line=dict(color='#00ffcc')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_network['Distance'], y=df_network['Brake'], name='Brake', line=dict(color='#ff3333')), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_network['Distance'], y=df_network['nGear'], name='Gear', line=dict(color='#ffff00')), row=3, col=1)
        
        fig.update_layout(height=600, margin=dict(l=0, r=0, t=30, b=0), plot_bgcolor="rgba(0,0,0,0)", hovermode='x unified')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.1)')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("Threat Detection Panel")
        st.info("Investigate the telemetry traces. Is the data integrity compromised?")
        
        # Interface de réponse de l'utilisateur
        options_map = {
            "Pending Analysis...": "None",
            "System Safe (Normal Data)": "Safe",
            "Critical: Engine CAN Spoofing (RPM > 15k)": "Engine_Spoof",
            "Critical: Brake-by-Wire Override": "Brake_Failure",
            "Critical: Gearbox/Hydraulic Signal Drop": "Gear_Drop"
        }
        
        user_selection = st.selectbox("Select Diagnosis:", list(options_map.keys()))
        
        if st.button("Submit Report", type="primary", use_container_width=True):
            if options_map[user_selection] == "None":
                st.warning("Please select a diagnosis before submitting.")
            else:
                st.session_state.diagnosis_submitted = True
            
        if st.session_state.diagnosis_submitted:
            st.divider()
            
            # Vérification du résultat
            if options_map[user_selection] == scenario:
                st.success("**THREAT NEUTRALIZED**\n\nExcellent work, Analyst. You correctly identified the network status.")
            else:
                actual_state_text = [k for k, v in options_map.items() if v == scenario][0]
                st.error(f" **SYSTEM BREACHED**\n\nIncorrect diagnosis. The actual network status was: **{actual_state_text}**")
            
            # Bouton pour relancer un niveau
            if st.button("Load Next Scenario", use_container_width=True):
                st.session_state.cyber_scenario = random.choice(['Safe', 'Engine_Spoof', 'Brake_Failure', 'Gear_Drop'])
                st.session_state.diagnosis_submitted = False
                st.rerun()

    st.markdown("Raw UDP Traffic Log (Decrypted)")
    st.dataframe(df_network[['Distance', 'Speed', 'RPM', 'nGear', 'Throttle', 'Brake']].iloc[injection_idx-5 : injection_idx+25], use_container_width=True)
#rythme de course des écuries et classement basé sur les tours propres
def render_team_race_pace(session) -> None:
    st.markdown("### Team Race Pace & Ranking")
    
    # Prend en compte seulement les clean laps pour une analyse précise
    valid_laps = session.laps.pick_track_status('1')
    valid_laps = valid_laps[valid_laps['IsAccurate'] == True].copy()

    if valid_laps.empty:
        st.warning("Insufficient green flag data for race pace analysis.")
        return

    # Convertit en secondes pour faciliter les calculs
    valid_laps['LapTime_s'] = valid_laps['LapTime'].dt.total_seconds()

    # Calculs des médians pour chaque écurie
    team_pace = valid_laps.groupby('Team')['LapTime_s'].median().sort_values().reset_index()
    fastest_time = team_pace['LapTime_s'].min()
    team_pace['Gap_to_Leader (s)'] = (team_pace['LapTime_s'] - fastest_time).round(3)
    
    color_map = {}
    for team in team_pace['Team']:
        driver = valid_laps[valid_laps['Team'] == team]['DriverNumber'].iloc[0]
        try:
            c = session.get_driver(driver)['TeamColor']
            color_map[team] = f"#{c}" if pd.notna(c) and str(c).strip() != "" else "#ffffff"
        except Exception:
            color_map[team] = "#ffffff"
    
    col1, col2 = st.columns([2, 1])

    with col1:
        # Le Boxplot permet de voir la médiane et l'étalement (régularité) des chronos
        fig = px.box(
            valid_laps, x="Team", y="LapTime_s", color="Team",
            category_orders={"Team": team_pace['Team'].tolist()},
            color_discrete_map=color_map,
            points="outliers" 
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis_title="Lap Time (Seconds)",
            xaxis_title=""
        )
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.1)')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("Median Pace Ranking")
        st.dataframe(
            team_pace[['Team', 'Gap_to_Leader (s)']],
            hide_index=True,
            use_container_width=True
        )

def main() -> None:
    setup_environment()

    st.sidebar.title("NAVIGATION")
    app_mode = st.sidebar.radio("Modules", ["Telemetry Analysis", "Cybersecurity SOC"])
    st.sidebar.divider()

    st.sidebar.title("SESSION PARAMETERS")
    
    year = st.sidebar.selectbox("Year", YEARS, index=0)
    
    gp_list = get_event_schedule(year)
    if not gp_list:
        st.sidebar.error("No events found for this year.")
        return
    gp = st.sidebar.selectbox("Grand Prix", gp_list)
    
    session_label = st.sidebar.selectbox("Session", list(SESSION_MAP.keys()), index=3)
    session_type = SESSION_MAP[session_label]

    try:
        session = load_session_data(year, gp, session_type)
        
        driver_numbers = session.drivers
        driver_list = [session.get_driver(d)['Abbreviation'] for d in driver_numbers]
        driver_list = [d for d in driver_list if isinstance(d, str) and d]
        
        if not driver_list:
            st.error("No telemetry available yet for this session.")
            return

        driver1 = st.sidebar.selectbox("Reference Driver (D1)", driver_list, index=0)
        driver2 = st.sidebar.selectbox("Comparison Driver (D2)", driver_list, index=1 if len(driver_list) > 1 else 0)
        
        # Color processing
        color1 = extract_driver_color(session, driver1, "#0078d7")
        color2 = extract_driver_color(session, driver2, "#dc3545")
        
        # Edge case: Same team comparison
        if color1 == color2 and driver1 != driver2:
            color2 = "#ffffff"

        cache_key = f"{year}_{gp}_{session_type}"
        
        lap1 = get_driver_lap(session, cache_key, driver1)
        if driver1 != driver2:
            lap2 = get_driver_lap(session, cache_key, driver2)
        else:
            lap2 = lap1
            
    except Exception as e:
        st.error(f"Failed to fetch session data. Details: {e}")
        return

    st.sidebar.divider()
    st.sidebar.divider()

    if app_mode == "Telemetry Analysis":
        render_telemetry_dashboard(lap1, lap2, driver1, driver2, color1, color2, gp, year)
        
        # Appel conditionnel du rythme de course
        if session_type in ["R", "S"]:
            st.divider()
            render_team_race_pace(session)
            
    elif app_mode == "Cybersecurity SOC":
        render_cyber_dashboard(lap1)
if __name__ == "__main__":
    main()