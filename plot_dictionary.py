"""
Editable plot/signal dictionary for the UAV analyzer.

Manual edit point:
- Change column names, labels, enabled signal lists, or Y-axis limits here.
- The plotting engine reads these values while building plots.
"""

PLOT_DICTIONARY = {
    "gps_instances": [0, 1],
    "attitude_pairs": [
        ("Roll", "DesRoll", "Roll"),
        ("Pitch", "DesPitch", "Pitch"),
        ("Yaw", "DesYaw", "Yaw"),
    ],
    "vibe_axes": ["VibeX", "VibeY", "VibeZ"],
    "motor_channels": ["C11", "C12", "C13", "C14"],
    "rcin_channels": ["C1", "C2", "C3", "C4"],
    "ekf3_columns": ["IPN", "IPE", "IPD"],
    "ekf4_columns": ["SV", "SP", "SH", "SM"],
    "ekf9_columns": ["SV"],
}

# Default per-plot limits used directly by plotting.py.
# These values are editable and come from the "Y-Axis limits" entries in the guideline PDF.
Y_AXIS_LIMITS = {
    "gps_sats": (12.0, 30.0),
    "gps_speed": (0.0, 20.0),
    "gps_hdop": (0.0, 2.0),
    "attitude_roll": (-30.0, 30.0),
    "attitude_pitch": (-30.0, 30.0),
    "attitude_yaw": (0.0, 360.0),
    "compass_heading": (0.0, 360.0),
    "compass_gcrs": (0.0, 360.0),
    "vibe_imu0": (0.0, 60.0),
    "vibe_imu1": (0.0, 60.0),
    "vibe_imu2": (0.0, 60.0),
    "vibe_clippings": (0.0, 3600.0),
    "battery_cv_left": (17.0, 25.2),
    "battery_cv_right": (0.0, 35.0),
    "battery_mah": (0.0, 12000.0),
    "motor_output": (1000.0, 2000.0),
    "rc_input": (1000.0, 2000.0),
    "ekf3": (-10.0, 10.0),
    "ekf4": (0.0, 10.0),
    "ekf9": (0.0, 10.0),
}


# Acceptance limits used for PASS/FAIL checks.
# Rule format:
#   - metric "range": checks min/max are within [lower, upper]
#   - metric "max": checks maximum is within optional [lower, upper]
#   - metric "mean": checks mean is within optional [lower, upper]
#
# If an acceptance rule exists for a signal, it is preferred over Y_AXIS_LIMITS.
# If absent, PASS/FAIL falls back to Y_AXIS_LIMITS.
ACCEPTANCE_LIMITS = {
    "gps_sats": {"metric": "range", "lower": 12.0, "upper": 30.0},
    "gps_hdop": {"metric": "max", "upper": 1.0},
    "attitude_roll": {"metric": "range", "lower": -30.0, "upper": 30.0},
    "attitude_pitch": {"metric": "range", "lower": -25.0, "upper": 25.0},
    "vibe_imu0": {"metric": "mean", "upper": 60.0},
    "vibe_imu1": {"metric": "mean", "upper": 60.0},
    "vibe_imu2": {
        "__default__": {"metric": "mean", "upper": 60.0},
        "IMU2 VibeZ": {"metric": "mean", "upper": 30.0},
    },
    "vibe_clippings": {
        "IMU0 Clip": {"metric": "mean", "upper": 20.0},
        "IMU1 Clip": {"metric": "mean", "upper": 20.0},
        "IMU2 Clip": {"metric": "mean", "upper": 50.0},
    },
    "battery_cv_left": {"metric": "range", "lower": 17.0, "upper": 25.2},
    "battery_cv_right": {"metric": "mean", "upper": 15.0},
    "battery_mah": {"metric": "max", "lower": 7920.0, "upper": 8910.0},
    "ekf4": {
        "NKF4 SV": {"metric": "max", "upper": 1.0},
        "NKF4 SP": {"metric": "max", "upper": 1.0},
        "NKF4 SH": {"metric": "range", "lower": 0.0, "upper": 1.0},
        "NKF4 SM": {"metric": "max", "upper": 1.0},
    },
    "ekf9": {"metric": "max", "upper": 1.0},
}

