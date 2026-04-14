from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from pathlib import Path
from textwrap import shorten
from typing import Callable, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle

from .branding import THEME
from .models import PlotResult, SignalStats
from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.formula_dictionary import (
    battery_mah as formula_battery_mah,
    compass_heading as formula_compass_heading,
    planar_speed as formula_planar_speed,
    summary_line as formula_summary_line,
)
from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.plot_dictionary import PLOT_DICTIONARY, Y_AXIS_LIMITS


@dataclass(frozen=True)
class Signal:
    label: str
    t: pd.Series | np.ndarray
    y: pd.Series | np.ndarray
    color: str
    linewidth: float = 1.5


BuildResult = tuple[plt.Figure, list[SignalStats]]
PlotBuilder = Callable[[dict[str, pd.DataFrame]], Optional[BuildResult]]
ProgressCallback = Optional[Callable[[int, int, str, bool], None]]

P0, P1, P2, P3, P4, P5, P6 = THEME.plot_colors[:7]

GPS_INSTANCE_COLORS = {0: P0, 1: P4, 2: P3, 3: P6}
MOTOR_COLORS = [P0, P4, P3, P6]
EKF_COLORS = [P0, P4, P3, P6, P5]

MODE_COLOR_BY_NAME = {
    "AUTO": "#D77E7E",
    "GUIDED": "#8D6FD1",
    "LOITER": "#D46F27",
    "POSHOLD": "#B56D2E",
    "ALTHOLD": "#8F7A35",
    "STABILIZE": "#3C8D74",
    "RTL": "#5B9A35",
    "LAND": "#2E8B57",
    "TAKEOFF": "#3A87C8",
}
MODE_FALLBACK_COLORS = ["#8A7BC0", "#3F9D7A", "#C8843E", "#B35C74", "#5A9BB5"]

SUMMARY_PLOT_LEFT = 0.05
SUMMARY_PLOT_RIGHT = 0.99
SUMMARY_PLOT_BOTTOM = 0.065
SUMMARY_TOP = 0.968
SUMMARY_BOX_WIDTH = 0.94
SUMMARY_MAX_HEIGHT = 0.23
SUMMARY_GAP_TO_PLOT = 0.012

PLOT_FIG_SIZE = (12.6, 8.0)
ATTITUDE_FIG_SIZE = (12.6, 8.0)

plt.rcParams.update(
    {
        "figure.facecolor": THEME.background,
        "axes.facecolor": THEME.white,
        "savefig.facecolor": THEME.white,
        "axes.edgecolor": THEME.border,
        "axes.labelcolor": THEME.text_dark,
        "axes.titlecolor": THEME.text_dark,
        "xtick.color": THEME.text_dark,
        "ytick.color": THEME.text_dark,
        "grid.color": THEME.border,
        "legend.edgecolor": THEME.border,
        "font.size": 10,
    }
)


def _to_numeric_array(values: pd.Series | np.ndarray) -> np.ndarray:
    return pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)


