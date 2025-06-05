# File: modules/jd_quotes_module.py
# JD Quotes Integration Module - Wraps the standalone jd_quote_app.py Tkinter application

import os
import sys
import logging
import subprocess
import signal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QMessageBox, QFrame, QSizePolicy, QSpacerItem)
from PyQt5.QtCore import QProcess, Qt, QSize, pyqtSlot
from PyQt5.QtGui import QFont, QIcon

# Try to import the base module
try:
    from ui.base_module import BaseModule
except ImportError:
    logging.warning("Failed to import BaseModule. Using QWidget fallback.")
    BaseModule = QWidget

class JDQuotesIntegrationModule(BaseModule):
    """Integration module for JD Quotes app. This module launches the JD Quote Tkinter app as a separate process."""
    
    MODULE_DISPLAY_NAME = "JD Quotes"
    MODULE_ICON_NAME = "quotes_icon.png"  # Make sure this icon exists in your resources directory
    
    def __init__(self, main_window=None, config=None, logger=None):
        """Initialize the JD Quotes integration module."""
        super().__init__(main_window=main_window)
        self.setObjectName("JDQuotesIntegrationModule")
        
        # Set up logging
        parent_logger = logger or getattr(self.main_window, 'logger', None)
        self.logger = parent_logger.getChild("JDQuotes") if parent_logger else logging.getLogger(__name__)
        self.logger.debug("Initializing JDQuotesIntegrationModule...")
        
        # Store config
        self.config = config or getattr(self.main_window, 'config', None)
        
        # Initialize attributes
        self.process = None
        self.jd_quote_app_path = self._find_jd_quote_app_path()
        
        # Initialize UI
        self.init_ui()
        
        self.logger.debug("JDQuotesIntegrationModule initialization complete.")
    
    def _find_jd_quote_app_path(self):
        """Find the path to the jd_quote_app.py script."""
        # Try various locations to find jd_quote_app.py
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'jd_quote_app.py'),  # Relative to module dir
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'jd_quote_app.py'),  # Relative to exe
        ]
        
        # If we have config with a base path, try there too
        if self.config and hasattr(self.config, 'base_path'):
            possible_paths.append(os.path.join(self.config.base_path, 'jd_quote_app.py'))
        
        # Check each path
        for path in possible_paths:
            if os.path.exists(path):
                self.logger.info(f"Found JD Quote app at: {path}")
                return path
        
        # Fallback - assume it's in the current working directory
        fallback_path = os.path.join(os.getcwd(), 'jd_quote_app.py')
        self.logger.warning(f"JD Quote app not found in standard locations. Using fallback: {fallback_path}")
        return fallback_path
    
    def init_ui(self):
        """Initialize the user interface."""
        self.logger.debug("Setting up JDQuotesIntegrationModule UI...")
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel(self.MODULE_DISPLAY_NAME)
        title_label.setFont(QFont('Arial', 16, QFont.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)
        
        # Content area
        content_frame = QFrame()
        content_frame.setFrameShape(QFrame.StyledPanel)
        content_layout = QVBoxLayout(content_frame)
        
        # Description
        description_label = QLabel(
            "The JD Quotes application allows you to manage quotes for John Deere equipment. "
            "You can create, search, edit, and manage quotes and customer information."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("font-size: 12px;")
        content_layout.addWidget(description_label)
        
        # Launch button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.launch_button = QPushButton("Launch JD Quotes Application")
        self.launch_button.setMinimumWidth(250)
        self.launch_button.setMinimumHeight(50)
        self.launch_button.setStyleSheet("font-size: 14px;")
        self.launch_button.clicked.connect(self.launch_jd_quote_app)
        
        # Set icon if available
        if hasattr(self.config, 'resources_dir'):
            icon_path = os.path.join(self.config.resources_dir, "launch_icon.png")
            if os.path.exists(icon_path):
                self.launch_button.setIcon(QIcon(icon_path))
                self.launch_button.setIconSize(QSize(24, 24))
        
        button_layout.addWidget(self.launch_button)
        button_layout.addStretch()
        content_layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("Ready to launch")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-style: italic; color: gray;")
        content_layout.addWidget(self.status_label)
        
        # Add content frame to main layout
        main_layout.addWidget(content_frame)
        main_layout.addStretch()
        
        # Footer with notes
        footer_label = QLabel(
            "Note: The JD Quotes application will open in a separate window. "
            "You can close it anytime and return to the main application."
        )
        footer_label.setWordWrap(True)
        footer_label.setStyleSheet("font-size: 10px; font-style: italic; color: #666;")
        main_layout.addWidget(footer_label)
        
        self.logger.debug("JDQuotesIntegrationModule UI setup complete.")
    
    @pyqtSlot()
    def launch_jd_quote_app(self):
        """Launch the JD Quote application as a separate process."""
        self.logger.info("Launching JD Quote application...")
        
        # Check if the process is already running
        if self.process is not None and self.process.state() == QProcess.Running:
            # Ask if they want to launch another instance
            response = QMessageBox.question(
                self, 
                "JD Quotes Already Running", 
                "The JD Quotes application is already running. Would you like to launch another instance?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if response == QMessageBox.No:
                self.logger.info("User chose not to launch another instance.")
                return
            
            # Terminate existing process if launching new one
            self.terminate_process()
        
        # Update status
        self.status_label.setText("Launching application...")
        self.launch_button.setEnabled(False)
        
        try:
            # Check if the script exists
            if not os.path.exists(self.jd_quote_app_path):
                raise FileNotFoundError(f"JD Quote app not found at: {self.jd_quote_app_path}")
            
            # Create QProcess
            self.process = QProcess()
            self.process.finished.connect(self.process_finished)
            self.process.errorOccurred.connect(self.process_error)
            
            # Set up process environment
            process_env = self.process.processEnvironment()
            for key, value in os.environ.items():
                process_env.insert(key, value)
            self.process.setProcessEnvironment(process_env)
            
            # Start the process
            python_executable = sys.executable
            self.logger.info(f"Starting JD Quote app with Python: {python_executable}")
            self.logger.info(f"JD Quote app path: {self.jd_quote_app_path}")
            
            self.process.start(python_executable, [self.jd_quote_app_path])
            
            if self.process.waitForStarted(5000):  # Wait up to 5 seconds for process to start
                self.logger.info("JD Quote application started successfully.")
                self.status_label.setText("Application running")
                if hasattr(self.main_window, 'update_status'):
                    self.main_window.update_status("JD Quotes application launched", 5000)
            else:
                raise RuntimeError("Failed to start process within timeout period")
            
        except Exception as e:
            self.logger.error(f"Error launching JD Quote app: {str(e)}", exc_info=True)
            self.status_label.setText(f"Error: {str(e)}")
            QMessageBox.critical(
                self,
                "Launch Error",
                f"Failed to launch the JD Quotes application:\n\n{str(e)}"
            )
            
        finally:
            # Re-enable the button regardless of outcome
            self.launch_button.setEnabled(True)
    
    @pyqtSlot(int, QProcess.ExitStatus)
    def process_finished(self, exit_code, exit_status):
        """Handle process completion."""
        status_text = "Normal" if exit_status == QProcess.NormalExit else "Crashed"
        self.logger.info(f"JD Quote application exited with code {exit_code} ({status_text})")
        
        self.status_label.setText(f"Application exited (code: {exit_code})")
        self.launch_button.setEnabled(True)
        self.process = None
    
    @pyqtSlot(QProcess.ProcessError)
    def process_error(self, error):
        """Handle process errors."""
        error_messages = {
            QProcess.FailedToStart: "Failed to start",
            QProcess.Crashed: "Process crashed",
            QProcess.Timedout: "Process timed out",
            QProcess.WriteError: "Write error",
            QProcess.ReadError: "Read error",
            QProcess.UnknownError: "Unknown error"
        }
        
        error_text = error_messages.get(error, "Unknown error")
        self.logger.error(f"JD Quote application process error: {error_text}")
        
        self.status_label.setText(f"Error: {error_text}")
        self.launch_button.setEnabled(True)
    
    def terminate_process(self):
        """Terminate the running JD Quote application process."""
        if self.process is not None and self.process.state() == QProcess.Running:
            self.logger.info("Terminating JD Quote application process...")
            
            # Ask the process to terminate gracefully
            self.process.terminate()
            
            # Wait for it to finish
            if not self.process.waitForFinished(3000):  # Wait up to 3 seconds
                self.logger.warning("Process did not terminate gracefully, killing...")
                self.process.kill()  # Force kill if it doesn't terminate
    
    # --- BaseModule interface methods ---
    
    def get_title(self):
        """Return the module title."""
        return self.MODULE_DISPLAY_NAME
    
    def get_icon_name(self):
        """Return the module icon name."""
        return self.MODULE_ICON_NAME
    
    def refresh(self):
        """Refresh the module."""
        self.logger.debug("JDQuotesIntegrationModule refresh called.")
        # Nothing to refresh in this module
        pass
    
    def on_display(self):
        """Called when the module is displayed."""
        self.logger.debug("JDQuotesIntegrationModule displayed.")
        # We could update the status here if needed
        pass
    
    def save_state(self):
        """Save module state."""
        self.logger.debug("JDQuotesIntegrationModule save_state called.")
        # No state to save
        pass
    
    def close(self):
        """Clean up resources when the module is closed."""
        self.logger.debug("Closing JDQuotesIntegrationModule...")
        self.terminate_process()
        self.logger.debug("JDQuotesIntegrationModule closed.")
    
    def shutdown(self):
        """Shut down the module."""
        self.logger.debug("Shutting down JDQuotesIntegrationModule...")
        self.terminate_process()
        self.logger.debug("JDQuotesIntegrationModule shutdown complete.")
