from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import dedent
import math
import shutil

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RunPaths:
    database_root: Path
    system_id: str
    date_folder: str
    run_id: str
    run_folder: Path
    plots_folder: Path


@dataclass(frozen=True)
class ComparisonResult:
    output_folder: Path
    plot_paths: list[Path]
    titles: list[str]


def _safe_token(text: str, fallback: str = "NA") -> str:
    token = "_".join((text or "").strip().split())
    token = "".join(ch for ch in token if ch.isalnum() or ch in {"_", "-"})
    return token or fallback


def _numeric(series: pd.Series | np.ndarray) -> np.ndarray:
    return pd.to_numeric(pd.Series(series), errors="coerce").to_numpy(dtype=float)


def _relative_seconds(msg: object, t0_us: float | None, t0_ms: float | None) -> float | None:
    t_us = getattr(msg, "TimeUS", None)
    if t_us is not None:
        try:
            t = float(t_us)
            if t0_us is None:
                return 0.0
            return max(0.0, (t - t0_us) / 1_000_000.0)
        except Exception:
            pass

    t_ms = getattr(msg, "TimeMS", None)
    if t_ms is not None:
        try:
            t = float(t_ms)
            if t0_ms is None:
                return 0.0
            return max(0.0, (t - t0_ms) / 1000.0)
        except Exception:
            pass

    return None


def _haversine_distance_km(lat_deg: np.ndarray, lon_deg: np.ndarray) -> float:
    if lat_deg.size < 2 or lon_deg.size < 2:
        return 0.0

    lat = np.deg2rad(lat_deg)
    lon = np.deg2rad(lon_deg)
    dlat = np.diff(lat)
    dlon = np.diff(lon)
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon / 2.0) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return float(np.nansum(6371.0 * c))


def _series_stats(values: np.ndarray) -> tuple[float, float, float] | None:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None
    return float(np.min(finite)), float(np.max(finite)), float(np.mean(finite))


def build_run_paths(
    *,
    log_path: Path,
    system_id: str,
    output_root: Path | None = None,
    now: datetime | None = None,
) -> RunPaths:
    timestamp = now or datetime.now()

    safe_system = _safe_token(system_id, fallback="UAV")
    safe_log_name = _safe_token(log_path.stem, fallback="LOG")
    run_id = f"{safe_system}_{safe_log_name}_{timestamp:%Y%m%d_%H%M%S}"

    parent = output_root.resolve() if output_root else log_path.resolve().parent
    database_root = parent / "UAV_LOG_DATABASE"
    date_folder = timestamp.strftime("%Y-%m-%d")

    run_folder = database_root / safe_system / date_folder / run_id
    plots_folder = run_folder / "Plots"

    plots_folder.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        database_root=database_root,
        system_id=safe_system,
        date_folder=date_folder,
        run_id=run_id,
        run_folder=run_folder,
        plots_folder=plots_folder,
    )