def _valid_xy(t_values: pd.Series | np.ndarray, y_values: pd.Series | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    t = _to_numeric_array(t_values)
    y = _to_numeric_array(y_values)
    mask = np.isfinite(t) & np.isfinite(y)
    return t[mask], y[mask]


def _subset_instance(df: pd.DataFrame, column: str, instance: int) -> pd.DataFrame:
    if df.empty:
        return df
    if column not in df.columns:
        return df
    return df[df[column].fillna(instance) == instance]


def _make_stats(plot_key: str, plot_title: str, signal: str, y: np.ndarray) -> Optional[SignalStats]:
    finite = y[np.isfinite(y)]
    if finite.size == 0:
        return None
    return SignalStats(
        plot_key=plot_key,
        plot_title=plot_title,
        signal=signal,
        minimum=float(np.min(finite)),
        maximum=float(np.max(finite)),
        mean=float(np.mean(finite)),
        samples=int(finite.size),
    )


def _time_window_mask(t: np.ndarray, windows: list[tuple[float, float]]) -> np.ndarray:
    mask = np.zeros(t.shape, dtype=bool)
    for start, end in windows:
        if not np.isfinite(start) or not np.isfinite(end):
            continue
        lo, hi = (start, end) if start <= end else (end, start)
        mask |= (t >= lo) & (t <= hi)
    return mask


def _max_time_in_frames(frames: dict[str, pd.DataFrame]) -> float | None:
    max_t: float | None = None
    for frame in frames.values():
        if not isinstance(frame, pd.DataFrame) or frame.empty or "t" not in frame.columns:
            continue
        t_values = pd.to_numeric(frame["t"], errors="coerce").to_numpy(dtype=float)
        finite = t_values[np.isfinite(t_values)]
        if finite.size == 0:
            continue
        t_max = float(np.max(finite))
        if max_t is None or t_max > max_t:
            max_t = t_max
    return max_t


def _armed_windows_from_frames(frames: dict[str, pd.DataFrame]) -> list[tuple[float, float]] | None:
    df_armed = frames.get("armed", pd.DataFrame())
    if not isinstance(df_armed, pd.DataFrame) or df_armed.empty:
        return None
    if "t" not in df_armed.columns or "armed" not in df_armed.columns:
        return None

    working = df_armed.copy()
    working["t"] = pd.to_numeric(working["t"], errors="coerce")
    working = working.dropna(subset=["t", "armed"]).sort_values("t")
    if working.empty:
        return None

    windows: list[tuple[float, float]] = []
    start_t: float | None = None

    for _, row in working.iterrows():
        t = float(row["t"])
        armed_state = bool(row["armed"])

        if armed_state and start_t is None:
            start_t = t
        elif not armed_state and start_t is not None:
            if t >= start_t:
                windows.append((start_t, t))
            start_t = None

    if start_t is not None:
        max_t = _max_time_in_frames(frames)
        end_t = max_t if (max_t is not None and max_t >= start_t) else start_t
        windows.append((start_t, end_t))

    return windows or None


def _plot_signals(
    ax: plt.Axes,
    plot_key: str,
    plot_title: str,
    signals: list[Signal],
    stats_windows: list[tuple[float, float]] | None = None,
) -> list[SignalStats]:
    stats: list[SignalStats] = []
    for signal in signals:
        t, y = _valid_xy(signal.t, signal.y)
        if y.size == 0:
            continue

        ax.plot(t, y, label=signal.label, color=signal.color, linewidth=signal.linewidth)

        stats_values = y
        if stats_windows:
            window_mask = _time_window_mask(t, stats_windows)
            if np.any(window_mask):
                stats_values = y[window_mask]

        stat = _make_stats(plot_key, plot_title, signal.label, stats_values)
        if stat is not None:
            stats.append(stat)
    return stats


def _normalized_limits(limit_key: str | None) -> tuple[float, float] | None:
    if not limit_key:
        return None

    raw = Y_AXIS_LIMITS.get(limit_key)
    if raw is None:
        return None

    try:
        lower = float(raw[0])
        upper = float(raw[1])
    except (TypeError, ValueError, IndexError):
        return None

    if not np.isfinite(lower) or not np.isfinite(upper):
        return None

    if lower > upper:
        lower, upper = upper, lower

    return lower, upper


def _expanded_limits(lower: float, upper: float, padding_ratio: float = 0.10) -> tuple[float, float] | None:
    if not np.isfinite(lower) or not np.isfinite(upper):
        return None

    if lower > upper:
        lower, upper = upper, lower

    if lower == upper:
        pad = max(abs(lower) * padding_ratio, 1.0)
        return lower - pad, upper + pad

    span = upper - lower
    pad = max(span * padding_ratio, 1e-9)
    return lower - pad, upper + pad


def _x_limits_from_origin(lower: float, upper: float, padding_ratio: float = 0.10) -> tuple[float, float] | None:
    if not np.isfinite(lower) or not np.isfinite(upper):
        return None

    if lower > upper:
        lower, upper = upper, lower

    upper = max(upper, 0.0)
    if upper <= 0.0:
        return 0.0, 1.0

    pad = max(upper * padding_ratio, 1e-9)
    return 0.0, upper + pad


def _y_limits_from_origin(lower: float, upper: float, padding_ratio: float = 0.10) -> tuple[float, float] | None:
    if not np.isfinite(lower) or not np.isfinite(upper):
        return None

    if lower > upper:
        lower, upper = upper, lower

    if lower >= 0.0:
        if upper <= 0.0:
            return 0.0, 1.0
        span = upper - lower
        pad = max(span * padding_ratio, upper * 0.02, 1e-9)
        return 0.0, upper + pad

    if upper <= 0.0:
        span = upper - lower
        pad = max(span * padding_ratio, abs(lower) * 0.02, 1e-9)
        return lower - pad, 0.0

    return _expanded_limits(lower, upper, padding_ratio=padding_ratio)


def _apply_limits(ax: plt.Axes, limit_key: str | None) -> None:
    for line in list(ax.get_lines()):
        if line.get_gid() == "origin_line":
            line.remove()

    finite_x: list[np.ndarray] = []
    finite_y: list[np.ndarray] = []

    for line in ax.get_lines():
        x = _to_numeric_array(line.get_xdata())
        y = _to_numeric_array(line.get_ydata())
        mask = np.isfinite(x) & np.isfinite(y)
        if not np.any(mask):
            continue
        finite_x.append(x[mask])
        finite_y.append(y[mask])

    if not finite_x or not finite_y:
        return

    all_x = np.concatenate(finite_x)
    all_y = np.concatenate(finite_y)

    x_limits = _x_limits_from_origin(float(np.min(all_x)), float(np.max(all_x)))
    y_min = float(np.min(all_y))
    y_max = float(np.max(all_y))

    threshold_limits = _normalized_limits(limit_key)
    if threshold_limits is not None:
        y_min = min(y_min, threshold_limits[0])
        y_max = max(y_max, threshold_limits[1])

    y_limits = _y_limits_from_origin(y_min, y_max)

    if x_limits is not None:
        ax.set_xlim(*x_limits)
    if y_limits is not None:
        ax.set_ylim(*y_limits)

    ax.axhline(0.0, color=THEME.border, linewidth=0.9, alpha=0.75, zorder=0.25, gid="origin_line")
    ax.axvline(0.0, color=THEME.border, linewidth=0.9, alpha=0.75, zorder=0.25, gid="origin_line")


def _draw_threshold_lines(ax: plt.Axes, limit_key: str | None) -> None:
    limits = _normalized_limits(limit_key)
    if limits is None:
        return

    lower, upper = limits
    y_min, y_max = ax.get_ylim()
    if not np.isfinite(y_min) or not np.isfinite(y_max) or y_max <= y_min:
        return

    def draw_line(value: float, color: str, label: str, va: str) -> None:
        if value < y_min or value > y_max:
            return
        ax.axhline(
            value,
            color=color,
            linewidth=1.8,
            linestyle=(0, (1.2, 2.0)),
            alpha=0.98,
            zorder=4.0,
        )
        ax.text(
            0.995,
            value,
            f"{label}: {value:.2f}",
            transform=ax.get_yaxis_transform(),
            ha="right",
            va=va,
            fontsize=7.8,
            fontweight="bold",
            color=color,
            bbox={
                "boxstyle": "round,pad=0.18",
                "facecolor": THEME.white,
                "edgecolor": color,
                "linewidth": 0.8,
                "alpha": 0.9,
            },
            zorder=4.2,
        )

    if lower == upper:
        draw_line(lower, "#111111", "Threshold", "bottom")
        return

    draw_line(lower, "#111111", "Lower", "bottom")
    draw_line(upper, "#A600FF", "Upper", "top")


def _mode_color(mode_name: str) -> str:
    mode = mode_name.upper().strip()
    if mode in MODE_COLOR_BY_NAME:
        return MODE_COLOR_BY_NAME[mode]

    checksum = sum(ord(ch) for ch in mode)
    return MODE_FALLBACK_COLORS[checksum % len(MODE_FALLBACK_COLORS)]


def _overlay_mode_messages_on_axis(ax: plt.Axes, mode_df: pd.DataFrame) -> None:
    if mode_df.empty or "t" not in mode_df.columns or "Mode" not in mode_df.columns:
        return

    if getattr(ax, "name", "") == "polar":
        return

    x_min, x_max = ax.get_xlim()
    if not np.isfinite(x_min) or not np.isfinite(x_max) or x_max <= x_min:
        return

    mode_times = pd.to_numeric(mode_df["t"], errors="coerce").to_numpy(dtype=float)
    mode_names = mode_df["Mode"].astype(str).to_numpy()
    valid = np.isfinite(mode_times)
    if not np.any(valid):
        return

    mode_times = mode_times[valid]
    mode_names = mode_names[valid]

    order = np.argsort(mode_times, kind="stable")
    mode_times = mode_times[order]
    mode_names = mode_names[order]

    segments: list[tuple[float, float, str]] = []
    for index, start_time in enumerate(mode_times):
        segment_start = x_min if index == 0 else float(start_time)
        segment_end = float(mode_times[index + 1]) if (index + 1) < mode_times.size else x_max

        if segment_end <= x_min or segment_start >= x_max:
            continue

        segment_start = max(segment_start, x_min)
        segment_end = min(segment_end, x_max)
        if segment_end <= segment_start:
            continue

        segments.append((segment_start, segment_end, mode_names[index].upper().strip()))

    if not segments:
        return

    y_min, y_max = ax.get_ylim()
    x_span = max(x_max - x_min, 1e-9)
    min_label_span = max(x_span * 0.03, 0.35)

    for segment_start, segment_end, mode_name in segments:
        color = _mode_color(mode_name)

        ax.axvspan(segment_start, segment_end, color=color, alpha=0.12, zorder=0)
        ax.axvline(segment_start, color=color, linewidth=0.7, alpha=0.38, zorder=0.2)

        if (segment_end - segment_start) >= min_label_span:
            ax.text(
                (segment_start + segment_end) / 2.0,
                0.01,
                mode_name,
                transform=ax.get_xaxis_transform(),
                rotation=-90,
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
                color=color,
                zorder=3,
                clip_on=False,
            )

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)


