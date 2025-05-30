# BRIDeal_refactored/app/views/settings_panels/app_settings_view.py
import logging
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, # QHBoxLayout is now imported
    QComboBox, QLabel, QGroupBox, QMessageBox, QScrollArea,
    QDialog, QDialogButtonBox, QFileDialog, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal 

# Refactored local imports
from app.core.config import BRIDealConfig, get_config
from app.utils.theme_manager import ThemeManager 
# Attempt to import general_utils for resource path resolution
try:
    from app.utils import general_utils 
except ImportError:
    general_utils = None 
    _early_logger_settings = logging.getLogger(__name__) 
    _early_logger_settings.warning("general_utils not imported in AppSettingsView, theme file path resolution might be affected.")


logger = logging.getLogger(__name__)

# Define keys for settings that are typically user-configurable
USER_CONFIGURABLE_SETTINGS = {
    "Display": [
        {"key": "APP_THEME", "label": "Application Theme", "type": "theme_selector", "default": "Default"},
    ],
    "Paths": [
        {"key": "DATA_DIR", "label": "Data Directory", "type": "path_selector", "default": "data"},
        {"key": "CACHE_DIR", "label": "Cache Directory", "type": "path_selector", "default": "cache"},
        {"key": "LOGS_DIR", "label": "Logs Directory", "type": "path_selector", "default": "logs"},
    ],
    "API": [
        {"key": "JD_API_BASE_URL", "label": "JD API Base URL (Info)", "type": "readonly_string"},
    ],
    "General": [
        {"key": "AUTO_SAVE_DEAL_DRAFT", "label": "Auto-save Deal Draft", "type": "bool", "default": True},
        {"key": "DEFAULT_CACHE_DURATION_SECONDS", "label": "Default Cache Duration (s)", "type": "int", "default": 3600},
    ]
}


