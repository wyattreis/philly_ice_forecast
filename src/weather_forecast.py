"""
weather_forecast.py
Fetches weather forecast data from the National Weather Service API
"""

import requests
from datetime import datetime


# Default location details for Sault Sainte Marie, MI
LOCATION = {
    'name': 'Sault Sainte Marie, MI',
    'lat': 46.5033,
    'lon': -84.3517,
    'elevation_ft': 597
}

# Predefined locations
PREDEFINED_LOCATIONS = {
    'Philadelphia, PA - Baxter Water Intake': {
        'lat': 40.039661,
        'lon': -74.992145,
        'elev': 5
    },
    'Philadelphia, PA - Schuylkill Rv. Near 30th St': {
        'lat': 39.955093,
        'lon': -75.180347,
        'elev': 5
    },
    'Trenton, NJ - Calhoun St Bridge': {
        'lat': 40.221788,
        'lon': -74.779903,
        'elev': 10
    }
}


def get_forecast(lat, lon):
    """
    Fetch weather forecast from NWS API.
    
    Parameters:
    - lat: Latitude (float)
    - lon: Longitude (float)
    
    Returns:
    - Dictionary with forecast data or error status
    """
    
    # Step 1: Get the grid point data
    try:
        # NWS API requires a User-Agent header
        headers = {
            'User-Agent': '(Great Lakes Weather App, contact@example.com)',
            'Accept': 'application/json'
        }
        
        # Get grid endpoint for this location
        points_url = f"https://api.weather.gov/points/{lat},{lon}"
        points_response = requests.get(points_url, headers=headers, timeout=10)
        points_response.raise_for_status()
        points_data = points_response.json()
        
        # Extract forecast URL
        forecast_url = points_data['properties']['forecast']
        forecast_hourly_url = points_data['properties']['forecastHourly']
        
        # Step 2: Get the actual forecast
        forecast_response = requests.get(forecast_url, headers=headers, timeout=10)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        
        # Step 3: Get hourly forecast
        hourly_response = requests.get(forecast_hourly_url, headers=headers, timeout=10)
        hourly_response.raise_for_status()
        hourly_data = hourly_response.json()
        
        return {
            'status': 'success',
            'forecast': forecast_data['properties']['periods'],
            'hourly': hourly_data['properties']['periods'],
            'updated': forecast_data['properties'].get('updated', forecast_data['properties'].get('generatedAt', 'N/A')),
            'elevation': forecast_data['properties'].get('elevation', {}).get('value', 'N/A'),
            'grid_id': points_data['properties']['gridId'],
            'grid_x': points_data['properties']['gridX'],
            'grid_y': points_data['properties']['gridY']
        }
        
    except requests.exceptions.RequestException as e:
        return {
            'status': 'error',
            'error': str(e)
        }
    except KeyError as e:
        return {
            'status': 'error',
            'error': f'Unexpected API response structure: {e}',
            'debug_info': 'Enable debug mode for more details'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': f'Unexpected error: {type(e).__name__}: {str(e)}'
        }


def format_forecast(forecast_data):
    """
    Format forecast data for display.
    
    Parameters:
    - forecast_data: Dictionary returned from get_forecast()
    
    Returns:
    - Formatted string
    """
    if forecast_data['status'] != 'success':
        return f"Error: {forecast_data.get('error', 'Unknown error')}"
    
    output = []
    output.append("=" * 80)
    output.append(f"WEATHER FORECAST: {LOCATION['name']}")
    output.append(f"Location: {LOCATION['lat']}°N, {LOCATION['lon']}°W (Elev. {LOCATION['elevation_ft']} ft)")
    output.append(f"Grid: {forecast_data['grid_id']} ({forecast_data['grid_x']}, {forecast_data['grid_y']})")
    output.append(f"Updated: {forecast_data['updated']}")
    output.append("=" * 80)
    
    # Display 7-day forecast
    output.append("\n📅 7-DAY FORECAST")
    output.append("-" * 80)
    
    for period in forecast_data['forecast'][:14]:  # 7 days = 14 periods (day/night)
        output.append(f"\n{period['name']}")
        output.append(f"Temperature: {period['temperature']}°{period['temperatureUnit']}")
        output.append(f"Wind: {period['windSpeed']} {period['windDirection']}")
        output.append(f"{period['shortForecast']}")
        if period['detailedForecast']:
            output.append(f"Details: {period['detailedForecast']}")
    
    return "\n".join(output)


