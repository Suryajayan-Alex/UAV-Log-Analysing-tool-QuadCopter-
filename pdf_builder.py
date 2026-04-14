"""
PDF builder compatibility module matching the reference function signature.
Internally uses the upgraded branded PDF reporting engine.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.models import PlotResult, SignalStats  # noqa: E402
from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.reporting import export_pdf_report  # noqa: E402


def _stat(plot_key: str, plot_title: str, signal: str, minimum: float, maximum: float, mean: float, samples: int = 1):
    return SignalStats(
        plot_key=plot_key,
        plot_title=plot_title,
        signal=signal,
        minimum=float(minimum),
        maximum=float(maximum),
        mean=float(mean),
        samples=int(samples),
    )


def _metrics_to_stats(metrics: dict) -> dict[str, list[SignalStats]]:
    by_plot: dict[str, list[SignalStats]] = {}

    def add(key: str, stat: SignalStats):
        by_plot.setdefault(key, []).append(stat)

    battery = metrics.get("battery", {}) if isinstance(metrics, dict) else {}
    cur = battery.get("current") or {}
    if cur:
        add("bat_cv", _stat("bat_cv", "Battery Voltage & Current", "Battery Current", cur.get("min", 0), cur.get("max", 0), cur.get("mean", 0), 1))

    vol = battery.get("voltage") or {}
    if vol:
        add("bat_cv", _stat("bat_cv", "Battery Voltage & Current", "Battery Voltage", vol.get("min", 0), vol.get("max", 0), (vol.get("min", 0) + vol.get("max", 0)) / 2.0, 1))

    mah_max = battery.get("mah_max")
    if mah_max is not None:
        add("bat_mah", _stat("bat_mah", "Battery mAh Consumed", "Battery mAh", 0.0, mah_max, mah_max, 1))

    for gps_key, label in [("gps0", "GPS0 NSats"), ("gps1", "GPS1 NSats")]:
        gps = metrics.get(gps_key) or {}
        if gps:
            add("gps_sats", _stat("gps_sats", "GPS Satellites", label, gps.get("min", 0), gps.get("max", 0), gps.get("mean", 0), 1))

    imu = metrics.get("imu") if isinstance(metrics, dict) else {}
    if isinstance(imu, dict):
        for inst in [0, 1, 2]:
            block = imu.get(inst) or imu.get(str(inst)) or {}
            for axis in ["VibeX", "VibeY", "VibeZ"]:
                s = block.get(axis) or {}
                if s:
                    add(
                        f"vibe{inst}_combined",
                        _stat(
                            f"vibe{inst}_combined",
                            f"IMU{inst} Vibrations",
                            f"IMU{inst} {axis}",
                            s.get("min", 0),
                            s.get("max", 0),
                            s.get("mean", 0),
                            1,
                        ),
                    )
            c = block.get("Clip") or {}
            if c:
                add(
                    "vibe_clippings_panel",
                    _stat(
                        "vibe_clippings_panel",
                        "IMU Clippings",
                        f"IMU{inst} Clip",
                        c.get("min", 0),
                        c.get("max", 0),
                        c.get("mean", 0),
                        1,
                    ),
                )

    return by_plot


def build_pdf(paths, metrics, title_info, pdf_path, order, critical_msgs=None):
    stats_by_plot = _metrics_to_stats(metrics or {})

    plot_results: list[PlotResult] = []
    for key, title in order:
        image = paths.get(key)
        if not image:
            continue
        image_path = Path(image)
        if not image_path.exists():
            continue

        plot_key = key[:-5] if key.endswith("_path") else key
        plot_results.append(
            PlotResult(
                key=plot_key,
                title=title,
                image_path=image_path,
                stats=stats_by_plot.get(plot_key, []),
            )
        )

    logo_path = None
    logo_txt = title_info.get("logo_path") if isinstance(title_info, dict) else None
    if logo_txt:
        p = Path(logo_txt)
        if p.exists():
            logo_path = p

    metadata = {
        "log_file": title_info.get("log_name", ""),
        "vehicle": title_info.get("vehicle", ""),
        "pilot": title_info.get("pilot", ""),
        "copilot": title_info.get("copilot", ""),
        "mission": title_info.get("mission", ""),
    }

    export_pdf_report(
        pdf_path=Path(pdf_path),
        metadata=metadata,
        plot_results=plot_results,
        skipped_plots=[],
        critical_messages=critical_msgs or [],
        logo_path=logo_path,
    )