def compute_flight_summary(frames: dict[str, pd.DataFrame]) -> dict[str, float]:
    duration_s = 0.0
    for key, df in frames.items():
        if isinstance(df, pd.DataFrame) and not df.empty and "t" in df.columns:
            try:
                t_max = float(np.nanmax(_numeric(df["t"])))
                duration_s = max(duration_s, t_max)
            except Exception:
                pass

    max_speed = 0.0
    avg_ground_speed = 0.0
    gps_df = frames.get("gps", pd.DataFrame())
    if not gps_df.empty and "Spd" in gps_df.columns:
        spd = _numeric(gps_df["Spd"])
        stats = _series_stats(spd)
        if stats:
            _, max_speed, avg_ground_speed = stats

    max_altitude = 0.0
    baro_df = frames.get("baro", pd.DataFrame())
    if not baro_df.empty and "Alt" in baro_df.columns:
        alt = _numeric(baro_df["Alt"])
        stats = _series_stats(alt)
        if stats:
            _, max_altitude, _ = stats
    elif not gps_df.empty and "Alt" in gps_df.columns:
        alt = _numeric(gps_df["Alt"])
        stats = _series_stats(alt)
        if stats:
            _, max_altitude, _ = stats

    avg_gps_sats = 0.0
    if not gps_df.empty and "NSats" in gps_df.columns:
        sats = _numeric(gps_df["NSats"])
        stats = _series_stats(sats)
        if stats:
            _, _, avg_gps_sats = stats

    flight_distance_km = 0.0
    if not gps_df.empty and {"Lat", "Lng"}.issubset(gps_df.columns):
        lat = _numeric(gps_df["Lat"])
        lon = _numeric(gps_df["Lng"])
        mask = np.isfinite(lat) & np.isfinite(lon)
        if np.count_nonzero(mask) > 1:
            flight_distance_km = _haversine_distance_km(lat[mask], lon[mask])

    battery_consumption_mah = 0.0
    bat_df = frames.get("bat", pd.DataFrame())
    if not bat_df.empty:
        if "CurrTot" in bat_df.columns:
            curr_tot = _numeric(bat_df["CurrTot"])
            finite = curr_tot[np.isfinite(curr_tot)]
            if finite.size:
                battery_consumption_mah = float(np.nanmax(finite))

        if battery_consumption_mah <= 0.0 and {"Curr", "t"}.issubset(bat_df.columns):
            t = _numeric(bat_df["t"])
            current = _numeric(bat_df["Curr"])
            mask = np.isfinite(t) & np.isfinite(current)
            t = t[mask]
            current = current[mask]
            if t.size > 1:
                dt = np.diff(t)
                i_mid = (current[:-1] + current[1:]) / 2.0
                consumed = np.concatenate([[0.0], np.cumsum(i_mid * dt)]) / 3600.0 * 1000.0
                battery_consumption_mah = float(np.nanmax(consumed)) if consumed.size else 0.0

    return {
        "flight_duration_s": float(duration_s),
        "maximum_speed_mps": float(max_speed),
        "maximum_altitude_m": float(max_altitude),
        "average_gps_satellites": float(avg_gps_sats),
        "battery_consumption_mah": float(battery_consumption_mah),
        "flight_distance_km": float(flight_distance_km),
        "average_ground_speed_mps": float(avg_ground_speed),
    }


