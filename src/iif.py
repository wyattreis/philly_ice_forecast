import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

import sys
from pathlib import Path

# Ensure project root is on sys.path so `external.hff` can be imported as a package
sys.path.insert(0, str(Path(__file__).parent.parent))

from water_temp import fetch_all_station_data, get_station_water_temp_for_hff
from weather_forecast import get_forecast, get_current_conditions, LOCATION
from hff_utils import (
    get_elevation, get_48h_hourly_forecast, get_full_forecast,
    get_solar, calc_solar, calc_downwelling_LW, calc_upwelling_LW,
    calc_wind_function, calc_vapor_pressure, calc_latent_heat,
    calc_sensible_heat, calc_fluxes, calc_cooling_rate,
    build_energy_df, tz_to_gmt_offset
)
from hff_plots import (
    plot_forecast_heat_fluxes, plot_met, plot_cooling_rate, plot_parcel_cooling
)


# Page configuration
st.set_page_config(
    page_title="Ice Island Forecasting",
    page_icon="🧊",
    layout="wide"
)

# Helper function for heat flux explanation
def heat_flux_blurb():
    """Return explanatory text for heat flux terms"""
    return """

    **Downwelling SW (Shortwave Radiation):** This represents the heat flux from incoming solar radiation that reaches the river's surface. Its magnitude fluctuates daily with the solar cycle, peaking during midday when sunlight is strongest.

    **Downwelling LW (Longwave Radiation):** This flux captures the longwave radiation emitted by the atmosphere and surroundings toward the river. It tends to be relatively steady compared to shortwave radiation, influenced by cloud cover and atmospheric conditions.

    **Upwelling LW (Longwave Radiation):** The heat flux emitted from the river's surface back into the atmosphere. This depends on the river's surface temperature, with warmer water emitting more longwave radiation.

    **Sensible Heat:** The heat exchange between the river surface and the air due to differences in temperature. Positive values indicate heat transfer from the air to the river, while negative values indicate heat loss from the river to the air.

    **Latent Heat:** The heat exchange associated with water evaporation or condensation at the river's surface. Evaporation (heat loss) is typically the dominant process, driven by humidity and wind.

    **Net Flux:** The overall heat budget combining all the fluxes. A positive net flux indicates heat gain by the river, while a negative net flux indicates heat loss."""

# Main app
st.title("Little Rapids Ice Island Data Collection Forecasting")

# Fetch data with caching
@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_data():
    return fetch_all_station_data()

# Load data
with st.spinner("Fetching latest temperature data..."):
    station_data = load_data()

# Fetch weather forecast
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_forecast():
    return get_forecast(LOCATION['lat'], LOCATION['lon'])

forecast_data = load_forecast()

# Create DataFrame
df = pd.DataFrame(station_data)

# Weather Forecast Section
st.header("🌤️ 7-Day Weather Forecast")

