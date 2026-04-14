from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

ProgressCallback = Optional[Callable[[float, str], None]]


@dataclass(frozen=True)
class SignalStats:
    plot_key: str
    plot_title: str
    signal: str
    minimum: float
    maximum: float
    mean: float
    samples: int

    def as_dict(self) -> dict[str, object]:
        return {
            "plot_key": self.plot_key,
            "plot_title": self.plot_title,
            "signal": self.signal,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "mean": self.mean,
            "samples": self.samples,
        }


@dataclass(frozen=True)
class PlotResult:
    key: str
    title: str
    image_path: Path
    stats: list[SignalStats]

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "image_path": str(self.image_path),
            "stats": [stat.as_dict() for stat in self.stats],
        }


@dataclass(frozen=True)
class AnalysisResult:
    output_folder: Path
    plots_folder: Path
    pdf_path: Path
    excel_path: Path
    plot_results: list[PlotResult]
    skipped_plots: list[str]
    critical_messages: list[str]
    current_stress: dict[str, object] | None = None

    @property
    def stats(self) -> list[SignalStats]:
        stats: list[SignalStats] = []
        for plot in self.plot_results:
            stats.extend(plot.stats)
        return stats

    def as_dict(self) -> dict[str, object]:
        return {
            "output_folder": str(self.output_folder),
            "plots_folder": str(self.plots_folder),
            "pdf_path": str(self.pdf_path),
            "excel_path": str(self.excel_path),
            "plot_results": [plot.as_dict() for plot in self.plot_results],
            "skipped_plots": self.skipped_plots,
            "critical_messages": self.critical_messages,
            "stats": [stat.as_dict() for stat in self.stats],
            "current_stress": self.current_stress or {},
        }
