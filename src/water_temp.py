import requests
from datetime import datetime, timedelta

# Station data with coordinates
STATIONS_DATA = {
    'S.W. Pier, MI': {
        'id': '9076070',
        'lat': 46.5022,
        'lon': -84.3478,
        'lake': 'St. Marys River'
    },
    'Little Rapids, MI': {
        'id': '9076033',
        'lat': 46.3514,
        'lon': -84.2183,
        'lake': 'St. Marys River'
    },
    'De Tour Village, MI': {
        'id': '9075099',
        'lat': 45.9947,
        'lon': -83.8972,
        'lake': 'Lake Michigan'
    },
    'Mackinaw City, MI': {
        'id': '9075080',
        'lat': 45.7769,
        'lon': -84.7278,
        'lake': 'Lake Michigan'
    }
}


def get_water_temperature(station_id, begin_date=None, end_date=None):
    """
    Fetch water temperature data from NOAA CO-OPS API for Great Lakes stations.
    
    Parameters:
    - station_id: NOAA station ID (string)
    - begin_date: Start date in YYYYMMDD format (defaults to 7 days ago)
    - end_date: End date in YYYYMMDD format (defaults to today)
    
    Returns:
    - Dictionary with station data and temperature readings
    """
    
    # Set default dates if not provided
    if not end_date:
        end_date = datetime.now().strftime('%Y%m%d')
    if not begin_date:
        begin_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
    
    # NOAA CO-OPS API endpoint
    base_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    
    # API parameters
    params = {
        'product': 'water_temperature',
        'application': 'NOS.COOPS.TAC.WL',
        'interval' : 'h',
        'begin_date': begin_date,
        'end_date': end_date,
        'station': station_id,
        'time_zone': 'GMT',
        'units': 'english',
        'format': 'json'
    }
    
    try:
        # Make API request
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Check if data exists
        if 'data' in data and len(data['data']) > 0:
            # Extract all readings
            all_readings = [
                {
                    'time': reading['t'],
                    'temp': float(reading['v'])
                }
                for reading in data['data']
            ]
            
            # Get latest reading
            latest = data['data'][-1]

            return {
                'all_readings': all_readings,
                'latest_temp': float(latest['v']),
                'latest_time': latest['t'],
                'count': len(all_readings),
                'status': 'success'
            }
        else:
            return {'status': 'no_data'}
            
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
    
def get_color_for_temp(temp):
    """
    Return RGB color based on temperature.
    
    Parameters:
    - temp: Temperature in F
    
    Returns:
    - List of RGB values [R, G, B]
    """

    if temp < 32:
        return [0, 0, 255]  # Blue for freezing
    elif temp < 41:
        return [0, 150, 255]  # Light blue
    elif temp < 50:
        return [0, 255, 200]  # Cyan
    elif temp < 59:
        return [0, 255, 0]  # Green
    elif temp < 68:
        return [255, 255, 0]  # Yellow
    elif temp < 77:
        return [255, 150, 0]  # Orange
    else:
        return [255, 0, 0]  # Red for warm
    
def fetch_all_station_data():
    """
    Fetch temperature data for all stations.
    
    Returns:
    - List of dictionaries containing station data with 7-day history
    """
    station_data = []
    
    for location, info in STATIONS_DATA.items():
        result = get_water_temperature(info['id'])
        
        if result['status'] == 'success':
            temp = result['latest_temp']
            station_data.append({
                'location': location,
                'station_id': info['id'],
                'lat': info['lat'],
                'lon': info['lon'],
                'lake': info['lake'],
                'temperature': temp,
                'time': result['latest_time'],
                'color': get_color_for_temp(temp),
                'all_readings': result['all_readings'],  # Include full 7-day data
                'reading_count': result['count']
            })
    
    return station_data


def get_station_water_temp_for_hff():
    """
    Get water temperature for heat flux forecast from available stations.
    
    Priority order:
    1. Little Rapids, MI
    2. S.W. Pier, MI
    3. De Tour Village, MI
    4. Mackinaw City, MI
    5. If no data available, use 2°C
    
    Returns:
    - Tuple: (temperature_C, source_name)
      temperature_C: Water temperature in Celsius
      source_name: Name of the station or "Default" if using fallback
    """
    priority_stations = [
        'Little Rapids, MI',
        'S.W. Pier, MI',
        'De Tour Village, MI',
        'Mackinaw City, MI'
    ]
    
    for station_name in priority_stations:
        if station_name in STATIONS_DATA:
            station_info = STATIONS_DATA[station_name]
            result = get_water_temperature(station_info['id'])
            
            if result['status'] == 'success':
                # Convert from Fahrenheit to Celsius
                temp_f = result['latest_temp']
                temp_c = (temp_f - 32) * (5 / 9)
                return temp_c, station_name
    
    # If no station data available, use default
    return 2.0, "Default"
    

if __name__ == "__main__":
    print("Testing Great Lakes Water Temperature API")
    print("=" * 70)
    
    # Test 1: Single station
    print("\nTest 1: Fetching data for a single station")
    print("-" * 70)
    test_station_id = '9075080'  # Point Iroquois, MI
    
    print
    
    print(f"Station ID: {test_station_id}")
    result = get_water_temperature(test_station_id)

    print(f"✓ Status: {result['status']}")
    print(f"✓ Latest Temperature: {result['latest_temp']:.2f}°F)")
    print(f"✓ Latest Reading Time: {result['latest_time']}")
    print(f"✓ Total Readings: {result['count']}")
    print(f"✓ Color Code: RGB{tuple(get_color_for_temp(result['latest_temp']))}")