import sys
import os
import time
import json
import socket
import datetime
import winreg
import threading
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QCheckBox, QSystemTrayIcon, QMenu, QDialog,
    QListWidget, QTextEdit, QFrame, QScrollArea, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

import keyring

# Setup directories
ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "data" / "logs"
OUTPUTS_DIR = ROOT_DIR / "data" / "outputs"
WHITELIST_DIR = ROOT_DIR / "whitelist"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
WHITELIST_DIR.mkdir(parents=True, exist_ok=True)

# Settings config
SETTINGS_FILE = ROOT_DIR / "data" / "settings.json"

# Keyring config
SERVICE_NAME = "PhishGuard"
API_KEYS = ["google_safe_browsing", "virustotal", "phishtank", "spamhaus", "cloudflare"]


def get_first_launch() -> bool:
    if not SETTINGS_FILE.exists():
        return True
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data.get("first_launch", True)
    except Exception:
        return True


def set_first_launch(value: bool):
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    data["first_launch"] = value
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def set_setup_complete(active_port: int, auto_start: bool):
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    data["first_launch"] = False
    data["active_port"] = active_port
    data["auto_start"] = auto_start
    data["setup_complete"] = True
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def set_autostart_registry(enabled: bool):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            cmd = f'"{sys.executable}" "{Path(__file__).resolve()}"'
            winreg.SetValueEx(key, "PhishGuard", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, "PhishGuard")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Error setting autostart: {e}")


def is_autostart_registry_enabled() -> bool:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "PhishGuard")
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def create_color_icon(color_hex: str) -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color_hex))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)


# Find an available port in the range 5000-5003
def find_available_port() -> int:
    for port in [5000, 5001, 5002, 5003]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 5000  # Default fallback


ACTIVE_PORT = find_available_port()


# Thread to run Uvicorn server in background
class ServerThread(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.daemon = True
        self.server = None

    def run(self):
        import uvicorn
        from server.main import app
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="info")
        self.server = uvicorn.Server(config)
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True


# Signaller for Manual Scan results
class ScanWorkerSignals(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)


class SetupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PhishGuard Setup Wizard")
        self.setFixedSize(500, 450)
        self.current_page = 0
        
        # Stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #111827;
            }
            QLabel {
                color: #f3f4f6;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px;
                color: #f3f4f6;
            }
            QPushButton {
                background-color: #6366f1;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4f46e5;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
            QCheckBox {
                color: #f3f4f6;
            }
        """)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Header area
        self.header_label = QLabel("Welcome to PhishGuard V2.0.0")
        self.header_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #6366f1; margin-bottom: 15px;")
        self.layout.addWidget(self.header_label)

        # Content area (stacked layout simulated using visible/hidden widgets)
        self.pages = []
        self._init_pages()

        # Footer Buttons
        self.footer_layout = QHBoxLayout()
        self.back_btn = QPushButton("< Back")
        self.back_btn.clicked.connect(self.prev_page)
        self.back_btn.setEnabled(False)
        
        self.next_btn = QPushButton("Next >")
        self.next_btn.clicked.connect(self.next_page)
        
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.back_btn)
        self.footer_layout.addWidget(self.next_btn)
        self.layout.addLayout(self.footer_layout)

        # Timer to check extension status on page 3
        self.extension_check_timer = QTimer()
        self.extension_check_timer.timeout.connect(self.check_extension_connection)

    def _init_pages(self):
        # PAGE 0: API KEYS
        page_0 = QWidget()
        layout_0 = QVBoxLayout()
        page_0.setLayout(layout_0)
        
        desc = QLabel("Enter your API keys for the blocklist threat engines (at least 1 key required):\nKeys are stored securely in Windows Credential Manager.")
        desc.setWordWrap(True)
        layout_0.addWidget(desc)
        
        grid = QGridLayout()
        layout_0.addLayout(grid)
        
        self.keys_inputs = {}
        apis = [
            ("Google Safe Browsing", "google_safe_browsing"),
            ("VirusTotal", "virustotal"),
            ("PhishTank", "phishtank"),
            ("Spamhaus", "spamhaus"),
            ("Cloudflare (format: account_id:token)", "cloudflare")
        ]
        for row, (label_text, key_name) in enumerate(apis):
            label = QLabel(label_text)
            input_field = QLineEdit()
            input_field.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
            # Preload if exists
            preloaded_val = keyring.get_password(SERVICE_NAME, key_name) or ""
            input_field.setText(preloaded_val)
            grid.addWidget(label, row, 0)
            grid.addWidget(input_field, row, 1)
            self.keys_inputs[key_name] = input_field

        self.api_error_label = QLabel("")
        self.api_error_label.setStyleSheet("color: #ef4444; font-weight: bold; margin-top: 8px;")
        layout_0.addWidget(self.api_error_label)

        for input_field in self.keys_inputs.values():
            input_field.textChanged.connect(lambda: self.api_error_label.setText(""))
            
        self.pages.append(page_0)
        self.layout.addWidget(page_0)

        # PAGE 1: AUTO START
        page_1 = QWidget()
        layout_1 = QVBoxLayout()
        page_1.setLayout(layout_1)
        
        desc_1 = QLabel("Configure PhishGuard to start with Windows so protection is always active in the background.")
        desc_1.setWordWrap(True)
        layout_1.addWidget(desc_1)
        
        self.autostart_chk = QCheckBox("Start PhishGuard automatically when Windows starts")
        self.autostart_chk.setChecked(is_autostart_registry_enabled())
        layout_1.addWidget(self.autostart_chk)
        layout_1.addStretch()
        
        self.pages.append(page_1)
        self.layout.addWidget(page_1)
        page_1.hide()

        # PAGE 2: EXTENSION CONNECTION
        page_2 = QWidget()
        layout_2 = QVBoxLayout()
        page_2.setLayout(layout_2)
        
        desc_2 = QLabel("Connect the PhishGuard Chrome Extension:\n\n1. Ensure the extension is loaded in Chrome.\n2. Chrome will auto-connect to the local backend port.")
        desc_2.setWordWrap(True)
        layout_2.addWidget(desc_2)
        
        self.conn_status_label = QLabel("Waiting for extension connection...")
        self.conn_status_label.setStyleSheet("color: #f59e0b; font-weight: bold; margin-top: 20px;")
        layout_2.addWidget(self.conn_status_label)
        layout_2.addStretch()
        
        self.pages.append(page_2)
        self.layout.addWidget(page_2)
        page_2.hide()

    def show_page(self, index):
        self.pages[self.current_page].hide()
        self.current_page = index
        self.pages[self.current_page].show()
        
        # Update header
        headers = [
            "Step 1: API Configuration",
            "Step 2: Startup Configuration",
            "Step 3: Extension Synchronization"
        ]
        self.header_label.setText(headers[self.current_page])

        # Enable/Disable buttons
        self.back_btn.setEnabled(self.current_page > 0)
        
        if self.current_page == 2:
            self.next_btn.setText("Finish")
            self.next_btn.setEnabled(False)
            self.extension_check_timer.start(1500)
        else:
            self.next_btn.setText("Next >")
            self.next_btn.setEnabled(True)
            self.extension_check_timer.stop()

    def prev_page(self):
        if self.current_page > 0:
            self.show_page(self.current_page - 1)

    def next_page(self):
        # Save inputs
        if self.current_page == 0:
            has_at_least_one_key = any(input_field.text().strip() for input_field in self.keys_inputs.values())
            if not has_at_least_one_key:
                self.api_error_label.setText("⚠️ At least one API key is required to proceed.")
                return

            self.api_error_label.setText("")
            # Save API keys
            for key_name, input_field in self.keys_inputs.items():
                val = input_field.text().strip()
                if val:
                    keyring.set_password(SERVICE_NAME, key_name, val)
                else:
                    try:
                        keyring.delete_password(SERVICE_NAME, key_name)
                    except Exception:
                        pass
        elif self.current_page == 1:
            set_autostart_registry(self.autostart_chk.isChecked())
            
        if self.current_page < 2:
            self.show_page(self.current_page + 1)
        else:
            # Finish Setup
            set_setup_complete(ACTIVE_PORT, self.autostart_chk.isChecked())
            self.accept()

    def check_extension_connection(self):
        # Query fast_tier LAST_PING_TIME
        try:
            from server.routers import fast_tier as ft
            import time
            if time.time() - ft.LAST_PING_TIME < 40.0:
                self.conn_status_label.setText("✅ Extension detected & connected successfully!")
                self.conn_status_label.setStyleSheet("color: #10b981; font-weight: bold; margin-top: 20px;")
                self.next_btn.setEnabled(True)
        except Exception:
            pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhishGuard Desktop Console")
        self.setMinimumSize(850, 600)
        
        # Custom Status Icons
        self.icon_running = create_color_icon("#10b981")
        self.icon_paused = create_color_icon("#f59e0b")
        
        self.setWindowIcon(self.icon_running)

        # Style sheet definition
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QTabWidget::pane {
                border: 1px solid #1e293b;
                background-color: #1e293b;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #0f172a;
                border: 1px solid #1e293b;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                color: #94a3b8;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #1e293b;
                border-color: #1e293b;
                color: #f8fafc;
                border-bottom: 3px solid #6366f1;
            }
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #6366f1;
            }
            QPushButton:pressed {
                background-color: #4338ca;
            }
            QLineEdit, QTextEdit {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px;
                color: #f8fafc;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #6366f1;
            }
            QTableWidget {
                background-color: #1e293b;
                alternate-background-color: #162030;
                color: #f8fafc;
                gridline-color: #334155;
                border: none;
            }
            QHeaderView::section {
                background-color: #0f172a;
                color: #94a3b8;
                padding: 8px;
                border: 1px solid #334155;
                font-weight: bold;
            }
            QCheckBox {
                color: #f8fafc;
                font-size: 13px;
            }
            QLabel {
                color: #f8fafc;
            }
        """)

        # Main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Top Header (App Status & Control)
        self.setup_header_ui()

        # Tabs
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        self.setup_tabs_ui()

        # System Tray Setup
        self.setup_tray_ui()

        # Timers to update logs and stats
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_dashboard)
        self.refresh_timer.start(2500)

    def setup_header_ui(self):
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #1e293b; border-radius: 8px; margin-bottom: 10px;")
        header_layout = QHBoxLayout(header_frame)
        
        # Status text & indicator
        status_layout = QVBoxLayout()
        self.status_title = QLabel("PhishGuard Protection: ACTIVE")
        self.status_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #10b981;")
        self.port_label = QLabel(f"Local Server running on port: {ACTIVE_PORT}")
        self.port_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        
        self.keys_summary_label = QLabel("")
        self.keys_summary_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #10b981;")

        status_layout.addWidget(self.status_title)
        status_layout.addWidget(self.port_label)
        status_layout.addWidget(self.keys_summary_label)
        header_layout.addLayout(status_layout)
        
        header_layout.addStretch()
        
        # Control Buttons
        self.toggle_btn = QPushButton("Pause Protection")
        self.toggle_btn.setStyleSheet("background-color: #ef4444; min-width: 140px;")
        self.toggle_btn.clicked.connect(self.toggle_protection)
        header_layout.addWidget(self.toggle_btn)
        
        self.autostart_box = QCheckBox("Run on Startup")
        self.autostart_box.setChecked(is_autostart_registry_enabled())
        self.autostart_box.stateChanged.connect(self.toggle_autostart)
        header_layout.addWidget(self.autostart_box)

        self.main_layout.addWidget(header_frame)

    def setup_tabs_ui(self):
        # 1. Overview Dashboard
        self.tab_dashboard = QWidget()
        self.setup_dashboard_tab()
        self.tabs.addTab(self.tab_dashboard, "Dashboard")

        # 2. API Keys Config
        self.tab_api_keys = QWidget()
        self.setup_api_keys_tab()
        self.tabs.addTab(self.tab_api_keys, "API Keys")

        # 3. Browsing Logs
        self.tab_logs = QWidget()
        self.setup_logs_tab()
        self.tabs.addTab(self.tab_logs, "Browsing Logs")

        # 4. Reports Viewer
        self.tab_reports = QWidget()
        self.setup_reports_tab()
        self.tabs.addTab(self.tab_reports, "Deep Scan Reports")

        # 5. Whitelist Manager
        self.tab_whitelist = QWidget()
        self.setup_whitelist_tab()
        self.tabs.addTab(self.tab_whitelist, "Whitelist")

        # 6. Manual URL scan
        self.tab_manual_scan = QWidget()
        self.setup_manual_scan_tab()
        self.tabs.addTab(self.tab_manual_scan, "Manual Scan")

    # TABS IMPLEMENTATION
    def setup_dashboard_tab(self):
        layout = QVBoxLayout(self.tab_dashboard)
        
        intro = QLabel("Real-time local scanning metrics calculated from local telemetry:")
        intro.setStyleSheet("font-size: 14px; color: #94a3b8; margin-bottom: 10px;")
        layout.addWidget(intro)
        
        grid = QGridLayout()
        layout.addLayout(grid)
        
        # Grid Cards Design
        card_style = "background-color: #0f172a; padding: 15px; border-radius: 8px; border: 1px solid #1e293b;"
        val_style = "font-size: 24px; font-weight: bold; color: #6366f1;"
        label_style = "font-size: 12px; color: #94a3b8;"
        
        stats_labels = [
            ("Sites Scanned Today", "scanned_today", 0, 0),
            ("Sites Flagged Today", "flagged_today", 0, 1),
            ("Total Scanned (All Time)", "scanned_total", 1, 0),
            ("Total Flagged (All Time)", "flagged_total", 1, 1),
            ("Deep Scans Run", "deep_scans_total", 2, 0),
            ("Most Active API", "most_active_api", 2, 1),
        ]
        
        self.stats_widgets = {}
        for name, key, r, c in stats_labels:
            frame = QFrame()
            frame.setStyleSheet(card_style)
            frame_layout = QVBoxLayout(frame)
            
            val_lbl = QLabel("0" if key != "most_active_api" else "None")
            val_lbl.setStyleSheet(val_style)
            lbl = QLabel(name)
            lbl.setStyleSheet(label_style)
            
            frame_layout.addWidget(val_lbl)
            frame_layout.addWidget(lbl)
            grid.addWidget(frame, r, c)
            self.stats_widgets[key] = val_lbl
            
        # Last Scan Time Card
        last_scan_frame = QFrame()
        last_scan_frame.setStyleSheet(card_style)
        last_scan_layout = QHBoxLayout(last_scan_frame)
        self.last_scan_val = QLabel("Never")
        self.last_scan_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #10b981;")
        lbl = QLabel("Last Fast Tier Check:")
        lbl.setStyleSheet(label_style)
        last_scan_layout.addWidget(lbl)
        last_scan_layout.addWidget(self.last_scan_val)
        layout.addWidget(last_scan_frame)

        # Active Threat API Engines Card
        active_keys_frame = QFrame()
        active_keys_frame.setStyleSheet(card_style)
        active_keys_layout = QHBoxLayout(active_keys_frame)
        self.active_keys_val = QLabel("0 / 5 active")
        self.active_keys_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #10b981;")
        lbl_k = QLabel("Configured Threat API Engines:")
        lbl_k.setStyleSheet(label_style)
        active_keys_layout.addWidget(lbl_k)
        active_keys_layout.addWidget(self.active_keys_val)
        layout.addWidget(active_keys_frame)
        
        layout.addStretch()

    def setup_api_keys_tab(self):
        layout = QVBoxLayout(self.tab_api_keys)
        
        desc = QLabel("Enter your API Keys for threat intelligence. Configured services run checks in parallel:")
        desc.setStyleSheet("margin-bottom: 15px;")
        layout.addWidget(desc)
        
        grid = QGridLayout()
        layout.addLayout(grid)
        
        self.api_fields = {}
        self.api_status_labels = {}
        
        apis = [
            ("Google Safe Browsing", "google_safe_browsing"),
            ("VirusTotal API Key", "virustotal"),
            ("PhishTank API Key (Optional)", "phishtank"),
            ("Spamhaus API Key", "spamhaus"),
            ("Cloudflare (account_id:api_token)", "cloudflare")
        ]
        
        for row, (display_name, key_name) in enumerate(apis):
            lbl = QLabel(display_name)
            entry = QLineEdit()
            entry.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
            preloaded_val = keyring.get_password(SERVICE_NAME, key_name) or ""
            entry.setText(preloaded_val)
            
            status_lbl = QLabel("")
            status_lbl.setStyleSheet("font-weight: bold;")
            
            grid.addWidget(lbl, row, 0)
            grid.addWidget(entry, row, 1)
            grid.addWidget(status_lbl, row, 2)
            
            self.api_fields[key_name] = entry
            self.api_status_labels[key_name] = status_lbl
            
        save_btn = QPushButton("Save Keys")
        save_btn.clicked.connect(self.save_api_keys)
        layout.addWidget(save_btn)

        self.api_keys_summary_tab = QLabel("")
        self.api_keys_summary_tab.setWordWrap(True)
        layout.addWidget(self.api_keys_summary_tab)
        
        layout.addStretch()
        self.update_api_status_labels()

    def update_api_status_labels(self):
        active_count = 0
        active_names = []
        apis = [
            ("Google Safe Browsing", "google_safe_browsing"),
            ("VirusTotal", "virustotal"),
            ("PhishTank", "phishtank"),
            ("Spamhaus", "spamhaus"),
            ("Cloudflare", "cloudflare")
        ]
        
        for display_name, key_name in apis:
            status_lbl = self.api_status_labels.get(key_name)
            val = keyring.get_password(SERVICE_NAME, key_name)
            if val:
                active_count += 1
                active_names.append(display_name)
                if status_lbl:
                    status_lbl.setText("🟢 Active")
                    status_lbl.setStyleSheet("color: #10b981;")
            else:
                if status_lbl:
                    status_lbl.setText("⚪ Not configured")
                    status_lbl.setStyleSheet("color: #94a3b8;")

        if active_count == 0:
            msg = "⚠️ Active API Keys: 0/5 (No API keys configured)"
            color = "#ef4444"
            if hasattr(self, "api_keys_summary_tab"):
                self.api_keys_summary_tab.setText("⚠️ Warning: 0 out of 5 API keys active. Threat scanning will rely on URL pattern heuristics only.")
                self.api_keys_summary_tab.setStyleSheet("font-size: 13px; font-weight: bold; color: #ef4444; margin-top: 10px;")
        else:
            names_str = ", ".join(active_names)
            msg = f"🟢 Active API Keys: {active_count}/5 ({names_str})"
            color = "#10b981"
            if hasattr(self, "api_keys_summary_tab"):
                self.api_keys_summary_tab.setText(f"🟢 {active_count} out of 5 API keys active: {names_str}")
                self.api_keys_summary_tab.setStyleSheet("font-size: 13px; font-weight: bold; color: #10b981; margin-top: 10px;")

        if hasattr(self, "keys_summary_label"):
            self.keys_summary_label.setText(msg)
            self.keys_summary_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {color};")
            
        if hasattr(self, "active_keys_val"):
            self.active_keys_val.setText(f"{active_count} / 5 active")
            self.active_keys_val.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")

    def save_api_keys(self):
        for key_name, entry in self.api_fields.items():
            val = entry.text().strip()
            if val:
                keyring.set_password(SERVICE_NAME, key_name, val)
            else:
                try:
                    keyring.delete_password(SERVICE_NAME, key_name)
                except Exception:
                    pass
        self.update_api_status_labels()
        # Clear fields to keep visual safety
        for entry in self.api_fields.values():
            entry.setText("")
        # Force endpoints config reload via status labels
        self.update_api_status_labels()

    def setup_logs_tab(self):
        layout = QVBoxLayout(self.tab_logs)
        
        # Search & controls
        top_bar = QHBoxLayout()
        self.log_search = QLineEdit()
        self.log_search.setPlaceholderText("Search history logs by URL...")
        self.log_search.textChanged.connect(self.load_logs)
        
        refresh_btn = QPushButton("Refresh Logs")
        refresh_btn.clicked.connect(self.load_logs)
        
        top_bar.addWidget(self.log_search)
        top_bar.addWidget(refresh_btn)
        layout.addLayout(top_bar)
        
        # Table
        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(7)
        self.logs_table.setHorizontalHeaderLabels([
            "Timestamp", "URL", "Source", "Heuristic/Fast Flag", "Deep Scan Run", "Action", "Note"
        ])
        self.logs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.logs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.logs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.logs_table)
        
        self.load_logs()

    def load_logs(self):
        log_file = LOGS_DIR / "browsing_log.json"
        if not log_file.exists():
            return
        
        query = self.log_search.text().lower()
        
        try:
            logs = json.loads(log_file.read_text(encoding="utf-8"))
            # Reverse order (latest first)
            logs = list(reversed(logs))
            
            self.logs_table.setRowCount(0)
            row = 0
            for item in logs:
                url = item.get("url", "")
                if query and query not in url.lower():
                    continue
                
                self.logs_table.insertRow(row)
                
                # Format time
                ts = item.get("timestamp", "")
                try:
                    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    ts_display = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    ts_display = ts
                    
                self.logs_table.setItem(row, 0, QTableWidgetItem(ts_display))
                self.logs_table.setItem(row, 1, QTableWidgetItem(url))
                self.logs_table.setItem(row, 2, QTableWidgetItem(item.get("source", "")))
                
                flag = item.get("fastTierFlag", "")
                flag_item = QTableWidgetItem(flag)
                if "suspicious" in flag.lower() or "flagged" in flag.lower():
                    flag_item.setForeground(QColor("#ef4444"))
                else:
                    flag_item.setForeground(QColor("#10b981"))
                self.logs_table.setItem(row, 3, flag_item)
                
                self.logs_table.setItem(row, 4, QTableWidgetItem("Yes" if item.get("deepScanRun") else "No"))
                
                act = item.get("userAction", "")
                act_item = QTableWidgetItem(act)
                if act == "Go Back":
                    act_item.setForeground(QColor("#ef4444"))
                elif act == "Continue":
                    act_item.setForeground(QColor("#f59e0b"))
                elif act == "No prompt":
                    act_item.setForeground(QColor("#10b981"))
                self.logs_table.setItem(row, 5, act_item)
                
                self.logs_table.setItem(row, 6, QTableWidgetItem(item.get("note") or ""))
                row += 1
                
                if row >= 500:  # Show max 500 logs in the UI
                    break
        except Exception as e:
            print("Error loading logs", e)

    def setup_reports_tab(self):
        layout = QHBoxLayout(self.tab_reports)
        
        # Splitter to divide reports list and detailed report viewer
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left side: list of reports
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.addWidget(QLabel("Recent Deep Scans:"))
        self.reports_list = QListWidget()
        self.reports_list.itemClicked.connect(self.display_report_details)
        list_layout.addWidget(self.reports_list)
        splitter.addWidget(list_widget)
        
        # Right side: report details
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.addWidget(QLabel("Scan Analysis Report Details:"))
        
        self.report_viewer = QTextEdit()
        self.report_viewer.setReadOnly(True)
        self.report_viewer.setFont(QFont("Consolas", 10))
        details_layout.addWidget(self.report_viewer)
        splitter.addWidget(details_widget)
        
        splitter.setSizes([300, 550])
        self.load_reports_list()

    def load_reports_list(self):
        self.reports_list.clear()
        # Read server/outputs folder
        for file in sorted(OUTPUTS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                ts = data.get("created_at", "")
                url = data.get("url", "")
                scan_id = data.get("scan_id", file.stem)
                
                # Format string
                try:
                    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    ts_str = dt.strftime("%H:%M:%S")
                except Exception:
                    ts_str = ts[:10]
                    
                self.reports_list.addItem(f"[{ts_str}] {url} | ID: {scan_id}")
            except Exception:
                continue

    def display_report_details(self, item):
        if not item:
            return
        text = item.text()
        if "ID: " not in text:
            return
        scan_id = text.split("ID: ")[1].strip()
        report_file = OUTPUTS_DIR / f"{scan_id}.json"
        
        if not report_file.exists():
            # Fallback to server/outputs just in case
            report_file = ROOT_DIR / "server" / "outputs" / f"{scan_id}.json"
            if not report_file.exists():
                self.report_viewer.setPlainText("Report file not found.")
                return
            
        try:
            report_data = json.loads(report_file.read_text(encoding="utf-8"))
            formatted_json = json.dumps(report_data, indent=2)
            self.report_viewer.setPlainText(formatted_json)
        except Exception as e:
            self.report_viewer.setPlainText(f"Error reading report: {e}")

    def setup_whitelist_tab(self):
        layout = QVBoxLayout(self.tab_whitelist)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left side: Base Whitelist (readonly)
        base_widget = QWidget()
        base_layout = QVBoxLayout(base_widget)
        base_layout.addWidget(QLabel("Base Whitelist (Built-in, Read-only):"))
        self.base_whitelist_list = QListWidget()
        base_layout.addWidget(self.base_whitelist_list)
        splitter.addWidget(base_widget)
        
        # Right side: User Whitelist (Editable)
        user_widget = QWidget()
        user_layout = QVBoxLayout(user_widget)
        user_layout.addWidget(QLabel("Personal Whitelist (Custom additions):"))
        self.user_whitelist_list = QListWidget()
        user_layout.addWidget(self.user_whitelist_list)
        
        # Input & actions for custom whitelist
        input_bar = QHBoxLayout()
        self.whitelist_input = QLineEdit()
        self.whitelist_input.setPlaceholderText("Enter domain name (e.g. mybank.com)...")
        add_btn = QPushButton("Add Domain")
        add_btn.clicked.connect(self.add_whitelist_domain)
        input_bar.addWidget(self.whitelist_input)
        input_bar.addWidget(add_btn)
        user_layout.addLayout(input_bar)
        
        remove_btn = QPushButton("Remove Selected Domain")
        remove_btn.clicked.connect(self.remove_whitelist_domain)
        remove_btn.setStyleSheet("background-color: #ef4444;")
        user_layout.addWidget(remove_btn)
        
        splitter.addWidget(user_widget)
        splitter.setSizes([400, 400])
        
        self.load_whitelists()

    def load_whitelists(self):
        self.base_whitelist_list.clear()
        self.user_whitelist_list.clear()
        
        # Read base whitelist
        base_file = WHITELIST_DIR / "whitelist_fast.json"
        if not base_file.exists():
            base_file = ROOT_DIR / "whitelist" / "whitelist_fast.json"
            
        if base_file.exists():
            try:
                domains = json.loads(base_file.read_text(encoding="utf-8"))
                for d in sorted(domains):
                    self.base_whitelist_list.addItem(d)
            except Exception:
                pass
                
        # Read user whitelist
        user_file = WHITELIST_DIR / "user_whitelist.json"
        if user_file.exists():
            try:
                data = json.loads(user_file.read_text(encoding="utf-8"))
                domains = data.get("user_added_domains", [])
                for d in sorted(domains):
                    self.user_whitelist_list.addItem(d)
            except Exception:
                pass

    def add_whitelist_domain(self):
        domain = self.whitelist_input.text().strip().lower()
        if not domain:
            return
        
        # Clean domain
        domain = domain.replace("https://", "").replace("http://", "").split("/")[0].replace("www.", "")
        if not domain:
            return
            
        user_file = WHITELIST_DIR / "user_whitelist.json"
        domains = []
        version = "1.0"
        if user_file.exists():
            try:
                data = json.loads(user_file.read_text(encoding="utf-8"))
                domains = data.get("user_added_domains", [])
                version = data.get("version", "1.0")
            except Exception:
                domains = []
                
        if domain not in domains:
            domains.append(domain)
            try:
                payload = {"version": version, "user_added_domains": domains}
                user_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                self.whitelist_input.clear()
                self.load_whitelists()
            except Exception as e:
                print("Error saving whitelist addition", e)

    def remove_whitelist_domain(self):
        selected_item = self.user_whitelist_list.currentItem()
        if not selected_item:
            return
        domain = selected_item.text()
        
        user_file = WHITELIST_DIR / "user_whitelist.json"
        if user_file.exists():
            try:
                data = json.loads(user_file.read_text(encoding="utf-8"))
                domains = data.get("user_added_domains", [])
                version = data.get("version", "1.0")
                if domain in domains:
                    domains.remove(domain)
                    payload = {"version": version, "user_added_domains": domains}
                    user_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    self.load_whitelists()
            except Exception:
                pass

    def setup_manual_scan_tab(self):
        layout = QVBoxLayout(self.tab_manual_scan)
        
        desc = QLabel("Enter any URL below to run the complete PhishGuard threat analysis pipeline (WHOIS, DNS, DOM, redirect chain, and network traffic):")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        input_bar = QHBoxLayout()
        self.manual_url_input = QLineEdit()
        self.manual_url_input.setPlaceholderText("https://suspicious-site.com/login")
        self.scan_start_btn = QPushButton("Start Diagnostic Scan")
        self.scan_start_btn.clicked.connect(self.run_manual_scan)
        
        input_bar.addWidget(self.manual_url_input)
        input_bar.addWidget(self.scan_start_btn)
        layout.addLayout(input_bar)
        
        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 0) # Infinite busy status
        self.scan_progress.hide()
        layout.addWidget(self.scan_progress)
        
        self.scan_results_viewer = QTextEdit()
        self.scan_results_viewer.setReadOnly(True)
        self.scan_results_viewer.setFont(QFont("Consolas", 10))
        layout.addWidget(self.scan_results_viewer)

    def run_manual_scan(self):
        url = self.manual_url_input.text().strip()
        if not url:
            return
            
        self.scan_start_btn.setEnabled(False)
        self.scan_progress.show()
        self.scan_results_viewer.setPlainText("Initializing tools and performing diagnostic scan on: " + url + "\nRunning WHOIS query, DNS resolution checks, DOM layout heuristics, and redirects tracker...")
        
        # Run deep scan asynchronously in a worker thread
        def scan_worker():
            try:
                import asyncio
                from server.tools import dns_tool, dom_tool, network_tool, redirect_tool, whois_tool
                
                # Check URL format
                parsed = urlparse(url)
                if not parsed.scheme:
                    full_url = "http://" + url
                else:
                    full_url = url
                    
                # Run the synchronous/asynchronous scan tools in a thread-safe gather event loop
                async def run_pipeline():
                    whois_task = asyncio.to_thread(whois_tool.run, full_url)
                    dns_task = asyncio.to_thread(dns_tool.run, full_url)
                    dom_task = dom_tool.run(full_url)
                    redirect_task = redirect_tool.run(full_url)
                    network_task = network_tool.run(full_url)
                    
                    results = await asyncio.gather(
                        whois_task, dns_task, dom_task, redirect_task, network_task,
                        return_exceptions=True
                    )
                    return results
                
                # Standard pattern for running asyncio loop in thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(run_pipeline())
                loop.close()
                
                import uuid
                scan_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
                
                # Format document
                document = {
                    "scan_id": scan_id,
                    "url": full_url,
                    "source": "desktop_manual",
                    "created_at": datetime.datetime.now().isoformat() + "Z",
                    "tools": {
                        "whois": res[0] if not isinstance(res[0], Exception) else {"status": "error", "reason": str(res[0])},
                        "dns": res[1] if not isinstance(res[1], Exception) else {"status": "error", "reason": str(res[1])},
                        "dom": res[2] if not isinstance(res[2], Exception) else {"status": "error", "reason": str(res[2])},
                        "nlp": {"status": "ok", "data": {"placeholder": True, "message": "Developer NLP output slot reserved"}},
                        "redirect_chain": res[3] if not isinstance(res[3], Exception) else {"status": "error", "reason": str(res[3])},
                        "network_traffic": res[4] if not isinstance(res[4], Exception) else {"status": "error", "reason": str(res[4])},
                    },
                }
                
                # Write to disk
                report_file = OUTPUTS_DIR / f"{scan_id}.json"
                report_file.write_text(json.dumps(document, indent=2), encoding="utf-8")
                
                # Also log this manual scan to logs/browsing_log.json
                log_file = LOGS_DIR / "browsing_log.json"
                log_entry = {
                    "timestamp": datetime.datetime.now().isoformat() + "Z",
                    "source": "desktop_manual",
                    "url": full_url,
                    "fastTierFlag": "Clean diagnostic request",
                    "deepScanRun": True,
                    "userAction": "Diagnostic Scan Completed",
                    "note": f"Manual scan initiated directly from desktop interface.",
                    "scanId": scan_id
                }
                
                existing_logs = []
                if log_file.exists():
                    try:
                        existing_logs = json.loads(log_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                existing_logs.append(log_entry)
                log_file.write_text(json.dumps(existing_logs, indent=2), encoding="utf-8")
                
                # Send result back to GUI thread
                self.manual_scan_finished(document)
            except Exception as e:
                self.manual_scan_error(str(e))
                
        threading.Thread(target=scan_worker, daemon=True).start()

    def manual_scan_finished(self, document):
        # We must interact with UI widgets from the GUI main thread, so these are thread safe callback calls
        self.scan_start_btn.setEnabled(True)
        self.scan_progress.hide()
        formatted_json = json.dumps(document, indent=2)
        self.scan_results_viewer.setPlainText("Scan Complete! Result saved as Scan ID: " + document["scan_id"] + "\n\n" + formatted_json)
        self.load_reports_list()
        self.load_logs()

    def manual_scan_error(self, err_msg):
        self.scan_start_btn.setEnabled(True)
        self.scan_progress.hide()
        self.scan_results_viewer.setPlainText("Error occurred during diagnostic scan:\n" + err_msg)

    # REFRESH DASHBOARD STATS
    def refresh_dashboard(self):
        self.update_api_status_labels()
        log_file = LOGS_DIR / "browsing_log.json"
        if not log_file.exists():
            return
            
        try:
            logs = json.loads(log_file.read_text(encoding="utf-8"))
            
            total_checks = len(logs)
            suspicious_checks = sum(1 for log in logs if "suspicious" in log.get("fastTierFlag", "").lower() or "flagged" in log.get("fastTierFlag", "").lower())
            
            # Today's checks
            today_str = datetime.date.today().isoformat()
            today_logs = [log for log in logs if log.get("timestamp", "").startswith(today_str)]
            
            today_total = len(today_logs)
            today_flagged = sum(1 for log in today_logs if "suspicious" in log.get("fastTierFlag", "").lower() or "flagged" in log.get("fastTierFlag", "").lower())
            
            total_deep_scans = sum(1 for log in logs if log.get("deepScanRun", False))
            
            # Last scan time
            last_check_time = "Never"
            if logs:
                ts = logs[-1].get("timestamp", "")
                try:
                    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    last_check_time = dt.strftime("%H:%M:%S")
                except Exception:
                    last_check_time = ts
                    
            # Most active API calculation
            api_counts = {}
            for log in logs:
                details = log.get("details", {})
                if not details:
                    continue
                blocklists = details.get("blocklists", {})
                if blocklists.get("verdict") == "suspicious":
                    for result in blocklists.get("results", []):
                        if result.get("verdict") == "suspicious":
                            name = result.get("api_display_name", result.get("api", "Unknown"))
                            api_counts[name] = api_counts.get(name, 0) + 1
                            
            most_active = "None"
            if api_counts:
                most_active = max(api_counts, key=api_counts.get)
                most_active = f"{most_active} ({api_counts[most_active]} flags)"
                
            # Update labels
            self.stats_widgets["scanned_today"].setText(str(today_total))
            self.stats_widgets["flagged_today"].setText(str(today_flagged))
            self.stats_widgets["scanned_total"].setText(str(total_checks))
            self.stats_widgets["flagged_total"].setText(str(suspicious_checks))
            self.stats_widgets["deep_scans_total"].setText(str(total_deep_scans))
            self.stats_widgets["most_active_api"].setText(most_active)
            self.last_scan_val.setText(last_check_time)
            
        except Exception as e:
            print("Error refreshing stats dashboard", e)

    # PROTECTION CONTROL STATE
    def toggle_protection(self):
        from server.routers import fast_tier as ft
        ft.PROTECTION_ACTIVE = not ft.PROTECTION_ACTIVE
        self.update_protection_ui()

    def update_protection_ui(self):
        from server.routers import fast_tier as ft
        if ft.PROTECTION_ACTIVE:
            self.status_title.setText("PhishGuard Protection: ACTIVE")
            self.status_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #10b981;")
            self.toggle_btn.setText("Pause Protection")
            self.toggle_btn.setStyleSheet("background-color: #ef4444; min-width: 140px;")
            self.tray_icon.setIcon(self.icon_running)
            self.setWindowIcon(self.icon_running)
            self.tray_icon.setToolTip("PhishGuard - Active")
            self.pause_resume_action.setText("Pause Protection")
        else:
            self.status_title.setText("PhishGuard Protection: PAUSED")
            self.status_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f59e0b;")
            self.toggle_btn.setText("Resume Protection")
            self.toggle_btn.setStyleSheet("background-color: #10b981; min-width: 140px;")
            self.tray_icon.setIcon(self.icon_paused)
            self.setWindowIcon(self.icon_paused)
            self.tray_icon.setToolTip("PhishGuard - Paused")
            self.pause_resume_action.setText("Start Protection")

    def toggle_autostart(self, state):
        set_autostart_registry(state == Qt.CheckState.Checked.value)

    # SYSTEM TRAY INTEGRATION
    def setup_tray_ui(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.icon_running)
        self.tray_icon.setToolTip("PhishGuard - Active")
        
        # Context Menu
        menu = QMenu()
        
        open_action = menu.addAction("Open PhishGuard Console")
        open_action.triggered.connect(self.show_normal)
        
        self.pause_resume_action = menu.addAction("Pause Protection")
        self.pause_resume_action.triggered.connect(self.toggle_protection)
        
        menu.addSeparator()
        
        exit_action = menu.addAction("Exit Completely")
        exit_action.triggered.connect(self.exit_application)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick or reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_normal()

    def show_normal(self):
        self.show()
        self.activateWindow()

    def closeEvent(self, event):
        # Minimize to system tray instead of closing
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.exit_application()

    def exit_application(self):
        self.tray_icon.hide()
        # Stop uvicorn background server thread
        global server_thread
        if server_thread:
            server_thread.stop()
        QApplication.quit()


server_thread = None


def main():
    # Setup PyQt6 App
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Start FastAPI server in background thread
    global server_thread
    server_thread = ServerThread("127.0.0.1", ACTIVE_PORT)
    server_thread.start()

    # Wait a small moment to let server initialize
    time.sleep(0.5)

    # Setup Wizard check
    if get_first_launch():
        wizard = SetupWizard()
        if wizard.exec() != QDialog.DialogCode.Accepted:
            # Quit if they exit setup wizard
            server_thread.stop()
            sys.exit(0)

    # Create Main dashboard window
    window = MainWindow()
    window.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
