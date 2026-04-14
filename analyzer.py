from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from .branding import find_logo_path
from .models import AnalysisResult, ProgressCallback
from .parser import critical_messages, extract_frames, read_log_messages, extract_utc_start_time
from .plot_dictionary import SIGNAL_Y_AXIS_LIMITS, Y_AXIS_LIMITS, ACCEPTANCE_LIMITS
from .plotting import PLOT_BUILDERS, generate_plots
from .reporting import export_excel_report, export_pdf_report
from .variant_certification import evaluate_criteria
from .weather_analyzer import get_weather_data
from .current_analyzer import evaluate_current_stress


VARIANT_PROFILES = {
    "main": {
        "name": "Main",
        "battery_capacity_mah": 9900.0,
        "endurance_minutes": 40.0,
        "battery_voltage_lower": 17.0,
        "battery_voltage_upper": 25.2,
    },
}


def _safe_name(text: str) -> str:
    # Sanitizes input for use in folder/file names
    text = str(text).strip() or "UAV"
    # Replace illegal filename characters with underscores
    text = re.sub(r'[\\/*?:"<>|]', '_', text)
    return "_".join(text.split())


def _normalize_variant_key(variant: str) -> str:
    return "main"


def _variant_profile(variant: str) -> dict[str, float | str]:
    return VARIANT_PROFILES.get(_normalize_variant_key(variant), VARIANT_PROFILES["main"])


def _apply_variant_plot_boundaries(profile: dict[str, float | str]) -> tuple[float, float]:
    lower = float(profile.get("battery_voltage_lower", 17.0))
    upper = float(profile.get("battery_voltage_upper", 25.2))
    if lower > upper:
        lower, upper = upper, lower

    # Clear old visual limits and old acceptance rules
    Y_AXIS_LIMITS.clear()
    SIGNAL_Y_AXIS_LIMITS.clear()
    ACCEPTANCE_LIMITS.clear()

    # Apply ONLY new variant-specific limits onto the graphs
    Y_AXIS_LIMITS["battery_cv_left"] = (lower, upper)
    Y_AXIS_LIMITS["battery_cv_right"] = (0.0, 31.0)
    Y_AXIS_LIMITS["gps_sats"] = (10.0, 10.0)
    Y_AXIS_LIMITS["gps_hdop"] = (0.0, 1.3)
    Y_AXIS_LIMITS["vibe_imu0"] = (0.0, 60.0)
    Y_AXIS_LIMITS["vibe_imu1"] = (0.0, 60.0)
    Y_AXIS_LIMITS["vibe_imu2"] = (0.0, 120.0)
    Y_AXIS_LIMITS["ekf3"] = (-0.8, 0.8)
    Y_AXIS_LIMITS["ekf4"] = (0.0, 0.6)

    SIGNAL_Y_AXIS_LIMITS["BAT.Volt (6s)"] = (lower, upper)
    
    return lower, upper


def _estimate_flight_time_minutes(frames: dict[str, pd.DataFrame]) -> float:
    max_time_seconds = 0.0
    for frame in frames.values():
        if not isinstance(frame, pd.DataFrame) or frame.empty or "t" not in frame.columns:
            continue

        t_values = pd.to_numeric(frame["t"], errors="coerce")
        if t_values.empty:
            continue

        t_max = t_values.max(skipna=True)
        if pd.notna(t_max):
            max_time_seconds = max(max_time_seconds, float(t_max))

    return max_time_seconds / 60.0 if max_time_seconds > 0.0 else 0.0