if forecast_data and forecast_data['status'] == 'success':
    # Current conditions
    # current = get_current_conditions(forecast_data)
    
    # if current:
    #     st.subheader(f"Current Conditions - {LOCATION['name']}")
        
    #     col1, col2, col3, col4 = st.columns(4)
        
    #     with col1:
    #         st.metric("Temperature", f"{current['temperature']}°{current['temperature_unit']}")
    #     with col2:
    #         st.metric("Wind", f"{current['wind_speed']} {current['wind_direction']}")
    #     with col3:
    #         st.metric("Humidity", f"{current['humidity']}%")
    #     with col4:
    #         st.metric("Precip. Chance", f"{current['precipitation_probability']}%")
        
    #     st.info(f"**Conditions:** {current['short_forecast']}")
      
    forecast_periods = forecast_data['forecast'][:14]  # 7 days = 14 periods (day/night)
    
    # Create columns for forecast cards
    cols_per_row = 5
    for i in range(0, len(forecast_periods), cols_per_row):
        cols = st.columns(cols_per_row)
        
        # Determine number of rows to know which row is last (for bottom borders)
        import math
        nrows = math.ceil(len(forecast_periods) / cols_per_row)
        current_row = i // cols_per_row

        for j in range(cols_per_row):
            idx = i + j
            if idx < len(forecast_periods):
                period = forecast_periods[idx]

                with cols[j]:
                    # Determine if day or night for styling
                    is_daytime = period.get('isDaytime', True)
                    icon = "☀️" if is_daytime else "🌘"

                    temp_color = "red" if is_daytime else "blue"

                    # Add borders between columns and rows by wrapping card content in a bordered div.
                    # Right border for all but last column; bottom border for all but last row.
                    is_last_col = (j == cols_per_row - 1)
                    is_last_row = (current_row == nrows - 1)

                    right_border = '1px solid #ddd' if not is_last_col else 'none'
                    bottom_border = '1px solid #ddd' if not is_last_row else 'none'

                    html = f"""
<div style='padding:10px; border-right:{right_border}; border-bottom:{bottom_border};'>
  <h5 style='margin:0 0 6px 0;'>{icon} {period['name']}</h5>
  <p style='margin:0 0 6px 0;'><em>{period['shortForecast']}</em></p>
  <p style='margin:0 0 6px 0;'>
    🌡️: <span style='color:{temp_color}; font-weight:600;'>{period.get('temperature', 'N/A')}°{period.get('temperatureUnit', '')}</span>
    | 🌬️ {period.get('windSpeed', '')} {period.get('windDirection', '')}
"""

                    # Add precipitation probability if available
                    if 'probabilityOfPrecipitation' in period and period['probabilityOfPrecipitation'].get('value') is not None:
                        precip_prob = period['probabilityOfPrecipitation']['value']
                        html += f" | 💧 {precip_prob}%"

                    # Add cloud cover if available
                    if 'skyCover' in period:
                        cloud_cover = period['skyCover'].get('value', 'N/A')
                        html += f" | ☁️ {cloud_cover}%"

                    html += "</p>"

                    # Include the detailed forecast inside the card using a native HTML
                    # <details> element so it appears above the bottom border line.
                    detailed_text = period.get('detailedForecast', '') or ''
                    # sanitize newlines for HTML display
                    detailed_html = detailed_text.replace('\n', '<br/>')

                    html += f"<div style='margin-top:6px;'><details><summary style='cursor:pointer;font-weight:600;'>Detailed Forecast</summary><div style='margin-top:6px;color:#333;'>{detailed_html}</div></details></div></div>"

                    st.markdown(html, unsafe_allow_html=True)
    
    st.caption(f"Forecast updated: {forecast_data.get('updated', 'N/A')}")
    
else:
    st.error("⚠️ Unable to load weather forecast at this time.")

st.divider()

# Water Temperature Section
st.header("🌊 Station Water Temperature")

