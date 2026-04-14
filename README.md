# UAV Log Analyser Tool - Quadcopter

A comprehensive flight log analysis and reporting tool for UAV/Quadcopter systems using Ardupilot telemetry data. This professional-grade application parses flight logs, performs advanced analysis, generates visualizations, and produces detailed PDF/Excel reports with certification evaluations.

## Overview

The Log Analyser Tool processes Ardupilot binary and text log files to extract comprehensive telemetry data, perform multi-dimensional analysis, and generate professional reports. It's designed for UAV operators, engineers, and aviation professionals who need detailed insights into flight performance and aircraft health.

## Key Features

✅ **Log File Parsing**
- Support for Ardupilot binary (.bin) and text format log files
- Extracts comprehensive telemetry using pymavlink
- Hierarchical data organization and processing

✅ **GPS Performance Analysis**
- Satellite count and signal strength (HDOP)
- Ground speed and altitude tracking
- GPS range analysis and accuracy metrics

✅ **Battery Health Monitoring**
- Voltage and current consumption tracking
- Over-current spike detection
- Battery capacity estimation and discharge curves
- Power consumption statistics

✅ **Vibration Analysis**
- IMU sensor data processing
- Clipping detection across 3 axes
- Vibration frequency analysis
- Accelerometer health assessment

✅ **Flight Attitude Monitoring**
- Roll, pitch, and yaw tracking (actual vs desired)
- Flight mode analysis
- Control surface servo monitoring
- Attitude error calculations

✅ **EKF Filter Analysis**
- Extended Kalman Filter variance tracking
- Navigation state estimation quality
- Error covariance analysis

✅ **Weather Integration**
- Real-time weather data from Open-Meteo API
- Temperature and altitude correlation
- Weather impact on flight performance

✅ **Professional Reporting**
- Multi-page PDF reports with styling and branding
- Excel export with detailed statistics
- Automated report generation with timestamps
- Custom acceptance criteria thresholds

✅ **Certification Evaluation**
- Aircraft variant certification assessment
- Health status indicators
- Compliance evaluation against predefined criteria

## Installation

### Prerequisites
- Python 3.8 or higher
- Windows/macOS/Linux operating system

### Quick Start

1. **Clone the Repository**
```bash
git clone <repository_url>
cd Log_Analyser_Tool_Quadcopter
```

2. **Run Dependencies Installer**
```bash
python install_packages.py
```

This will automatically install all required dependencies:
- `pymavlink` - Ardupilot log file parsing
- `matplotlib` - Data visualization
- `scipy` - Advanced signal processing
- `pandas` - Data manipulation
- `openpyxl` - Excel file generation
- `reportlab` - PDF generation
- `PySide6` - Desktop GUI framework
- `requests` - HTTP operations (weather API)

3. **Launch the Application**
```bash
python RUN THIS.py
```

## Usage

### Graphical Interface

1. Launch the application using `python RUN THIS.py`
2. Fill in the required information:
   - **Vehicle Name**: Identifier for your UAV/Quadcopter
   - **Mission Name**: Name of the flight mission
   - **Log File**: Select the Ardupilot log file (.bin or .txt)
3. Click "Analyze" to process the log
4. Reports are generated in: `Output/Vehicle_Name/Mission_Name/LogFile_Name/Timestamp/`

### Programmatic Usage

```python
from analyzer import analyze_log

# Analyze a log file
output_path = analyze_log(
    vehicle_name="MyQuadcopter",
    mission_name="TestFlight",
    log_file_path="path/to/logfile.bin"
)

print(f"Reports generated in: {output_path}")
```

## Project Structure

```
├── RUN THIS.py                 # Main entry point - GUI launcher
├── app.py                      # PySide6 desktop application
├── analyzer.py                 # Main orchestration pipeline
├──
├── Core Analysis Modules
├── parser.py                   # Ardupilot log file extraction
├── flight_data.py              # Telemetry data structures
├── advanced_analysis.py        # Signal processing and analysis
├── ekf.py                      # EKF filter analysis
├── current_analyzer.py         # Current/battery analysis
│
├── Visualization & Reporting
├── plotting.py                 # Matplotlib visualization engine
├── plot_dictionary.py          # Plot configuration and thresholds
├── plot_attitude.py            # Attitude visualization
├── plot_battery_consumption.py # Battery analysis plots
├── plot_compass.py             # Compass heading plots
├── plot_gps.py                 # GPS performance plots
├── plot_servos.py              # Servo control plots
├── plot_vibes.py               # Vibration analysis plots
├── plot_vibe_clippings.py      # Clipping detection plots
├── plot_weather.py             # Weather integration plots
├──
├── Configuration & Utilities
├── formula_dictionary.py       # Signal calculation formulas
├── branding.py                 # Visual theme and styling
├── models.py                   # Data models
├── reporting.py                # PDF/Excel report generation
├── pdf_builder.py              # PDF document construction
├── variant_certification.py    # Certification evaluation
├── weather_analyzer.py         # Weather data processing
├── verify_weather.py           # Weather validation
├──
└── Documentation
    ├── README.md               # This file
    └── MANUAL_EDIT_GUIDE.md    # Configuration guide
```

