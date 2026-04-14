"""Clipping plot compatibility module."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.plotting import _build_vibe_clippings  # noqa: E402


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


def clippings_panel(df_vibe):
    frames = _blank_frames()
    frames["vibe"] = df_vibe
    built = _build_vibe_clippings(frames)
    return built[0] if built else None

