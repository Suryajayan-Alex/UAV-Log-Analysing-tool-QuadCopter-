from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrandTheme:
    name: str
    primary: str
    secondary: str
    accent: str
    text_dark: str
    background: str
    panel_background: str
    border: str
    white: str
    success: str
    danger: str
    warning: str
    info: str
    plot_colors: tuple[str, ...]


DEFAULT_THEME = BrandTheme(
    name="UAV Log Analyzer",
    primary="#FDE300",
    secondary="#C8A011",
    accent="#989F99",
    text_dark="#141210",
    background="#141210",
    panel_background="#FFFFFF",
    border="#E8EDEE",
    white="#E8EDEE",
    success="#C8A011",
    danger="#E74C3C",
    warning="#FDE300",
    info="#989F99",
    plot_colors=(
        "#FDE300",
        "#C8A011",
        "#E8EDEE",
        "#C2C9C5",
        "#989F99",
        "#141210",
        "#000000",
    ),
)

THEME = DEFAULT_THEME
ASTERIA = DEFAULT_THEME  # legacy alias for backward compatibility


def find_logo_path(project_root: Path) -> Path | None:
    """
    Resolve a logo file path from common project locations.
    Preferred filenames:
      - assets/logo.png
      - assets/brand_logo.png
      - logo.png
      - brand_logo.png
    """

    candidates = (
        project_root / "assets" / "logo.png",
        project_root / "assets" / "brand_logo.png",
        project_root / "logo.png",
        project_root / "brand_logo.png",
    )

    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None
