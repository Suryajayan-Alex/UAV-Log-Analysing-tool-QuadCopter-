"""GPS plots compatibility module."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.plotting import (  # noqa: E402
    _build_gps_hdop,
    _build_gps_satellites,
    _build_gps_speed_vs_psc,
)


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


def gps_sats(df_gps):
    frames = _blank_frames()
    frames["gps"] = df_gps
    built = _build_gps_satellites(frames)
    return built[0] if built else None


def gps_health(df_gps, df_psc, df_psce, df_pscn):
    frames = _blank_frames()
    frames["gps"] = df_gps
    frames["psc"] = df_psc
    frames["psce"] = df_psce
    frames["pscn"] = df_pscn
    built = _build_gps_speed_vs_psc(frames)
    return built[0] if built else None


def gps_glitch(df_gps):
    frames = _blank_frames()
    frames["gps"] = df_gps
    built = _build_gps_hdop(frames)
    return built[0] if built else None

