"""
Editable formula definitions for the UAV analyzer.

Manual edit point:
- Update formulas/functions in this file to change computed values in plots/reports.
- The main analyzer engine imports and uses these functions directly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FORMULA_DICTIONARY = {
    # Reference: "NT-AP Log Diagnostic Guideline-090326-113936.pdf"
    # Keep formulas editable here so they can be tuned without changing plot engine code.
    "flight_distance": "sqrt(PSC.PX**2 + PSC.PY**2) or sqrt(PSCE.PE**2 + PSCN.PN**2)",
    "flight_altitude": "BARO[0].Alt",
    "flight_time": "GPA.SMS / 60000 or FT.flight_time / 60",
    "dbfs_estimated_mah": "(RTLE.RtlEst * 1.05) + BAT.CurrTot",
    "dbfs_available_mah": "9900 * 0.85",
    "gps_speed": "GPS[0].Spd",
    "psc_speed": "sqrt(PSC.VX**2 + PSC.VY**2) or sqrt(PSCE.VE**2 + PSCN.VN**2)",
    "gps_hdop": "GPS[0].HDop, GPS[1].HDop",
    "attitude_roll": "ATT.DesRoll, ATT.Roll",
    "attitude_pitch": "ATT.DesPitch, ATT.Pitch",
    "attitude_yaw": "ATT.DesYaw, ATT.Yaw",
    "vibe_clipping": "VIBE[0].Clip, VIBE[1].Clip, VIBE[2].Clip",
    "compass_heading": "mag_heading_df(MAG[0], ATT)",
    "compass_reference": "ATT.Yaw, AHR2.Yaw, GPS[0].GCrs, GPS[1].GCrs",
    "battery_voltage": "BAT.Volt",
    "battery_current": "BAT.Curr",
    "battery_energy_wh": "BAT.EnrgTot",
    "battery_capacity_mah_raw": "BAT.CurrTot",
    "battery_internal_resistance": "BAT.Res",
    "battery_mah": "BAT.CurrTot (fallback: integral(BAT.Curr[A] * dt) / 3600 * 1000)",
    "motor_output": "RCOU.C11, RCOU.C12, RCOU.C13, RCOU.C14",
    "rc_input": "RCIN.C1, RCIN.C2, RCIN.C3, RCIN.C4",
    "ekf_velocity_variances": "NKF3.IPN, NKF3.IPE, NKF3.IPD",
    "ekf_position_variances": "NKF4[0].SV, NKF4[1].SV, NKF4[2].SV",
    "ekf_height_variances": "NKF4[0].SP, NKF4[1].SP, NKF4[2].SP, NKF4[0].SH, NKF4[1].SH, NKF4[2].SH",
    "ekf_mag_variances": "NKF4[0].SM, NKF4[1].SM, NKF4[2].SM",
    "ekf_lane_switch": "NKF4.PI",
    "summary_line": "{signal} | Min:{min:.3f} Max:{max:.3f} Mean:{mean:.3f}",
}

PLOT_FORMULA_MAP = {
    "gps_sats": {
        "GPS0 NSats": "GPS[0].NSats",
        "GPS1 NSats": "GPS[1].NSats",
    },
    "gps_speed": {
        "GPS Speed": FORMULA_DICTIONARY["gps_speed"],
        "PSC Speed": FORMULA_DICTIONARY["psc_speed"],
    },
    "gps_hdop": {
        "GPS0 HDop": "GPS[0].HDop",
        "GPS1 HDop": "GPS[1].HDop",
    },
    "attitude": {
        "Roll": FORMULA_DICTIONARY["attitude_roll"],
        "Pitch": FORMULA_DICTIONARY["attitude_pitch"],
        "Yaw": FORMULA_DICTIONARY["attitude_yaw"],
    },
    "compass_heading": {
        "MAG Heading": FORMULA_DICTIONARY["compass_heading"],
        "Reference Yaw/Course": FORMULA_DICTIONARY["compass_reference"],
    },
    "compass_gcrs": {
        "GPS Course": "GPS[0].GCrs, GPS[1].GCrs",
    },
    "vibe_imu0": {
        "IMU0 Axes": "VIBE[0].VibeX, VIBE[0].VibeY, VIBE[0].VibeZ",
    },
    "vibe_imu1": {
        "IMU1 Axes": "VIBE[1].VibeX, VIBE[1].VibeY, VIBE[1].VibeZ",
    },
    "vibe_imu2": {
        "IMU2 Axes": "VIBE[2].VibeX, VIBE[2].VibeY, VIBE[2].VibeZ",
    },
    "vibe_clippings": {
        "IMU Clipping": FORMULA_DICTIONARY["vibe_clipping"],
    },
    "battery_cv": {
        "Voltage": FORMULA_DICTIONARY["battery_voltage"],
        "Current": FORMULA_DICTIONARY["battery_current"],
    },
    "battery_mah": {
        "Capacity Consumed (mAh)": FORMULA_DICTIONARY["battery_mah"],
    },
    "motor_output": {
        "Motor PWM": FORMULA_DICTIONARY["motor_output"],
    },
    "rc_input": {
        "RC Input PWM": FORMULA_DICTIONARY["rc_input"],
    },
    "ekf3": {
        "Velocity Variances": FORMULA_DICTIONARY["ekf_velocity_variances"],
    },
    "ekf4": {
        "Position/Height/Mag Variances": ", ".join(
            [
                FORMULA_DICTIONARY["ekf_position_variances"],
                FORMULA_DICTIONARY["ekf_height_variances"],
                FORMULA_DICTIONARY["ekf_mag_variances"],
            ]
        ),
    },
    "ekf9": {
        "Position Variance Lane 3": "NKF9.SV or NKF4[2].SV",
    },
}


def numeric(values: pd.Series | np.ndarray) -> np.ndarray:
    return pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)


def planar_speed(comp_a: pd.Series | np.ndarray, comp_b: pd.Series | np.ndarray) -> np.ndarray:
    """Default PSC speed formula: sqrt(a^2 + b^2)."""
    a = numeric(comp_a)
    b = numeric(comp_b)
    return np.sqrt(a**2 + b**2)


def compass_heading(mag_x: pd.Series | np.ndarray, mag_y: pd.Series | np.ndarray) -> np.ndarray:
    """Default compass heading formula from magnetometer XY wrapped to [0, 360)."""
    x = numeric(mag_x)
    y = numeric(mag_y)
    heading = np.degrees(np.arctan2(y, x))
    return np.mod(heading + 360.0, 360.0)


def battery_mah(t_values: pd.Series | np.ndarray, current_values: pd.Series | np.ndarray) -> np.ndarray:
    """Fallback battery consumption integration in mAh when BAT.CurrTot is unavailable."""
    t = numeric(t_values)
    current = numeric(current_values)

    mask = np.isfinite(t) & np.isfinite(current)
    t = t[mask]
    current = current[mask]

    if t.size == 0:
        return np.array([], dtype=float)
    if t.size == 1:
        return np.array([0.0], dtype=float)

    delta_t = np.diff(t)
    midpoint_current = (current[:-1] + current[1:]) / 2.0
    consumed_mah = np.concatenate([[0.0], np.cumsum(midpoint_current * delta_t)]) / 3600.0 * 1000.0
    return consumed_mah


def summary_line(signal: str, minimum: float, maximum: float, mean: float) -> str:
    """Summary row text used inside plot summary dialog."""
    return FORMULA_DICTIONARY["summary_line"].format(
        signal=signal,
        min=minimum,
        max=maximum,
        mean=mean,
    )