def get_hourly_summary(forecast_data, hours=24):
    """
    Get summary of hourly forecast.
    
    Parameters:
    - forecast_data: Dictionary returned from get_forecast()
    - hours: Number of hours to display (default: 24)
    
    Returns:
    - Formatted string
    """
    if forecast_data['status'] != 'success':
        return f"Error: {forecast_data.get('error', 'Unknown error')}"
    
    output = []
    output.append("\n" + "=" * 80)
    output.append(f"⏰ HOURLY FORECAST (Next {hours} hours)")
    output.append("-" * 80)
    output.append(f"{'Time':<20} {'Temp':<8} {'Wind':<15} {'Conditions':<30}")
    output.append("-" * 80)
    
    for period in forecast_data['hourly'][:hours]:
        # Parse and format time
        start_time = datetime.fromisoformat(period['startTime'].replace('Z', '+00:00'))
        time_str = start_time.strftime('%a %m/%d %I:%M %p')
        
        temp_str = f"{period['temperature']}°{period['temperatureUnit']}"
        wind_str = f"{period['windSpeed']} {period['windDirection']}"
        conditions = period['shortForecast']
        
        output.append(f"{time_str:<20} {temp_str:<8} {wind_str:<15} {conditions:<30}")
    
    return "\n".join(output)


def get_current_conditions(forecast_data):
    """
    Extract current conditions from hourly forecast.
    
    Parameters:
    - forecast_data: Dictionary returned from get_forecast()
    
    Returns:
    - Dictionary with current conditions
    """
    if forecast_data['status'] != 'success':
        return None
    
    current = forecast_data['hourly'][0]
    
    return {
        'temperature': current['temperature'],
        'temperature_unit': current['temperatureUnit'],
        'wind_speed': current['windSpeed'],
        'wind_direction': current['windDirection'],
        'short_forecast': current['shortForecast'],
        'detailed_forecast': current['detailedForecast'],
        'precipitation_probability': current.get('probabilityOfPrecipitation', {}).get('value', 0),
        'humidity': current.get('relativeHumidity', {}).get('value', 'N/A'),
        'dewpoint': current.get('dewpoint', {}).get('value', 'N/A')
    }


# Test the functions when running this file directly
if __name__ == "__main__":
    print("\nFetching weather forecast from National Weather Service...")
    print("Please wait...\n")
    
    # Fetch forecast
    forecast_data = get_forecast(LOCATION['lat'], LOCATION['lon'])
    
    if forecast_data['status'] == 'success':
        # Display 7-day forecast
        print(format_forecast(forecast_data))
        
        # Display hourly forecast
        print(get_hourly_summary(forecast_data, hours=12))
        
        # Display current conditions
        print("\n" + "=" * 80)
        print("🌤️  CURRENT CONDITIONS")
        print("-" * 80)
        current = get_current_conditions(forecast_data)
        
        if current:
            print(f"Temperature: {current['temperature']}°{current['temperature_unit']}")
            print(f"Conditions: {current['short_forecast']}")
            print(f"Wind: {current['wind_speed']} {current['wind_direction']}")
            print(f"Humidity: {current['humidity']}%")
            print(f"Precipitation Probability: {current['precipitation_probability']}%")
        
        print("\n" + "=" * 80)
        print("✓ Forecast retrieved successfully!")
        
    else:
        print(f"✗ Error fetching forecast: {forecast_data.get('error', 'Unknown error')}")