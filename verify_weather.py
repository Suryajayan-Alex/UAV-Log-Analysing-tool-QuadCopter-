import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Add current directory to path so we can import our modules
sys.path.append(os.getcwd())

try:
    from weather_analyzer import get_weather_data
    print("Successfully imported weather_analyzer")
except ImportError as e:
    print(f"Failed to import weather_analyzer: {e}")
    sys.exit(1)

def test_weather():
    # Test coordinates for the local UAV operating area (approx Bangalore)
    lat, lon = 12.9716, 77.5946
    # Test date: Yesterday to ensure archive data exists
    dt = datetime.now(timezone.utc)
    print(f"Testing weather fetching for Bangalore at {dt}...")
    
    weather = get_weather_data(lat, lon, dt)
    if weather:
        print("Weather Fetch Success!")
        print(f"Temperature: {weather['temperature']}°C")
        print(f"Wind Speed: {weather['wind_speed']} km/h")
        print(f"Condition: {weather['condition']}")
    else:
        print("Weather Fetch Failed (returned None)")

if __name__ == "__main__":
    test_weather()
