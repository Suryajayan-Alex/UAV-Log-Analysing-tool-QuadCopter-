"""
Modern launcher file matching the reference project layout.
Run this file to start the UAV Log Analyzer GUI.

Manual edit points:
- Formula file: Asteria_Aerospace_Log_Analyser_Tool_Quadcopter/formula_dictionary.py
- Dictionary file: Asteria_Aerospace_Log_Analyser_Tool_Quadcopter/plot_dictionary.py
"""

from __future__ import annotations

from pathlib import Path
import importlib
import site
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parent

for extra_path in (PROJECT_ROOT, Path(site.getusersitepackages())):
    try:
        if extra_path.exists() and str(extra_path) not in sys.path:
            sys.path.insert(0, str(extra_path))
    except Exception:
        # Best-effort path injection.
        pass

REQUIRED_MODULES = {
    "PySide6.QtCore": "PySide6>=6.7",
    "pandas": "pandas>=2.2",
    "numpy": "numpy>=1.26",
    "matplotlib.pyplot": "matplotlib>=3.8",
    "pymavlink.mavutil": "pymavlink>=2.4",
    "reportlab.pdfgen": "reportlab>=4.0",
    "openpyxl": "openpyxl>=3.1",
    "PIL.Image": "pillow>=10.0",
}


def _missing_dependencies() -> list[str]:
    missing: list[str] = []
    for module_name, package_spec in REQUIRED_MODULES.items():
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(package_spec)
    return missing


def _ensure_dependencies() -> None:
    missing = _missing_dependencies()
    if not missing:
        return

    print("Missing dependencies detected:")
    for item in missing:
        print(f"  - {item}")
    print("Attempting automatic installation...")

    installer_script = PACKAGE_ROOT / "install_packages.py"
    try:
        subprocess.check_call([sys.executable, str(installer_script)])
    except subprocess.CalledProcessError as exc:
        print("\nAutomatic install failed.")
        print("Please run this command manually and retry:")
        print(f"  {sys.executable} \"{installer_script}\"")
        raise SystemExit(exc.returncode) from exc

    user_site = Path(site.getusersitepackages())
    try:
        if user_site.exists() and str(user_site) not in sys.path:
            sys.path.insert(0, str(user_site))
    except Exception:
        pass

    still_missing = _missing_dependencies()
    if still_missing:
        print("\nSome dependencies are still missing after installation:")
        for item in still_missing:
            print(f"  - {item}")
        print("Please install them manually and run again.")
        raise SystemExit(1)


def main() -> None:
    _ensure_dependencies()

    from Asteria_Aerospace_Log_Analyser_Tool_Quadcopter.app import launch

    launch()


if __name__ == "__main__":
    main()