## Configuration

The tool uses three main configuration dictionaries for customization:

### 1. **formula_dictionary.py**
Define signal extraction and computation formulas:
```python
FORMULAS = {
    "GPS_Speed": "GPS.Spd",
    "Battery_Voltage": "BAT.V",
    "IMU_AccelX": "IMU.AccX",
    # Add custom signal definitions
}
```

### 2. **plot_dictionary.py**
Configure plotting parameters and acceptance thresholds:
```python
PLOTS = {
    "battery_voltage": {
        "title": "Battery Voltage",
        "y_limits": [9.5, 13.2],
        "acceptance_limit": 10.0,
        # Customizable plot parameters
    }
}
```

### 3. **branding.py**
Customize visual appearance:
```python
THEME = {
    "color_scheme": "professional",
    "title_font_size": 14,
    "company_name": "Asteria Aerospace",
}
```

See [MANUAL_EDIT_GUIDE.md](MANUAL_EDIT_GUIDE.md) for detailed configuration instructions.

## Data Output

All outputs are organized hierarchically:

```
Output/
├── [Vehicle_Name]/
│   ├── [Mission_Name]/
│   │   ├── [Log_File_Name]/
│   │   │   └── [Timestamp]/
│   │   │       ├── Report.pdf           # Professional PDF report
│   │   │       ├── Analysis.xlsx        # Detailed Excel spreadsheet
│   │   │       ├── Plots/               # Individual plot images
│   │   │       ├── analysis_log.txt     # Detailed analysis log
│   │   │       └── flight_data.json     # Raw extracted telemetry
```

**Report Contents:**
- Executive summary with key metrics
- GPS performance analysis
- Battery health assessment
- Vibration analysis and clipping detection
- Attitude tracking and control accuracy
- EKF filter health status
- Weather data integration
- Certification evaluation results
- Detailed statistics and graphs

## API Integration

### Weather Data
The tool integrates with the **Open-Meteo API** (free, no API key required):
- Retrieves historical weather data for flight location
- Integrates temperature and atmospheric data
- Correlates weather with flight performance

## Dependencies

Key Python packages:
- **pymavlink** - Ardupilot telemetry parsing
- **matplotlib** - Data visualization
- **scipy** - Signal processing
- **pandas** - Data manipulation
- **openpyxl** - Excel generation
- **reportlab** - PDF creation
- **PySide6** - GUI framework
- **requests** - HTTP requests
- **numpy** - Numerical computing

All dependencies are automatically installed via `install_packages.py`

## Requirements

- **Minimum RAM**: 2GB
- **Storage**: 500MB for application + outputs
- **Display**: 1024x768 or higher resolution recommended
- **Internet**: Required for live weather data (optional feature)

## Troubleshooting

### Log File Not Recognized
- Ensure file is a valid Ardupilot log (.bin or .txt)
- Check file permissions and read access
- Try uploading to Ardupilot's official log viewer to validate

### Missing Dependencies
```bash
python install_packages.py
```

### Weather Data Not Loading
- Verify internet connection
- Open-Meteo API may be temporarily unavailable
- Check firewall/proxy settings

### Report Generation Errors
- Ensure adequate disk space
- Verify write permissions in Output directory
- Check for special characters in file/mission names

## Contributing

For issues, feature requests, or contributions, please refer to the project repository or contact the development team.

## License

This tool is developed by Asteria Aerospace Limited for professional UAV analysis and reporting.

## Support

For detailed configuration and advanced usage, see [MANUAL_EDIT_GUIDE.md](MANUAL_EDIT_GUIDE.md)

## Version

Current Version: 1.0  
Last Updated: April 2026

---

**Ready to analyze your flight logs?** Start with `python RUN THIS.py` and follow the on-screen instructions.
