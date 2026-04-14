from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .analyzer import run_analysis
from .branding import THEME, find_logo_path


class AnalysisWorker(QObject):
    progress = Signal(float, str)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        log_path: str,
        vehicle: str,
        pilot: str,
        copilot: str,
        mission: str,
        variant: str,
        output_dir: str,
    ) -> None:
        super().__init__()
        self.log_path = log_path
        self.vehicle = vehicle
        self.pilot = pilot
        self.copilot = copilot
        self.mission = mission
        self.variant = variant
        self.output_dir = output_dir

    @Slot()
    def run(self) -> None:
        try:
            result = run_analysis(
                log_path=self.log_path,
                vehicle=self.vehicle,
                pilot=self.pilot,
                copilot=self.copilot,
                mission=self.mission,
                variant=self.variant,
                output_dir=self.output_dir or None,
                progress_cb=self._progress,
            )
            self.finished.emit(result.as_dict())
        except Exception:
            self.failed.emit(traceback.format_exc())

    def _progress(self, percent: float, message: str) -> None:
        self.progress.emit(percent, message)


class AnalyzerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("UAV Log Analyzer")
        self.resize(1350, 820)

        project_root = Path(__file__).resolve().parent
        self._logo_path = find_logo_path(project_root)
        if self._logo_path:
            self.setWindowIcon(QIcon(str(self._logo_path)))

        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None
        self._last_result: dict | None = None

        self._build_ui()
        self._apply_modern_style()

    def _build_brand_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 8)

        brand_title = QLabel("UAV Log Analyzer")
        brand_title.setObjectName("BrandTitle")
        brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(brand_title)
        layout.addStretch(1)
        return header

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        main_layout = QHBoxLayout(root)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        left_layout.addWidget(self._build_brand_header())

        form_group = QGroupBox("Analysis Inputs")
        form_layout = QVBoxLayout(form_group)

        self.log_input = QLineEdit()
        self.log_input.setPlaceholderText("Select .bin or .log file")
        log_button = QPushButton("Browse")
        log_button.clicked.connect(self._browse_log)
        log_row = QWidget()
        log_row_layout = QHBoxLayout(log_row)
        log_row_layout.setContentsMargins(0, 0, 0, 0)
        log_row_layout.addWidget(self.log_input)
        log_row_layout.addWidget(log_button)

        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Output folder (optional)")
        output_button = QPushButton("Choose")
        output_button.clicked.connect(self._browse_output)
        output_row = QWidget()
        output_row_layout = QHBoxLayout(output_row)
        output_row_layout.setContentsMargins(0, 0, 0, 0)
        output_row_layout.addWidget(self.output_input)
        output_row_layout.addWidget(output_button)

        self.vehicle_input = QLineEdit("UAV")
        self.pilot_input = QLineEdit("Pilot")
        self.copilot_input = QLineEdit()
        self.mission_input = QLineEdit("Test Mission")

        self.vehicle_input.setPlaceholderText("System ID")
        self.pilot_input.setPlaceholderText("Pilot")
        self.copilot_input.setPlaceholderText("Co Pilot")
        self.mission_input.setPlaceholderText("Mission Type")

        def add_labeled_field(label_text: str, widget: QWidget) -> None:
            label = QLabel(label_text)
            label.setObjectName("InputLabel")
            form_layout.addWidget(label)
            form_layout.addWidget(widget)

        add_labeled_field("Log file", log_row)
        add_labeled_field("Output", output_row)
        add_labeled_field("System ID", self.vehicle_input)
        add_labeled_field("Pilot", self.pilot_input)
        add_labeled_field("Co Pilot", self.copilot_input)
        add_labeled_field("Mission Type", self.mission_input)

        self.run_button = QPushButton("Analyze and Export (PDF + Excel)")
        self.run_button.clicked.connect(self._start_analysis)
        
        self.reset_button = QPushButton("Reset UI")
        self.reset_button.clicked.connect(self._reset_ui)
        self.reset_button.setStyleSheet("background: #95a5a6;") # Neutral grey
        
        self.quit_button = QPushButton("Quit")
        self.quit_button.clicked.connect(self.close)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.status_label = QLabel("Ready")

        left_layout.addWidget(form_group)
        left_layout.addWidget(self.run_button)
        left_layout.addWidget(self.progress_bar)
        left_layout.addWidget(self.status_label)
        left_layout.addStretch(1)
        left_layout.addWidget(self.reset_button)
        left_layout.addWidget(self.quit_button)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        tabs = QTabWidget()
        preview_tab = QWidget()
        preview_layout = QHBoxLayout(preview_tab)

        self.plot_list = QListWidget()
        self.plot_list.currentItemChanged.connect(self._on_plot_selected)
        self.plot_list.setMinimumWidth(290)

        self.preview_label = QLabel("Run analysis to preview generated plots")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumSize(640, 480)
        self.preview_label.setObjectName("PreviewPane")

        preview_layout.addWidget(self.plot_list)
        preview_layout.addWidget(self.preview_label, 1)

        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        log_layout.addWidget(self.log_box)

        tabs.addTab(preview_tab, "Plot Preview")
        tabs.addTab(log_tab, "Run Log")

        right_layout.addWidget(tabs)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([430, 920])

    def _apply_modern_style(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background: {THEME.background};
            }}
            QLabel#BrandTitle {{
                color: {THEME.primary};
                font-size: 36px;
                font-weight: 900;
                letter-spacing: 1.2px;
                text-transform: uppercase;
            }}
            QLabel#AppTitle {{
                color: {THEME.text_dark};
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 0.4px;
            }}
            QLabel#InputLabel {{
                color: {THEME.text_dark};
                font-size: 12px;
                font-weight: 600;
                padding-left: 2px;
            }}
            QLabel#PreviewPane {{
                border: 1px solid {THEME.border};
                border-radius: 10px;
                background: {THEME.panel_background};
                color: {THEME.text_dark};
                padding: 8px;
            }}
            QGroupBox {{
                border: 1px solid {THEME.border};
                border-radius: 10px;
                margin-top: 28px;
                padding-top: 8px;
                padding-left: 14px;
                padding-right: 14px;
                padding-bottom: 16px;
                background: {THEME.panel_background};
                font-weight: 600;
                color: {THEME.text_dark};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                top: -6px;
                left: 14px;
                padding: 2px 6px;
                color: {THEME.primary};
            }}
            QLineEdit, QTextEdit, QListWidget, QComboBox {{
                border: 1px solid {THEME.border};
                border-radius: 8px;
                padding: 8px;
                background: {THEME.panel_background};
                color: {THEME.text_dark};
            }}
            QComboBox {{
                min-height: 22px;
                padding-right: 26px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 22px;
            }}
            QComboBox QAbstractItemView {{
                border: 1px solid {THEME.border};
                background: {THEME.panel_background};
                color: {THEME.text_dark};
                selection-background-color: {THEME.secondary};
                selection-color: {THEME.white};
            }}
            QPushButton {{
                border: none;
                border-radius: 8px;
                background: {THEME.primary};
                color: {THEME.white};
                padding: 9px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {THEME.secondary};
            }}
            QPushButton:disabled {{
                background: {THEME.accent};
            }}
            QProgressBar {{
                border: 1px solid {THEME.border};
                border-radius: 8px;
                text-align: center;
                background: {THEME.panel_background};
                min-height: 22px;
                color: {THEME.text_dark};
            }}
            QProgressBar::chunk {{
                border-radius: 8px;
                background: {THEME.success};
            }}
            QTabWidget::pane {{
                border: 1px solid {THEME.border};
                border-radius: 10px;
                background: {THEME.panel_background};
            }}
            QTabBar::tab {{
                background: {THEME.background};
                color: {THEME.white};
                border: 1px solid {THEME.border};
                padding: 8px 12px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {THEME.primary};
                color: {THEME.background};
                font-weight: 700;
                border-color: {THEME.primary};
            }}
            """
        )

    def _append_log(self, text: str) -> None:
        self.log_box.append(text)

    def _browse_log(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ArduPilot Log",
            str(Path.home()),
            "ArduPilot Logs (*.bin *.log);;All Files (*.*)",
        )
        if path:
            self.log_input.setText(path)
            if not self.output_input.text().strip():
                self.output_input.setText(str(Path(path).resolve().parent))

    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Output Folder", str(Path.home()))
        if folder:
            self.output_input.setText(folder)

    def _start_analysis(self) -> None:
        log_path = self.log_input.text().strip()
        if not log_path:
            QMessageBox.warning(self, "Missing Log", "Please select a .bin/.log file.")
            return

        if not Path(log_path).exists():
            QMessageBox.critical(self, "File Not Found", f"Log file not found:\n{log_path}")
            return

        self.plot_list.clear()
        self.preview_label.setText("Generating plots...")
        self.preview_label.setPixmap(QPixmap())
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting analysis")
        self.run_button.setEnabled(False)
        self._append_log(f"Starting analysis for: {log_path}")

        if not self._logo_path:
            self._append_log("Brand logo not found. Add assets/logo.png to include it in reports.")

        self._thread = QThread(self)
        self._worker = AnalysisWorker(
            log_path=log_path,
            vehicle=self.vehicle_input.text().strip(),
            pilot=self.pilot_input.text().strip(),
            copilot=self.copilot_input.text().strip(),
            mission=self.mission_input.text().strip(),
            variant="Main",
            output_dir=self.output_input.text().strip(),
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)

        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup_worker)

        self._thread.start()

    @Slot()
    def _cleanup_worker(self) -> None:
        self._worker = None
        self._thread = None

    @Slot(float, str)
    def _on_progress(self, percent: float, message: str) -> None:
        value = max(0, min(int(round(percent)), 100))
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        self._append_log(f"[{value:>3}%] {message}")

    @Slot(dict)
    def _on_finished(self, result: dict) -> None:
        self._last_result = result
        self.run_button.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_label.setText("Analysis complete")

        for plot in result.get("plot_results", []):
            item = QListWidgetItem(plot.get("title", "Untitled Plot"))
            item.setData(Qt.ItemDataRole.UserRole, plot.get("image_path"))
            self.plot_list.addItem(item)

        output_folder = result.get("output_folder", "")
        pdf_path = result.get("pdf_path", "")
        excel_path = result.get("excel_path", "")

        self._append_log(f"Completed. Output folder: {output_folder}")
        self._append_log(f"PDF report: {pdf_path}")
        self._append_log(f"Excel report: {excel_path}")

        QMessageBox.information(
            self,
            "Analysis Complete",
            "Reports generated successfully.\n\n"
            f"PDF: {pdf_path}\n"
            f"Excel: {excel_path}",
        )

        if self.plot_list.count() > 0:
            self.plot_list.setCurrentRow(0)
        else:
            self.preview_label.setText("No plottable signals found in this log.")

    @Slot(str)
    def _on_failed(self, trace: str) -> None:
        self.run_button.setEnabled(True)
        self.status_label.setText("Analysis failed")
        self._append_log("Analysis failed.")
        self._append_log(trace)

        QMessageBox.critical(self, "Analysis Failed", trace)

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_plot_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is None:
            return

        image_path = current.data(Qt.ItemDataRole.UserRole)
        if not image_path:
            self.preview_label.setText("No image path available")
            return

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.preview_label.setText("Unable to load image preview")
            return

        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        current_item = self.plot_list.currentItem()
        if current_item is not None:
            self._on_plot_selected(current_item, None)

    @Slot()
    def _reset_ui(self) -> None:
        """Clear all inputs, reset the UI to its initial state, and prepare for a new analysis."""
        # Reset text inputs
        self.log_input.clear()
        self.output_input.clear()
        self.vehicle_input.setText("UAV")
        self.pilot_input.setText("Pilot")
        self.copilot_input.clear()
        self.mission_input.setText("Test Mission")

        # Reset analysis output states
        self.plot_list.clear()
        self.preview_label.setText("Run analysis to preview generated plots")
        self.preview_label.setPixmap(QPixmap())
        
        self.log_box.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")
        
        # Ensure buttons are interactable
        self.run_button.setEnabled(True)
        
        # Internal state clear
        self._last_result = None

def launch() -> None:
    app = QApplication.instance() or QApplication([])
    window = AnalyzerWindow()
    window.show()
    app.exec()



