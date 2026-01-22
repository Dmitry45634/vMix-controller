import sys
import os
import json
import requests
import logging
import xml.etree.ElementTree as ET
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)  # оставляем вывод в консоль
    ]
)


# ==================== SETTINGS CLASS ====================
class Settings:
    def __init__(self): #define deafault settings
        logging.info("Init settings...")
        self.ip = "127.0.0.1"
        self.port = "8088"
        self.login = ""
        self.password = ""
        self.remember_creds = False
        self.show_settings = True
        self.ui_scale = 1.0
        self.fullscreen = False
        self.version = 1.2
        self.scale_slider_step = 5

    def load(self): #try to parse from json
        try:
            logging.info("Settings parse...")
            with open('vmix_settings.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.ip = data.get('ip', self.ip)
                self.port = data.get('port', self.port)
                self.login = data.get('login', self.login)
                self.password = data.get('password', self.password)
                self.remember_creds = data.get('remember_creds', False)
                self.show_settings = data.get('show_settings', True)
                self.ui_scale = data.get('ui_scale', self.ui_scale)
                self.fullscreen = data.get('fullscreen', False)
                self.version = data.get('version', self.version)
                self.scale_slider_step = data.get('scale_slider_step', self.scale_slider_step)
        except FileNotFoundError: #if theres no json create one
            logging.info("No settings file found! Creating one...")
            self.save()

    def save(self): #save json with defined settings
        logging.info("Saving settings file...")
        data = {
            'ip': self.ip,
            'port': self.port,
            'login': self.login if self.remember_creds else "",
            'password': self.password if self.remember_creds else "",
            'remember_creds': self.remember_creds,
            'show_settings': self.show_settings,
            'ui_scale': self.ui_scale,
            'fullscreen': self.fullscreen,
            'version': self.version,
            'scale_slider_step': self.scale_slider_step
        }
        with open('vmix_settings.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)


# ==================== VMIX API CLASS ====================
class vMixAPI:
    """
    API client for communicating with vMix instance.
    Handles HTTP requests and XML data parsing from vMix API.
    """

    def __init__(self, ip, port):
        """Initialize API client with server IP and port"""
        logging.info("API init...")
        self.base_url = f"http://{ip}:{port}/api"
        self.timeout = 5  # Request timeout in second

    def send_command(self, command, **params):
        """
        Send command to vMix API.

        Args:
            command: vMix API function name (e.g., "PreviewInput")
            **params: Additional parameters for the command

        Returns:
            bool: True if command was successful, False otherwise
        """
        try:
            # Build URL with command and parameters
            params_str = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{self.base_url}/?Function={command}"
            if params_str:
                url += f"&{params_str}"

            # Send HTTP GET request to vMix
            response = requests.get(url, timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Command send error: {e}")
            return False

    def get_xml_data(self):
        """
        Get raw XML data from vMix API containing current state.

        Returns:
            str: XML data string or None if failed
        """
        try:
            url = f"{self.base_url}/"
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return response.text
            return None
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error: {e}")
            return None
        except requests.exceptions.Timeout as e:
            logging.error(f"Connection timeout: {e}")
            return None
        except Exception as e:
            logging.error(f"Data retrieval error: {e}")
            return None

    def get_inputs(self):
        logging.info("Getting all inputs...")
        """
        Get list of all inputs from vMix.

        Returns:
            list: List of dictionaries containing input information
        """
        xml_data = self.get_xml_data()
        if not xml_data:
            return []

        try:
            root = ET.fromstring(xml_data)
            inputs = []

            # Parse each input element from XML
            for input_elem in root.findall('inputs/input'):
                input_data = {
                    'number': input_elem.get('number'),
                    'title': input_elem.get('title', f"Input {input_elem.get('number')}"),
                    'type': input_elem.get('type', 'Unknown'),
                    'state': input_elem.get('state', ''),
                    'duration': input_elem.get('duration', '0'),
                    'position': input_elem.get('position', '0'),
                    'short_title': input_elem.get('shortTitle', ''),
                    'key': input_elem.get('key', '')
                }
                inputs.append(input_data)
            
            logging.info(str(len(inputs)))
            return inputs
        except Exception as e:
            logging.error(f"XML parsing error: {e}")
            return []

    def get_active_input(self):
        logging.info('Getting active input...')
        """
        Get currently active (live) input number.

        Returns:
            str: Active input number or None if failed
        """
        xml_data = self.get_xml_data()
        if not xml_data:
            return None

        try:
            root = ET.fromstring(xml_data)
            active_input = root.find('active')
            if active_input is not None:
                return active_input.text
            return None
        except Exception as e:
            logging.error(f"Active input retrieval error: {e}")
            return None

    def get_preview_input(self):
        """
        Get current preview input number.

        Returns:
            str: Preview input number or None if failed
        """
        logging.info('Getting preview input...')
        xml_data = self.get_xml_data()
        if not xml_data:
            return None

        try:
            root = ET.fromstring(xml_data)
            preview_input = root.find('preview')
            if preview_input is not None:
                return preview_input.text
            return None
        except Exception as e:
            logging.error(f"Preview input retrieval error: {e}")
            return None


# ==================== INPUT TILE WIDGET ====================
class InputTile(QWidget):
    """
    Custom widget representing a single vMix input as a tile.
    Displays input number and title with visual state indicators.
    """
    clicked = pyqtSignal(str)  # Signal emitted when tile is clicked

    def __init__(self, input_data, is_active=False, is_preview=False, parent=None, scale_factor=1.0):
        """
        Initialize input tile widget.

        Args:
            input_data: Dictionary containing input information
            is_active: Whether this input is currently active/live
            is_preview: Whether this input is in preview
            parent: Parent widget
            scale_factor: UI scaling factor for responsive design
        """
        super().__init__(parent)
        self.input_data = input_data
        self.is_active = is_active
        self.is_preview = is_preview
        self.scale_factor = scale_factor
        self.base_size = QSize(130, 100)  # Base size for 100% scale
        self.setup_ui()
        self.setMouseTracking(True)  # Enable mouse tracking for hover effects

    def setup_ui(self):
        """Setup the tile UI with labels and styling"""
        # Apply scaling to tile size
        scaled_size = self.base_size * self.scale_factor
        self.setFixedSize(scaled_size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)  # Hand cursor on hover

        # Create vertical layout for tile content
        layout = QVBoxLayout(self)
        scaled_margin = int(5 * self.scale_factor)
        layout.setContentsMargins(scaled_margin, scaled_margin, scaled_margin, scaled_margin)
        layout.setSpacing(int(2 * self.scale_factor))

        # Get and truncate title if too long
        title = self.input_data.get('short_title') or self.input_data.get('title', '')
        title_length = int(18 * self.scale_factor)
        if len(title) > title_length:
            title = title[:int(title_length * 0.8)] + "..."

        # Input number label (e.g., "V1")
        self.number_label = QLabel(f"V{self.input_data['number']}")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setStyleSheet(self.get_number_style())

        # Input title label
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)  # Allow text wrapping
        self.title_label.setStyleSheet(self.get_title_style())

        # Add widgets to layout
        layout.addWidget(self.number_label)
        layout.addWidget(self.title_label)

        # Set tooltip with full title
        self.setToolTip(f"V{self.input_data['number']}: {title}")
        self.update_style()

    def get_number_style(self):
        """Generate dynamic CSS style for number label based on scale"""
        font_size = int(24 * self.scale_factor)
        return f"""
            QLabel {{
                color: white;
                font-weight: bold;
                font-size: {font_size}px;
                background: transparent;
            }}
        """

    def get_title_style(self):
        """Generate dynamic CSS style for title label based on state and scale"""
        font_size = int(13 * self.scale_factor)
        # Different color based on active/preview state
        if self.is_active or self.is_preview:
            color = "white"
        else:
            color = "#dddddd"
        return f"""
            QLabel {{
                color: {color};
                font-size: {font_size}px;
                background: transparent;
            }}
        """

    def paintEvent(self, event):
        """
        Custom paint event to draw rounded rectangle background.
        Called automatically by Qt for custom widget painting.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # Smooth edges

        # Determine background and border colors based on state
        if self.is_active:
            bg_color = QColor("#ff4444")  # Red for active input
            border_color = QColor("#ff0000")
            border_width = int(3 * self.scale_factor)
        elif self.is_preview:
            bg_color = QColor("#44aaff")  # Blue for preview input
            border_color = QColor("#0088ff")
            border_width = int(3 * self.scale_factor)
        else:
            bg_color = QColor("#404B56")  # Gray for regular inputs
            border_color = QColor("#555555")
            border_width = int(2 * self.scale_factor)

        # Apply scaling to padding
        padding = int(5 * self.scale_factor)
        rect = self.rect().adjusted(padding, padding, -padding, -padding)
        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, border_width))

        # Apply scaling to border radius
        radius = int(10 * self.scale_factor)
        painter.drawRoundedRect(rect, radius, radius)

        super().paintEvent(event)

    def update_style(self):
        """Update widget styles and trigger repaint"""
        self.number_label.setStyleSheet(self.get_number_style())
        self.title_label.setStyleSheet(self.get_title_style())
        self.update()

    def mousePressEvent(self, event):
        """Handle mouse click events - emit clicked signal"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.input_data['number'])
            event.accept()

    def enterEvent(self, event):
        """Handle mouse enter events for hover effects"""
        if not self.is_active and not self.is_preview:
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave events"""
        self.update()
        super().leaveEvent(event)

    def set_active(self, active):
        """Set active state and update appearance"""
        self.is_active = active
        self.update_style()

    def set_preview(self, preview):
        """Set preview state and update appearance"""
        self.is_preview = preview
        self.update_style()

    def set_scale(self, scale_factor):
        """Change tile scale and rebuild UI"""
        self.scale_factor = scale_factor
        self.setup_ui()  # Recreate UI with new scale


# ==================== MAIN APPLICATION WINDOW ====================
class VMixController(QMainWindow):
    """
    Main application window for vMix Controller.
    Contains all UI elements and handles vMix communication.
    """

    def __init__(self):
        logging.info("Init main windows class")
        super().__init__()
        # Initialize settings and API
        self.settings = Settings()
        self.settings.load()
        self.vmix_api = None

        # State tracking
        self.input_tiles = {}  # Dictionary of input number -> tile widget
        self.selected_input = None
        self.active_input = None
        self.preview_input = None

        # Timers for periodic updates and effects
        self.timer = QTimer()
        self.ftb_timer = QTimer()
        self.ftb_flash_state = False
        self.ftb_active = False

        # Overlay state tracking
        self.active_overlays = {1: False, 2: False, 3: False, 4: False}

        # Base sizes for scaling - store original 100% scale sizes
        self.base_sizes = {
            'window': QSize(1100, 800),
            'tile': QSize(130, 100),
            'quick_play_btn': QSize(120, 0),  # 0 means auto height
            'ftb_btn': QSize(120, 0),
            'settings_btn': QSize(90, 35),
            'refresh_btn': QSize(90, 35),
            'overlay_btn': QSize(70, 0),
            'preview_label': QSize(180, 0),
            'active_label': QSize(180, 0)
        }

        self.setup_ui()
        self.setWindowTitle("vMix Controller")

        # Apply saved UI scale
        self.apply_scale(self.settings.ui_scale)

        # Apply fullscreen mode if saved
        if self.settings.fullscreen:
            self.toggle_fullscreen()

        # Setup timers
        self.timer.timeout.connect(self.update_states)
        self.timer.start(1000)  # Update every second

        self.ftb_timer.timeout.connect(self.toggle_ftb_flash)
        self.ftb_timer.setInterval(500)  # Flash every 500ms for FTB

        # Auto-connect after short delay
        QTimer.singleShot(500, self.auto_connect)

        # Setup keyboard shortcuts
        self.setup_hotkeys()

    def setup_hotkeys(self):
        logging.info("Hotkey init")
        """Setup keyboard shortcuts for application"""
        # F11 for toggling fullscreen mode
        shortcut = QShortcut(QKeySequence("F11"), self)
        shortcut.activated.connect(self.toggle_fullscreen)

        # Escape for exiting fullscreen mode
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self.exit_fullscreen)

    def auto_connect(self):
        """Attempt auto-connect if IP is not localhost"""
        logging.info("Tried to autoconnect!")
        if self.settings.ip and self.settings.ip != "127.0.0.1":
            self.connect_to_vmix()

    def setup_ui(self):
        logging.info("UI setting up...")
        """Setup all UI elements and layouts"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(2)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # ========== INPUTS HEADER ==========
        inputs_header_layout = QHBoxLayout()

        inputs_label = QLabel("Inputs")
        inputs_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 13px;
                color: #bbb;
            }
        """)
        inputs_header_layout.addWidget(inputs_label)

        inputs_header_layout.addStretch()  # Push to left

        main_layout.addLayout(inputs_header_layout)

        # ========== INPUT TILES CONTAINER ==========
        self.tiles_container = QWidget()
        self.tiles_container.setStyleSheet("""
            QWidget {
                background-color: #1E2328;  /* Container background */
            }
        """)

        # Custom flow layout for tiles (wraps to next line)
        self.tiles_layout = QFlowLayout(self.tiles_container)
        self.tiles_layout.setSpacing(10)
        self.tiles_layout.setContentsMargins(35, 20, 35, 20)

        # Scroll area for tiles (in case many inputs)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.tiles_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(400)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 2px solid #555;
                border-radius: 6px;
                background: #1E2328;
            }
            QScrollBar:vertical {
                border: none;
                background: #222;
                width: 40px;
                border-radius: 10px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #666;
                border-radius: 10px;
                min-height: 40px;
            }
            QScrollBar::handle:vertical:hover {
                background: #888;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar:horizontal {
                height: 0px;
            }
        """)

        main_layout.addWidget(scroll_area)

        # ========== CONTROL PANEL ==========
        self.control_group = QGroupBox()
        self.control_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #555;
                border-radius: 6px;
                margin-top: 2px;
                padding-top: 0px;
                color: #bbb;
            }
        """)

        self.control_layout = QVBoxLayout()
        self.control_layout.setSpacing(8)

        # ========== ROW 1: QUICK PLAY, FTB + RIGHT BUTTONS ==========
        self.row1 = QHBoxLayout()
        self.row1.setSpacing(8)
        self.row1.setContentsMargins(0, 0, 0, 0)

        # Quick Play button
        self.btn_quick_play = QPushButton("QUICK PLAY")
        self.btn_quick_play.clicked.connect(self.quick_play)
        self.btn_quick_play.setToolTip("Smooth transition from preview to program")
        self.btn_quick_play.setEnabled(False)  # Disabled until connected
        self.row1.addWidget(self.btn_quick_play)

        # Fade To Black button
        self.btn_ftb = QPushButton("FTB")
        self.btn_ftb.clicked.connect(self.fade_to_black)
        self.btn_ftb.setToolTip("Fade To Black")
        self.btn_ftb.setEnabled(False)  # Disabled until connected
        self.row1.addWidget(self.btn_ftb)

        self.row1.addStretch()  # Push buttons to left

        # Right side buttons container
        self.right_buttons_layout = QHBoxLayout()
        self.right_buttons_layout.setSpacing(6)
        self.right_buttons_layout.setContentsMargins(0, 8, 0, 0)

        # Settings toggle button
        self.btn_toggle_settings = QPushButton("Settings")
        self.btn_toggle_settings.clicked.connect(self.toggle_settings)
        self.right_buttons_layout.addWidget(self.btn_toggle_settings)

        # Refresh button
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_inputs)
        self.btn_refresh.setToolTip("Refresh inputs list")
        self.btn_refresh.setEnabled(False)  # Disabled until connected
        self.right_buttons_layout.addWidget(self.btn_refresh)

        self.row1.addLayout(self.right_buttons_layout)
        self.control_layout.addLayout(self.row1)

        # ========== ROW 2: OVERLAYS AND PREVIEW/PROGRAM ==========
        self.second_row_container = QWidget()
        self.second_row_layout = QHBoxLayout(self.second_row_container)
        self.second_row_layout.setSpacing(10)
        self.second_row_layout.setContentsMargins(0, 0, 0, 0)

        # ========== LEFT SIDE: OVERLAY BUTTONS ==========
        self.overlay_container = QWidget()
        self.overlay_layout = QVBoxLayout(self.overlay_container)
        self.overlay_layout.setSpacing(4)
        self.overlay_layout.setContentsMargins(0, 0, 0, 0)

        # Overlay section label
        self.overlay_label = QLabel("OVERLAY")
        self.overlay_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 13px;
                color: #bbb;
            }
        """)
        self.overlay_layout.addWidget(self.overlay_label)

        # Overlay buttons container
        self.overlay_buttons_widget = QWidget()
        self.overlay_buttons_layout = QHBoxLayout(self.overlay_buttons_widget)
        self.overlay_buttons_layout.setSpacing(4)
        self.overlay_buttons_layout.setContentsMargins(0, 0, 0, 0)

        # Overlay buttons 1-4
        self.btn_overlay1 = QPushButton("LAYER 1")
        self.btn_overlay1.clicked.connect(lambda: self.overlay_selected(1))
        self.btn_overlay1.setToolTip("Overlay on layer 1")
        self.btn_overlay1.setEnabled(False)
        self.overlay_buttons_layout.addWidget(self.btn_overlay1)

        self.btn_overlay2 = QPushButton("LAYER 2")
        self.btn_overlay2.clicked.connect(lambda: self.overlay_selected(2))
        self.btn_overlay2.setToolTip("Overlay on layer 2")
        self.btn_overlay2.setEnabled(False)
        self.overlay_buttons_layout.addWidget(self.btn_overlay2)

        self.btn_overlay3 = QPushButton("LAYER 3")
        self.btn_overlay3.clicked.connect(lambda: self.overlay_selected(3))
        self.btn_overlay3.setToolTip("Overlay on layer 3")
        self.btn_overlay3.setEnabled(False)
        self.overlay_buttons_layout.addWidget(self.btn_overlay3)

        self.btn_overlay4 = QPushButton("LAYER 4")
        self.btn_overlay4.clicked.connect(lambda: self.overlay_selected(4))
        self.btn_overlay4.setToolTip("Overlay on layer 4")
        self.btn_overlay4.setEnabled(False)
        self.overlay_buttons_layout.addWidget(self.btn_overlay4)

        # Remove overlay button
        self.btn_remove_overlay = QPushButton("REMOVE")
        self.btn_remove_overlay.clicked.connect(self.remove_overlay)
        self.btn_remove_overlay.setToolTip("Remove overlay from active layer")
        self.btn_remove_overlay.setEnabled(False)
        self.overlay_buttons_layout.addWidget(self.btn_remove_overlay)

        self.overlay_layout.addWidget(self.overlay_buttons_widget)
        self.second_row_layout.addWidget(self.overlay_container)

        self.second_row_layout.addStretch()  # Push to sides

        # ========== RIGHT SIDE: PREVIEW AND PROGRAM ==========
        self.preview_active_container = QWidget()
        self.preview_active_layout = QVBoxLayout(self.preview_active_container)
        self.preview_active_layout.setSpacing(4)
        self.preview_active_layout.setContentsMargins(0, 0, 0, 0)

        # Preview and Program labels row
        self.labels_row = QHBoxLayout()
        self.labels_row.setSpacing(10)
        self.labels_row.setContentsMargins(0, 0, 0, 0)

        self.preview_label = QLabel("PREVIEW")
        self.preview_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 13px;
                color: #44aaff;
                min-width: 180px;
                text-align: center;
            }
        """)
        self.labels_row.addWidget(self.preview_label)

        self.active_label = QLabel("PROGRAM")
        self.active_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 13px;
                color: #ff4444;
                min-width: 180px;
                text-align: center;
            }
        """)
        self.labels_row.addWidget(self.active_label)

        self.preview_active_layout.addLayout(self.labels_row)

        # Preview and Program input display row
        self.inputs_row = QHBoxLayout()
        self.inputs_row.setSpacing(10)
        self.inputs_row.setContentsMargins(0, 0, 0, 0)

        self.preview_input_label = QLabel("Not selected")
        self.inputs_row.addWidget(self.preview_input_label)

        self.active_input_label = QLabel("No data")
        self.inputs_row.addWidget(self.active_input_label)

        self.preview_active_layout.addLayout(self.inputs_row)
        self.second_row_layout.addWidget(self.preview_active_container)

        self.control_layout.addWidget(self.second_row_container)
        self.control_group.setLayout(self.control_layout)
        main_layout.addWidget(self.control_group)

        # ========== SETTINGS PANEL (BOTTOM) ==========
        self.settings_group = QGroupBox("Settings")
        self.settings_group.setVisible(self.settings.show_settings)

        self.settings_layout = QGridLayout()
        self.settings_layout.setSpacing(10)
        self.settings_layout.setContentsMargins(15, 15, 15, 15)

        #IP and Port
        
        #label
        ip_label = QLabel("IP Address:")
        self.settings_layout.addWidget(ip_label, 0, 0)

        #text boxes ip:port
        self.ip_edit = QLineEdit(self.settings.ip)
        self.ip_edit.setPlaceholderText("Example: 192.168.1.100")

        self.port_edit = QLineEdit(self.settings.port)
        self.port_edit.setPlaceholderText("8088")
        
        #create a layout
        ip_port_layout = QHBoxLayout()
        ip_port_layout.addWidget(self.ip_edit, 0)
        ip_port_layout.addWidget(QLabel(":"))
        ip_port_layout.addWidget(self.port_edit, 0)
        self.settings_layout.addLayout(ip_port_layout, 0, 1)

        # Login and Password
        login_label = QLabel("Login:")
        self.settings_layout.addWidget(login_label, 1, 0)

        self.login_edit = QLineEdit(self.settings.login)
        self.login_edit.setPlaceholderText("Default: admin")
        self.settings_layout.addWidget(self.login_edit, 1, 1)

        pass_label = QLabel("Password:")
        self.settings_layout.addWidget(pass_label, 2, 0)

        self.pass_edit = QLineEdit(self.settings.password)
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("Your Password")
        self.settings_layout.addWidget(self.pass_edit, 2, 1)

        # Checkbox and connect
        self.remember_check = QCheckBox("Remember credentials")
        self.remember_check.setChecked(self.settings.remember_creds)
        
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_to_vmix)
        
        connecting_layout = QHBoxLayout()
        connecting_layout.setSpacing(40)
        connecting_layout.addWidget(self.remember_check, 0)
        connecting_layout.addWidget(self.btn_connect, 1)
        self.settings_layout.addLayout(connecting_layout, 3, 1)

        # Scale slider
        scale_label = QLabel("UI Scale:")
        self.settings_layout.addWidget(scale_label, 0, 2)

        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(70, 180)  # 70% to 180%
        self.scale_slider.setValue(int(self.settings.ui_scale * 100))
        self.scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.scale_slider.setTickInterval(int(self.settings.scale_slider_step)) #some parsing from settings visual interval of ticks
        self.scale_slider.setSingleStep(int(self.settings.scale_slider_step)) #some parsing from settings, sets up up and down key step behavior
        self.scale_slider.setPageStep(int(self.settings.scale_slider_step)) #some parsing from settings, fixes macos click behavior and pgup pgdown behavior
        self.scale_slider.setTracking(False) #apply changes when slider is released
        self.scale_slider.valueChanged.connect(self.on_scale_changed) #trigger this func on value change
        #alue = round(value / int(self.settings.scale_slider_step)) * int(self.settings.scale_slider_step) # rounding slider value
        self.scale_slider.sliderMoved.connect(
            lambda value: self.scale_label.setText(f"{round(value / int(self.settings.scale_slider_step)) * int(self.settings.scale_slider_step)}%")
        )
        self.settings_layout.addWidget(self.scale_slider, 0, 3)

        self.scale_label = QLabel(f"{self.scale_slider.value()}%")
        self.settings_layout.addWidget(self.scale_label, 0, 4)

        self.btn_reset_scale = QPushButton("Reset")
        self.btn_reset_scale.clicked.connect(self.reset_scale)
        self.settings_layout.addWidget(self.btn_reset_scale, 1, 3)
        
        #Save button
        self.btn_save = QPushButton("Save settings")
        self.btn_save.clicked.connect(self.save_settings)
        self.settings_layout.addWidget(self.btn_save, 3, 4)

        #Fullscreen mode
        fullscreen_label = QLabel("Fullscreen mode:")
        self.settings_layout.addWidget(fullscreen_label, 2, 2)

        self.fullscreen_checkbox = QCheckBox("Enable fullscreen mode (F11)")
        self.fullscreen_checkbox.setChecked(self.settings.fullscreen)
        self.fullscreen_checkbox.stateChanged.connect(self.toggle_fullscreen)
        self.settings_layout.addWidget(self.fullscreen_checkbox, 2, 3, 1, 3)

        self.settings_group.setLayout(self.settings_layout)

        # Add settings panel to bottom
        main_layout.addWidget(self.settings_group)

        # ========== STATUS BAR ==========
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2d3748, stop:1 #1a202c);
                color: #e2e8f0;
                font-weight: bold;
                font-size: 12px;
                padding: 5px;
                border-top: 1px solid #4a5568;
            }
        """)

        self.status_bar.showMessage("Ready to connect")
        logging.info("Ready to connect")

        # Version label in status bar
        version_str = "Version: " + str(self.settings.version)
        self.version = QLabel(version_str)
        self.version.setStyleSheet("""
                    QLabel {
                        color: #718096;
                        font-size: 14px;
                        font-style: italic;
                        padding-right: 10px;
                    }
                """)
        self.status_bar.addPermanentWidget(self.version)

        # Initialize all styles after creating widgets
        self.update_all_styles()

    # ========== SCALING AND STYLING METHODS ==========

    def update_scale_display(self, value):
        """Update scale display label without applying changes"""
        self.scale_label.setText(f"{value}%")

    def on_scale_changed(self, value):
        scale_factor = round(value / int(self.settings.scale_slider_step)) * int(self.settings.scale_slider_step) # rounding slider value
        scale_factor = scale_factor / 100 # convert to scale factor
        self.status_bar.showMessage(str(scale_factor), 3000)
        logging.info("Scaling changed to " + str(scale_factor))
        self.scale_label.setText(f"{value}%")
        self.scale_slider.setValue(int(scale_factor * 100)) # set slider to round value
        self.apply_scale(scale_factor) # apply scale

    def get_large_button_style(self, bg_color="#2196F3"):
        """Generate CSS style for large buttons (QUICK PLAY, FTB) with scaling"""
        return f"""
            QPushButton {{
                padding: {int(14 * self.settings.ui_scale)}px {int(25 * self.settings.ui_scale)}px;
                font-weight: bold;
                font-size: {int(15 * self.settings.ui_scale)}px;
                border: {int(2 * self.settings.ui_scale)}px solid #666;
                border-radius: {int(6 * self.settings.ui_scale)}px;
                min-width: {int(120 * self.settings.ui_scale)}px;
                color: white;
                background: {bg_color};
            }}
            QPushButton:hover {{
                border: {int(2 * self.settings.ui_scale)}px solid #888;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #505050, stop:1 #404040);
            }}
            QPushButton:disabled {{
                background: #555;
                color: #888;
            }}
        """

    def get_ftb_active_style(self):
        """Generate flashing style for active FTB button"""
        if self.ftb_flash_state:
            return f"""
                QPushButton {{
                    padding: {int(14 * self.settings.ui_scale)}px {int(25 * self.settings.ui_scale)}px;
                    font-weight: bold;
                    font-size: {int(15 * self.settings.ui_scale)}px;
                    border: {int(2 * self.settings.ui_scale)}px solid #ff0000;
                    border-radius: {int(6 * self.settings.ui_scale)}px;
                    min-width: {int(120 * self.settings.ui_scale)}px;
                    color: white;
                    background: #ff4444;
                }}
                QPushButton:hover {{
                    background: #ff6666;
                    border: {int(2 * self.settings.ui_scale)}px solid #ff3333;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    padding: {int(14 * self.settings.ui_scale)}px {int(25 * self.settings.ui_scale)}px;
                    font-weight: bold;
                    font-size: {int(15 * self.settings.ui_scale)}px;
                    border: {int(2 * self.settings.ui_scale)}px solid #cc0000;
                    border-radius: {int(6 * self.settings.ui_scale)}px;
                    min-width: {int(120 * self.settings.ui_scale)}px;
                    color: white;
                    background: #cc3333;
                }}
                QPushButton:hover {{
                    background: #dd4444;
                    border: {int(2 * self.settings.ui_scale)}px solid #dd2222;
                }}
            """

    def get_small_button_style(self, bg_color):
        """Generate CSS style for small buttons (Settings, Refresh)"""
        return f"""
            QPushButton {{
                padding: {int(5 * self.settings.ui_scale)}px {int(10 * self.settings.ui_scale)}px;
                font-weight: bold;
                font-size: {int(11 * self.settings.ui_scale)}px;
                border: {int(1 * self.settings.ui_scale)}px solid #555;
                border-radius: {int(4 * self.settings.ui_scale)}px;
                background: {bg_color};
                color: white;
            }}
            QPushButton:hover {{
                background: {self.darken_color(bg_color)};
                border: {int(1 * self.settings.ui_scale)}px solid #666;
            }}
            QPushButton:disabled {{
                background: #555;
                color: #888;
            }}
        """

    def get_overlay_button_style(self):
        """Generate CSS style for overlay buttons"""
        return f"""
            QPushButton {{
                padding: {int(6 * self.settings.ui_scale)}px {int(10 * self.settings.ui_scale)}px;
                font-weight: bold;
                border: {int(2 * self.settings.ui_scale)}px solid #555;
                border-radius: {int(4 * self.settings.ui_scale)}px;
                min-width: {int(70 * self.settings.ui_scale)}px;
                color: white;
                background: #666666;
            }}
            QPushButton:hover {{
                border: {int(2 * self.settings.ui_scale)}px solid #777;
                background: #777777;
            }}
            QPushButton:disabled {{
                background: #555;
                color: #888;
            }}
        """

    def get_active_overlay_button_style(self):
        """Generate CSS style for active overlay button (orange highlight)"""
        return f"""
            QPushButton {{
                padding: {int(6 * self.settings.ui_scale)}px {int(10 * self.settings.ui_scale)}px;
                font-weight: bold;
                border: {int(2 * self.settings.ui_scale)}px solid #F57C00;
                border-radius: {int(4 * self.settings.ui_scale)}px;
                min-width: {int(70 * self.settings.ui_scale)}px;
                color: white;
                background: #FF9800;
            }}
            QPushButton:hover {{
                border: {int(2 * self.settings.ui_scale)}px solid #FFB74D;
                background: #FFB74D;
            }}
        """

    def get_preview_label_style(self):
        """Generate CSS style for preview label (blue theme)"""
        return f"""
            QLabel {{
                padding: {int(8 * self.settings.ui_scale)}px {int(12 * self.settings.ui_scale)}px;
                font-weight: bold;
                font-size: {int(13 * self.settings.ui_scale)}px;
                border: {int(3 * self.settings.ui_scale)}px solid #44aaff;
                border-radius: {int(6 * self.settings.ui_scale)}px;
                background: #2a2a2a;
                color: #44aaff;
                min-width: {int(180 * self.settings.ui_scale)}px;
                min-height: {int(23 * self.settings.ui_scale)}px;
                text-align: center;
            }}
        """

    def get_active_label_style(self):
        """Generate CSS style for program label (red theme)"""
        return f"""
            QLabel {{
                padding: {int(8 * self.settings.ui_scale)}px {int(12 * self.settings.ui_scale)}px;
                font-weight: bold;
                font-size: {int(13 * self.settings.ui_scale)}px;
                border: {int(3 * self.settings.ui_scale)}px solid #ff4444;
                border-radius: {int(6 * self.settings.ui_scale)}px;
                background: #2a2a2a;
                color: #ff4444;
                min-width: {int(180 * self.settings.ui_scale)}px;
                min-height: {int(23 * self.settings.ui_scale)}px;
                text-align: center;
            }}
        """

    def get_label_style(self):
        """Generate CSS style for labels in settings panel"""
        return f"""
            QLabel {{
                color: #cbd5e0;
                font-weight: bold;
                font-size: {int(12 * self.settings.ui_scale)}px;
                padding: {int(2 * self.settings.ui_scale)}px;
            }}
        """

    def get_input_style(self):
        """Generate CSS style for input fields"""
        return f"""
            QLineEdit {{
                padding: {int(8 * self.settings.ui_scale)}px {int(12 * self.settings.ui_scale)}px;
                font-size: {int(13 * self.settings.ui_scale)}px;
                border: {int(1 * self.settings.ui_scale)}px solid #4a5568;
                border-radius: {int(5 * self.settings.ui_scale)}px;
                background: #2d3748;
                color: #e2e8f0;
                selection-background-color: #4299e1;
            }}
            QLineEdit:focus {{
                border: {int(1 * self.settings.ui_scale)}px solid #4299e1;
                background: #2d3748;
            }}
            QLineEdit:hover {{
                border: {int(1 * self.settings.ui_scale)}px solid #718096;
            }}
        """

    def get_checkbox_style(self):
        """Generate CSS style for checkboxes"""
        return f"""
            QCheckBox {{
                color: #cbd5e0;
                font-weight: bold;
                font-size: {int(12 * self.settings.ui_scale)}px;
                spacing: {int(10 * self.settings.ui_scale)}px;
            }}
            QCheckBox::indicator {{
                width: {int(20 * self.settings.ui_scale)}px;
                height: {int(20 * self.settings.ui_scale)}px;
                background: #2d3748;
                border: {int(2 * self.settings.ui_scale)}px solid #4a5568;
                border-radius: {int(4 * self.settings.ui_scale)}px;
            }}
            QCheckBox::indicator:checked {{
                background: #4299e1;
                border: {int(2 * self.settings.ui_scale)}px solid #63b3ed;
            }}
            QCheckBox::indicator:hover {{
                border: {int(2 * self.settings.ui_scale)}px solid #718096;
            }}
        """

    def get_settings_button_style(self, color1, color2):
        """Generate CSS style for buttons in settings panel with gradient"""
        return f"""
            QPushButton {{
                padding: {int(8 * self.settings.ui_scale)}px {int(16 * self.settings.ui_scale)}px;
                font-weight: bold;
                font-size: {int(12 * self.settings.ui_scale)}px;
                border: none;
                border-radius: {int(5 * self.settings.ui_scale)}px;
                min-width: {int(80 * self.settings.ui_scale)}px;
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {color1}, stop:1 {color2});
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.lighten_color(color1)}, stop:1 {self.lighten_color(color2)});
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.darken_color(color1)}, stop:1 {self.darken_color(color2)});
            }}
        """

    def darken_color(self, color):
        """Darken color by 10% (simplified implementation)"""
        # Simplified implementation - in production you'd want proper color manipulation
        if color.startswith('#'):
            return color  # Implement proper color darkening if needed
        return color

    def lighten_color(self, color):
        """Lighten color by 10% (simplified implementation)"""
        # Simplified implementation - in production you'd want proper color manipulation
        if color.startswith('#'):
            return color  # Implement proper color lightening if needed
        return color

    # ========== SCALING APPLICATION METHODS ==========

    def apply_scale(self, scale_factor):
        """
        Apply scaling factor to entire UI.

        Args:
            scale_factor: Scaling factor (0.7 to 2.2)
        """
        # Save new scale to settings
        self.settings.ui_scale = scale_factor

        # Update window size (only if not in fullscreen)
        if not self.settings.fullscreen:
            base_window_size = self.base_sizes['window']
            new_window_size = base_window_size * scale_factor
            self.resize(new_window_size)

        # Update all styles with new scale
        self.update_all_styles()

        # Update tile scales
        self.update_tiles_scale()

        # Save settings
        self.settings.save()

    def update_all_styles(self):
        """Update all widget styles with current scale factor"""
        # Update large buttons
        self.btn_quick_play.setStyleSheet(self.get_large_button_style())

        # Update FTB button based on state
        if self.ftb_active:
            self.btn_ftb.setStyleSheet(self.get_ftb_active_style())
        else:
            self.btn_ftb.setStyleSheet(self.get_large_button_style("#666666"))

        # Update small buttons
        self.btn_toggle_settings.setStyleSheet(self.get_small_button_style("#666666"))
        self.btn_refresh.setStyleSheet(self.get_small_button_style("#607d8b"))

        # Update overlay buttons
        overlay_style = self.get_overlay_button_style()
        active_overlay_style = self.get_active_overlay_button_style()

        for i in range(1, 5):
            button = getattr(self, f'btn_overlay{i}')
            if self.active_overlays[i]:
                button.setStyleSheet(active_overlay_style)
            else:
                button.setStyleSheet(overlay_style)

        self.btn_remove_overlay.setStyleSheet(overlay_style)

        # Update labels
        self.preview_input_label.setStyleSheet(self.get_preview_label_style())
        self.active_input_label.setStyleSheet(self.get_active_label_style())

        # Update settings panel
        self.settings_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: {int(14 * self.settings.ui_scale)}px;
                border: {int(2 * self.settings.ui_scale)}px solid #4a5568;
                border-radius: {int(8 * self.settings.ui_scale)}px;
                margin-top: {int(5 * self.settings.ui_scale)}px;
                padding-top: {int(15 * self.settings.ui_scale)}px;
                color: #ffffff;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2d3748, stop:1 #1a202c);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {int(15 * self.settings.ui_scale)}px;
                padding: 0 {int(10 * self.settings.ui_scale)}px 0 {int(10 * self.settings.ui_scale)}px;
                color: #63b3ed;
                font-weight: bold;
            }}
        """)

        # Update input fields in settings
        input_style = self.get_input_style()
        self.ip_edit.setStyleSheet(input_style)
        self.port_edit.setStyleSheet(input_style)
        self.login_edit.setStyleSheet(input_style)
        self.pass_edit.setStyleSheet(input_style)

        # Update labels in settings
        label_style = self.get_label_style()
        for i in range(self.settings_layout.count()):
            widget = self.settings_layout.itemAt(i).widget()
            if isinstance(widget, QLabel):
                widget.setStyleSheet(label_style)

        # Update checkboxes
        self.remember_check.setStyleSheet(self.get_checkbox_style())
        self.fullscreen_checkbox.setStyleSheet(self.get_checkbox_style())

        # Update buttons in settings
        self.btn_save.setStyleSheet(self.get_settings_button_style("#48bb78", "#38a169"))
        self.btn_connect.setStyleSheet(self.get_settings_button_style("#4299e1", "#3182ce"))
        self.btn_reset_scale.setStyleSheet(self.get_settings_button_style("#718096", "#4a5568"))

        # Update input field sizes
        self.port_edit.setFixedWidth(int(100 * self.settings.ui_scale))

        # Update button sizes
        btn_width = int(90 * self.settings.ui_scale)
        btn_height = int(35 * self.settings.ui_scale)
        self.btn_toggle_settings.setFixedWidth(btn_width)
        self.btn_toggle_settings.setFixedHeight(btn_height)
        self.btn_refresh.setFixedWidth(btn_width)
        self.btn_refresh.setFixedHeight(btn_height)

        # Update large button sizes
        large_btn_width = int(120 * self.settings.ui_scale)
        self.btn_quick_play.setMinimumWidth(large_btn_width)
        self.btn_ftb.setMinimumWidth(large_btn_width)

        # Update layout spacings and margins
        self.control_layout.setSpacing(int(8 * self.settings.ui_scale))
        self.row1.setSpacing(int(8 * self.settings.ui_scale))
        self.right_buttons_layout.setSpacing(int(6 * self.settings.ui_scale))
        self.right_buttons_layout.setContentsMargins(0, int(8 * self.settings.ui_scale), 0, 0)
        self.second_row_layout.setSpacing(int(10 * self.settings.ui_scale))
        self.overlay_layout.setSpacing(int(4 * self.settings.ui_scale))
        self.overlay_buttons_layout.setSpacing(int(4 * self.settings.ui_scale))
        self.preview_active_layout.setSpacing(int(4 * self.settings.ui_scale))
        self.labels_row.setSpacing(int(10 * self.settings.ui_scale))
        self.inputs_row.setSpacing(int(10 * self.settings.ui_scale))
        self.settings_layout.setSpacing(int(10 * self.settings.ui_scale))
        self.settings_layout.setContentsMargins(
            int(15 * self.settings.ui_scale),
            int(15 * self.settings.ui_scale),
            int(15 * self.settings.ui_scale),
            int(15 * self.settings.ui_scale)
        )

        # Update tiles layout
        self.tiles_layout.setSpacing(int(10 * self.settings.ui_scale))
        self.tiles_layout.setContentsMargins(
            int(35 * self.settings.ui_scale),
            int(20 * self.settings.ui_scale),
            int(35 * self.settings.ui_scale),
            int(20 * self.settings.ui_scale)
        )

        # Update status bar
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2d3748, stop:1 #1a202c);
                color: #e2e8f0;
                font-weight: bold;
                font-size: {int(12 * self.settings.ui_scale)}px;
                padding: {int(5 * self.settings.ui_scale)}px;
                border-top: {int(1 * self.settings.ui_scale)}px solid #4a5568;
            }}
        """)

        # Update version label
        self.version.setStyleSheet(f"""
                    QLabel {{
                        color: #718096;
                        font-size: {int(14 * self.settings.ui_scale)}px;
                        font-style: italic;
                        padding-right: {int(10 * self.settings.ui_scale)}px;
                    }}
                """)

    def update_tiles_scale(self):
        """Update scale for all input tiles"""
        for tile in self.input_tiles.values():
            if hasattr(tile, 'set_scale'):
                tile.set_scale(self.settings.ui_scale)

    def reset_scale(self):
        """Reset UI scale to 100%"""
        self.scale_slider.setValue(100)
        self.apply_scale(1.0)

    # ========== FULLSCREEN METHODS ==========

    def toggle_fullscreen(self, checked=None):
        """
        Toggle fullscreen mode.

        Args:
            checked: Checkbox state if called from checkbox, None if from hotkey
        """
        if checked is None:
            # Called from hotkey
            self.settings.fullscreen = not self.settings.fullscreen
        else:
            # Called from checkbox
            self.settings.fullscreen = checked

        # Update checkbox state without triggering signals
        self.fullscreen_checkbox.blockSignals(True)
        self.fullscreen_checkbox.setChecked(self.settings.fullscreen)
        self.fullscreen_checkbox.blockSignals(False)

        if self.settings.fullscreen:
            # Enter fullscreen mode
            self.showFullScreen()
            self.status_bar.showMessage("🖥️ Fullscreen mode enabled", 2000)
            logging.info("Fullscreen on")

            # Save normal window geometry for restoration
            if not hasattr(self, 'normal_geometry'):
                self.normal_geometry = self.geometry()
        else:
            # Exit fullscreen mode
            self.showNormal()
            self.status_bar.showMessage("🖥️ Fullscreen mode disabled", 2000)
            logging.info("Fullscreen off")

            # Restore normal size with scaling
            if hasattr(self, 'normal_geometry'):
                base_size = self.base_sizes['window']
                scaled_size = base_size * self.settings.ui_scale
                self.resize(scaled_size)

    def exit_fullscreen(self):
        """Exit fullscreen mode when Escape key is pressed"""
        if self.settings.fullscreen:
            self.toggle_fullscreen()

    def toggle_ftb_flash(self):
        """Toggle FTB button flash state for visual feedback"""
        if self.ftb_active:
            self.ftb_flash_state = not self.ftb_flash_state
            self.btn_ftb.setStyleSheet(self.get_ftb_active_style())

    def toggle_settings(self):
        """Toggle settings panel visibility"""
        self.settings.show_settings = not self.settings_group.isVisible()
        self.settings_group.setVisible(self.settings.show_settings)
        self.settings.save()

        # Update button text and size
        if self.settings.show_settings:
            self.btn_toggle_settings.setText("Hide Settings")
            self.btn_toggle_settings.setMinimumWidth(int(135 * self.settings.ui_scale))
            self.btn_toggle_settings.setMaximumWidth(int(135 * self.settings.ui_scale))
        else:
            self.btn_toggle_settings.setText("Settings")
            self.btn_toggle_settings.setMinimumWidth(int(95 * self.settings.ui_scale))
            self.btn_toggle_settings.setMaximumWidth(int(95 * self.settings.ui_scale))

    def save_settings(self):
        """Save settings from UI to settings object"""
        self.settings.ip = self.ip_edit.text()
        self.settings.port = self.port_edit.text()
        self.settings.login = self.login_edit.text()
        self.settings.password = self.pass_edit.text()
        self.settings.remember_creds = self.remember_check.isChecked()
        self.settings.save()

        self.status_bar.showMessage("Settings saved!", 3000)
        logging.info("Saved settings")

    def connect_to_vmix(self):
        """Connect to vMix instance with provided credentials"""
        ip = self.ip_edit.text()
        port = self.port_edit.text()

        if not ip:
            self.status_bar.showMessage("❌ Enter vMix IP address!", 3000)
            logging.warning("IP is not valid")
            return

        self.status_bar.showMessage(f"Connecting to {ip}:{port}...")
        logging.info(f"Connecting to {ip}:{port}...")
        self.btn_connect.setEnabled(False)  # Disable button during connection
        QApplication.processEvents()  # Update UI immediately

        try:
            self.vmix_api = vMixAPI(ip, port)
            xml_data = self.vmix_api.get_xml_data()

            if xml_data:
                self.status_bar.showMessage(f"✅ Connected to vMix {ip}:{port}")
                logging.info("Connected!")
                self.btn_connect.setText("Connected")
                self.btn_connect.setStyleSheet(self.get_settings_button_style("#48bb78", "#38a169"))

                # Enable all control buttons
                self.btn_quick_play.setEnabled(True)
                self.btn_ftb.setEnabled(True)
                self.btn_overlay1.setEnabled(True)
                self.btn_overlay2.setEnabled(True)
                self.btn_overlay3.setEnabled(True)
                self.btn_overlay4.setEnabled(True)
                self.btn_remove_overlay.setEnabled(True)
                self.btn_refresh.setEnabled(True)

                self.load_inputs()
            else:
                self.status_bar.showMessage("❌ Failed to connect to vMix", 3000)
                logging.info("Failed to connect")
                self.btn_connect.setText("Connect")
                self.btn_connect.setStyleSheet(self.get_settings_button_style("#4299e1", "#3182ce"))
                self.vmix_api = None  # Reset API on failure

        except Exception as e:
            # Log error to console only
            logging.error(f"Connection error: {e}")
            self.status_bar.showMessage("❌ Connection error", 3000)
            self.btn_connect.setText("Connect")
            self.btn_connect.setStyleSheet(self.get_settings_button_style("#4299e1", "#3182ce"))
            self.vmix_api = None  # Reset API on error

        finally:
            # Always re-enable connect button
            self.btn_connect.setEnabled(True)

    def load_inputs(self):
        """Load and display all inputs from vMix"""
        if not self.vmix_api:
            self.status_bar.showMessage("❌ Not connected to vMix", 2000)
            return

        try:
            # Clear existing tiles
            for tile in self.input_tiles.values():
                self.tiles_layout.removeWidget(tile)
                tile.deleteLater()
            self.input_tiles.clear()

            # Get inputs from vMix
            inputs = self.vmix_api.get_inputs()

            if not inputs:
                self.status_bar.showMessage("❌ Failed to get inputs list", 2000)
                return

            # Get current active and preview inputs
            self.active_input = self.vmix_api.get_active_input()
            self.preview_input = self.vmix_api.get_preview_input()

            # Create tile for each input
            for input_data in inputs:
                is_active = (self.active_input == input_data['number'])
                is_preview = (self.preview_input == input_data['number'])

                tile = InputTile(input_data, is_active, is_preview, self, self.settings.ui_scale)
                tile.clicked.connect(self.on_tile_clicked)
                self.tiles_layout.addWidget(tile)
                self.input_tiles[input_data['number']] = tile

            # Ensure layout is set
            if not self.tiles_container.layout():
                self.tiles_container.setLayout(self.tiles_layout)

            self.update_input_info()

            self.status_bar.showMessage(f"✅ Loaded inputs: {len(inputs)}", 2000)
            self.tiles_container.update()

        except Exception as e:
            # Log error only
            logging.error(f"Inputs loading error: {e}")
            self.status_bar.showMessage(f"❌ Inputs loading error", 2000)

    def refresh_inputs(self):
        """Refresh inputs list from vMix"""
        if not self.vmix_api:
            self.status_bar.showMessage("❌ Connect to vMix first!", 2000)
            return

        # Change button color to green for visual feedback
        original_style = self.btn_refresh.styleSheet()
        green_style = f"""
            QPushButton {{
                padding: {int(5 * self.settings.ui_scale)}px {int(10 * self.settings.ui_scale)}px;
                font-weight: bold;
                font-size: {int(11 * self.settings.ui_scale)}px;
                border: {int(1 * self.settings.ui_scale)}px solid #4CAF50;
                border-radius: {int(4 * self.settings.ui_scale)}px;
                background: #4CAF50;
                color: white;
            }}
            QPushButton:hover {{
                background: #45a049;
                border: {int(1 * self.settings.ui_scale)}px solid #45a049;
            }}
        """
        self.btn_refresh.setStyleSheet(green_style)

        self.status_bar.showMessage("Refreshing inputs list...")

        # Load new data
        self.load_inputs()

        # Restore original color after 1 second
        QTimer.singleShot(1000, lambda: self.btn_refresh.setStyleSheet(original_style))
        QTimer.singleShot(1000, lambda: self.status_bar.showMessage("Inputs list refreshed", 2000))

    def on_tile_clicked(self, input_number):
        """Handle tile click - set input to preview"""
        if not self.vmix_api:
            self.status_bar.showMessage("❌ Not connected to vMix", 2000)
            return

        try:
            success = self.vmix_api.send_command("PreviewInput", Input=input_number)

            if success:
                self.preview_input = input_number
                self.update_tile_styles()
                self.update_input_info()
                self.btn_quick_play.setEnabled(True)
                self.status_bar.showMessage(f"📺 Set to preview: V{input_number}", 2000)
            else:
                self.status_bar.showMessage(f"❌ Preview set error", 3000)
        except Exception as e:
            logging.error(f"Command send error: {e}")
            self.status_bar.showMessage(f"❌ Command send error", 2000)

    def update_tile_styles(self):
        """Update visual state of all tiles"""
        if not self.input_tiles:
            return

        for input_number, tile in self.input_tiles.items():
            is_active = (self.active_input == input_number)
            is_preview = (self.preview_input == input_number)

            tile.set_active(is_active)
            tile.set_preview(is_preview)

    def update_input_info(self):
        """Update preview and program display labels"""
        # Update preview label
        if self.preview_input and self.preview_input in self.input_tiles:
            tile = self.input_tiles[self.preview_input]
            title = tile.input_data.get('short_title') or tile.input_data.get('title', '')
            title_length = int(25 * self.settings.ui_scale)
            if len(title) > title_length:
                title = title[:int(title_length * 0.85)] + "..."
            self.preview_input_label.setText(f"V{self.preview_input}: {title}")
        else:
            self.preview_input_label.setText("Not selected")

        # Update program label
        if self.active_input and self.active_input in self.input_tiles:
            tile = self.input_tiles[self.active_input]
            title = tile.input_data.get('short_title') or tile.input_data.get('title', '')
            title_length = int(25 * self.settings.ui_scale)
            if len(title) > title_length:
                title = title[:int(title_length * 0.85)] + "..."
            self.active_input_label.setText(f"V{self.active_input}: {title}")
        else:
            self.active_input_label.setText("No data")

    def quick_play(self):
        """Perform smooth transition from preview to program"""
        if not self.vmix_api or not self.preview_input:
            self.status_bar.showMessage("❌ Select input in preview first!", 2000)
            return

        try:
            # Use Fade command for smooth transition
            success = self.vmix_api.send_command("Fade", Input=self.preview_input)

            if success:
                self.active_input = self.preview_input
                self.update_tile_styles()
                self.update_input_info()
                self.flash_button(self.btn_quick_play, "#2196F3")
                self.status_bar.showMessage(f"🔄 Smooth transition to V{self.preview_input}", 2000)
            else:
                # Try Cut command as fallback
                success_cut = self.vmix_api.send_command("Cut", Input=self.preview_input)
                if success_cut:
                    self.active_input = self.preview_input
                    self.update_tile_styles()
                    self.update_input_info()
                    self.flash_button(self.btn_quick_play, "#2196F3")
                    self.status_bar.showMessage(f"✅ Cut transition to V{self.preview_input}", 2000)
                else:
                    self.status_bar.showMessage(f"❌ Transition error", 3000)
        except Exception as e:
            logging.error(f"Transition error: {e}")
            self.status_bar.showMessage(f"❌ Transition error", 2000)

    def fade_to_black(self):
        """Toggle Fade To Black effect"""
        if not self.vmix_api:
            self.status_bar.showMessage("❌ Not connected to vMix", 2000)
            return

        self.ftb_active = not self.ftb_active

        if self.ftb_active:
            self.btn_ftb.setStyleSheet(self.get_ftb_active_style())

            try:
                success = self.vmix_api.send_command("FadeToBlack")
                if success:
                    self.ftb_timer.start()
                    self.status_bar.showMessage("🌙 Fade To Black enabled", 2000)
                else:
                    self.ftb_active = False
                    self.btn_ftb.setStyleSheet(self.get_large_button_style("#666666"))
                    self.status_bar.showMessage("❌ Fade To Black error", 3000)
            except Exception as e:
                self.ftb_active = False
                logging.error(f"Fade To Black error: {e}")
                self.btn_ftb.setStyleSheet(self.get_large_button_style("#666666"))
                self.status_bar.showMessage(f"❌ Fade To Black error", 2000)
        else:
            try:
                success = self.vmix_api.send_command("FadeToBlack")
                if success:
                    self.ftb_timer.stop()
                    self.btn_ftb.setStyleSheet(self.get_large_button_style("#666666"))
                    self.status_bar.showMessage("🌙 Fade To Black disabled", 2000)
            except Exception as e:
                logging.error(f"Fade To Black disable error: {e}")
                self.status_bar.showMessage(f"❌ Fade To Black disable error", 2000)

    def overlay_selected(self, layer):
        """Overlay preview input on specified layer"""
        if not self.vmix_api or not self.preview_input:
            self.status_bar.showMessage("❌ Select input in preview first!", 2000)
            return

        try:
            success = self.vmix_api.send_command(f"OverlayInput{layer}", Input=self.preview_input)

            if success:
                self.active_overlays[layer] = not self.active_overlays[layer]
                self.update_all_styles()
                self.status_bar.showMessage(f"➕ Overlay on layer {layer}: V{self.preview_input}", 2000)
            else:
                self.status_bar.showMessage(f"❌ Overlay on layer {layer} error", 3000)
        except Exception as e:
            logging.error(f"Overlay error: {e}")
            self.status_bar.showMessage(f"❌ Overlay error", 2000)

    def remove_overlay(self):
        """Remove all overlays"""
        if not self.vmix_api:
            self.status_bar.showMessage("❌ Not connected to vMix", 2000)
            return

        try:
            for layer in range(1, 5):
                self.vmix_api.send_command(f"OverlayInput{layer}Out")
                self.active_overlays[layer] = False

            self.update_all_styles()
            self.status_bar.showMessage(f"✖ All overlays removed", 2000)
        except Exception as e:
            logging.error(f"Overlay remove error: {e}")
            self.status_bar.showMessage(f"❌ Overlay remove error", 2000)

    def update_states(self):
        """Periodic update of vMix states (active/preview inputs)"""
        if self.vmix_api:
            try:
                new_active = self.vmix_api.get_active_input()
                new_preview = self.vmix_api.get_preview_input()

                if new_active != self.active_input or new_preview != self.preview_input:
                    self.active_input = new_active
                    self.preview_input = new_preview
                    self.update_tile_styles()
                    self.update_input_info()
            except:
                # Ignore update errors
                pass

    def send_command(self, command, **params):
        """Generic command sender to vMix"""
        if self.vmix_api:
            try:
                success = self.vmix_api.send_command(command, **params)
                return success
            except:
                return False
        return False

    def flash_button(self, button, color):
        """Flash button with specified color for visual feedback"""
        original_style = button.styleSheet()
        flash_style = self.get_large_button_style(color)

        button.setStyleSheet(flash_style)
        QTimer.singleShot(300, lambda: button.setStyleSheet(original_style))


# ==================== CUSTOM FLOW LAYOUT ====================
class QFlowLayout(QLayout):
    """
    Custom flow layout that arranges widgets left-to-right,
    wrapping to next line when needed (like CSS flex-wrap).
    """

    def __init__(self, parent=None, margin=0, spacing=0):
        super().__init__(parent)

        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)

        self.setSpacing(spacing)

        self.itemList = []
        self.max_width = 0

    def __del__(self):
        """Clean up layout items"""
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        """Add QLayoutItem to layout"""
        self.itemList.append(item)

    def count(self):
        """Return number of items in layout"""
        return len(self.itemList)

    def itemAt(self, index):
        """Get item at specified index"""
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        """Remove and return item at specified index"""
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        """Return expansion directions"""
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self):
        """Layout height depends on width"""
        return True

    def heightForWidth(self, width):
        """Calculate height needed for given width"""
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        """Set geometry for layout and arrange items"""
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        """Return suggested size"""
        return self.minimumSize()

    def minimumSize(self):
        """Calculate minimum size needed"""
        size = QSize()

        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())

        margin = self.contentsMargins()
        size += QSize(2 * margin.left(), 2 * margin.top())
        return size

    def doLayout(self, rect, testOnly):
        """
        Arrange items in layout.

        Args:
            rect: Available rectangle
            testOnly: If True, only calculate, don't move items

        Returns:
            Height needed for layout
        """
        x = rect.x()
        y = rect.y()
        lineHeight = 0

        for item in self.itemList:
            wid = item.widget()
            spaceX = self.spacing()
            spaceY = self.spacing()
            nextX = x + item.sizeHint().width() + spaceX

            # Move to next line if doesn't fit
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()


# ==================== APPLICATION ENTRY POINT ====================
def main():
    """Main application entry point"""
    logging.info("-------------------Initializing app...-------------------")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for consistent look

    # Global application stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background: #1a1a1a;
        }
        QLabel {
            color: #ddd;
        }
        QLineEdit, QComboBox {
            background: #2a2a2a;
            color: #ddd;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 6px;
        }
        QLineEdit:focus, QComboBox:focus {
            border: 1px solid #777;
        }
        QCheckBox {
            color: #ddd;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            background: #444444;
            border: 1px solid #666666;
            border-radius: 3px;
        }
        QCheckBox::indicator:checked {
            background-color: #ffffff;
            border: 1px solid #888888;
        }
        QCheckBox::indicator:checked:disabled {
            background-color: #aaaaaa;
            border: 1px solid #888888;
        }
        QCheckBox::indicator:hover {
            border: 1px solid #888888;
        }
    """)

    # Create and show main window
    window = VMixController()
    window.show()

    # Start application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