def detect_flight_anomalies(frames: dict[str, pd.DataFrame]) -> list[str]:
    warnings: list[str] = []

    vibe_df = frames.get("vibe", pd.DataFrame())
    if not vibe_df.empty and {"VibeX", "VibeY", "VibeZ"}.issubset(vibe_df.columns):
        for imu in [0, 1, 2]:
            sub = vibe_df[vibe_df.get("IMU", pd.Series(dtype=float)).fillna(imu) == imu] if "IMU" in vibe_df.columns else vibe_df
            if sub.empty:
                continue
            axis_means = []
            for col in ["VibeX", "VibeY", "VibeZ"]:
                vals = _numeric(sub[col])
                stats = _series_stats(vals)
                if stats:
                    axis_means.append(stats[2])
            if not axis_means:
                continue
            mean_vibe = float(np.mean(axis_means))
            limit = 120.0 if imu == 2 else 60.0
            if mean_vibe > limit:
                warnings.append(f"High IMU vibration detected on IMU{imu} (mean={mean_vibe:.2f}).")

    gps_df = frames.get("gps", pd.DataFrame())
    if not gps_df.empty and "NSats" in gps_df.columns:
        sats = _numeric(gps_df["NSats"])
        finite = sats[np.isfinite(sats)]
        if finite.size and float(np.nanmin(finite)) < 10.0:
            warnings.append("GPS satellites dropped below threshold (NSats < 10).")

    bat_df = frames.get("bat", pd.DataFrame())
    if not bat_df.empty and "Volt" in bat_df.columns:
        volt = _numeric(bat_df["Volt"])
        finite = volt[np.isfinite(volt)]
        if finite.size and float(np.nanmin(finite)) < 18.0:
            warnings.append("Battery voltage sag detected (minimum voltage below 18V).")

    mag_df = frames.get("mag", pd.DataFrame())
    att_df = frames.get("att", pd.DataFrame())
    if not mag_df.empty and not att_df.empty and {"t", "MagX", "MagY"}.issubset(mag_df.columns) and {"t", "Yaw"}.issubset(att_df.columns):
        t_mag = _numeric(mag_df["t"])
        mx = _numeric(mag_df["MagX"])
        my = _numeric(mag_df["MagY"])
        t_att = _numeric(att_df["t"])
        yaw = _numeric(att_df["Yaw"])

        m_mask = np.isfinite(t_mag) & np.isfinite(mx) & np.isfinite(my)
        a_mask = np.isfinite(t_att) & np.isfinite(yaw)

        if np.count_nonzero(m_mask) > 5 and np.count_nonzero(a_mask) > 5:
            t_common = np.union1d(t_mag[m_mask], t_att[a_mask])
            heading_mag = np.degrees(np.arctan2(my[m_mask], mx[m_mask]))
            interp_mag = np.interp(t_common, t_mag[m_mask], heading_mag)
            interp_yaw = np.interp(t_common, t_att[a_mask], yaw[a_mask])
            diff = np.abs((interp_mag - interp_yaw + 180.0) % 360.0 - 180.0)
            if diff.size and float(np.nanmean(diff)) > 25.0:
                warnings.append("Compass heading mismatch detected (MAG vs ATT Yaw).")

    rcin_df = frames.get("rcin", pd.DataFrame())
    if not rcin_df.empty and {"C1", "C2", "C3", "C4"}.issubset(rcin_df.columns):
        for ch in ["C1", "C2", "C3", "C4"]:
            vals = _numeric(rcin_df[ch])
            finite = vals[np.isfinite(vals)]
            if finite.size and (float(np.nanmin(finite)) < 900.0 or float(np.nanmax(finite)) > 2100.0):
                warnings.append(f"RC signal anomaly detected on {ch}.")
                break

    if not gps_df.empty and {"t", "Spd"}.issubset(gps_df.columns):
        t = _numeric(gps_df["t"])
        spd = _numeric(gps_df["Spd"])
        mask = np.isfinite(t) & np.isfinite(spd)
        t = t[mask]
        spd = spd[mask]
        if t.size > 3:
            dt = np.diff(t)
            dv = np.diff(spd)
            with np.errstate(divide="ignore", invalid="ignore"):
                accel = np.abs(np.divide(dv, dt, out=np.zeros_like(dv), where=dt > 1e-6))
            if accel.size and float(np.nanmax(accel)) > 8.0:
                warnings.append("Speed spike detected (high acceleration event).")

    alt_df = frames.get("baro", pd.DataFrame())
    if not alt_df.empty and {"t", "Alt"}.issubset(alt_df.columns):
        t = _numeric(alt_df["t"])
        alt = _numeric(alt_df["Alt"])
        mask = np.isfinite(t) & np.isfinite(alt)
        t = t[mask]
        alt = alt[mask]
        if t.size > 3:
            dt = np.diff(t)
            dz = np.diff(alt)
            with np.errstate(divide="ignore", invalid="ignore"):
                climb_rate = np.abs(np.divide(dz, dt, out=np.zeros_like(dz), where=dt > 1e-6))
            if climb_rate.size and float(np.nanmax(climb_rate)) > 10.0:
                warnings.append("Altitude spike detected (rapid climb/descent event).")

    # Keep order stable and remove duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for item in warnings:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def extract_flight_timeline(messages: list[object]) -> list[dict[str, object]]:
    t0_us: float | None = None
    t0_ms: float | None = None

    for msg in messages:
        if t0_us is None and getattr(msg, "TimeUS", None) is not None:
            try:
                t0_us = float(getattr(msg, "TimeUS"))
            except Exception:
                pass
        if t0_ms is None and getattr(msg, "TimeMS", None) is not None:
            try:
                t0_ms = float(getattr(msg, "TimeMS"))
            except Exception:
                pass
        if t0_us is not None or t0_ms is not None:
            break

    events: list[tuple[float, str]] = [(0.0, "System Boot")]

    keyword_map = [
        ("armed", "Motors Armed"),
        ("arm", "Motors Armed"),
        ("takeoff", "Takeoff"),
        ("mission", "Mission Start"),
        ("waypoint", "Waypoint Navigation"),
        ("rtl", "Return to Launch"),
        ("land", "Landing"),
    ]

    for msg in messages:
        t_rel = _relative_seconds(msg, t0_us, t0_ms)
        if t_rel is None:
            continue

        msg_type = str(msg.get_type())

        if msg_type == "MODE":
            mode = getattr(msg, "Mode", None) or getattr(msg, "mode", None)
            if mode:
                events.append((t_rel, f"Mode: {mode}"))

        if msg_type == "MSG":
            raw = getattr(msg, "Message", None) or getattr(msg, "Msg", "")
            text = str(raw).strip()
            low = text.lower()
            for key, label in keyword_map:
                if key in low:
                    events.append((t_rel, label))

    # keep first occurrence for semantic labels
    important_order = [
        "System Boot",
        "Motors Armed",
        "Takeoff",
        "Mission Start",
        "Waypoint Navigation",
        "Return to Launch",
        "Landing",
    ]

    selected: list[tuple[float, str]] = []
    for label in important_order:
        matches = [item for item in events if item[1] == label]
        if matches:
            selected.append(min(matches, key=lambda i: i[0]))

    # Include up to a few mode events for extra context.
    mode_events = sorted([item for item in events if item[1].startswith("Mode:")], key=lambda i: i[0])
    selected.extend(mode_events[:6])

    selected = sorted(selected, key=lambda i: i[0])

    timeline: list[dict[str, object]] = []
    seen: set[tuple[int, str]] = set()
    for t_s, label in selected:
        minute = int(t_s // 60)
        second = int(t_s % 60)
        key = (int(round(t_s)), label)
        if key in seen:
            continue
        seen.add(key)
        timeline.append(
            {
                "time_s": float(t_s),
                "time": f"{minute:02d}:{second:02d}",
                "event": label,
            }
        )

    return timeline


def compute_quality_assessment(frames: dict[str, pd.DataFrame], summary: dict[str, float], warnings: list[str]) -> dict[str, object]:
    gps_score = 25.0
    avg_sats = float(summary.get("average_gps_satellites", 0.0))
    if avg_sats < 12:
        gps_score = 10.0
    elif avg_sats < 15:
        gps_score = 18.0

    imu_score = 25.0
    vibe_df = frames.get("vibe", pd.DataFrame())
    imu_means: list[float] = []
    if not vibe_df.empty and {"VibeX", "VibeY", "VibeZ"}.issubset(vibe_df.columns):
        for imu in [0, 1, 2]:
            sub = vibe_df[vibe_df.get("IMU", pd.Series(dtype=float)).fillna(imu) == imu] if "IMU" in vibe_df.columns else vibe_df
            if sub.empty:
                continue
            means = []
            for col in ["VibeX", "VibeY", "VibeZ"]:
                stats = _series_stats(_numeric(sub[col]))
                if stats:
                    means.append(stats[2])
            if means:
                imu_means.append(float(np.mean(means)))
    max_imu_mean = max(imu_means) if imu_means else 0.0
    if max_imu_mean > 120:
        imu_score = 8.0
    elif max_imu_mean > 80:
        imu_score = 15.0

    battery_score = 25.0
    bat_df = frames.get("bat", pd.DataFrame())
    min_volt = None
    if not bat_df.empty and "Volt" in bat_df.columns:
        vals = _numeric(bat_df["Volt"])
        finite = vals[np.isfinite(vals)]
        if finite.size:
            min_volt = float(np.nanmin(finite))
    if min_volt is not None:
        if min_volt < 17.0:
            battery_score = 8.0
        elif min_volt < 18.0:
            battery_score = 15.0

    stability_score = 25.0
    att_df = frames.get("att", pd.DataFrame())
    error_values: list[float] = []
    if not att_df.empty:
        for actual, desired in [("Roll", "DesRoll"), ("Pitch", "DesPitch"), ("Yaw", "DesYaw")]:
            if actual not in att_df.columns or desired not in att_df.columns:
                continue
            a = _numeric(att_df[actual])
            d = _numeric(att_df[desired])
            mask = np.isfinite(a) & np.isfinite(d)
            if np.count_nonzero(mask) > 10:
                diff = np.abs(a[mask] - d[mask])
                error_values.append(float(np.nanmean(diff)))
    mean_error = float(np.mean(error_values)) if error_values else 0.0
    if mean_error > 25:
        stability_score = 8.0
    elif mean_error > 15:
        stability_score = 15.0

    total_score = max(0.0, min(100.0, gps_score + imu_score + battery_score + stability_score))

    components = {
        "GPS HEALTH": {
            "score": gps_score,
            "status": "PASS" if gps_score >= 18.0 else "FAIL",
        },
        "IMU VIBRATION": {
            "score": imu_score,
            "status": "PASS" if imu_score >= 18.0 else "FAIL",
        },
        "BATTERY PERFORMANCE": {
            "score": battery_score,
            "status": "PASS" if battery_score >= 18.0 else "FAIL",
        },
        "FLIGHT STABILITY": {
            "score": stability_score,
            "status": "PASS" if stability_score >= 18.0 else "FAIL",
        },
    }

    # Ensure severe warnings force FAIL.
    severe_markers = ["sag", "mismatch", "spike", "signal anomaly", "high imu vibration"]
    severe_hit = any(any(marker in item.lower() for marker in severe_markers) for item in warnings)

    final_result = "PASS" if all(v["status"] == "PASS" for v in components.values()) and not severe_hit else "FAIL"

    return {
        "flight_score": round(total_score, 1),
        "components": components,
        "final_result": final_result,
    }


def write_text_outputs(
    *,
    run_folder: Path,
    summary: dict[str, float],
    warnings: list[str],
    quality: dict[str, object],
    timeline: list[dict[str, object]],
    run_id: str,
) -> dict[str, Path]:
    summary_path = run_folder / "Flight_Summary.txt"
    warnings_path = run_folder / "Warnings.txt"
    quality_path = run_folder / "Quality_Check.txt"

    summary_text = dedent(
        f"""
        Run ID: {run_id}

        Flight Duration (s): {summary.get('flight_duration_s', 0.0):.2f}
        Maximum Speed (m/s): {summary.get('maximum_speed_mps', 0.0):.2f}
        Maximum Altitude (m): {summary.get('maximum_altitude_m', 0.0):.2f}
        Average GPS Satellites: {summary.get('average_gps_satellites', 0.0):.2f}
        Battery Consumption (mAh): {summary.get('battery_consumption_mah', 0.0):.2f}
        Flight Distance (km): {summary.get('flight_distance_km', 0.0):.3f}
        Average Ground Speed (m/s): {summary.get('average_ground_speed_mps', 0.0):.2f}

        Timeline:
        """
    ).strip()

    timeline_lines = [f"{item.get('time', '00:00')}  {item.get('event', '')}" for item in timeline]
    if not timeline_lines:
        timeline_lines.append("00:00  System Boot")

    summary_path.write_text(summary_text + "\n" + "\n".join(timeline_lines) + "\n", encoding="utf-8")

    if warnings:
        warnings_path.write_text("\n".join(f"- {item}" for item in warnings) + "\n", encoding="utf-8")
    else:
        warnings_path.write_text("No anomalies detected.\n", encoding="utf-8")

    quality_lines = ["Flight Quality Report", ""]
    components = quality.get("components", {})
    if isinstance(components, dict):
        for name in ["GPS HEALTH", "IMU VIBRATION", "BATTERY PERFORMANCE", "FLIGHT STABILITY"]:
            comp = components.get(name, {})
            status = comp.get("status", "N/A") if isinstance(comp, dict) else "N/A"
            quality_lines.append(f"{name} : {status}")

    quality_lines.append("")
    quality_lines.append(f"Flight Score: {quality.get('flight_score', 0)} / 100")
    quality_lines.append(f"FINAL RESULT : {quality.get('final_result', 'N/A')}")

    quality_path.write_text("\n".join(quality_lines) + "\n", encoding="utf-8")

    return {
        "summary_path": summary_path,
        "warnings_path": warnings_path,
        "quality_path": quality_path,
    }


def copy_raw_log(log_path: Path, run_folder: Path) -> Path:
    destination = run_folder / log_path.name
    shutil.copy2(log_path, destination)
    return destination


def _series_for_dashboard(frames: dict[str, pd.DataFrame], key: str, column: str, *, instance: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    df = frames.get(key, pd.DataFrame())
    if df.empty or "t" not in df.columns or column not in df.columns:
        return np.array([], dtype=float), np.array([], dtype=float)

    source = df
    if instance is not None and "I" in source.columns:
        source = source[source["I"].fillna(instance) == instance]
    if instance is not None and "IMU" in source.columns:
        source = source[source["IMU"].fillna(instance) == instance]

    if source.empty:
        return np.array([], dtype=float), np.array([], dtype=float)

    t = _numeric(source["t"])
    y = _numeric(source[column])
    mask = np.isfinite(t) & np.isfinite(y)
    return t[mask], y[mask]


def generate_interactive_dashboard(frames: dict[str, pd.DataFrame], output_html: Path) -> bool:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except Exception:
        fallback = dedent(
            """
            <html>
              <head><title>Interactive Dashboard Unavailable</title></head>
              <body style='font-family:Segoe UI,Arial,sans-serif;padding:24px;'>
                <h2>Interactive Dashboard</h2>
                <p>Plotly is not installed in this Python environment.</p>
                <p>Install <code>plotly</code> to enable interactive dashboard rendering in the GUI.</p>
              </body>
            </html>
            """
        ).strip()
        output_html.write_text(fallback, encoding="utf-8")
        return False

    # ── Subplot definitions ──────────────────────────────────────────────────
    SUBPLOT_TITLES = (
        "GPS Speed (m/s)",
        "Altitude (m)",
        "Battery Voltage (V)",
        "IMU Vibration Magnitude",
        "Attitude – Roll / Pitch / Yaw (deg)",
        "GPS Satellites",
    )
    NUM_ROWS = len(SUBPLOT_TITLES)

    fig = make_subplots(
        rows=NUM_ROWS,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=SUBPLOT_TITLES,
    )

    # ── Signal traces ────────────────────────────────────────────────────────
    t, y = _series_for_dashboard(frames, "gps", "Spd", instance=0)
    if y.size:
        fig.add_trace(go.Scatter(x=t, y=y, mode="lines", name="GPS Speed",
                                 line=dict(color="#0D4DA1", width=1.4)), row=1, col=1)

    t_alt, y_alt = _series_for_dashboard(frames, "baro", "Alt", instance=0)
    if y_alt.size == 0:
        t_alt, y_alt = _series_for_dashboard(frames, "gps", "Alt", instance=0)
    if y_alt.size:
        fig.add_trace(go.Scatter(x=t_alt, y=y_alt, mode="lines", name="Altitude",
                                 line=dict(color="#1F8A57", width=1.4)), row=2, col=1)

    t_v, y_v = _series_for_dashboard(frames, "bat", "Volt")
    t_c, y_c = _series_for_dashboard(frames, "bat", "Curr")
    if y_v.size:
        fig.add_trace(go.Scatter(x=t_v, y=y_v, mode="lines", name="Battery Voltage",
                                 line=dict(color="#E07B00", width=1.4)), row=3, col=1)
    if y_c.size:
        fig.add_trace(go.Scatter(x=t_c, y=y_c, mode="lines", name="Battery Current",
                                 line=dict(color="#B84545", width=1.4),
                                 yaxis="y3b"), row=3, col=1)

    for imu, color in [(0, "#0D4DA1"), (1, "#1F8A57"), (2, "#B84545")]:
        t_x, v_x = _series_for_dashboard(frames, "vibe", "VibeX", instance=imu)
        t_y, v_y = _series_for_dashboard(frames, "vibe", "VibeY", instance=imu)
        t_z, v_z = _series_for_dashboard(frames, "vibe", "VibeZ", instance=imu)
        if t_x.size and t_y.size and t_z.size:
            common_t = np.union1d(np.union1d(t_x, t_y), t_z)
            interp_x = np.interp(common_t, t_x, v_x)
            interp_y = np.interp(common_t, t_y, v_y)
            interp_z = np.interp(common_t, t_z, v_z)
            vibe_mag = np.sqrt(interp_x**2 + interp_y**2 + interp_z**2)
            fig.add_trace(
                go.Scatter(x=common_t, y=vibe_mag, mode="lines", name=f"IMU{imu} Vibe",
                           line=dict(color=color, width=1.2)),
                row=4, col=1,
            )

    t_roll, y_roll = _series_for_dashboard(frames, "att", "Roll")
    t_pitch, y_pitch = _series_for_dashboard(frames, "att", "Pitch")
    t_yaw, y_yaw = _series_for_dashboard(frames, "att", "Yaw")
    if y_roll.size:
        fig.add_trace(go.Scatter(x=t_roll, y=y_roll, mode="lines", name="Roll",
                                 line=dict(color="#0D4DA1", width=1.3)), row=5, col=1)
    if y_pitch.size:
        fig.add_trace(go.Scatter(x=t_pitch, y=y_pitch, mode="lines", name="Pitch",
                                 line=dict(color="#B84545", width=1.3)), row=5, col=1)
    if y_yaw.size:
        fig.add_trace(go.Scatter(x=t_yaw, y=y_yaw, mode="lines", name="Yaw",
                                 line=dict(color="#1F8A57", width=1.3)), row=5, col=1)

    for gps_inst in [0, 1]:
        t_s, y_s = _series_for_dashboard(frames, "gps", "NSats", instance=gps_inst)
        if y_s.size:
            fig.add_trace(go.Scatter(x=t_s, y=y_s, mode="lines", name=f"GPS{gps_inst} NSats",
                                     line=dict(width=1.4)), row=6, col=1)

    # ── Flight-mode bands across ALL subplots ────────────────────────────────
    _MODE_PALETTE = {
        "STABILIZE": ("rgba(174,214,241,0.30)", "#1A5276"),
        "ACRO":      ("rgba(169,223,191,0.30)", "#1D6A39"),
        "ALT HOLD":  ("rgba(169,204,227,0.30)", "#1A5276"),
        "AUTO":      ("rgba(250,219,216,0.30)", "#922B21"),
        "GUIDED":    ("rgba(215,189,226,0.30)", "#6C3483"),
        "LOITER":    ("rgba(250,215,160,0.30)", "#7D6608"),
        "RTL":       ("rgba(162,217,206,0.30)", "#148F77"),
        "CIRCLE":    ("rgba(213,216,220,0.30)", "#5D6D7E"),
        "LAND":      ("rgba(171,235,198,0.30)", "#1E8449"),
        "POSHOLD":   ("rgba(249,231,159,0.30)", "#7D6608"),
        "BRAKE":     ("rgba(245,203,167,0.30)", "#784212"),
        "SMART_RTL": ("rgba(169,223,191,0.30)", "#1D6A39"),
    }
    _DEFAULT_PALETTE = ("rgba(232,234,246,0.25)", "#424242")

    df_mode = frames.get("mode", pd.DataFrame())
    shapes: list[dict] = []
    annotations: list[dict] = []

    if not df_mode.empty and "t" in df_mode.columns and "mode_name" in df_mode.columns:
        mode_rows = df_mode.sort_values("t")[["t", "mode_name"]].dropna().values.tolist()

        # Compute t_end from all available data
        all_t_ends: list[float] = []
        for key in ("gps", "baro", "bat", "att", "vibe"):
            df_k = frames.get(key, pd.DataFrame())
            if not df_k.empty and "t" in df_k.columns:
                arr = _numeric(df_k["t"])
                finite = arr[np.isfinite(arr)]
                if finite.size:
                    all_t_ends.append(float(finite.max()))
        t_end_dash = max(all_t_ends) if all_t_ends else 0.0

        # Row y-ref strings in plotly
        yref_map = {1: "y", 2: "y2", 3: "y3", 4: "y4", 5: "y5", 6: "y6"}

        for i_seg, (t_start, mode_name) in enumerate(mode_rows):
            t_stop = mode_rows[i_seg + 1][0] if i_seg + 1 < len(mode_rows) else t_end_dash
            fill_rgba, text_color = _MODE_PALETTE.get(str(mode_name), _DEFAULT_PALETTE)

            # One vrect shape per subplot row
            for row_idx in range(1, NUM_ROWS + 1):
                shapes.append(dict(
                    type="rect",
                    xref="x",
                    yref=f"{yref_map[row_idx]} domain",
                    x0=t_start,
                    x1=t_stop,
                    y0=0,
                    y1=1,
                    fillcolor=fill_rgba,
                    line=dict(color=text_color, width=0.6, dash="dot"),
                    layer="below",
                ))

            # Mode label annotation pinned to bottom of row 6 (shared x-axis row)
            # Place one annotation per mode in each subplot at y=0.01 in domain coords
            for row_idx in range(1, NUM_ROWS + 1):
                mid_t = (t_start + t_stop) / 2.0
                annotations.append(dict(
                    x=mid_t,
                    y=0.02,
                    xref="x",
                    yref=f"{yref_map[row_idx]} domain",
                    text=f"<b>{mode_name}</b>",
                    showarrow=False,
                    font=dict(size=8, color=text_color),
                    bgcolor=fill_rgba.replace("0.30", "0.75"),
                    bordercolor=text_color,
                    borderwidth=0.8,
                    borderpad=2,
                    opacity=0.92,
                    xanchor="center",
                    yanchor="bottom",
                    textangle=-90,
                ))

            # Vertical boundary line at mode start
            shapes.append(dict(
                type="line",
                xref="x",
                yref="paper",
                x0=t_start,
                x1=t_start,
                y0=0,
                y1=1,
                line=dict(color="rgba(127,140,141,0.50)", width=0.8, dash="dash"),
            ))

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        height=1600,
        title=dict(
            text="<b>Interactive UAV Flight Dashboard</b>  ·  Flight Mode bands shown",
            font=dict(size=16),
        ),
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0.0),
        margin=dict(l=60, r=30, t=80, b=50),
        shapes=shapes,
        annotations=annotations,
    )
    fig.update_xaxes(title_text="Time (s)", row=NUM_ROWS, col=1)

    output_html.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        str(output_html),
        include_plotlyjs="cdn",
        full_html=True,
        config={
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": "dashboard_export",
                "scale": 2,
            },
        },
    )
    return True


