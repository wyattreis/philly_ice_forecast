# Wrapper utilities for heat-flux functions that default to the app LOCATION
# This module delegates to the original implementations in external.hff.utils

try:
    # Try the standard package import first
    from external.hff import utils as eh_utils
except Exception:
    # Fallback: load the utils.py directly by file path (handles deploy environments
    # where the package import path isn't configured).
    import importlib.util
    from pathlib import Path

    utils_path = Path(__file__).resolve().parent.parent / 'external' / 'hff' / 'utils.py'
    if utils_path.exists():
        spec = importlib.util.spec_from_file_location('external_hff_utils', str(utils_path))
        eh_utils = importlib.util.module_from_spec(spec)
        loader = spec.loader
        if loader is None:
            raise ImportError(f"Could not load module from {utils_path}")
        loader.exec_module(eh_utils)
    else:
        raise ImportError(f"Could not locate external.hff.utils at {utils_path}")

# Try to lazily import weather_forecast only when needed to avoid circular import

def _get_default_location():
    try:
        import weather_forecast
        loc = weather_forecast.LOCATION
        return loc.get('lat'), loc.get('lon')
    except Exception:
        return None, None


def get_full_forecast(lat=None, lon=None):
    """Get full forecast. If lat/lon not provided, use `weather_forecast.LOCATION`."""
    if lat is None or lon is None:
        lat_def, lon_def = _get_default_location()
        if lat_def is None or lon_def is None:
            raise ValueError("Latitude and longitude must be provided or weather_forecast.LOCATION must be available.")
        lat = lat_def
        lon = lon_def
    return eh_utils.get_full_forecast(lat, lon)


def calc_fluxes(df, T_water_C, lat=None, lon=None):
    """Calculate heat fluxes. If lat/lon not provided, use `weather_forecast.LOCATION`."""
    if lat is None or lon is None:
        lat_def, lon_def = _get_default_location()
        if lat_def is None or lon_def is None:
            raise ValueError("Latitude and longitude must be provided or weather_forecast.LOCATION must be available.")
        lat = lat_def
        lon = lon_def
    return eh_utils.calc_fluxes(df, T_water_C, lat, lon)


# Re-export other utilities for convenience
get_elevation = eh_utils.get_elevation
get_48h_hourly_forecast = eh_utils.get_48h_hourly_forecast
get_solar = eh_utils.get_solar
calc_solar = eh_utils.calc_solar
calc_downwelling_LW = eh_utils.calc_downwelling_LW
calc_upwelling_LW = eh_utils.calc_upwelling_LW
calc_wind_function = eh_utils.calc_wind_function
calc_vapor_pressure = eh_utils.calc_vapor_pressure
calc_latent_heat = eh_utils.calc_latent_heat
calc_sensible_heat = eh_utils.calc_sensible_heat
calc_cooling_rate = eh_utils.calc_cooling_rate
build_energy_df = eh_utils.build_energy_df
tz_to_gmt_offset = eh_utils.tz_to_gmt_offset

__all__ = [
    'get_full_forecast', 'calc_fluxes', 'get_elevation', 'get_48h_hourly_forecast',
    'get_solar', 'calc_solar', 'calc_downwelling_LW', 'calc_upwelling_LW',
    'calc_wind_function', 'calc_vapor_pressure', 'calc_latent_heat', 'calc_sensible_heat',
    'calc_cooling_rate', 'build_energy_df', 'tz_to_gmt_offset'
]
