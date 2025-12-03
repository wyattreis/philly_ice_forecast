# -------------------------------------------------------------------------------
# Name          Heat Flux Utilities Wrapper
# Description:  Self-contained heat-flux utilities with defaults to app LOCATION.
#               All functions from external.hff.utils are included here
#               so the module is deployable without external package imports.
# -------------------------------------------------------------------------------

import numpy as np
import pandas as pd
from pvlib.location import Location
import pytz
import datetime
import streamlit as st
import requests


def get_elevation(lat, lon):
    """Get elevation data from OpenTopoData API"""
    url = f'https://api.opentopodata.org/v1/ned10m?locations={lat},{lon}'
    result = requests.get(url)
    return result.json()['results'][0]['elevation']


def get_48h_hourly_forecast(lat, lon, ahead_hour=0):
    """Fetch 48-hour hourly forecast from NWS"""
    url = rf'https://forecast.weather.gov/MapClick.php?w0=t&w1=td&w2=wc&w3=sfcwind&w3u=1&w4=sky&w5=pop&w6=rh&w7=rain&w8=thunder&w9=snow&w10=fzg&w11=sleet&w13u=0&w16u=1&w17u=1&AheadHour={ahead_hour}&Submit=Submit&FcstType=digital&textField1={lat}&textField2={lon}&site=all&unit=0&dd=&bw='

    pd_tables = pd.read_html(url)
    table1 = pd_tables[4].iloc[1:17]
    table2 = pd_tables[4].iloc[18:35]
    table1.set_index(0, inplace=True)
    table2.set_index(0, inplace=True)
    df = pd.merge(table1, table2, left_index=True, right_index=True)
    df = df.T

    # generalize the hour column and extract timezone
    hours_col = df.columns[1]
    timezone = hours_col[5:].strip('()')
    gmt_tz = tz_to_gmt_offset(timezone)
    pytz_gmt_tz = pytz.timezone(gmt_tz)
    df = df.rename(columns={hours_col: "hour"})

    # make datetime index
    df.Date = df.Date.fillna(method='ffill')
    df[["month", "day"]] = df["Date"].str.split("/", expand=True).astype(int)
    # figure out if the data spans one year to the next and correct
    current_year = datetime.datetime.now(tz=pytz_gmt_tz).year
    current_month = datetime.datetime.now(tz=pytz_gmt_tz).month
    df['year'] = np.where(df['month'] >= current_month, current_year, current_year + 1)
    df['date'] = pd.to_datetime(df[['year', 'month', 'day']]) + pd.to_timedelta(df['hour'].astype(int), unit="h")
    df = df.set_index('date').drop(['Date', 'hour', 'month', 'day', 'year'], axis=1)

    df.index = df.index.tz_localize(tz=gmt_tz)
    return df


@st.cache_data
def get_full_forecast(lat=None, lon=None):
    """Get full 6.5 day forecast by combining multiple 48-hour forecasts.
    If lat/lon not provided, use weather_forecast.LOCATION."""
    if lat is None or lon is None:
        try:
            import weather_forecast
            loc = weather_forecast.LOCATION
            lat = loc.get('lat')
            lon = loc.get('lon')
        except Exception:
            raise ValueError("Latitude and longitude must be provided or weather_forecast.LOCATION must be available.")
    
    aheadhours = [48, 96, 107]
    df = get_48h_hourly_forecast(lat, lon, 0)
    for aheadhour in aheadhours:
        df2 = get_48h_hourly_forecast(lat, lon, aheadhour)
        df = pd.concat([df, df2], axis=0)
    df = df[~df.index.duplicated(keep='first')]
    df = df.apply(pd.to_numeric, errors='coerce')
    return df


def get_solar(lat, lon, elevation, site_name, times, tz):
    """Get clearsky solar radiation from pvlib"""
    site = Location(lat, lon, tz, elevation, site_name)
    cs = site.get_clearsky(times)
    return cs


def calc_solar(q0_a_t, R, Cl):
    """Calculate net solar radiation into water"""
    q_sw = q0_a_t * (1 - R) * (1 - 0.65 * Cl ** 2)
    return q_sw


def calc_downwelling_LW(T_air, Cl):
    """Calculate downwelling longwave radiation"""
    Tak = T_air + 273.15
    sbc = 5.670374419 * 10 ** -8  # W m-2 K-4
    emissivity = 0.937 * 10 ** -5 * (1 + 0.17 * Cl ** 2) * Tak ** 2
    q_atm = emissivity * sbc * Tak ** 4
    return q_atm


def calc_upwelling_LW(T_water):
    """Calculate upwelling longwave radiation"""
    Twk = T_water + 273.15
    sbc = 5.670374419 * 10 ** -8  # W m-2 K-4
    emissivity = 0.97
    q_b = emissivity * sbc * Twk ** 4
    return q_b


def calc_wind_function(a, b, c, R, U):
    """Calculate wind function for latent and sensible heat"""
    return R * (a + b * U ** c)


