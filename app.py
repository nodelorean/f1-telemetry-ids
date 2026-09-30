import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import fastf1

# Application Configuration
st.set_page_config(
    page_title="F1 Telemetry & Network IDS",
    layout="wide",
    initial_sidebar_state="expanded"
)


YEARS = list(range(2026, 2017, -1))
SESSIONS = ["FP1", "FP2", "FP3", "Q", "SQ", "S", "R"]

def setup_environment() -> None:
    if not os.path.exists('cache'):
        os.makedirs('cache')
    fastf1.Cache.enable_cache('cache')

@st.cache_data(show_spinner="Fetching F1 calendar...")
def get_event_schedule(year: int) -> list:
    """Retrieve the official list of Grand Prix events for a given year."""
    try:
        schedule = fastf1.get_event_schedule(year)
        # Filter out pre-season testing to only keep actual race weekends
        events = schedule[schedule['EventFormat'] != 'testing']
        return events['EventName'].tolist()
    except Exception:
        return []

@st.cache_data(show_spinner="Downloading session telemetry data...")
def load_session_data(year: int, gp: str, session_type: str):
    """Load the complete session data (cached)."""
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=True, weather=False, messages=False)
    return session

def render_telemetry_dashboard(telemetry: pd.DataFrame, driver: str, gp: str) -> None:
    st.title("PERFORMANCE ANALYSIS")
    st.markdown(f"**Driver:** {driver} | **Event:** {gp}")
    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Top Speed", f"{telemetry['Speed'].max():.1f} km/h")
    col2.metric("Max RPM", f"{telemetry['RPM'].max():.0f}")
    col3.metric("Avg Speed", f"{telemetry['Speed'].mean():.1f} km/h")
    col4.metric("Telemetry Packets", f"{len(telemetry)}")

    st.markdown("### Circuit Map & Speed Profile")
    st.markdown("Hover over the track trajectory to analyze local speed and inputs.")
    
    fig_map = px.scatter(
        telemetry, x="X", y="Y", color="Speed",
        color_continuous_scale="Turbo",
        hover_data=["Time", "Speed", "nGear", "Brake"]
    )
    fig_map.update_yaxes(scaleanchor="x", scaleratio=1)
    fig_map.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        coloraxis_colorbar=dict(title="km/h"),
        margin=dict(l=0, r=0, t=0, b=0)
    )
    st.plotly_chart(fig_map, use_container_width=True)

    st.markdown("### Speed & Input Dynamics")
    
    fig_dynamics = go.Figure()
    fig_dynamics.add_trace(go.Scatter(x=telemetry['Distance'], y=telemetry['Speed'], name='Speed (km/h)', line=dict(color='#0078d7')))
    fig_dynamics.add_trace(go.Scatter(x=telemetry['Distance'], y=telemetry['Throttle'], name='Throttle (%)', line=dict(color='#28a745'), yaxis='y2'))
    fig_dynamics.add_trace(go.Scatter(x=telemetry['Distance'], y=telemetry['Brake'] * 100, name='Brake (Active)', line=dict(color='#dc3545'), yaxis='y2'))

    fig_dynamics.update_layout(
        yaxis=dict(title='Speed (km/h)'),
        yaxis2=dict(title='Pedal Input (%)', overlaying='y', side='right'),
        hovermode='x unified',
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0)
    )
    st.plotly_chart(fig_dynamics, use_container_width=True)

def render_cyber_dashboard(telemetry: pd.DataFrame, is_attack_active: bool) -> None:
    st.title("SECURITY OPERATIONS CENTER (SOC)")
    st.markdown("Intrusion Detection System - Live Network Traffic Monitoring")
    st.divider()

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
    
    
    session_type = st.sidebar.selectbox("Session", SESSIONS, index=3)

    st.sidebar.divider()
    st.sidebar.title("CYBER THREAT SIMULATION")
    simulate_attack = st.sidebar.checkbox("Enable Automated Data Injection")

    # Load session to extract actual drivers
    try:
        session = load_session_data(year, gp, session_type)
        
        # Extract drivers who actually participated in this specific session
        driver_numbers = session.drivers
        driver_list = [session.get_driver(d)['Abbreviation'] for d in driver_numbers]
        driver_list = [d for d in driver_list if isinstance(d, str) and d] # Clean up any empty data
        
        if not driver_list:
            st.error("No telemetry available yet for this session.")
            return

        # Dynamic Driver Selection
        driver = st.sidebar.selectbox("Driver", driver_list)
        
        # Extract fastest lap for the selected driver
        lap = session.laps.pick_driver(driver).pick_fastest()
        telemetry = lap.get_telemetry()
        
    except Exception as e:
        st.error(f"Failed to fetch session data. The session may not have occurred yet or telemetry is missing. Details: {e}")
        return

    # Routing based on app mode
    if app_mode == "Telemetry Analysis":
        render_telemetry_dashboard(telemetry, driver, gp)
    elif app_mode == "Cybersecurity SOC":
        render_cyber_dashboard(telemetry, simulate_attack)

if __name__ == "__main__":
    main()