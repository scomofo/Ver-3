import os
import logging
import json
import requests
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                            QPushButton, QGroupBox, QFormLayout, QTabWidget,
                            QCheckBox, QMessageBox, QSpinBox)
from PyQt5.QtCore import Qt

from api.MaintainQuotesAPI import MaintainQuotesAPI
from utils.token_handler import TokenHandler

class JDAuthSettingsPanel(QWidget):
    """Settings panel for John Deere API authentication."""
    
    def __init__(self, parent=None, config=None, main_window=None):
        """Initialize the JD Auth Settings panel.
        
        Args:
            parent: Parent widget
            config: Application configuration
            main_window: Main application window
        """
        super().__init__(parent)
        self.config = config
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)
        
        # Initialize token handler if config is available
        if self.config and hasattr(self.config, 'cache_path'):
            self.token_handler = TokenHandler(
                cache_path=self.config.cache_path,
                logger=self.logger
            )
        else:
            self.token_handler = None
            self.logger.warning("No config provided, token handling will be limited")
        
        # Create the UI
        self.init_ui()
        
        # Load saved settings
        self.load_settings()
    
    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # API settings section
        api_group = QGroupBox("JD Quotes API Settings")
        api_layout = QFormLayout(api_group)
        
        # API URL
        self.api_url_edit = QLineEdit()
        self.api_url_edit.setPlaceholderText("https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote")
        api_layout.addRow("API URL:", self.api_url_edit)
        
        # Use sandbox toggle
        self.use_sandbox_checkbox = QCheckBox("Use sandbox environment")
        self.use_sandbox_checkbox.setChecked(True)
        self.use_sandbox_checkbox.toggled.connect(self.toggle_sandbox)
        api_layout.addRow("", self.use_sandbox_checkbox)
        
        # Dealer ID
        self.dealer_id_edit = QLineEdit()
        self.dealer_id_edit.setPlaceholderText("X123456")
        api_layout.addRow("Dealer ID:", self.dealer_id_edit)
        
        # Dealer Account Number
        self.dealer_account_edit = QLineEdit()
        self.dealer_account_edit.setPlaceholderText("012345")
        api_layout.addRow("Dealer Account:", self.dealer_account_edit)
        
        # Token input
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("Enter your OAuth token here")
        self.token_edit.setEchoMode(QLineEdit.Password)  # Hide token by default
        api_layout.addRow("OAuth Token:", self.token_edit)
        
        # Show token checkbox
        self.show_token_checkbox = QCheckBox("Show token")
        self.show_token_checkbox.toggled.connect(self.toggle_token_visibility)
        api_layout.addRow("", self.show_token_checkbox)
        
        # Test connection button
        test_button = QPushButton("Test API")
        test_button.clicked.connect(self.test_api_connection)
        
        # Save button
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(test_button)
        button_layout.addWidget(save_button)
        api_layout.addRow("", button_layout)
        
        # Add API group to main layout
        layout.addWidget(api_group)
        
        # Network settings
        network_group = QGroupBox("Network Settings")
        network_layout = QFormLayout(network_group)
        
        # Timeout
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" seconds")
        network_layout.addRow("Connection timeout:", self.timeout_spin)
        
        # Retry count
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        self.retry_spin.setSuffix(" retries")
        network_layout.addRow("Retry count:", self.retry_spin)
        
        # Add network group to main layout
        layout.addWidget(network_group)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-style: italic;")
        layout.addWidget(self.status_label)
        
        # Add stretch to push everything to the top
        layout.addStretch()
    
    def toggle_sandbox(self, checked):
        """Toggle between sandbox and production URLs.
        
        Args:
            checked: Whether the checkbox is checked
        """
        if checked:
            self.api_url_edit.setText("https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote")
        else:
            self.api_url_edit.setText("https://jdquote2-api.deere.com/om/maintainquote")
    
    def toggle_token_visibility(self, checked):
        """Toggle visibility of the token field.
        
        Args:
            checked: Whether the checkbox is checked
        """
        self.token_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
    
    def load_settings(self):
        """Load settings from configuration or environment variables."""
        # Load from environment variables as defaults
        api_url = os.getenv('JD_QUOTE_API_BASE_URL', "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote")
        dealer_id = os.getenv('DEFAULT_DEALER_ID', "")
        dealer_account = os.getenv('DEALER_NUMBER', "")
        
        # If we have a config object, it takes precedence
        if self.config:
            # Check if the config has JD API settings
            if hasattr(self.config, 'jd_api_url'):
                api_url = self.config.jd_api_url
            if hasattr(self.config, 'dealer_id'):
                dealer_id = self.config.dealer_id
            if hasattr(self.config, 'dealer_account'):
                dealer_account = self.config.dealer_account
        
        # Set values in the UI
        self.api_url_edit.setText(api_url)
        self.dealer_id_edit.setText(dealer_id)
        self.dealer_account_edit.setText(dealer_account)
        
        # Determine sandbox setting from URL
        is_sandbox = "sandbox" in api_url
        self.use_sandbox_checkbox.setChecked(is_sandbox)
        
        # Load token from cache if available
        if self.token_handler:
            token = self.token_handler.load_token()
            if token:
                self.token_edit.setText(token)
                self.status_label.setText("Loaded cached token")
    
    def save_settings(self):
        """Save the current settings."""
        # Validate required fields
        if not self.api_url_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "API URL cannot be empty")
            return
            
        if not self.dealer_id_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Dealer ID cannot be empty")
            return
        
        # Ensure dealer ID has proper format (starts with X)
        dealer_id = self.dealer_id_edit.text().strip()
        if not dealer_id.startswith('X') and dealer_id.isdigit():
            dealer_id = f"X{dealer_id}"
            self.dealer_id_edit.setText(dealer_id)
        
        # Save to config if available
        if self.config:
            # Add JD API settings to config
            self.config.jd_api_url = self.api_url_edit.text().strip()
            self.config.dealer_id = dealer_id
            self.config.dealer_account = self.dealer_account_edit.text().strip()
            
            # Save config to file if it has a save method
            if hasattr(self.config, 'save'):
                self.config.save()
        
        # Save token if provided
        token = self.token_edit.text().strip()
        if token and self.token_handler:
            self.token_handler.save_token(token)
        
        # Update main window if available
        if self.main_window:
            if hasattr(self.main_window, 'quote_integration'):
                # Update dealer ID
                if hasattr(self.main_window.quote_integration, 'set_dealer'):
                    self.main_window.quote_integration.set_dealer(dealer_id)
                
                # Update API base URL
                if hasattr(self.main_window.quote_integration, 'api') and self.main_window.quote_integration.api:
                    self.main_window.quote_integration.api.base_url = self.api_url_edit.text().strip()
                
                # Set token if available
                if token and hasattr(self.main_window.quote_integration, 'api'):
                    self.main_window.quote_integration.api.set_access_token(token)
        
        self.status_label.setText("Settings saved")
        QMessageBox.information(self, "Settings Saved", "JD API settings have been saved successfully.")
    
    def test_api_connection(self):
        """Test the API connection with the current settings."""
        # Get the token
        token = self.token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Validation Error", "Please enter an OAuth token")
            return
        
        # Get the API URL
        api_url = self.api_url_edit.text().strip()
        if not api_url:
            QMessageBox.warning(self, "Validation Error", "Please enter an API URL")
            return
        
        # Show loading message
        self.status_label.setText("Testing connection...")
        if hasattr(self.main_window, 'show_loading'):
            self.main_window.show_loading("Testing JD API connection...")
        
        try:
            # Create temporary API client
            api = MaintainQuotesAPI(base_url=api_url, logger=self.logger)
            
            # Clean and set token
            cleaned_token = token.strip()
            api.set_access_token(cleaned_token)
            
            # Try to ping the API
            success = api.ping()
            
            if hasattr(self.main_window, 'hide_loading'):
                self.main_window.hide_loading()
            
            if success:
                # Token is valid, save it
                if self.token_handler:
                    self.token_handler.save_token(cleaned_token)
                
                self.status_label.setText("Connection successful")
                QMessageBox.information(
                    self,
                    "Connection Successful",
                    "Successfully connected to JD Quotes API."
                )
                
                # Update the main quote_integration if available
                if self.main_window and hasattr(self.main_window, 'quote_integration') and self.main_window.quote_integration:
                    if hasattr(self.main_window.quote_integration, 'api'):
                        self.main_window.quote_integration.api.set_access_token(cleaned_token)
            else:
                self.status_label.setText("Connection failed")
                QMessageBox.critical(
                    self,
                    "Connection Failed",
                    "Failed to connect to JD Quotes API. Token may be invalid or expired."
                )
        except Exception as e:
            self.logger.error(f"Error testing API connection: {str(e)}")
            
            if hasattr(self.main_window, 'hide_loading'):
                self.main_window.hide_loading()
                
            self.status_label.setText("Connection error")
            QMessageBox.critical(
                self,
                "Connection Error",
                f"Error connecting to JD Quotes API: {str(e)}"
            )