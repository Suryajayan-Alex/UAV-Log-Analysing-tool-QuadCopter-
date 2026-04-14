"""
Compatibility data module matching the reference layout.
Uses the upgraded parser backend and keeps the original function names.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.parser import (  # noqa: E402
    critical_messages as _critical_messages,
    extract_frames,
    read_log_messages as _read_log_messages,
)


def read_log_messages(path):
    return _read_log_messages(path)


def extract_all(messages):
    return extract_frames(messages)


def critical_messages(messages):
    return _critical_messages(messages)


def compute_metrics(dfs, has_scipy=False, cumtrapz=None):
    """
    Compute summary metrics used by report pages.
    """
    duration_s = None
    for df_key in ["gps", "att", "baro", "bat"]:
        df = dfs.get(df_key, pd.DataFrame())
        if not df.empty and "t" in df:
            duration_s = max(duration_s or 0, float(pd.to_numeric(df["t"], errors="coerce").max()))

    track_km = None
    df_gps = dfs.get("gps", pd.DataFrame())
    if not df_gps.empty and {"Lat", "Lng"}.issubset(df_gps.columns):
        lat = pd.to_numeric(df_gps["Lat"], errors="coerce").dropna().to_numpy()
        lng = pd.to_numeric(df_gps["Lng"], errors="coerce").dropna().to_numpy()
        if len(lat) > 1 and len(lng) > 1:
            lat_r = np.deg2rad(lat)
            lng_r = np.deg2rad(lng)
            dlat = np.diff(lat_r)
            dlng = np.diff(lng_r)
            a = np.sin(dlat / 2.0) ** 2 + np.cos(lat_r[:-1]) * np.cos(lat_r[1:]) * np.sin(dlng / 2.0) ** 2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
            dist_m = float(np.sum(6_371_000.0 * c))
            track_km = dist_m / 1000.0

    max_baro_alt = None
    df_baro = dfs.get("baro", pd.DataFrame())
    if not df_baro.empty and "Alt" in df_baro:
        src = df_baro
        if "I" in df_baro.columns:
            sub0 = df_baro[df_baro["I"].fillna(0) == 0]
            if not sub0.empty:
                src = sub0
        s_alt = pd.to_numeric(src["Alt"], errors="coerce").dropna()
        if len(s_alt):
            max_baro_alt = float(s_alt.max())

    bat_stats = {"current": None, "voltage": None, "mah_max": None}
    df_bat = dfs.get("bat", pd.DataFrame())
    if not df_bat.empty:
        if "Curr" in df_bat:
            s_i = pd.to_numeric(df_bat["Curr"], errors="coerce").dropna()
            if len(s_i):
                bat_stats["current"] = {"min": float(s_i.min()), "max": float(s_i.max()), "mean": float(s_i.mean())}
        if "Volt" in df_bat:
            s_v = pd.to_numeric(df_bat["Volt"], errors="coerce").dropna()
            if len(s_v):
                bat_stats["voltage"] = {"min": float(s_v.min()), "max": float(s_v.max())}

        if {"Curr", "t"}.issubset(df_bat.columns):
            t = pd.to_numeric(df_bat["t"], errors="coerce").to_numpy()
            i = pd.to_numeric(df_bat["Curr"], errors="coerce").fillna(0).to_numpy()
            mask = np.isfinite(t)
            t = t[mask]
            i = i[mask]
            try:
                if len(t) > 1:
                    if has_scipy and cumtrapz is not None:
                        m_ah = cumtrapz(i, t, initial=0) / 3600.0 * 1000.0
                    else:
                        dt = np.diff(t)
                        i_mid = (i[:-1] + i[1:]) / 2.0
                        m_ah = np.concatenate([[0.0], np.cumsum(i_mid * dt)]) / 3600.0 * 1000.0
                    bat_stats["mah_max"] = float(np.nanmax(m_ah)) if len(m_ah) else None
            except Exception:
                pass

    def gps_sats_stats(inst):
        sub = df_gps[df_gps["I"].fillna(0) == inst] if "I" in df_gps.columns else pd.DataFrame()
        s = pd.to_numeric(sub.get("NSats"), errors="coerce").dropna()
        if len(s):
            return {"min": float(s.min()), "max": float(s.max()), "mean": float(s.mean())}
        return None

    gps0_stats = gps_sats_stats(0)
    gps1_stats = gps_sats_stats(1)

    imu_stats = {0: {}, 1: {}, 2: {}}
    df_vibe = dfs.get("vibe", pd.DataFrame())

    def stat_series(series):
        s = pd.to_numeric(series, errors="coerce").dropna()
        if len(s):
            return {"min": float(s.min()), "max": float(s.max()), "mean": float(s.mean())}
        return None

    if not df_vibe.empty:
        for inst in [0, 1, 2]:
            sub = df_vibe[df_vibe["IMU"].fillna(inst) == inst] if "IMU" in df_vibe.columns else df_vibe
            if "VibeX" in sub:
                imu_stats[inst]["VibeX"] = stat_series(sub["VibeX"])
            if "VibeY" in sub:
                imu_stats[inst]["VibeY"] = stat_series(sub["VibeY"])
            if "VibeZ" in sub:
                imu_stats[inst]["VibeZ"] = stat_series(sub["VibeZ"])
            if "Clip" in sub:
                imu_stats[inst]["Clip"] = stat_series(sub["Clip"])

    return {
        "duration_s": duration_s,
        "track_km": track_km,
        "max_baro_alt": max_baro_alt,
        "battery": bat_stats,
        "gps0": gps0_stats,
        "gps1": gps1_stats,
        "imu": imu_stats,
    }