def _overlay_mode_messages_on_figure(fig: plt.Figure, mode_df: pd.DataFrame) -> None:
    if mode_df.empty:
        return

    seen_positions: set[tuple[float, float, float, float]] = set()
    for axis in fig.axes:
        pos = tuple(round(value, 6) for value in axis.get_position().bounds)
        if pos in seen_positions:
            continue
        seen_positions.add(pos)
        _overlay_mode_messages_on_axis(axis, mode_df)


def _summary_rows(stats: list[SignalStats], signal_colors: dict[str, str], max_chars: int) -> list[tuple[str, str]]:
    ordered = sorted(stats, key=lambda s: s.signal)
    rows: list[tuple[str, str]] = []
    for stat in ordered:
        line = formula_summary_line(stat.signal, stat.minimum, stat.maximum, stat.mean)
        rows.append((shorten(line, width=max_chars, placeholder="..."), signal_colors.get(stat.signal, THEME.text_dark)))
    return rows


def _step_fraction(font_size_pt: float, fig_size_inches: float, spacing_factor: float) -> float:
    return (font_size_pt * spacing_factor) / (72.0 * max(fig_size_inches, 1.0))


def _fit_top_summary_layout(fig: plt.Figure, row_count: int, longest_chars: int) -> dict[str, float | int]:
    fig_w = max(fig.get_figwidth(), 1.0)
    fig_h = max(fig.get_figheight(), 1.0)

    box_w = SUMMARY_BOX_WIDTH
    panel_h = SUMMARY_MAX_HEIGHT

    outer_pad = 0.0075
    col_gap = 0.012
    title_gap = 0.0035
    marker_gap = 0.0038

    def chars_fit(text_w: float, font_size: float) -> int:
        char_w = max((0.55 * font_size) / (72.0 * fig_w), 1e-6)
        return max(8, int(text_w / char_w))

    for cols in [1, 2, 3, 4]:
        rows_per_col = ceil(max(row_count, 1) / cols)

        for row_font in [8.6, 8.2, 7.8, 7.4, 7.0, 6.6, 6.2, 5.8, 5.4, 5.0, 4.6, 4.2]:
            title_font = min(9.2, row_font + 0.6)
            row_step = _step_fraction(row_font, fig_h, 1.26)
            title_step = _step_fraction(title_font, fig_h, 1.18)

            marker_w = min(0.010, row_step * 0.62)
            inner_w = box_w - outer_pad * 2 - col_gap * (cols - 1)
            col_w = inner_w / cols
            text_w = col_w - marker_w - marker_gap - 0.0015
            if text_w <= 0:
                continue

            max_chars = chars_fit(text_w, row_font)
            if max_chars < 24:
                continue

            total_h = outer_pad * 2 + title_step + title_gap + row_step * rows_per_col
            if total_h <= panel_h:
                return {
                    "cols": cols,
                    "rows_per_col": rows_per_col,
                    "title_font": title_font,
                    "row_font": row_font,
                    "title_step": title_step,
                    "row_step": row_step,
                    "padding": outer_pad,
                    "title_gap": title_gap,
                    "total_h": total_h,
                    "marker_w": marker_w,
                    "marker_gap": marker_gap,
                    "col_gap": col_gap,
                    "box_w": box_w,
                    "max_chars": max_chars,
                }

    cols = 4
    rows_per_col = ceil(max(row_count, 1) / cols)
    title_font = 5.0
    row_font = 3.2
    title_step = _step_fraction(title_font, fig_h, 1.18)
    free_h = max(panel_h - (outer_pad * 2 + title_step + title_gap), 1e-5)
    row_step = free_h / max(rows_per_col, 1)

    marker_w = min(0.009, row_step * 0.62)
    inner_w = box_w - outer_pad * 2 - col_gap * (cols - 1)
    col_w = inner_w / cols
    text_w = max(col_w - marker_w - marker_gap - 0.0015, 0.02)
    max_chars = max(14, chars_fit(text_w, row_font))

    total_h = outer_pad * 2 + title_step + title_gap + row_step * rows_per_col

    return {
        "cols": cols,
        "rows_per_col": rows_per_col,
        "title_font": title_font,
        "row_font": row_font,
        "title_step": title_step,
        "row_step": row_step,
        "padding": outer_pad,
        "title_gap": title_gap,
        "total_h": total_h,
        "marker_w": marker_w,
        "marker_gap": marker_gap,
        "col_gap": col_gap,
        "box_w": box_w,
        "max_chars": max_chars,
    }


