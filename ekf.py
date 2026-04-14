"""EKF plots compatibility module."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.plotting import _build_ekf3, _build_ekf4, _build_ekf9  # noqa: E402


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


def ekf_variances(df_nkf3, df_nkf4, df_nkf9):
    frames = _blank_frames()
    frames["nkf3"] = df_nkf3
    frames["nkf4"] = df_nkf4
    frames["nkf9"] = df_nkf9

    out = {}
    built3 = _build_ekf3(frames)
    built4 = _build_ekf4(frames)
    built9 = _build_ekf9(frames)

    if built3:
        out["ekf3"] = built3[0]
    if built4:
        out["ekf4"] = built4[0]
    if built9:
        out["ekf9"] = built9[0]

    return out