class AppSettingsView(QWidget):
    settings_changed_signal = pyqtSignal() 

    def __init__(self, config: BRIDealConfig, theme_manager: ThemeManager = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.theme_manager = theme_manager
        self.input_widgets = {} 

        if not self.config:
            logger.error("Config object not provided to AppSettingsView. Panel will be non-functional.")
            self._show_config_error_message()
            return

        self._init_ui()
        self._load_settings_to_ui()

    def _show_config_error_message(self):
        layout = QVBoxLayout(self)
        error_label = QLabel("Error: Configuration object not available. Settings cannot be displayed.")
        error_label.setStyleSheet("color: red; font-weight: bold;")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(error_label)
        self.setLayout(layout)


    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content_widget = QWidget()
        form_container_layout = QVBoxLayout(scroll_content_widget)
        form_container_layout.setSpacing(15)

        for category, settings in USER_CONFIGURABLE_SETTINGS.items():
            group_box = QGroupBox(category)
            group_layout = QFormLayout()
            group_layout.setSpacing(10)

            for setting_def in settings:
                key = setting_def["key"]
                label_text = setting_def["label"]
                setting_type = setting_def.get("type", "string")
                
                widget = None
                if setting_type == "theme_selector" and self.theme_manager:
                    widget = QComboBox()
                    widget.addItems(self.theme_manager.available_styles())
                elif setting_type == "path_selector":
                    widget_layout = QHBoxLayout() # QHBoxLayout is now imported
                    path_edit = QLineEdit()
                    browse_button = QPushButton("Browse...")
                    browse_button.clicked.connect(lambda checked, le=path_edit: self._browse_directory(le))
                    widget_layout.addWidget(path_edit)
                    widget_layout.addWidget(browse_button)
                    widget = QWidget() 
                    widget.setLayout(widget_layout)
                    self.input_widgets[key] = path_edit 
                elif setting_type == "bool": widget = QCheckBox()
                elif setting_type == "int": widget = QLineEdit() 
                elif setting_type == "readonly_string": widget = QLineEdit(); widget.setReadOnly(True)
                else: widget = QLineEdit()

                if widget:
                    if setting_type != "path_selector": self.input_widgets[key] = widget
                    group_layout.addRow(QLabel(f"{label_text}:"), widget)
            
            group_box.setLayout(group_layout)
            form_container_layout.addWidget(group_box)

        form_container_layout.addStretch(1)
        scroll_area.setWidget(scroll_content_widget)
        main_layout.addWidget(scroll_area)

        button_layout = QHBoxLayout() 
        button_layout.addStretch()
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.clicked.connect(self._apply_settings)
        button_layout.addWidget(self.apply_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)


    def _load_settings_to_ui(self):
        if not self.config: return
        for category, settings in USER_CONFIGURABLE_SETTINGS.items():
            for setting_def in settings:
                key = setting_def["key"]
                widget = self.input_widgets.get(key)
                if not widget:
                    logger.warning(f"No input widget found for setting key: {key}")
                    continue
                current_value = self.config.get(key, setting_def.get("default"))
                setting_type = setting_def.get("type", "string")

                if setting_type == "theme_selector" and isinstance(widget, QComboBox):
                    if widget.findText(str(current_value)) == -1:
                        widget.addItem(str(current_value)) 
                    widget.setCurrentText(str(current_value))
                elif setting_type == "bool" and isinstance(widget, QCheckBox):
                    widget.setChecked(bool(current_value))
                elif isinstance(widget, QLineEdit): 
                    widget.setText(str(current_value) if current_value is not None else "")
        logger.info("Settings loaded into UI.")

    def _apply_settings(self):
        if not self.config:
            QMessageBox.critical(self, "Error", "Configuration manager not available. Cannot apply settings.")
            return

        applied_theme = None
        changes_made = False
        for category, settings in USER_CONFIGURABLE_SETTINGS.items():
            for setting_def in settings:
                key = setting_def["key"]
                widget = self.input_widgets.get(key)
                if not widget: continue
                setting_type = setting_def.get("type","string")
                new_value = None
                current_config_value = self.config.get(key, setting_def.get("default"))

                if setting_type == "theme_selector" and isinstance(widget,QComboBox):
                    new_value = widget.currentText()
                    if new_value != current_config_value: 
                        applied_theme = new_value 
                elif setting_type == "bool" and isinstance(widget,QCheckBox):
                    new_value = widget.isChecked()
                elif isinstance(widget,QLineEdit):
                    new_value_str = widget.text()
                    if setting_type == "int":
                        try: new_value = int(new_value_str)
                        except ValueError: 
                            logger.warning(f"Invalid integer value for {key}: '{new_value_str}'. Skipping update.")
                            QMessageBox.warning(self,"Invalid Input",f"Value for '{setting_def['label']}' must be an integer.")
                            continue 
                    else: 
                        new_value = new_value_str
                
                if new_value is not None and new_value != current_config_value:
                    self.config.set(key, new_value) 
                    logger.info(f"Setting '{key}' updated to: {new_value}")
                    changes_made = True
        
        if applied_theme and self.theme_manager:
            if applied_theme in self.theme_manager.available_styles():
                self.theme_manager.apply_system_style(applied_theme)
            else: 
                qss_file_to_try = f"{applied_theme.lower().replace(' ','_')}.qss"
                qss_path = None
                if general_utils and hasattr(general_utils, 'get_resource_path'):
                    relative_qss_path = os.path.join(self.theme_manager.themes_dir, qss_file_to_try)
                    qss_path = general_utils.get_resource_path(relative_qss_path, self.config)

                if qss_path and os.path.exists(qss_path):
                    if not self.theme_manager.apply_qss_theme(qss_file_to_try): 
                        logger.warning(f"Could not apply QSS theme '{qss_file_to_try}' via ThemeManager.")
                elif not self.theme_manager.apply_qss_theme(applied_theme): 
                    logger.warning(f"Could not apply theme '{applied_theme}' as system style or QSS (tried {qss_file_to_try}).")

        if changes_made or applied_theme:
            QMessageBox.information(self,"Settings Applied","Settings have been applied. Some changes may require an application restart to take full effect.")
            self.settings_changed_signal.emit()
        else: QMessageBox.information(self,"Settings","No changes detected to apply.")

    def _browse_directory(self, line_edit_widget: QLineEdit):
        current_path = line_edit_widget.text()
        if not current_path or not os.path.isdir(current_path):
            current_path = os.path.expanduser("~") 
        directory = QFileDialog.getExistingDirectory(
            self,"Select Directory",current_path,
            QFileDialog.ShowDirsOnly|QFileDialog.DontResolveSymlinks
        )
        if directory:
            line_edit_widget.setText(directory)

# Example Usage
if __name__ == '__main__':
    import sys; import json; logging.basicConfig(level=logging.DEBUG)
    app = QApplication(sys.argv)
    class MCfg(Config): 
        def __init__(self):
            self.tp=".env_app_set_t"; self.tcp="t_app_set_cfg.json"
            with open(self.tp,"w") as f: f.write("APP_THEME=FusionFromEnv\nDATA_DIR=./env_data_dir\n")
            djc = {"APP_THEME":"DarkModeFromJson","LOGS_DIR":"./json_logs_dir","AUTO_SAVE_DEAL_DRAFT":False,"JD_API_BASE_URL":"https://api.example.com/jd_from_json"}
            with open(self.tcp,"w") as f: json.dump(djc,f)
            ds = {"DEFAULT_CACHE_DURATION_SECONDS":7200,"CACHE_DIR":"./default_cache_dir"}
            super().__init__(env_path=self.tp,config_json_path=self.tcp,default_config=ds)
            logger.info("MCfg initialized.")
        def cleanup(self):
            if os.path.exists(self.tp): os.remove(self.tp)
            if os.path.exists(self.tcp): os.remove(self.tcp)
    mock_cfg_as = MCfg() 
    mock_tm_as = ThemeManager(app,config=mock_cfg_as) 
    from PyQt6.QtWidgets import QMainWindow 
    mw_as = QMainWindow(); mw_as.setWindowTitle("AppSettings Test") 
    sp_as = AppSettingsView(config=mock_cfg_as,theme_manager=mock_tm_as) 
    mw_as.setCentralWidget(sp_as); mw_as.setGeometry(200,100,700,550); mw_as.show()
    ec=app.exec(); mock_cfg_as.cleanup(); sys.exit(ec) 