def _load_frames_for_log(log_path: Path) -> tuple[list[object], dict[str, pd.DataFrame]]:
    from .parser import extract_frames, read_log_messages

    messages = read_log_messages(log_path)
    frames = extract_frames(messages)
    return messages, frames


def _comparison_metric(frames: dict[str, pd.DataFrame], metric: str) -> tuple[np.ndarray, np.ndarray]:
    if metric == "GPS Speed":
        return _series_for_dashboard(frames, "gps", "Spd", instance=0)
    if metric == "Altitude":
        t, y = _series_for_dashboard(frames, "baro", "Alt", instance=0)
        if y.size:
            return t, y
        return _series_for_dashboard(frames, "gps", "Alt", instance=0)
    if metric == "Battery Voltage":
        return _series_for_dashboard(frames, "bat", "Volt")
    if metric == "IMU Vibration":
        t_x, v_x = _series_for_dashboard(frames, "vibe", "VibeX", instance=0)
        t_y, v_y = _series_for_dashboard(frames, "vibe", "VibeY", instance=0)
        t_z, v_z = _series_for_dashboard(frames, "vibe", "VibeZ", instance=0)
        if t_x.size and t_y.size and t_z.size:
            common_t = np.union1d(np.union1d(t_x, t_y), t_z)
            vx = np.interp(common_t, t_x, v_x)
            vy = np.interp(common_t, t_y, v_y)
            vz = np.interp(common_t, t_z, v_z)
            return common_t, np.sqrt(vx**2 + vy**2 + vz**2)
        return np.array([], dtype=float), np.array([], dtype=float)
    if metric == "Attitude Stability":
        return _series_for_dashboard(frames, "att", "Roll")
    return np.array([], dtype=float), np.array([], dtype=float)