def run_analysis(
    log_path: str | Path,
    vehicle: str,
    pilot: str,
    copilot: str,
    mission: str,
    variant: str = "Main",
    output_dir: str | Path | None = None,
    progress_cb: ProgressCallback = None,
) -> AnalysisResult:
    """Run complete analysis pipeline and produce plots + PDF + Excel outputs."""

    path = Path(log_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    parent_dir = Path(output_dir).expanduser().resolve() if output_dir else path.parent
    date_str = datetime.now().strftime("%d-%m-%Y")
    vehicle_display = vehicle.strip() or "UAV"
    base_name = path.stem

    profile = _variant_profile(variant)
    variant_name = str(profile["name"])
    battery_capacity_mah = float(profile["battery_capacity_mah"])
    endurance_minutes = float(profile["endurance_minutes"])
    battery_voltage_lower, battery_voltage_upper = _apply_variant_plot_boundaries(profile)

    # Build Hierarchical Output Tree: System / Mission / Log / [RunTime]
    safe_vehicle = _safe_name(vehicle_display)
    safe_mission = _safe_name(mission)
    safe_base_name = _safe_name(base_name)
    run_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    output_folder = parent_dir / safe_vehicle / safe_mission / safe_base_name / run_ts
    plots_folder = output_folder / "plots"
    
    output_folder.mkdir(parents=True, exist_ok=True)
    plots_folder.mkdir(parents=True, exist_ok=True)

    total_steps = 3 + len(PLOT_BUILDERS) + 2
    step = 0

    def report(message: str) -> None:
        if progress_cb:
            percent = (step / total_steps) * 100.0
            progress_cb(percent, message)

    messages = read_log_messages(path)
    step += 1
    report("Read log messages")

    frames = extract_frames(messages)
    step += 1
    report("Extracted telemetry frames")
    
    report("Evaluating battery current stress metrics")
    current_stress = evaluate_current_stress(frames)
    frames['current_stress'] = current_stress

    observed_flight_minutes = _estimate_flight_time_minutes(frames)

    critical = critical_messages(messages)
    step += 1
    report("Collected critical messages")

    # Extract UTC start time and location for weather fetching
    report("Determining flight start time and location")
    utc_start = extract_utc_start_time(messages)
    
    weather_info = None
    weather_timeseries = None
    utc_armed = None

    if utc_start:
        df_gps = frames.get("gps", pd.DataFrame())
        if not df_gps.empty and "Lat" in df_gps.columns and "Lng" in df_gps.columns:
            # Use the first valid GPS position during the flight
            valid_gps = df_gps.dropna(subset=["Lat", "Lng"])
            if not valid_gps.empty:
                first_gps = valid_gps.iloc[0]
                lat, lon = first_gps["Lat"], first_gps["Lng"]
                
                # Fetch weather for the whole day to get time-series
                report(f"Fetching weather for {lat:.4f}, {lon:.4f}")
                full_weather = get_weather_data(lat, lon, utc_start, duration_min=int(observed_flight_minutes))
                
                if full_weather:
                    weather_timeseries = full_weather["hourly"]
                    
                    # Determine Armed Time weather
                    df_armed = frames.get("armed", pd.DataFrame())
                    t_armed = 0.0
                    if not df_armed.empty and "armed" in df_armed.columns:
                        armed_rows = df_armed[df_armed["armed"] == True]
                        if not armed_rows.empty:
                            t_armed = float(armed_rows.iloc[0]["t"])
                    
                    from datetime import timedelta
                    utc_armed = utc_start + timedelta(seconds=t_armed)
                    # Use point data for the specific hour of arming
                    weather_info = full_weather["point"]
                    report(f"Weather fetched. Armed at {utc_armed.strftime('%H:%M:%S UTC')}")

                    if weather_info:
                        weather_info["weather_plots"] = []

    endurance_status = "N/A" if observed_flight_minutes <= 0.0 else ("PASS" if observed_flight_minutes >= endurance_minutes else "FAIL")

    def plot_progress(index: int, total: int, title: str, generated: bool) -> None:
        del total
        nonlocal step
        step = 3 + index
        status = "Generated" if generated else "Skipped"
        report(f"{status}: {title}")

    plot_results, skipped_plots = generate_plots(frames, plots_folder, progress_cb=plot_progress)

    step += 1
    report("Evaluating Variant Certification Criteria")
    cert_results = evaluate_criteria(frames, variant_name, messages, observed_flight_minutes)

    pdf_path = output_folder / f"{safe_vehicle}_{safe_base_name}_{safe_mission}.pdf"
    excel_path = output_folder / f"{safe_vehicle}_{safe_base_name}_{safe_mission}.xlsx"

    project_root = Path(__file__).resolve().parent
    logo_path = find_logo_path(project_root)

    metadata = {
        "log_file": path.name,
        "vehicle": vehicle_display,
        "pilot": pilot,
        "copilot": copilot,
        "mission": mission,
        "variant": variant_name,
        "battery_capacity_mah": f"{battery_capacity_mah:.0f}",
        "endurance_minutes": f"{endurance_minutes:.0f}",
        "battery_voltage_lower": f"{battery_voltage_lower:.1f}",
        "battery_voltage_upper": f"{battery_voltage_upper:.1f}",
        "flight_time_minutes": f"{observed_flight_minutes:.2f}",
        "endurance_status": endurance_status,
        "logo_path": str(logo_path) if logo_path else "",
        "weather_temp": f"{weather_info.get('temperature', 'N/A')} °C" if weather_info else "N/A",
        "weather_wind": f"{weather_info.get('wind_speed', 0):.2f} m/s" if weather_info else "N/A",
        "weather_condition": weather_info.get("condition", "N/A") if weather_info else "N/A",
        "weather_gust": f"{weather_info.get('wind_gust', 0):.2f} m/s" if weather_info else "N/A",
        "weather_cloud": f"{weather_info.get('cloud_cover', 0)}%" if weather_info else "N/A",
        "weather_precip": f"{weather_info.get('precipitation', 0)} mm" if weather_info else "N/A",
        "weather_plots": weather_info.get("weather_plots", []) if weather_info else [],
        "flight_utc": utc_start.strftime("%Y-%m-%d %H:%M UTC") if utc_start else "N/A",
        "armed_utc": utc_armed.strftime("%H:%M:%S UTC") if utc_armed else "N/A",
    }

    step += 1
    report("Building Excel report")
    export_excel_report(excel_path, metadata, plot_results, skipped_plots, critical, logo_path=logo_path, cert_results=cert_results, current_stress=current_stress)

    step += 1
    report("Building PDF report")
    export_pdf_report(pdf_path, metadata, plot_results, skipped_plots, critical, logo_path=logo_path, cert_results=cert_results, current_stress=current_stress)

    if progress_cb:
        progress_cb(100.0, "Analysis complete")

    return AnalysisResult(
        output_folder=output_folder,
        plots_folder=plots_folder,
        pdf_path=pdf_path,
        excel_path=excel_path,
        plot_results=plot_results,
        skipped_plots=skipped_plots,
        critical_messages=critical,
        current_stress=current_stress,
    )