if len(df) > 0:
    # Station status summary
    from water_temp import STATIONS_DATA
    
    # Get list of active station IDs
    active_station_ids = set(df['station_id'].tolist())
    
    # Build status line
    status_parts = []
    for location, info in STATIONS_DATA.items():
        if info['id'] in active_station_ids:
            status_parts.append(f"✅ {location}")
        else:
            status_parts.append(f"❌ {location}")
    
    # Display station status
    st.markdown("**Station Status:** " + " | ".join(status_parts))
    
    # Data table
    st.subheader("📊 Current Readings")
    
    # Format the dataframe for display and include Celsius column
    display_df = df[['location', 'lake', 'temperature', 'time']].copy()
    # Ensure numeric
    display_df['temperature'] = pd.to_numeric(display_df['temperature'], errors='coerce')
    # Compute Celsius
    display_df['temperature_C'] = (display_df['temperature'] - 32) * (5 / 9)

    # Append latest USACE hydro plant reading to the table (if CSV present)
    try:
        usace_csv = Path(__file__).parent.parent / 'USACEhydro_WT_daily.csv'
        if usace_csv.exists():
            usace_df = pd.read_csv(usace_csv)
            if 'date' in usace_df.columns and 'temp_dy' in usace_df.columns:
                usace_df['date'] = pd.to_datetime(usace_df['date'], errors='coerce')
                usace_df = usace_df.dropna(subset=['date'])
                if not usace_df.empty:
                    latest = usace_df.loc[usace_df['date'].idxmax()]
                    try:
                        temp_f = float(latest['temp_dy'])
                        temp_c = (temp_f - 32) * (5.0 / 9.0)
                        time_str = pd.to_datetime(latest['date']).strftime('%Y-%m-%d')
                        usace_row = {
                            'location': 'USACE Hydro Plant',
                            'lake': 'Hydro Plant',
                            'temperature': temp_f,
                            'time': time_str,
                            'temperature_C': temp_c
                        }
                        display_df = pd.concat([display_df, pd.DataFrame([usace_row])], ignore_index=True)
                    except Exception:
                        pass
    except Exception:
        pass

    # Format strings for display
    display_df['Temperature (°F)'] = display_df['temperature'].apply(lambda x: f"{x:.1f}°F" if pd.notna(x) else "N/A")
    display_df['Temperature (°C)'] = display_df['temperature_C'].apply(lambda x: f"{x:.1f}°C" if pd.notna(x) else "N/A")

    # Reorder and rename columns for display
    display_df = display_df[['location', 'lake', 'Temperature (°F)', 'Temperature (°C)', 'time']]
    display_df.columns = ['Station', 'Water Body', 'Temperature (°F)', 'Temperature (°C)', 'Last Updated (GMT)']

    st.dataframe(display_df, use_container_width=True)
    
    # # Statistics
    # col1, col2, col3 = st.columns(3)
    
    # with col1:
    #     st.metric("Warmest Station", 
    #               df.loc[df['temperature'].idxmax(), 'location'],
    #               f"{df['temperature'].max():.1f}°F")
    
    # with col2:
    #     st.metric("Coldest Station",
    #               df.loc[df['temperature'].idxmin(), 'location'],
    #               f"{df['temperature'].min():.1f}°F")
    
    # with col3:
    #     st.metric("Average Temperature",
    #               f"{df['temperature'].mean():.1f}°F")
    
    # Temperature trends
    st.subheader("📈 7-Day Temperature Trends")
    
    # Create plot with all stations
    fig = go.Figure()

    # Determine station time window (use station 7-day series if available)
    station_start = None
    station_end = None
    try:
        if len(df) > 0:
            mins = []
            maxs = []
            for _, row in df.iterrows():
                readings_df_tmp = pd.DataFrame(row.get('all_readings', []))
                if 'time' in readings_df_tmp.columns:
                    times_tmp = pd.to_datetime(readings_df_tmp['time'], errors='coerce')
                    if times_tmp.notna().any():
                        mins.append(times_tmp.min())
                        maxs.append(times_tmp.max())
            if mins and maxs:
                station_start = min(mins)
                station_end = max(maxs)
    except Exception:
        station_start = None
        station_end = None

    # Try to load USACE hydro plant CSV and add as a trace limited to station window
    try:
        usace_csv = Path(__file__).parent.parent / 'USACEhydro_WT_daily.csv'
        if usace_csv.exists():
            usace_df = pd.read_csv(usace_csv)
            # Expect columns: date, temp_dy (temperatures in °F)
            if 'date' in usace_df.columns and 'temp_dy' in usace_df.columns:
                usace_df['date'] = pd.to_datetime(usace_df['date'], errors='coerce')
                # If station window available, filter USACE data to that range
                if station_start is not None and station_end is not None:
                    mask = (usace_df['date'] >= station_start) & (usace_df['date'] <= station_end)
                    usace_df = usace_df.loc[mask]
                else:
                    # fallback: take last 7 days from the CSV if no station data
                    latest = usace_df['date'].max()
                    if pd.notna(latest):
                        earliest = latest - pd.Timedelta(days=7)
                        usace_df = usace_df.loc[usace_df['date'] >= earliest]

                # Add a trace for USACE Hydro Plant (daily points/line)
                if not usace_df.empty:
                    fig.add_trace(go.Scatter(
                        x=usace_df['date'],
                        y=usace_df['temp_dy'],
                        mode='lines+markers',
                        name='USACE Hydro Plant',
                        line=dict(width=2, dash='dash', color='black'),
                        marker=dict(symbol='x', size=6)
                    ))
    except Exception:
        # Don't let missing/invalid CSV break the app
        pass

    for idx, row in df.iterrows():
        readings_df = pd.DataFrame(row['all_readings'])
        readings_df['time'] = pd.to_datetime(readings_df['time'])
        
        fig.add_trace(go.Scatter(
            x=readings_df['time'],
            y=readings_df['temp'],
            mode='lines+markers',
            name=row['location'],
            line=dict(width=2),
            marker=dict(size=4)
        ))
    
    fig.update_layout(
        xaxis_title="Date/Time (GMT)",
        yaxis_title="Temperature (°F)",
        hovermode='x unified',
        height=500,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
#     # Individual station details (expandable)
#     st.subheader("🔍 Individual Station Details")
    
#     for idx, row in df.iterrows():
#         with st.expander(f"{row['location']} - Current: {row['temperature']:.1f}°C"):
#             readings_df = pd.DataFrame(row['all_readings'])
#             readings_df['time'] = pd.to_datetime(readings_df['time'])
            
#             # Create individual plot
#             fig_individual = go.Figure()
#             fig_individual.add_trace(go.Scatter(
#                 x=readings_df['time'],
#                 y=readings_df['temp'],
#                 mode='lines+markers',
#                 name=row['location'],
#                 line=dict(width=2, color=f"rgb{tuple(row['color'])}"),
#                 marker=dict(size=6),
#                 fill='tozeroy',
#                 fillcolor=f"rgba{tuple(row['color'] + [0.1])}"
#             ))
            
#             fig_individual.update_layout(
#                 xaxis_title="Date/Time (GMT)",
#                 yaxis_title="Temperature (°C)",
#                 height=300,
#                 showlegend=False
#             )
            
#             st.plotly_chart(fig_individual, use_container_width=True)
            
#             # Stats for this station
#             temps = readings_df['temp'].values
#             col1, col2, col3, col4 = st.columns(4)
            
#             with col1:
#                 st.metric("Max", f"{temps.max():.1f}°C")
#             with col2:
#                 st.metric("Min", f"{temps.min():.1f}°C")
#             with col3:
#                 st.metric("Avg", f"{temps.mean():.1f}°C")
#             with col4:
#                 st.metric("Readings", len(temps))
    st.caption("Data sources: NOAA CO-OPS API - Updates every hour | USACE Hydro Plant CSV - Manual updates ~daily")
    
else:
    st.error("⚠️ No temperature data available at this time. Please try again later.")

st.divider()

# Heat Flux Forecast Section
st.header("❄️ Heat Flux Forecast")
st.write('Forecast met input data from NOAA Hourly Tabular Forecast Data. Heat Flux forecast from CRREL HeatFluxForecast model.Based on Water Quality Module calculations in HEC-RAS.')

# Heat flux calculation inputs
col1, col2, col3, col4 = st.columns(4)

# Determine default water temperature: prefer latest USACE reading, else station, else 2°C
# Read latest USACE temperature from CSV (if present)
usace_temp_c = None
usace_temp_date = None
try:
    usace_csv = Path(__file__).parent.parent / 'USACEhydro_WT_daily.csv'
    if usace_csv.exists():
        usace_df_all = pd.read_csv(usace_csv)
        if 'date' in usace_df_all.columns and 'temp_dy' in usace_df_all.columns:
            usace_df_all['date'] = pd.to_datetime(usace_df_all['date'], errors='coerce')
            usace_df_all = usace_df_all.dropna(subset=['date'])
            if not usace_df_all.empty:
                latest_row = usace_df_all.loc[usace_df_all['date'].idxmax()]
                try:
                    temp_f = float(latest_row['temp_dy'])
                    usace_temp_c = (temp_f - 32) * (5.0 / 9.0)
                    usace_temp_date = latest_row['date']
                except Exception:
                    usace_temp_c = None
except Exception:
    usace_temp_c = None

# Get station-derived temperature as fallback
station_temp_c, station_source = get_station_water_temp_for_hff()

# Choose default and source label
if usace_temp_c is not None:
    default_water_temp = usace_temp_c
    water_temp_source_label = f"USACE Hydro Plant ({usace_temp_date.strftime('%Y-%m-%d')})"
elif station_source != 'Default':
    default_water_temp = station_temp_c
    water_temp_source_label = station_source
else:
    default_water_temp = 2.0
    water_temp_source_label = 'Default'

with col1:
    hf_lat = st.number_input('Heat Flux Latitude', value=float(LOCATION.get('lat', 41.1242)), format="%.6f", step=0.000001, key='hf_lat')
with col2:
    hf_lon = st.number_input('Heat Flux Longitude', value=float(LOCATION.get('lon', -101.3644337)), format="%.6f", step=0.000001, key='hf_lon')
with col3:
    T_water_C = st.number_input('Water Temperature (°C)', value=default_water_temp, key='T_water')
with col4:
    D = st.number_input('Characteristic Depth (m)', value=2.0, key='depth')

# Display active location info
default_loc_lat = LOCATION.get('lat')
default_loc_lon = LOCATION.get('lon')
is_default = (hf_lat == default_loc_lat and hf_lon == default_loc_lon)
if is_default:
    st.markdown(f"**Active Location:** {LOCATION.get('name', 'Default')} — {hf_lat:.6f}, {hf_lon:.6f}")
else:
    st.markdown(f"**Active Location (override):** {hf_lat:.6f}, {hf_lon:.6f} — default: {LOCATION.get('name', 'Default')} {default_loc_lat:.6f}, {default_loc_lon:.6f}")

if usace_temp_c is not None:
    st.markdown(f"**Water Temperature Source:** {water_temp_source_label} — {usace_temp_c:.1f}°C")
else:
    st.markdown(f"**Water Temperature Source:** {water_temp_source_label} — {default_water_temp:.1f}°C")

if st.button('🌡️ Compute Heat Fluxes'):
    try:
        # If the user inputs match the app LOCATION, let the wrapper use LOCATION by calling without args
        use_default_loc = (hf_lat == LOCATION.get('lat') and hf_lon == LOCATION.get('lon'))
        if use_default_loc:
            df_hf = get_full_forecast()
        else:
            df_hf = get_full_forecast(hf_lat, hf_lon)
        df_hf = df_hf.replace([np.inf, -np.inf], np.nan)

        first_forecast_time = df_hf.index[0]
        timezone = first_forecast_time.tz
        time_now = pd.Timestamp.now(tz=timezone)

        with st.expander("**Notes on Flux Terms**", expanded=False):
            st.write(heat_flux_blurb())

        #st.write(f'Current Time: {time_now}')
        #st.write(f'Current Forecast Start Time: {first_forecast_time}')
        if time_now - first_forecast_time > pd.Timedelta(hours=1):
            get_full_forecast.clear()
            if use_default_loc:
                df_hf = get_full_forecast()
            else:
                df_hf = get_full_forecast(hf_lat, hf_lon)

        if use_default_loc:
            q_sw, q_atm, q_b, q_l, q_h, q_net = calc_fluxes(df_hf, T_water_C)
        else:
            q_sw, q_atm, q_b, q_l, q_h, q_net = calc_fluxes(df_hf, T_water_C, hf_lat, hf_lon)

        energy_df = build_energy_df(q_sw, q_atm, q_b, q_l, q_h)
        fig = plot_forecast_heat_fluxes(energy_df)
        st.plotly_chart(fig, use_container_width=True)

        g = plot_met(df_hf)
        st.plotly_chart(g, use_container_width=True)

        cooling_rate = calc_cooling_rate(q_net, D)

        with st.expander("Experimental Plots", expanded=False):
            st.write(plot_cooling_rate(cooling_rate))
            st.write(plot_parcel_cooling(cooling_rate, T_water_C))

        st.caption(f'Current Heat Flux Forecast Start Time: {first_forecast_time}')
            
    except Exception as e:
        st.error(f"Error computing heat fluxes: {str(e)}")

st.divider()
# Refresh button
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()