def _add_summary_dialog(fig: plt.Figure, stats: list[SignalStats], signal_colors: dict[str, str]) -> float:
    if not stats:
        return 0.84

    ordered = sorted(stats, key=lambda s: s.signal)
    longest_chars = max(len(formula_summary_line(s.signal, s.minimum, s.maximum, s.mean)) for s in ordered)
    layout = _fit_top_summary_layout(fig, len(ordered), longest_chars)

    max_chars = int(layout["max_chars"])
    rows = _summary_rows(stats, signal_colors, max_chars=max_chars)

    box_w = float(layout["box_w"])
    box_left = (1.0 - box_w) / 2.0
    box_top = SUMMARY_TOP
    box_bottom = box_top - float(layout["total_h"])

    box = FancyBboxPatch(
        (box_left, box_bottom),
        box_w,
        float(layout["total_h"]),
        boxstyle="round,pad=0.005",
        transform=fig.transFigure,
        facecolor="#F5F9FF",
        edgecolor=THEME.border,
        linewidth=1.1,
        zorder=2,
    )
    fig.patches.append(box)

    padding = float(layout["padding"])
    title_step = float(layout["title_step"])
    row_step = float(layout["row_step"])
    title_gap = float(layout["title_gap"])
    title_font = float(layout["title_font"])
    row_font = float(layout["row_font"])
    cols = int(layout["cols"])
    rows_per_col = int(layout["rows_per_col"])
    col_gap = float(layout["col_gap"])
    marker_w = float(layout["marker_w"])
    marker_gap = float(layout["marker_gap"])

    left = box_left + padding
    top = box_top - padding

    fig.text(
        left,
        top,
        "Min / Max / Mean Summary",
        ha="left",
        va="top",
        fontsize=title_font,
        color=THEME.text_dark,
        fontweight="bold",
        zorder=3,
    )

    inner_w = box_w - padding * 2 - col_gap * (cols - 1)
    col_w = inner_w / cols

    y0 = top - title_step - title_gap
    for idx, (line, color) in enumerate(rows):
        col_idx = idx // rows_per_col
        row_idx = idx % rows_per_col

        x = left + col_idx * (col_w + col_gap)
        y = y0 - row_idx * row_step

        marker_h = min(marker_w, row_step * 0.60)
        marker_y = y - marker_h * 0.80

        marker = Rectangle(
            (x, marker_y),
            marker_w,
            marker_h,
            transform=fig.transFigure,
            facecolor=color,
            edgecolor=THEME.border,
            linewidth=0.65,
            zorder=3,
        )
        fig.patches.append(marker)

        fig.text(
            x + marker_w + marker_gap,
            y,
            line,
            ha="left",
            va="top",
            fontsize=row_font,
            color=color,
            zorder=3,
        )

    return box_bottom