def calc_vapor_pressure(T_dewpoint):
    """Calculate vapor pressure from dewpoint"""
    return 6.11 * 10 ** (7.5 * T_dewpoint / (237.3 + T_dewpoint))


def calc_latent_heat(P, T_water, ea, f_U):
    """Calculate latent heat flux"""
    Twk = T_water + 273.15
    Lv = 2.500 * 10 ** 6 - 2.386 * 10 ** 3 * (T_water)
    rho_w = 1000  # kg/m3
    es = 6984.505294 + Twk * (-188.903931 + Twk * (2.133357675 + Twk * (-1.28858097 * 10 ** -2 + Twk * (
            4.393587233 * 10 ** -5 + Twk * (-8.023923082 * 10 ** -8 + Twk * 6.136820929 * 10 ** -11)))))
    ql = 0.622 / P * Lv * rho_w * (es - ea) * f_U
    return ql


def calc_sensible_heat(T_air, f_U, T_water):
    """Calculate sensible heat flux"""
    Cp = 1.006 * 10 ** 3  # J/kg-K
    rho_w = 1000
    qh = Cp * rho_w * (T_air - T_water) * f_U
    return qh


def calc_fluxes(df, T_water_C, lat=None, lon=None):
    """Calculate all heat flux components.
    If lat/lon not provided, use weather_forecast.LOCATION."""
    if lat is None or lon is None:
        try:
            import weather_forecast
            loc = weather_forecast.LOCATION
            lat = loc.get('lat')
            lon = loc.get('lon')
        except Exception:
            raise ValueError("Latitude and longitude must be provided or weather_forecast.LOCATION must be available.")
    
    # calc solar input
    times = pd.date_range(start=df.index.min(), end=df.index.max(), freq='1H')

    elevation = get_elevation(lat, lon)

    site_name = 'general location'
    tz = df.index.tz
    ghi = get_solar(lat, lon, elevation, site_name, times, tz).ghi

    # calculate effects of clouds on shortwave
    R = 0.15  # Maidment et al. (1996) Handbook of Hydrology
    Cl = df['Sky Cover (%)'].astype(int) / 100
    q_sw = calc_solar(ghi, R, Cl)

    # calc longwave down
    T_air_C = (df['Temperature (°F)'].astype(int) - 32) * (5 / 9)
    q_atm = calc_downwelling_LW(T_air_C, Cl)

    # calc longwave up
    q_b = calc_upwelling_LW(T_water_C)

    # calc wind function
    a = 10 ** -6
    b = 10 ** -6
    c = 1
    R = 1

    U = df['Surface Wind (mph)'].astype(int) * 0.44704
    f_U = calc_wind_function(a, b, c, R, U)

    # calc latent heat
    T_dewpoint_C = (df['Dewpoint (°F)'].astype(int) - 32) * (5 / 9)
    P = 1000  # mb don't have a forecast for this, but heat flux not that sensitive to it
    ea = calc_vapor_pressure(T_dewpoint_C)
    q_l = calc_latent_heat(P, T_water_C, ea, f_U)

    # calc sensible heat
    q_h = calc_sensible_heat(T_air_C, f_U, T_water_C)

    # calculate net heat flux
    q_net = q_sw + q_atm - q_b + q_h - q_l

    return q_sw, q_atm, q_b, q_l, q_h, q_net


def calc_cooling_rate(q_net, D):
    """Calculate water cooling rate"""
    pw = 1000  # kg/m^3 density of water
    cpw = 4182  # J/kg-K specific heat of water
    cooling_rate = q_net / (pw * cpw * D) * 60  # C/min
    return cooling_rate


def build_energy_df(q_sw, q_atm, q_b, q_l, q_h):
    """Build DataFrame with all energy flux components"""
    energy_df = pd.DataFrame(
        {
            'downwelling SW': q_sw, 
            'downwelling LW': q_atm, 
            'upwelling LW': -q_b, 
            'sensible heat': q_h,
            'latent heat': -q_l
        }
    )
    energy_df['net flux'] = energy_df.sum(axis=1)
    return energy_df


def tz_to_gmt_offset(tz_string):
    """Convert NOAA timezone string to pytz timezone"""
    tz_map = {
        'AKST': 'Etc/GMT+9',
        'AKDT': 'Etc/GMT+8',
        'PST': 'Etc/GMT+8',
        'PDT': 'Etc/GMT+7',
        'MST': 'Etc/GMT+7',
        'MDT': 'Etc/GMT+6',
        'CST': 'Etc/GMT+6',
        'CDT': 'Etc/GMT+5',
        'EST': 'Etc/GMT+5',
        'EDT': 'Etc/GMT+4'
    }
    return tz_map[tz_string]


__all__ = [
    'get_full_forecast', 'calc_fluxes', 'get_elevation', 'get_48h_hourly_forecast',
    'get_solar', 'calc_solar', 'calc_downwelling_LW', 'calc_upwelling_LW',
    'calc_wind_function', 'calc_vapor_pressure', 'calc_latent_heat', 'calc_sensible_heat',
    'calc_cooling_rate', 'build_energy_df', 'tz_to_gmt_offset'
]