def generate_log_comparison(log_a: Path, log_b: Path, output_folder: Path) -> ComparisonResult:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _, frames_a = _load_frames_for_log(log_a)
    _, frames_b = _load_frames_for_log(log_b)

    output_folder.mkdir(parents=True, exist_ok=True)

    metrics = [
        "GPS Speed",
        "Altitude",
        "Battery Voltage",
        "IMU Vibration",
        "Attitude Stability",
    ]

    paths: list[Path] = []
    titles: list[str] = []

    for metric in metrics:
        t_a, y_a = _comparison_metric(frames_a, metric)
        t_b, y_b = _comparison_metric(frames_b, metric)

        if y_a.size == 0 and y_b.size == 0:
            continue

        fig, ax = plt.subplots(figsize=(11.5, 5.2))
        if y_a.size:
            ax.plot(t_a, y_a, color="#0D4DA1", linewidth=1.5, label=f"A: {log_a.name}")
        if y_b.size:
            ax.plot(t_b, y_b, color="#B84545", linewidth=1.5, label=f"B: {log_b.name}")

        ax.set_title(f"Comparison: {metric}", fontsize=12, fontweight="semibold")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel(metric)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)

        filename = _safe_token(metric.lower().replace(" ", "_"), fallback="metric")
        out = output_folder / f"compare_{filename}.png"
        fig.savefig(out, dpi=220, bbox_inches="tight")
        plt.close(fig)

        paths.append(out)
        titles.append(metric)

    return ComparisonResult(output_folder=output_folder, plot_paths=paths, titles=titles)
