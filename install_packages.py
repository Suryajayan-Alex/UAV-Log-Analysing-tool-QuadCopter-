"""Install required Python packages for the UAV log analyzer."""

from __future__ import annotations

from pathlib import Path
import importlib
import site
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Required dependencies based on current code imports.
REQUIRED_PACKAGES = [
    "PySide6>=6.7",
    "pandas>=2.2",
    "numpy>=1.26",
    "matplotlib>=3.8",
    "pymavlink>=2.4",
    "reportlab>=4.0",
    "openpyxl>=3.1",
    "pillow>=10.0",
    "plotly>=5.18",
    "requests>=2.31",
]

# Module checks that must import successfully after installation.
REQUIRED_MODULES = {
    "PySide6.QtCore": "PySide6",
    "pandas": "pandas",
    "numpy": "numpy",
    "matplotlib.pyplot": "matplotlib",
    "pymavlink.mavutil": "pymavlink",
    "reportlab.pdfgen": "reportlab",
    "openpyxl": "openpyxl",
    "PIL.Image": "pillow",
    "plotly.graph_objects": "plotly",
    "requests": "requests",
}


def _run_pip(packages: list[str]) -> None:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--user", *packages]
    subprocess.check_call(cmd)


def _ensure_import_path() -> None:
    user_site = Path(site.getusersitepackages())
    if user_site.exists() and str(user_site) not in sys.path:
        sys.path.insert(0, str(user_site))


def _validate_imports() -> list[str]:
    missing: list[str] = []
    for module_name, package_name in REQUIRED_MODULES.items():
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(package_name)
    return sorted(set(missing))


def main() -> None:
    print(f"Project root: {PROJECT_ROOT}")
    print("Installing dependencies into user site-packages...")

    _run_pip(REQUIRED_PACKAGES)

    _ensure_import_path()
    missing = _validate_imports()
    if missing:
        print("\nDependencies installed, but these imports are still missing:")
        for package in missing:
            print(f"  - {package}")
        raise SystemExit(1)

    print("All packages installed successfully into: user site-packages")


if __name__ == "__main__":
    main()