def _single_axis_plot(
    plot_key: str,
    plot_title: str,
    y_label: str,
    signals: list[Signal],
    legend_cols: int = 1,
    y_limit_key: str | None = None,
    stats_windows: list[tuple[float, float]] | None = None,
) -> Optional[BuildResult]:
    del legend_cols
    fig, ax = plt.subplots(figsize=PLOT_FIG_SIZE)
    stats = _plot_signals(ax, plot_key, plot_title, signals, stats_windows=stats_windows)
    if not stats:
        plt.close(fig)
        return None

    ax.set_title(plot_title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(y_label)
    ax.grid(True, alpha=0.3)
    _apply_limits(ax, y_limit_key or plot_key)
    _draw_threshold_lines(ax, y_limit_key or plot_key)

    signal_colors = {signal.label: signal.color for signal in signals}
    summary_bottom = _add_summary_dialog(fig, stats, signal_colors)

    plot_bottom = SUMMARY_PLOT_BOTTOM
    plot_top = max(plot_bottom + 0.26, summary_bottom - SUMMARY_GAP_TO_PLOT)
    ax.set_position([
        SUMMARY_PLOT_LEFT,
        plot_bottom,
        SUMMARY_PLOT_RIGHT - SUMMARY_PLOT_LEFT,
        plot_top - plot_bottom,
    ])
    return fig, stats


def _dual_axis_plot(
    plot_key: str,
    plot_title: str,
    left_label: str,
    right_label: str,
    left_signals: list[Signal],
    right_signals: list[Signal],
    left_limit_key: str | None = None,
    right_limit_key: str | None = None,
) -> Optional[BuildResult]:
    fig, left_ax = plt.subplots(figsize=PLOT_FIG_SIZE)
    right_ax = left_ax.twinx()

    left_stats = _plot_signals(left_ax, plot_key, plot_title, left_signals)
    right_stats = _plot_signals(right_ax, plot_key, plot_title, right_signals)
    stats = left_stats + right_stats
    if not stats:
        plt.close(fig)
        return None

    left_ax.set_title(plot_title)
    left_ax.set_xlabel("Time (s)")
    left_ax.set_ylabel(left_label)
    right_ax.set_ylabel(right_label)
    left_ax.grid(True, alpha=0.3)
    _apply_limits(left_ax, left_limit_key or plot_key)
    _draw_threshold_lines(left_ax, left_limit_key or plot_key)
    _apply_limits(right_ax, right_limit_key or plot_key)
    _draw_threshold_lines(right_ax, right_limit_key or plot_key)

    signal_colors = {signal.label: signal.color for signal in (left_signals + right_signals)}
    summary_bottom = _add_summary_dialog(fig, stats, signal_colors)

    plot_bottom = SUMMARY_PLOT_BOTTOM
    plot_top = max(plot_bottom + 0.26, summary_bottom - SUMMARY_GAP_TO_PLOT)
    pos = [
        SUMMARY_PLOT_LEFT,
        plot_bottom,
        SUMMARY_PLOT_RIGHT - SUMMARY_PLOT_LEFT,
        plot_top - plot_bottom,
    ]
    left_ax.set_position(pos)
    right_ax.set_position(pos)
    return fig, stats


def _polar_compass_plot(
    plot_key: str,
    plot_title: str,
    signals: list[Signal],
    stats_windows: list[tuple[float, float]] | None = None,
) -> Optional[BuildResult]:
    fig, ax = plt.subplots(figsize=PLOT_FIG_SIZE, subplot_kw={'projection': 'polar'})
    
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    
    stats: list[SignalStats] = []
    merged_t = []
    
    for signal in signals:
        t, y = _valid_xy(signal.t, signal.y)
        if y.size == 0:
            continue
            
        merged_t.extend(t)
        theta = np.radians(y)
        ax.plot(theta, t, label=signal.label, color=signal.color, linewidth=signal.linewidth)
        
        stats_values = y
        if stats_windows:
            window_mask = _time_window_mask(t, stats_windows)
            if np.any(window_mask):
                stats_values = y[window_mask]

        stat = _make_stats(plot_key, plot_title, signal.label, stats_values)
        if stat is not None:
            stats.append(stat)

    if not stats:
        plt.close(fig)
        return None

    ax.set_title(plot_title, pad=20)
    ax.grid(True, alpha=0.3)
    
    if merged_t:
        max_t = np.max(merged_t)
        ax.set_rlim(0, max_t)

    # Let r-axis have a label to indicate what the radius represents
    ax.text(np.radians(45), ax.get_rmax() * 1.15, "Radius = Time (s)", ha='center', va='center', fontsize=9, color=THEME.text_dark)

    signal_colors = {signal.label: signal.color for signal in signals}
    summary_bottom = _add_summary_dialog(fig, stats, signal_colors)

    plot_bottom = SUMMARY_PLOT_BOTTOM
    plot_top = max(plot_bottom + 0.26, summary_bottom - SUMMARY_GAP_TO_PLOT)
    ax.set_position([
        SUMMARY_PLOT_LEFT,
        plot_bottom,
        SUMMARY_PLOT_RIGHT - SUMMARY_PLOT_LEFT,
        plot_top - plot_bottom,
    ])
    return fig, stats


def _integrate_mah(t: np.ndarray, current: np.ndarray) -> np.ndarray:
    return formula_battery_mah(t, current)

def _build_gps_satellites(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_gps = frames["gps"]
    if df_gps.empty or "NSats" not in df_gps.columns or "t" not in df_gps.columns:
        return None

    signals: list[Signal] = []
    for instance in PLOT_DICTIONARY["gps_instances"]:
        color = GPS_INSTANCE_COLORS.get(instance, P0)
        sub = _subset_instance(df_gps, "I", instance)
        if sub.empty:
            continue
        signals.append(Signal(label=f"GPS{instance} NSats", t=sub["t"], y=sub["NSats"], color=color))

    armed_windows = _armed_windows_from_frames(frames)
    return _single_axis_plot("gps_sats", "GPS Satellites vs Time", "Satellites", signals, stats_windows=armed_windows)


def _build_gps_speed_vs_psc(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_gps = frames["gps"]
    df_psc = frames["psc"]
    df_psce = frames["psce"]
    df_pscn = frames["pscn"]

    signals: list[Signal] = []

    if not df_gps.empty and {"t", "Spd"}.issubset(df_gps.columns):
        gps0 = _subset_instance(df_gps, "I", 0)
        source = gps0 if not gps0.empty else df_gps
        signals.append(Signal(label="GPS Speed", t=source["t"], y=source["Spd"], color=P0))

    if not df_psc.empty and "t" in df_psc.columns:
        if {"VX", "VY"}.issubset(df_psc.columns):
            vx = _to_numeric_array(df_psc["VX"])
            vy = _to_numeric_array(df_psc["VY"])
            speed = formula_planar_speed(vx, vy)
            signals.append(Signal(label="PSC Speed", t=df_psc["t"], y=speed, color=P4))
        elif {"VE", "VN"}.issubset(df_psc.columns):
            ve = _to_numeric_array(df_psc["VE"])
            vn = _to_numeric_array(df_psc["VN"])
            speed = formula_planar_speed(ve, vn)
            signals.append(Signal(label="PSC Speed", t=df_psc["t"], y=speed, color=P4))

    elif not df_psce.empty and not df_pscn.empty and {"t", "VE"}.issubset(df_psce.columns) and {"t", "VN"}.issubset(df_pscn.columns):
        t_ve = _to_numeric_array(df_psce["t"])
        t_vn = _to_numeric_array(df_pscn["t"])
        ve = _to_numeric_array(df_psce["VE"])
        vn = _to_numeric_array(df_pscn["VN"])

        ve_mask = np.isfinite(t_ve) & np.isfinite(ve)
        vn_mask = np.isfinite(t_vn) & np.isfinite(vn)

        if np.count_nonzero(ve_mask) > 1 and np.count_nonzero(vn_mask) > 1:
            common_t = np.union1d(t_ve[ve_mask], t_vn[vn_mask])
            interp_ve = np.interp(common_t, t_ve[ve_mask], ve[ve_mask])
            interp_vn = np.interp(common_t, t_vn[vn_mask], vn[vn_mask])
            speed = formula_planar_speed(interp_ve, interp_vn)
            signals.append(Signal(label="PSC Speed", t=common_t, y=speed, color=P4))

    armed_windows = _armed_windows_from_frames(frames)
    return _single_axis_plot("gps_speed", "GPS Speed vs PSC Speed", "Speed (m/s)", signals, stats_windows=armed_windows)


def _build_gps_hdop(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_gps = frames["gps"]
    if df_gps.empty or "t" not in df_gps.columns or "HDop" not in df_gps.columns:
        return None

    signals: list[Signal] = []
    for instance in PLOT_DICTIONARY["gps_instances"]:
        color = GPS_INSTANCE_COLORS.get(instance, P0)
        sub = _subset_instance(df_gps, "I", instance)
        if sub.empty:
            continue
        signals.append(Signal(label=f"GPS{instance} HDop", t=sub["t"], y=sub["HDop"], color=color))

    armed_windows = _armed_windows_from_frames(frames)
    return _single_axis_plot("gps_hdop", "GPS HDop vs Time", "HDop", signals, stats_windows=armed_windows)


def _build_attitude(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_att = frames["att"]
    if df_att.empty or "t" not in df_att.columns:
        return None

    fig, axes = plt.subplots(3, 1, figsize=ATTITUDE_FIG_SIZE, sharex=True)
    stats: list[SignalStats] = []
    signal_colors: dict[str, str] = {}

    pairs = PLOT_DICTIONARY["attitude_pairs"]
    attitude_limits = {
        "Roll": "attitude_roll",
        "Pitch": "attitude_pitch",
        "Yaw": "attitude_yaw",
    }

    for axis, (actual_col, desired_col, name) in zip(axes, pairs):
        local_signals: list[Signal] = []
        if actual_col in df_att.columns:
            local_signals.append(Signal(label=f"{name} Actual", t=df_att["t"], y=df_att[actual_col], color=P0))
        if desired_col in df_att.columns:
            local_signals.append(Signal(label=f"{name} Desired", t=df_att["t"], y=df_att[desired_col], color=P4))

        for signal in local_signals:
            signal_colors[signal.label] = signal.color
        local_stats = _plot_signals(axis, "attitude", "Attitude Desired vs Actual", local_signals)
        stats.extend(local_stats)
        axis.set_ylabel("deg")
        axis.set_title(f"{name} Desired vs Actual")
        axis.grid(True, alpha=0.3)
        limit_key = attitude_limits.get(name)
        _apply_limits(axis, limit_key)
        _draw_threshold_lines(axis, limit_key)

    if not stats:
        plt.close(fig)
        return None

    axes[-1].set_xlabel("Time (s)")
    summary_bottom = _add_summary_dialog(fig, stats, signal_colors)

    plot_bottom = SUMMARY_PLOT_BOTTOM
    plot_top = max(plot_bottom + 0.42, summary_bottom - SUMMARY_GAP_TO_PLOT)
    fig.subplots_adjust(
        left=SUMMARY_PLOT_LEFT,
        right=SUMMARY_PLOT_RIGHT,
        bottom=plot_bottom,
        top=plot_top,
        hspace=0.26,
    )
    return fig, stats


def _build_compass_heading(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_mag = frames["mag"]
    df_att = frames["att"]
    df_ahr2 = frames["ahr2"]

    signals: list[Signal] = []

    if not df_mag.empty and {"t", "MagX", "MagY"}.issubset(df_mag.columns):
        mag_x = _to_numeric_array(df_mag["MagX"])
        mag_y = _to_numeric_array(df_mag["MagY"])
        heading = formula_compass_heading(mag_x, mag_y)
        signals.append(Signal(label="MAG Heading", t=df_mag["t"], y=heading, color=P0))

    if not df_att.empty and {"t", "Yaw"}.issubset(df_att.columns):
        signals.append(Signal(label="ATT Yaw", t=df_att["t"], y=np.mod(_to_numeric_array(df_att["Yaw"]), 360.0), color=P4))

    if not df_ahr2.empty and {"t", "Yaw"}.issubset(df_ahr2.columns):
        signals.append(Signal(label="AHR2 Yaw", t=df_ahr2["t"], y=np.mod(_to_numeric_array(df_ahr2["Yaw"]), 360.0), color=P3))

    armed_windows = _armed_windows_from_frames(frames)
    return _polar_compass_plot("compass_heading", "Compass Heading Comparison", signals, stats_windows=armed_windows)


def _build_compass_gcrs(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_gps = frames["gps"]
    if df_gps.empty or "t" not in df_gps.columns or "GCrs" not in df_gps.columns:
        return None

    signals: list[Signal] = []
    for instance, color in [(0, P6), (1, P5)]:
        sub = _subset_instance(df_gps, "I", instance)
        if sub.empty:
            continue
        signals.append(Signal(label=f"GPS{instance} GCrs", t=sub["t"], y=np.mod(_to_numeric_array(sub["GCrs"]), 360.0), color=color))

    armed_windows = _armed_windows_from_frames(frames)
    return _single_axis_plot("compass_gcrs", "GPS Course (GCrs)", "Course (deg)", signals, stats_windows=armed_windows)


def _build_vibe(frames: dict[str, pd.DataFrame], instance: int) -> Optional[BuildResult]:
    df_vibe = frames["vibe"]
    if df_vibe.empty or "t" not in df_vibe.columns:
        return None

    sub = _subset_instance(df_vibe, "IMU", instance)
    vibe_axes = PLOT_DICTIONARY["vibe_axes"]
    if sub.empty or not set(vibe_axes).issubset(sub.columns):
        return None

    signals = [
        Signal(
            label=f"IMU{instance} {axis}",
            t=sub["t"],
            y=_to_numeric_array(sub[axis]),
            color=MOTOR_COLORS[idx % len(MOTOR_COLORS)],
        )
        for idx, axis in enumerate(vibe_axes)
    ]

    return _single_axis_plot(
        plot_key=f"vibe_imu{instance}",
        plot_title=f"IMU{instance} Vibration (X/Y/Z)",
        y_label="Vibration",
        signals=signals,
        legend_cols=2,
    )


def _build_vibe_imu0(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    return _build_vibe(frames, instance=0)


def _build_vibe_imu1(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    return _build_vibe(frames, instance=1)


def _build_vibe_imu2(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    return _build_vibe(frames, instance=2)

def _build_vibe_clippings(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_vibe = frames["vibe"]
    if df_vibe.empty or not {"t", "Clip"}.issubset(df_vibe.columns):
        return None

    CLIP_THRESHOLD = 30.0
    RATE_THRESHOLD = 10.0

    valid_instances = []
    for instance, color in [(0, P0), (1, P4), (2, P3)]:
        sub = _subset_instance(df_vibe, "IMU", instance).copy()
        if not sub.empty:
            valid_instances.append((instance, color, sub))
            
    if not valid_instances:
        return None
        
    num_axes = len(valid_instances)
    fig, axes = plt.subplots(num_axes, 1, figsize=PLOT_FIG_SIZE, sharex=True)
    if not isinstance(axes, (list, np.ndarray)):
        axes = [axes]

    stats: list[SignalStats] = []
    signal_colors: dict[str, str] = {}
    
    for idx, (instance, color, sub) in enumerate(valid_instances):
        ax = axes[idx]
        
        t = _to_numeric_array(sub["t"])
        clip = _to_numeric_array(sub["Clip"])
        
        dt = np.diff(t)
        dclip = np.diff(clip)
        dt[dt == 0] = 1e-6
        rate = np.zeros_like(clip)
        rate[1:] = dclip / dt
        
        # Smoothed rate of change
        rate_smooth = pd.Series(rate).rolling(window=5, min_periods=1).mean().to_numpy()
        
        # Severity Score
        severity = (0.7 * clip / CLIP_THRESHOLD) + (0.3 * rate_smooth / RATE_THRESHOLD)
        
        # Detection
        spike_event = rate_smooth > RATE_THRESHOLD
        early_warning = spike_event & (clip < CLIP_THRESHOLD)
        critical_spike = spike_event & (clip >= CLIP_THRESHOLD)
        
        clip_sig = Signal(label=f"IMU{instance} Clip", t=t, y=clip, color=color)
        rate_sig = Signal(label=f"IMU{instance} Rate", t=t, y=rate_smooth, color="#D35400") # Orange
        sev_sig  = Signal(label=f"IMU{instance} Sev", t=t, y=severity * 10, color="#C0392B") # Red
        
        ax_right = ax.twinx()
        
        local_stats_left = _plot_signals(ax, "vibe_clippings", "IMU Clippings Advanced", [clip_sig])
        local_stats_right = _plot_signals(ax_right, "vibe_clippings", "IMU Clippings Advanced", [rate_sig, sev_sig])
        
        if np.any(early_warning):
            # Professional Peak Marking: Only mark the highest point in a sustained clipping event
            # to avoid clumsy clustering of markers.
            ew_indices = np.where(early_warning)[0]
            if len(ew_indices) > 0:
                # Group consecutive indices to find local peaks
                groups = np.split(ew_indices, np.where(np.diff(ew_indices) > 10)[0] + 1)
                peak_indices = [g[np.argmax(rate_smooth[g])] for g in groups if len(g) > 0]
                
                ax_right.scatter(t[peak_indices], rate_smooth[peak_indices], 
                               color='#F39C12', zorder=10, marker='o', s=45, 
                               edgecolors='white', linewidths=1, label="Early Warn Pulse")
            
        if np.any(critical_spike):
            cs_indices = np.where(critical_spike)[0]
            if len(cs_indices) > 0:
                groups = np.split(cs_indices, np.where(np.diff(cs_indices) > 10)[0] + 1)
                peak_indices = [g[np.argmax(rate_smooth[g])] for g in groups if len(g) > 0]
                
                # Add professional stem lines for critical spikes
                ax_right.vlines(t[peak_indices], 0, rate_smooth[peak_indices], 
                              color='#E74C3C', alpha=0.3, linestyle='--', linewidth=1)
                
                ax_right.scatter(t[peak_indices], rate_smooth[peak_indices], 
                               color='#E74C3C', zorder=11, marker='X', s=60, 
                               edgecolors='white', linewidths=1.2, label="Critical Pulse")
            
        stats.extend(local_stats_left)
        stats.extend(local_stats_right)
        
        for sig in [clip_sig, rate_sig, sev_sig]:
            signal_colors[sig.label] = sig.color

        ax.set_ylabel(f"IMU{instance} Clip Count")
        ax_right.set_ylabel("Rate / Sev(10x)")
        ax.grid(True, alpha=0.3)
        
        # Add legend for scatter points if any are drawn
        handles, labels = ax_right.get_legend_handles_labels()
        if handles:
            by_label = dict(zip(labels, handles))
            ax_right.legend(by_label.values(), by_label.keys(), loc='upper left', fontsize=8)

    if not stats:
        plt.close(fig)
        return None

    axes[-1].set_xlabel("Time (s)")
    
    summary_bottom = _add_summary_dialog(fig, stats, signal_colors)

    plot_bottom = SUMMARY_PLOT_BOTTOM
    plot_top = max(plot_bottom + 0.42, summary_bottom - SUMMARY_GAP_TO_PLOT)
    fig.subplots_adjust(
        left=SUMMARY_PLOT_LEFT,
        right=SUMMARY_PLOT_RIGHT,
        bottom=plot_bottom,
        top=plot_top,
        hspace=0.26,
    )
    return fig, stats


def _build_battery_voltage_current(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_bat = frames["bat"]
    if df_bat.empty or "t" not in df_bat.columns:
        return None

    fig, axes = plt.subplots(2, 1, figsize=PLOT_FIG_SIZE, sharex=True)
    stats: list[SignalStats] = []
    signal_colors: dict[str, str] = {}

    voltage_signals: list[Signal] = []
    current_signals: list[Signal] = []

    if "Volt" in df_bat.columns:
        voltage_signals.append(Signal(label="Battery Voltage", t=df_bat["t"], y=df_bat["Volt"], color=P0))
    if "Curr" in df_bat.columns:
        current_signals.append(Signal(label="Battery Current", t=df_bat["t"], y=df_bat["Curr"], color=P6))

    for signal in voltage_signals + current_signals:
        signal_colors[signal.label] = signal.color

    voltage_stats = _plot_signals(axes[0], "battery_cv", "Battery Voltage and Current", voltage_signals)
    current_stats = _plot_signals(axes[1], "battery_cv", "Battery Voltage and Current", current_signals)
    stats.extend(voltage_stats)
    stats.extend(current_stats)

    if not stats:
        plt.close(fig)
        return None

    axes[0].set_title("Battery Voltage")
    axes[0].set_ylabel("Voltage (V)")
    axes[0].grid(True, alpha=0.3)
    _apply_limits(axes[0], "battery_cv_left")
    _draw_threshold_lines(axes[0], "battery_cv_left")

    axes[1].set_title("Battery Current")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Current (A)")
    axes[1].grid(True, alpha=0.3)
    _apply_limits(axes[1], "battery_cv_right")
    _draw_threshold_lines(axes[1], "battery_cv_right")

    summary_bottom = _add_summary_dialog(fig, stats, signal_colors)

    plot_bottom = SUMMARY_PLOT_BOTTOM
    plot_top = max(plot_bottom + 0.34, summary_bottom - SUMMARY_GAP_TO_PLOT)
    fig.subplots_adjust(
        left=SUMMARY_PLOT_LEFT,
        right=SUMMARY_PLOT_RIGHT,
        bottom=plot_bottom,
        top=plot_top,
        hspace=0.30,
    )
    return fig, stats


def _build_battery_mah(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_bat = frames["bat"]
    if df_bat.empty or "t" not in df_bat.columns:
        return None

    if "CurrTot" in df_bat.columns:
        t, mah = _valid_xy(df_bat["t"], df_bat["CurrTot"])
        if mah.size == 0:
            return None
    elif "Curr" in df_bat.columns:
        t, current = _valid_xy(df_bat["t"], df_bat["Curr"])
        if current.size == 0:
            return None
        mah = _integrate_mah(t, current)
    else:
        return None

    signals = [Signal(label="Battery mAh", t=t, y=mah, color=P3)]
    return _single_axis_plot("battery_mah", "Battery Capacity Consumed", "mAh", signals)


def _build_motor_output(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_rcou = frames["rcou"]
    if df_rcou.empty or "t" not in df_rcou.columns:
        return None

    channels = PLOT_DICTIONARY["motor_channels"]
    signals = [
        Signal(label=f"RCOU {channel}", t=df_rcou["t"], y=df_rcou[channel], color=MOTOR_COLORS[idx % len(MOTOR_COLORS)])
        for idx, channel in enumerate(channels)
        if channel in df_rcou.columns
    ]
    return _single_axis_plot("motor_output", "Motor Output PWM (C11-C14)", "PWM", signals, legend_cols=2)


def _build_rc_input(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_rcin = frames["rcin"]
    if df_rcin.empty or "t" not in df_rcin.columns:
        return None

    channels = PLOT_DICTIONARY["rcin_channels"]
    signals = [
        Signal(label=f"RCIN {channel}", t=df_rcin["t"], y=df_rcin[channel], color=MOTOR_COLORS[idx % len(MOTOR_COLORS)])
        for idx, channel in enumerate(channels)
        if channel in df_rcin.columns
    ]
    return _single_axis_plot("rc_input", "RC Input Channels (C1-C4)", "PWM", signals, legend_cols=2)


def _build_ekf3(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_nkf3 = frames["nkf3"]
    if df_nkf3.empty or "t" not in df_nkf3.columns:
        return None

    cols = PLOT_DICTIONARY["ekf3_columns"]
    signals = [
        Signal(label=f"NKF3 {col}", t=df_nkf3["t"], y=df_nkf3[col], color=EKF_COLORS[idx % len(EKF_COLORS)])
        for idx, col in enumerate(cols)
        if col in df_nkf3.columns
    ]
    return _single_axis_plot("ekf3", "NKF3 Variances", "Variance", signals)


def _build_ekf4(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_nkf4 = frames["nkf4"]
    if df_nkf4.empty or "t" not in df_nkf4.columns:
        return None

    cols = PLOT_DICTIONARY["ekf4_columns"]
    signals = [
        Signal(label=f"NKF4 {col}", t=df_nkf4["t"], y=df_nkf4[col], color=EKF_COLORS[idx % len(EKF_COLORS)])
        for idx, col in enumerate(cols)
        if col in df_nkf4.columns
    ]
    return _single_axis_plot("ekf4", "NKF4 Variances", "Variance", signals, legend_cols=2)


def _build_ekf9(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_nkf9 = frames["nkf9"]
    if df_nkf9.empty or "t" not in df_nkf9.columns or "SV" not in df_nkf9.columns:
        return None

    signals = [Signal(label="NKF9 SV", t=df_nkf9["t"], y=df_nkf9["SV"], color=P5)]
    return _single_axis_plot("ekf9", "NKF9 Variances", "Variance", signals)


def _build_current_spike_analysis(frames: dict[str, pd.DataFrame]) -> Optional[BuildResult]:
    df_bat = frames.get('bat', pd.DataFrame())
    analysis = frames.get('current_stress', {}).get('results', {})
    
    if df_bat.empty or not analysis:
        return None
        
    t = pd.to_numeric(df_bat['t'], errors='coerce').to_numpy()
    curr = pd.to_numeric(df_bat['Curr'], errors='coerce').to_numpy()
    
    fig, ax = plt.subplots(figsize=PLOT_FIG_SIZE)
    ax.set_title("Current Over-Threshold Spike Analysis")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (A)")
    
    ax.plot(t, curr, label="Raw Current", color=THEME.primary, alpha=0.5, linewidth=0.8)
    ax.axhline(31.0, color=THEME.danger, linestyle='-', linewidth=1.2, label="Peak Threshold (31A)")
    
    # Highlight Spikes with staggered labels and collision avoidance
    spikes = analysis.get('spike_events', [])
    last_labeled_time = -999.0
    tier_index = 0
    
    # Get X range for proximity calculation
    xmin, xmax = ax.get_xlim()
    xrange = max(1.0, xmax - xmin)
    
    for i, p in enumerate(spikes):
        ax.axvspan(p['start'], p['end'], color=THEME.danger, alpha=0.3, linewidth=0)
        
        mid_time = (p['start'] + p['end']) / 2
        
        # Axes coordinates: 0.0 at bottom, 1.0 at top. 
        # We'll use levels from 0.88 down to 0.64 to stay well away from top title.
        y_levels = [0.88, 0.80, 0.72, 0.64]
        
        # Horizontal Proximity Check (5% of total width)
        if (mid_time - last_labeled_time) < (xrange * 0.05): 
            tier_index = (tier_index + 1) % len(y_levels)
        else:
            tier_index = 0
            
        y_pos_axes = y_levels[tier_index]
        last_labeled_time = mid_time
        
        # Use transform=ax.get_xaxis_transform() so X is data and Y is axes fraction
        ax.text(mid_time, y_pos_axes, f"{p['duration']:.2f}s", color=THEME.danger, 
                fontsize=6.5, fontweight='bold', ha='center', va='bottom',
                transform=ax.get_xaxis_transform(),
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.5))

    total = analysis.get('total_spikes', 0)
    ax.text(0.02, 0.95, f"Total Spikes Detected: {total}", transform=ax.transAxes, 
            color=THEME.danger, fontweight='bold', bbox=dict(facecolor='white', alpha=0.8))

    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    _overlay_mode_messages_on_axis(ax, frames.get("mode", pd.DataFrame()))
    
    stats = _make_stats("current_spike_analysis", "Current Spike", "Current", curr)
    return fig, [stats] if stats else []




PLOT_BUILDERS: list[tuple[str, str, PlotBuilder]] = [
    ("current_spike_analysis", "Current Spike Analysis", _build_current_spike_analysis),
    ("gps_sats", "GPS Satellites vs Time", _build_gps_satellites),
    ("gps_speed", "GPS Speed vs PSC Speed", _build_gps_speed_vs_psc),
    ("gps_hdop", "GPS HDop vs Time", _build_gps_hdop),
    ("attitude", "Attitude Desired vs Actual", _build_attitude),
    ("compass_heading", "Compass Heading Comparison", _build_compass_heading),
    ("vibe_imu0", "IMU0 Vibration (X/Y/Z)", _build_vibe_imu0),
    ("vibe_imu1", "IMU1 Vibration (X/Y/Z)", _build_vibe_imu1),
    ("vibe_imu2", "IMU2 Vibration (X/Y/Z)", _build_vibe_imu2),
    ("vibe_clippings", "IMU Clippings vs Time", _build_vibe_clippings),
    ("battery_cv", "Battery Voltage and Current", _build_battery_voltage_current),
    ("rc_input", "RC Input Channels (C1-C4)", _build_rc_input),
    ("ekf3", "NKF3 Variances", _build_ekf3),
    ("ekf4", "NKF4 Variances", _build_ekf4),
]


def generate_plots(
    frames: dict[str, pd.DataFrame],
    plots_folder: Path,
    progress_cb: ProgressCallback = None,
) -> tuple[list[PlotResult], list[str]]:
    plots_folder.mkdir(parents=True, exist_ok=True)

    results: list[PlotResult] = []
    skipped: list[str] = []
    mode_df = frames.get("mode", pd.DataFrame())
    total = len(PLOT_BUILDERS)

    for index, (key, title, builder) in enumerate(PLOT_BUILDERS, start=1):
        built = builder(frames)
        if built is None:
            skipped.append(title)
            if progress_cb:
                progress_cb(index, total, title, False)
            continue

        fig, stats = built
        _overlay_mode_messages_on_figure(fig, mode_df)
        image_path = plots_folder / f"{key}.png"
        fig.savefig(image_path, dpi=240, bbox_inches="tight")
        plt.close(fig)

        results.append(PlotResult(key=key, title=title, image_path=image_path, stats=stats))
        if progress_cb:
            progress_cb(index, total, title, True)

    return results, skipped

















































