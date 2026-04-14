# Manual Edit Guide (Current Project Structure)

This package contains the GUI, complete analysis pipeline, plot/report generation, and the editable configuration points for formulas, plot definitions, theming, and dependency management.

## Key files and responsibilities

- `RUN THIS.py` - launcher script for the GUI and dependency check/installation.
- `install_packages.py` - installs required Python packages for the tool.
- `app.py` - main PySide6 GUI window, input form, progress UI, preview list, and analysis workflow trigger.
- `analyzer.py` - core analysis pipeline: log validation, output folder creation, plot generation, PDF/Excel export, fixed Main variant behavior, and progress callbacks.
- `parser.py` - log message extraction, frame creation, critical message collection, and UTC start time detection.
- `formula_dictionary.py` - editable formula definitions, fallback computations, and plot summary text.
- `plot_dictionary.py` - editable signal/column mappings, default Y-axis limits, detailed signal reference limits, and PASS/FAIL acceptance rules.
- `plotting.py` - plot build engine, chart styling, data aggregation, and plot output generation.
- `reporting.py` - Excel/PDF report layout, styling, header/footer content, and logo insertion.
- `branding.py` - application theme colors, logo discovery logic, and shared UI/report palette.
- `variant_certification.py` - variant-specific certification criteria and PASS/FAIL evaluations for the fixed Main variant.
- `current_analyzer.py` - battery current stress analysis used by the main pipeline (not a separate visible UI tab).
- `weather_analyzer.py` - optional weather fetching and weather plot preparation.
- `plot_*.py` files (`plot_gps.py`, `plot_attitude.py`, `plot_compass.py`, `plot_battery_consumption.py`, `plot_servos.py`, `plot_vibes.py`, `plot_vibe_clippings.py`, `ekf.py`, `plot_weather.py`) - compatibility wrappers and plot-specific entrypoints.
- `pdf_builder.py` - compatibility wrapper for PDF generation, while `reporting.py` contains the current report styling logic.

## What to edit for formula changes

1. Open `formula_dictionary.py`.
2. Update:
   - `FORMULA_DICTIONARY` for text-based formula references.
   - `PLOT_FORMULA_MAP` to control which formulas appear on each plot.
   - `planar_speed(...)` for PSC speed calculations.
   - `compass_heading(...)` for magnetic heading computations.
   - `battery_mah(...)` for fallback battery consumption integration.
   - `summary_line(...)` for summary text formatting.
3. Save and re-run analysis.

## What to edit for signal mapping and threshold behavior

1. Open `plot_dictionary.py`.
2. Update:
   - `PLOT_DICTIONARY` to control which signals and channel mappings appear on each plot.
   - `Y_AXIS_LIMITS` for default visible axis ranges in plots.
   - `ACCEPTANCE_LIMITS` for PASS/FAIL rules that override y-axis limits.
   - `SIGNAL_Y_AXIS_LIMITS` for detailed per-signal reference ranges.
3. Save and re-run analysis.

## What to edit for theming and branding

1. Open `branding.py`.
2. Edit:
   - `DEFAULT_THEME` colors for primary, secondary, accent, background, panel background, borders, and plot colors.
   - `find_logo_path(...)` if you want to change the default logo search locations.
3. If you need to change visible application labels or window titles, edit `app.py`.

## What to edit for report appearance

1. Open `reporting.py`.
2. Edit Excel/PDF styling details such as:
   - header fonts, fill colors, and border styles.
   - the report title text inserted on the `Run_Info` sheet.
   - PDF page layout, table headers, and summary formatting.
3. Save and re-run analysis.

## What to edit for variant behavior

1. Open `analyzer.py`.
2. The application now uses a fixed Main variant only.
3. Update `VARIANT_PROFILES["main"]` if you need to adjust battery capacity, endurance, or voltage ranges.
4. `_apply_variant_plot_boundaries(...)` updates runtime plot limits and acceptance rules based on the Main profile.

## What to edit for dependency management

- `install_packages.py` now contains the full runtime dependency list.
- `RUN THIS.py` checks for required modules and calls `install_packages.py` if needed.
- There is no longer a `requirements.txt` file in this version.

## What to edit for PASS/FAIL logic

- `ACCEPTANCE_LIMITS` in `plot_dictionary.py` is evaluated first.
- If no acceptance rule exists for a signal, the system falls back to `Y_AXIS_LIMITS`.
- Variant-specific limit changes are applied dynamically in `analyzer.py` before plots are built.

## Important notes

- `formula_dictionary.py` and `plot_dictionary.py` remain the primary customization points for generated plot content and diagnostics.
- `app.py` is the GUI entry point, but the core processing occurs in `analyzer.py`, `plotting.py`, and `reporting.py`.
- The GUI now uses a single Main variant and no longer exposes variant selection or a separate current stress tab.
- Use `RUN THIS.py` to start the application and ensure dependencies are installed.
