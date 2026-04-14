import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

def generate_weather_plots(weather_timeseries, output_folder, flight_utc_armed, duration_min):
    """
    Generate 5 separate weather time-series plots for the exact flight duration.
    Returns a list of image paths.
    """
    if not weather_timeseries or not weather_timeseries.get("time"):
        return []

    # Convert API hourly time strings to timezone-naive datetime objects (assume UTC)
    # Then offset by +5:30 to get IST (Indian Standard Time)
    ist_offset = timedelta(hours=5, minutes=30)
    times_utc = [datetime.fromisoformat(t[:16]) for t in weather_timeseries["time"]]
    times_ist = [t + ist_offset for t in times_utc]
    
    # Create a DataFrame
    df = pd.DataFrame({
        "time": times_ist,
        "temperature": weather_timeseries.get("temperature", [0]*len(times_utc)),
        "wind_speed": weather_timeseries["wind_speed"],
        "wind_gust": weather_timeseries["wind_gust"],
        "cloud_cover": weather_timeseries["cloud_cover"],
        "precipitation": weather_timeseries["precipitation"]
    })

    # Set time as index for interpolation
    df.set_index("time", inplace=True)
    
    # Resample to 1-minute intervals and interpolate linearly
    # Add passing .bfill() and .ffill() to handle leading/trailing None values from Open-Meteo
    df_minutely = df.resample('1Min').interpolate(method='linear').bfill().ffill()
    df_minutely.reset_index(inplace=True)

    # Calculate exact flight window with a small 5-minute padding for visual context
    # Add IST offset to the armed time
    flight_tz_naive = flight_utc_armed.replace(tzinfo=None)
    flight_ist_armed = flight_tz_naive + ist_offset
    
    flight_end = flight_ist_armed + timedelta(minutes=duration_min)
    plot_start = flight_ist_armed - timedelta(minutes=5)
    plot_end = flight_end + timedelta(minutes=5)

    # Filter to just the plot window
    mask = (df_minutely["time"] >= plot_start) & (df_minutely["time"] <= plot_end)
    df_plot = df_minutely[mask]

    if df_plot.empty:
        return []

    plot_paths = []
    
    # Define parameters for each plot: (Column, Title, YLabel, Color, Formatting)
    plot_configs = [
        ("temperature", "Temperature (C)", "Temp (°C)", "#e67e22", "plot"),
        ("wind_speed", "Wind Speed (m/s)", "Speed (m/s)", "#3498db", "plot"),
        ("wind_gust", "Wind Gust (m/s)", "Gust (m/s)", "#e74c3c", "plot"),
        ("cloud_cover", "Cloud Cover (%)", "Cover (%)", "#95a5a6", "fill"),
        ("precipitation", "Precipitation (mm)", "Precip (mm)", "#2980b9", "bar")
    ]

    for col, title, ylabel, color, ptype in plot_configs:
        fig, ax = plt.subplots(figsize=(10, 5))
        
        if ptype == "plot":
            ax.plot(df_plot["time"], df_plot[col], color=color, linewidth=2.5)
        elif ptype == "fill":
            ax.fill_between(df_plot["time"], df_plot[col], color=color, alpha=0.4)
            ax.plot(df_plot["time"], df_plot[col], color=color, linewidth=2)
            ax.set_ylim(0, max(100, df_plot[col].max() + 10))
        elif ptype == "bar":
            ax.bar(df_plot["time"], df_plot[col], width=0.001, color=color, alpha=0.7)
            ax.set_ylim(0, max(2.5, df_plot[col].max() + 0.5))

        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.grid(True, alpha=0.3, linestyle="--")
        
        # Shade the exact flight duration
        ax.axvspan(flight_ist_armed, flight_end, color='yellow', alpha=0.15, label='Flight Period')
        ax.legend(loc="upper right")

        # Format X axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        fig.autofmt_xdate(rotation=45)

        # Remove top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Save plot
        p_path = Path(output_folder) / f"weather_trend_{col}.png"
        plt.savefig(p_path, bbox_inches='tight', dpi=150)
        plt.close(fig)
        
        plot_paths.append(str(p_path))

    return plot_paths
