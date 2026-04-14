import numpy as np
import pandas as pd

class CurrentAnalyzer:
    def __init__(self, data):
        """
        data: list of dicts [{"time": float, "current": float}]
        """
        self.data = data
        self.PEAK_LIMIT = 31.0

    # ----------------------------
    # Over-Current Spike Detection
    # ----------------------------
    def detect_overcurrent_spikes(self):
        """
        Calculates the duration of every spike in seconds 
        where the current exceeds the peak threshold (31A). 
        Calculates start time, duration, and peak current for each event.
        """
        spikes = []
        spike_active = False
        start_time = 0.0
        max_current = 0.0

        for i in range(len(self.data)):
            current = self.data[i]["current"]
            time = self.data[i]["time"]

            if current > self.PEAK_LIMIT:
                if not spike_active:
                    start_time = time
                    max_current = current
                    spike_active = True
                else:
                    max_current = max(max_current, current)
            else:
                if spike_active:
                    end_time = time
                    duration = end_time - start_time

                    spikes.append({
                        "start": start_time,
                        "end": end_time,
                        "duration": duration,
                        "max_current": max_current,
                        "status": "SPIKE"
                    })
                    spike_active = False

        if spike_active:
            end_time = self.data[-1]["time"]
            duration = end_time - start_time
            spikes.append({
                "start": start_time,
                "end": end_time,
                "duration": duration,
                "max_current": max_current,
                "status": "SPIKE"
            })

        return spikes

    # ----------------------------
    # Full Analysis
    # ----------------------------
    def analyze(self):
        spikes = self.detect_overcurrent_spikes()
        
        return {
            "spike_events": spikes,
            "total_spikes": len(spikes)
        }

def evaluate_current_stress(frames: dict[str, pd.DataFrame]) -> dict[str, object]:
    """
    Adapter function to integrate CurrentAnalyzer with the dataframe pipeline.
    """
    df_bat = frames.get('bat', pd.DataFrame())
    if df_bat.empty or 't' not in df_bat.columns or 'Curr' not in df_bat.columns:
        return {"error": "Battery current data not available"}

    # Format data for CurrentAnalyzer
    data = []
    # Drop rows with NaN in t or Curr to avoid issues
    df_bat_clean = df_bat.dropna(subset=['t', 'Curr'])
    for _, row in df_bat_clean.iterrows():
        data.append({"time": float(row['t']), "current": float(row['Curr'])})

    # Run Analysis
    analyzer = CurrentAnalyzer(data)
    results = analyzer.analyze()
    
    # Pack for pipeline delivery
    return {
        "results": results,
        "peak_limit": analyzer.PEAK_LIMIT,
    }