# Detailed signal-level reference limits from the same PDF.
# Not all are directly applied in a combined multi-signal plot, but all are editable here.
SIGNAL_Y_AXIS_LIMITS = {
    "PSCE.PE/PSCN.PN distance": (0.0, 5000.0),
    "BARO[0].Alt": (0.0, 500.0),
    "GPA.SMS/60000": (0.0, 60.0),
    "FT.flight_time/60": (0.0, 60.0),
    "(RTLE.RtlEst*1.05)+BAT.CurrTot": (0.0, 12000.0),
    "BAT.Volt (6s)": (17.0, 25.2),
    "BAT.Volt (4s)": (12.0, 16.0),
    "BAT.Curr (6s)": (0.0, 35.0),
    "BAT.Curr (4s)": (0.0, 40.0),
    "BAT.EnrgTot (6s)": (0.0, 800.0),
    "BAT.EnrgTot (4s)": (0.0, 160.0),
    "BAT.CurrTot (6s)": (0.0, 40000.0),
    "BAT.CurrTot (4s)": (0.0, 16000.0),
    "BAT.Res": (0.0, 0.08),
    "RCOU.C11": (1000.0, 2000.0),
    "RCOU.C12": (1000.0, 2000.0),
    "RCOU.C13": (1000.0, 2000.0),
    "RCOU.C14": (1000.0, 2000.0),
    "ATT.DesRoll": (-30.0, 30.0),
    "ATT.Roll": (-30.0, 30.0),
    "ATT.DesPitch": (-30.0, 30.0),
    "ATT.Pitch": (-30.0, 30.0),
    "ATT.DesYaw": (0.0, 360.0),
    "ATT.Yaw": (0.0, 360.0),
    "VIBE[0].Clip": (0.0, 3600.0),
    "VIBE[1].Clip": (0.0, 3600.0),
    "VIBE[2].Clip": (0.0, 3600.0),
    "GPS[0].Spd": (0.0, 20.0),
    "PSC.VX": (-20.0, 20.0),
    "PSC.VY": (-20.0, 20.0),
    "PSCE.VE": (-20.0, 20.0),
    "PSCN.VN": (-20.0, 20.0),
    "GPS[0].NSats": (0.0, 30.0),
    "GPS[1].NSats": (0.0, 30.0),
    "GPS[0].HDop": (0.0, 2.0),
    "GPS[1].HDop": (0.0, 2.0),
    "NKF4[0].SP": (0.0, 1.2),
    "NKF3[0].IPN": (-3.0, 3.0),
    "NKF3[0].IPE": (-10.0, 10.0),
    "NKF3[0].IPD": (-10.0, 10.0),
    "NKF4[0].SV": (0.0, 10.0),
    "NKF4[1].SV": (0.0, 10.0),
    "NKF4[2].SV": (0.0, 10.0),
    "NKF4[0].SH": (0.0, 1.0),
    "NKF4[1].SH": (0.0, 1.0),
    "NKF4[2].SH": (0.0, 1.0),
    "NKF4[0].SM": (0.0, 1.0),
    "NKF4[1].SM": (0.0, 1.0),
    "NKF4[2].SM": (0.0, 1.0),
    "NKF4[0].PI": (0.0, 2.0),
    "MAG heading": (0.0, 360.0),
    "AHR2.Yaw": (0.0, 360.0),
    "GPS[0].GCrs": (0.0, 360.0),
    "GPS[1].GCrs": (0.0, 360.0),
    "MAG[0].OfsX": (-500.0, 500.0),
    "MAG[0].OfsY": (-500.0, 500.0),
    "MAG[0].OfsZ": (-500.0, 500.0),
    "MAG[0].MOX": (-100.0, 100.0),
    "MAG[0].MOY": (-100.0, 100.0),
    "MAG[0].MOZ": (-100.0, 100.0),
    "RCIN.C1": (1000.0, 2000.0),
    "RCIN.C2": (1000.0, 2000.0),
    "RCIN.C3": (1000.0, 2000.0),
    "RCIN.C4": (1000.0, 2000.0),
}

