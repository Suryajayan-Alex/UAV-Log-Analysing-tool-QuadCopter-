import requests
from datetime import datetime
import logging

def get_weather_data(lat, lon, dt_utc, duration_min=60):
    """
    Fetch historical weather data from Open-Meteo.
    :param lat: Latitude
    :param lon: Longitude
    :param dt_utc: datetime object in UTC (start of flight)
    :param duration_min: Duration of flight in minutes
    :return: dict with weather info (point and time-series)
    """
    if lat is None or lon is None or dt_utc is None:
        return None

    date_str = dt_utc.strftime("%Y-%m-%d")
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,cloud_cover,precipitation,weather_code",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "hourly" not in data:
            return None

        # Point data at the specific hour
        hour = dt_utc.hour
        point_data = {
            "temperature": data["hourly"]["temperature_2m"][hour],
            "humidity": data["hourly"]["relative_humidity_2m"][hour],
            "wind_speed": data["hourly"]["wind_speed_10m"][hour] / 3.6, # Convert km/h to m/s
            "wind_gust": data["hourly"]["wind_gusts_10m"][hour] / 3.6,   # Convert km/h to m/s
            "cloud_cover": data["hourly"]["cloud_cover"][hour],
            "precipitation": data["hourly"]["precipitation"][hour],
            "condition": _get_weather_desc(data["hourly"]["weather_code"][hour])
        }

        # Time-series data (interpolated for the flight duration)
        # For simplicity, we'll return the raw hourly data for that day to the caller.
        time_series = {
            "time": data["hourly"]["time"],
            "temperature": data["hourly"]["temperature_2m"],
            "wind_speed": [v / 3.6 for v in data["hourly"]["wind_speed_10m"]],
            "wind_gust": [v / 3.6 for v in data["hourly"]["wind_gusts_10m"]],
            "cloud_cover": data["hourly"]["cloud_cover"],
            "precipitation": data["hourly"]["precipitation"]
        }

        return {"point": point_data, "hourly": time_series}
    except Exception as e:
        logging.error(f"Failed to fetch weather: {e}")
        return None

def _get_weather_desc(code):
    """Convert WMO weather code to description."""
    codes = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
    }
    return codes.get(code, "Unknown")
