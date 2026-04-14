"""Battery plots compatibility module."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.plotting import _build_battery_mah, _build_battery_voltage_current  # noqa: E402


def _blank_frames():
    return {
        "att": pd.DataFrame(),
        "gps": pd.DataFrame(),
        "baro": pd.DataFrame(),
        "psc": pd.DataFrame(),
        "psce": pd.DataFrame(),
        "pscn": pd.DataFrame(),
        "bat": pd.DataFrame(),
        "rcin": pd.DataFrame(),
        "rcou": pd.DataFrame(),
        "vibe": pd.DataFrame(),
        "nkf3": pd.DataFrame(),
        "nkf4": pd.DataFrame(),
        "nkf9": pd.DataFrame(),
        "mag": pd.DataFrame(),
        "ahr2": pd.DataFrame(),
    }


def battery_cv(df_bat):
    frames = _blank_frames()
    frames["bat"] = df_bat
    built = _build_battery_voltage_current(frames)
    return built[0] if built else None


def battery_mah(df_bat, has_scipy=False, cumtrapz=None):
    del has_scipy, cumtrapz
    frames = _blank_frames()
    frames["bat"] = df_bat
    built = _build_battery_mah(frames)
    return built[0] if built else None

