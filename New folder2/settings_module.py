from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                            QPushButton, QCheckBox, QLineEdit, QFormLayout, 
                            QTabWidget, QScrollArea, QFrame, QGroupBox, QSlider,
                            QSpinBox, QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from ui.base_module import BaseModule
from utils.constants import *
from utils.theme_manager import ThemeManager
import os
import logging

class SettingsModule(BaseModule):
    """Settings module for controlling application configuration."""
    
    # Signal emitted when settings change
    settings_changed = pyqtSignal(str, object)
    
    def __init__(self, main_window=None):
        """Initialize the settings module.
        
        Args:
            main_window: Reference to the main application window
        """
        self.logger = logging.getLogger(__name__)
        self.settings = QSettings("BRIDeal", "BRIDeal")
        super().__init__(main_window)
        
    def init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create title
        title_label = QLabel("Settings")
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        main_layout.addWidget(title_label)
        
        # Create tabs
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # Add tabs
        tab_widget.addTab(self.create_general_tab(), "General")
        tab_widget.addTab(self.create_appearance_tab(), "Appearance")
        tab_widget.addTab(self.create_connection_tab(), "Connections")
        tab_widget.addTab(self.create_advanced_tab(), "Advanced")
        
        # Add save/cancel buttons
        button_layout = QHBoxLayout()
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        
        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self.reset_to_defaults)
        
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        
        main_layout.addLayout(button_layout)
        
        # Load current settings
        self.load_settings()
        
    def create_general_tab(self):
        """Create the general settings tab.
        
        Returns:
            QWidget: The tab widget
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Create form layout for settings
        form_layout = QFormLayout()
        
        # User information group
        user_group = QGroupBox("User Information")
        user_layout = QFormLayout(user_group)
        
        self.user_name_edit = QLineEdit()
        self.user_email_edit = QLineEdit()
        self.user_company_edit = QLineEdit()
        
        user_layout.addRow("Name:", self.user_name_edit)
        user_layout.addRow("Email:", self.user_email_edit)
        user_layout.addRow("Company:", self.user_company_edit)
        
        layout.addWidget(user_group)
        
        # Application behavior group
        behavior_group = QGroupBox("Application Behavior")
        behavior_layout = QFormLayout(behavior_group)
        
        self.startup_module_combo = QComboBox()
        self.startup_module_combo.addItems(["Home", "DealForm", "RecentDeals", "PriceBook", "UsedInventory"])
        
        self.confirm_exit_check = QCheckBox("Confirm before exiting")
        self.auto_save_check = QCheckBox("Auto-save deals")
        self.auto_save_interval = QSpinBox()
        self.auto_save_interval.setRange(1, 60)
        self.auto_save_interval.setSuffix(" minutes")
        
        behavior_layout.addRow("Start with module:", self.startup_module_combo)
        behavior_layout.addRow("", self.confirm_exit_check)
        behavior_layout.addRow("", self.auto_save_check)
        behavior_layout.addRow("Auto-save interval:", self.auto_save_interval)
        
        layout.addWidget(behavior_group)
        
        # File locations group
        files_group = QGroupBox("File Locations")
        files_layout = QFormLayout(files_group)
        
        self.data_path_edit = QLineEdit()
        self.data_path_edit.setReadOnly(True)
        
        data_path_layout = QHBoxLayout()
        data_path_layout.addWidget(self.data_path_edit)
        
        browse_data_btn = QPushButton("Browse...")
        browse_data_btn.clicked.connect(self.browse_data_path)
        data_path_layout.addWidget(browse_data_btn)
        
        files_layout.addRow("Data directory:", data_path_layout)
        
        layout.addWidget(files_group)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        return tab
    
    def create_appearance_tab(self):
        """Create the appearance settings tab.
        
        Returns:
            QWidget: The tab widget
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Theme selection
        theme_group = QGroupBox("Theme")
        theme_layout = QFormLayout(theme_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "Blue"])
        self.theme_combo.currentTextChanged.connect(self.preview_theme)
        
        theme_layout.addRow("Color theme:", self.theme_combo)
        
        layout.addWidget(theme_group)
        
        # Font settings
        font_group = QGroupBox("Font")
        font_layout = QFormLayout(font_group)
        
        self.font_size_slider = QSlider(Qt.Horizontal)
        self.font_size_slider.setRange(8, 16)
        self.font_size_slider.setTickInterval(1)
        self.font_size_slider.setTickPosition(QSlider.TicksBelow)
        
        self.font_size_label = QLabel("12")
        self.font_size_slider.valueChanged.connect(
            lambda value: self.font_size_label.setText(str(value))
        )
        
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(self.font_size_slider)
        font_size_layout.addWidget(self.font_size_label)
        
        font_layout.addRow("Font size:", font_size_layout)
        
        layout.addWidget(font_group)
        
        # Table view settings
        table_group = QGroupBox("Table Views")
        table_layout = QFormLayout(table_group)
        
        self.alt_row_colors_check = QCheckBox("Use alternating row colors")
        self.grid_lines_check = QCheckBox("Show grid lines")
        
        table_layout.addRow("", self.alt_row_colors_check)
        table_layout.addRow("", self.grid_lines_check)
        
        layout.addWidget(table_group)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        return tab
    
    def create_connection_tab(self):
        """Create the connections settings tab.
        
        Returns:
            QWidget: The tab widget
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # SharePoint settings
        sharepoint_group = QGroupBox("SharePoint Connection")
        sharepoint_layout = QFormLayout(sharepoint_group)
        
        self.sharepoint_site_edit = QLineEdit()
        self.sharepoint_file_path_edit = QLineEdit()
        
        self.test_sharepoint_btn = QPushButton("Test Connection")
        self.test_sharepoint_btn.clicked.connect(self.test_sharepoint_connection)
        
        sharepoint_layout.addRow("SharePoint Site:", self.sharepoint_site_edit)
        sharepoint_layout.addRow("File Path:", self.sharepoint_file_path_edit)
        sharepoint_layout.addRow("", self.test_sharepoint_btn)
        
        layout.addWidget(sharepoint_group)
        
        # JD Quotes API settings
        jd_quotes_group = QGroupBox("JD Quotes API")
        jd_quotes_layout = QFormLayout(jd_quotes_group)
        
        self.api_url_edit = QLineEdit()
        self.use_sandbox_check = QCheckBox("Use sandbox environment")
        
        self.test_api_btn = QPushButton("Test API")
        self.test_api_btn.clicked.connect(self.test_api_connection)
        
        jd_quotes_layout.addRow("API URL:", self.api_url_edit)
        jd_quotes_layout.addRow("", self.use_sandbox_check)
        jd_quotes_layout.addRow("", self.test_api_btn)
        
        layout.addWidget(jd_quotes_group)
        
        # Network settings
        network_group = QGroupBox("Network Settings")
        network_layout = QFormLayout(network_group)
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setSuffix(" seconds")
        
        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(0, 10)
        self.retry_count_spin.setSuffix(" retries")
        
        network_layout.addRow("Connection timeout:", self.timeout_spin)
        network_layout.addRow("Retry count:", self.retry_count_spin)
        
        layout.addWidget(network_group)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        return tab
    
    def create_advanced_tab(self):
        """Create the advanced settings tab.
        
        Returns:
            QWidget: The tab widget
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Logging settings
        logging_group = QGroupBox("Logging")
        logging_layout = QFormLayout(logging_group)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["ERROR", "WARNING", "INFO", "DEBUG"])
        
        self.max_log_size_spin = QSpinBox()
        self.max_log_size_spin.setRange(1, 100)
        self.max_log_size_spin.setSuffix(" MB")
        
        self.log_backup_count_spin = QSpinBox()
        self.log_backup_count_spin.setRange(1, 20)
        self.log_backup_count_spin.setSuffix(" files")
        
        view_logs_btn = QPushButton("View Logs")
        view_logs_btn.clicked.connect(self.view_logs)
        
        logging_layout.addRow("Log level:", self.log_level_combo)
        logging_layout.addRow("Max log file size:", self.max_log_size_spin)
        logging_layout.addRow("Log backup count:", self.log_backup_count_spin)
        logging_layout.addRow("", view_logs_btn)
        
        layout.addWidget(logging_group)
        
        # Cache settings
        cache_group = QGroupBox("Cache Settings")
        cache_layout = QFormLayout(cache_group)
        
        self.cache_enabled_check = QCheckBox("Enable caching")
        
        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setRange(1, 72)
        self.cache_ttl_spin.setSuffix(" hours")
        
        clear_cache_btn = QPushButton("Clear Cache")
        clear_cache_btn.clicked.connect(self.clear_cache)
        
        cache_layout.addRow("", self.cache_enabled_check)
        cache_layout.addRow("Cache time-to-live:", self.cache_ttl_spin)
        cache_layout.addRow("", clear_cache_btn)
        
        layout.addWidget(cache_group)
        
        # Performance settings
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout(perf_group)
        
        self.use_threading_check = QCheckBox("Enable background threading")
        self.lazy_loading_check = QCheckBox("Use lazy loading for modules")
        
        perf_layout.addRow("", self.use_threading_check)
        perf_layout.addRow("", self.lazy_loading_check)
        
        layout.addWidget(perf_group)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        return tab
    
    def load_settings(self):
        """Load settings from QSettings."""
        # General tab
        self.user_name_edit.setText(self.settings.value("user/name", ""))
        self.user_email_edit.setText(self.settings.value("user/email", ""))
        self.user_company_edit.setText(self.settings.value("user/company", ""))
        
        self.startup_module_combo.setCurrentText(self.settings.value("app/startup_module", "Home"))
        self.confirm_exit_check.setChecked(self.settings.value("app/confirm_exit", True, type=bool))
        self.auto_save_check.setChecked(self.settings.value("app/auto_save", True, type=bool))
        self.auto_save_interval.setValue(self.settings.value("app/auto_save_interval", 5, type=int))
        
        self.data_path_edit.setText(self.settings.value("paths/data_path", os.path.join(os.path.expanduser("~"), "BRIDeal", "data")))
        
        # Appearance tab
        self.theme_combo.setCurrentText(self.settings.value("appearance/theme", "Light"))
        self.font_size_slider.setValue(self.settings.value("appearance/font_size", 12, type=int))
        self.alt_row_colors_check.setChecked(self.settings.value("appearance/alt_row_colors", True, type=bool))
        self.grid_lines_check.setChecked(self.settings.value("appearance/grid_lines", True, type=bool))
        
        # Connection tab
        self.sharepoint_site_edit.setText(self.settings.value("sharepoint/site", ""))
        self.sharepoint_file_path_edit.setText(self.settings.value("sharepoint/file_path", "Shared Documents/ISG and AMS/Documents/OngoingAMS.xlsx"))
        
        self.api_url_edit.setText(self.settings.value("api/url", "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote"))
        self.use_sandbox_check.setChecked(self.settings.value("api/use_sandbox", True, type=bool))
        
        self.timeout_spin.setValue(self.settings.value("network/timeout", 30, type=int))
        self.retry_count_spin.setValue(self.settings.value("network/retry_count", 3, type=int))
        
        # Advanced tab
        self.log_level_combo.setCurrentText(self.settings.value("logging/level", "INFO"))
        self.max_log_size_spin.setValue(self.settings.value("logging/max_size", 10, type=int))
        self.log_backup_count_spin.setValue(self.settings.value("logging/backup_count", 5, type=int))
        
        self.cache_enabled_check.setChecked(self.settings.value("cache/enabled", True, type=bool))
        self.cache_ttl_spin.setValue(self.settings.value("cache/ttl", 24, type=int))
        
        self.use_threading_check.setChecked(self.settings.value("performance/threading", True, type=bool))
        self.lazy_loading_check.setChecked(self.settings.value("performance/lazy_loading", True, type=bool))
    
    def save_settings(self):
        """Save settings to QSettings."""
        # General tab
        self.settings.setValue("user/name", self.user_name_edit.text())
        self.settings.setValue("user/email", self.user_email_edit.text())
        self.settings.setValue("user/company", self.user_company_edit.text())
        
        self.settings.setValue("app/startup_module", self.startup_module_combo.currentText())
        self.settings.setValue("app/confirm_exit", self.confirm_exit_check.isChecked())
        self.settings.setValue("app/auto_save", self.auto_save_check.isChecked())
        self.settings.setValue("app/auto_save_interval", self.auto_save_interval.value())
        
        self.settings.setValue("paths/data_path", self.data_path_edit.text())
        
        # Appearance tab
        self.settings.setValue("appearance/theme", self.theme_combo.currentText())
        self.settings.setValue("appearance/font_size", self.font_size_slider.value())
        self.settings.setValue("appearance/alt_row_colors", self.alt_row_colors_check.isChecked())
        self.settings.setValue("appearance/grid_lines", self.grid_lines_check.isChecked())
        
        # Connection tab
        self.settings.setValue("sharepoint/site", self.sharepoint_site_edit.text())
        self.settings.setValue("sharepoint/file_path", self.sharepoint_file_path_edit.text())
        
        self.settings.setValue("api/url", self.api_url_edit.text())
        self.settings.setValue("api/use_sandbox", self.use_sandbox_check.isChecked())
        
        self.settings.setValue("network/timeout", self.timeout_spin.value())
        self.settings.setValue("network/retry_count", self.retry_count_spin.value())
        
        # Advanced tab
        self.settings.setValue("logging/level", self.log_level_combo.currentText())
        self.settings.setValue("logging/max_size", self.max_log_size_spin.value())
        self.settings.setValue("logging/backup_count", self.log_backup_count_spin.value())
        
        self.settings.setValue("cache/enabled", self.cache_enabled_check.isChecked())
        self.settings.setValue("cache/ttl", self.cache_ttl_spin.value())
        
        self.settings.setValue("performance/threading", self.use_threading_check.isChecked())
        self.settings.setValue("performance/lazy_loading", self.lazy_loading_check.isChecked())
        
        # Sync settings
        self.settings.sync()
        
        # Show confirmation message
        QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")
        
        # Emit signal for settings that require immediate action
        self.settings_changed.emit("theme", self.theme_combo.currentText())
        
        # Apply theme immediately
        self.apply_theme()
    
    def reset_to_defaults(self):
        """Reset settings to default values."""
        reply = QMessageBox.question(
            self, "Reset to Defaults", 
            "Are you sure you want to reset all settings to their default values?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Clear all settings
            self.settings.clear()
            
            # Reload defaults
            self.load_settings()
            
            QMessageBox.information(self, "Settings Reset", "Settings have been reset to default values.")
    
    def preview_theme(self, theme_name):
        """Preview a theme when selected.
        
        Args:
            theme_name: Name of the theme to preview
        """
        # Only apply the theme temporarily for preview
        theme_name = theme_name.lower()
        ThemeManager.apply_theme(theme_name)
    
    def apply_theme(self):
        """Apply the currently selected theme."""
        theme_name = self.theme_combo.currentText().lower()
        ThemeManager.apply_theme(theme_name)
    
    def browse_data_path(self):
        """Open directory browser to select data path."""
        current_path = self.data_path_edit.text()
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Data Directory", current_path
        )
        
        if dir_path:
            self.data_path_edit.setText(dir_path)
    
    def test_sharepoint_connection(self):
        """Test the SharePoint connection with current settings."""
        if not self.main_window or not hasattr(self.main_window, 'sharepoint_manager'):
            QMessageBox.warning(self, "Test Failed", "SharePoint manager not available.")
            return
            
        self.main_window.show_loading("Testing SharePoint connection...")
        
        try:
            # Use the site and file path from settings
            site_name = self.sharepoint_site_edit.text()
            file_path = self.sharepoint_file_path_edit.text()
            
            # Try to authenticate
            if self.main_window.sharepoint_manager.ensure_authenticated():
                # Try to read the "Used AMS" sheet
                sheet_name = "Used AMS"  # This sheet was found in your logs
                data = self.main_window.sharepoint_manager.read_sheet(sheet_name, use_cache=False)
                
                if data is not None:
                    QMessageBox.information(
                        self, "Connection Successful", 
                        f"Successfully connected to SharePoint and read {len(data)} rows from '{sheet_name}' sheet."
                    )
                else:
                    QMessageBox.warning(
                        self, "Test Failed", 
                        f"Connection successful but failed to read sheet '{sheet_name}'."
                    )
            else:
                QMessageBox.critical(
                    self, "Connection Failed", 
                    "Failed to authenticate with SharePoint."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Connection Failed", 
                f"Error testing SharePoint connection: {str(e)}"
            )
            self.logger.error(f"SharePoint connection test error: {str(e)}")
        finally:
            self.main_window.hide_loading()
    
    def test_api_connection(self):
        """Test the JD Quotes API connection with current settings."""
        if not self.main_window or not hasattr(self.main_window, 'quotes_api'):
            QMessageBox.warning(self, "Test Failed", "Quotes API not available.")
            return
            
        # Prompt for authentication token
        from PyQt5.QtWidgets import QInputDialog
        token, ok = QInputDialog.getText(
            self, "API Authentication", 
            "Enter your OAuth access token:",
            QLineEdit.Password
        )
        
        if not ok or not token:
            return
            
        self.main_window.show_loading("Testing API connection...")
        
        try:
            # Set the API URL
            api_url = self.api_url_edit.text()
            self.main_window.quotes_api.base_url = api_url
            
            # Set the token
            self.main_window.quotes_api.set_access_token(token)
            
            # Try to call a simple endpoint
            dealer_id = "X250102"  # Example dealer ID
            data = {
                "dealerRacfID": dealer_id,
                "startModifiedDate": "01/01/2024",
                "endModifiedDate": "12/31/2024"
            }
            
            # Just test if the request works
            try:
                response = self.main_window.quotes_api.get_quotes(dealer_id, data)
                QMessageBox.information(
                    self, "Connection Successful", 
                    "Successfully connected to JD Quotes API."
                )
            except Exception as api_error:
                QMessageBox.warning(
                    self, "API Call Failed", 
                    f"Authentication successful but API call failed: {str(api_error)}"
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Connection Failed", 
                f"Error testing API connection: {str(e)}"
            )
            self.logger.error(f"API connection test error: {str(e)}")
        finally:
            self.main_window.hide_loading()
    
    def view_logs(self):
        """Open the logs directory or file."""
        if not self.main_window:
            return
            
        logs_path = self.main_window.logs_path
        log_file = os.path.join(logs_path, 'amsdeal.log')
        
        if os.path.exists(log_file):
            # Try to open the file with the default application
            import subprocess
            import platform
            
            try:
                if platform.system() == 'Windows':
                    os.startfile(log_file)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', log_file])
                else:  # Linux
                    subprocess.run(['xdg-open', log_file])
            except Exception as e:
                QMessageBox.warning(
                    self, "Open Failed", 
                    f"Could not open log file: {str(e)}"
                )
                # As fallback, show the file path
                QMessageBox.information(
                    self, "Log File", 
                    f"Log file is located at: {log_file}"
                )
        else:
            QMessageBox.information(
                self, "Log File", 
                f"Log file not found at {log_file}"
            )
    
    def clear_cache(self):
        """Clear the application cache."""
        if not self.main_window:
            return
            
        cache_path = self.main_window.cache_path
        
        reply = QMessageBox.question(
            self, "Clear Cache", 
            f"Are you sure you want to clear all cached data from {cache_path}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Count files before deleting
                file_count = 0
                for root, dirs, files in os.walk(cache_path):
                    file_count += len(files)
                
                # Delete all files in cache directory and subdirectories
                for root, dirs, files in os.walk(cache_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            self.logger.warning(f"Failed to delete cache file {file_path}: {str(e)}")
                
                QMessageBox.information(
                    self, "Cache Cleared", 
                    f"Successfully cleared {file_count} cache files."
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", 
                    f"Failed to clear cache: {str(e)}"
                )
    
    def get_title(self):
        """Return the module title for display purposes."""
        return "Settings"