import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import fastf1
from fastf1 import utils

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
    
    # Tolerance filter: Driver must be at least 2 km/h faster to claim the micro-sector
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

def render_cyber_dashboard(lap1, is_attack_active: bool) -> None:
    st.title("SECURITY OPERATIONS CENTER (SOC)")
    st.markdown("Intrusion Detection System - Live Network Traffic Monitoring")
    st.divider()

    telemetry = lap1.get_telemetry()
    df_network = telemetry.copy()

    if is_attack_active:
        injection_index = len(df_network) // 2
        df_network.loc[injection_index, 'Speed'] = 445.0
        df_network.loc[injection_index + 1, 'Speed'] = 450.0

    anomalies = df_network[df_network['Speed'] > 360.0]

    if not anomalies.empty:
        st.error("SYSTEM COMPROMISED - ILLEGAL VALUES DETECTED IN TELEMETRY STREAM", icon=None)
        
        col_alert, col_metrics = st.columns([2, 1])
        with col_alert:
            st.markdown("#### Detected Payload Anomalies")
            st.dataframe(anomalies[['Date', 'Time', 'Speed', 'RPM', 'Throttle', 'Brake']], use_container_width=True)
        
        with col_metrics:
            st.markdown("#### Incident Report")
            st.warning(
                "**Severity:** CRITICAL\n\n"
                f"**Packets Compromised:** {len(anomalies)}\n\n"
                "**Vector:** Suspected Man-in-the-Middle (MitM) or CAN bus injection. "
                "Speed parameters exceed physical engine limitations (>360 km/h)."
            )
    else:
        st.success("NETWORK SECURE - NO ANOMALIES DETECTED", icon=None)

    st.markdown("### Raw UDP Traffic Log")
    st.dataframe(df_network[['Time', 'X', 'Y', 'Speed', 'RPM', 'nGear', 'Throttle', 'Brake']].tail(15), use_container_width=True)

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
        
        # Edge case: Same team comparison (forces the second car to be white for visibility)
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
    if app_mode == "Cybersecurity SOC":
        st.sidebar.title("CYBER THREAT SIMULATION")
        simulate_attack = st.sidebar.checkbox("Enable Automated Data Injection")

    if app_mode == "Telemetry Analysis":
        render_telemetry_dashboard(lap1, lap2, driver1, driver2, color1, color2, gp , year)
    elif app_mode == "Cybersecurity SOC":
        render_cyber_dashboard(lap1, simulate_attack)

if __name__ == "__main__":
    main()