# app/views/dialogs/jd_auth_dialog.py
import os
import sys
import logging
import webbrowser
import threading
import http.server
import socketserver
import urllib.parse
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QLabel, 
                           QProgressBar, QMessageBox, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QThread

logger = logging.getLogger(__name__)

class AuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    """Handles the OAuth callback from John Deere"""
    callback_url = None
    
    def do_GET(self):
        """Process the callback URL"""
        # Store the full URL for state verification
        # Use server.server_address[1] to get the port number
        AuthCallbackHandler.callback_url = f"http://localhost:{self.server.server_address[1]}{self.path}"
        
        # Parse the query parameters
        query = urllib.parse.urlparse(self.path).query
        params = dict(urllib.parse.parse_qsl(query))
        
        # Check for errors
        if 'error' in params:
            error = params.get('error', 'unknown')
            error_description = params.get('error_description', 'Unknown error')
            
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            error_html = f"""
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 50px;">
                <h2>Authentication Failed</h2>
                <p>Error: {error}</p>
                <p>Description: {error_description}</p>
                <p>Please try again or contact support.</p>
                <p><a href="#" onclick="window.close();">Close Window</a></p>
                <script>
                    setTimeout(function() {{ window.close(); }}, 10000);
                </script>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())
            return
        
        # Check for auth code
        if 'code' in params:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Send success page
            success_html = """
            <html>
            <head><title>Authentication Successful</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 50px;">
                <h2>Authentication Successful!</h2>
                <p>You've successfully authenticated with John Deere.</p>
                <p>You can now close this window and return to the application.</p>
                <script>
                    setTimeout(function() { window.close(); }, 3000);
                </script>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())
        else:
            # Handle no code case
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            error_html = """
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 50px;">
                <h2>Authentication Failed</h2>
                <p>No authorization code was received.</p>
                <p>Please try again or contact support.</p>
                <p><a href="#" onclick="window.close();">Close Window</a></p>
                <script>
                    setTimeout(function() { window.close(); }, 10000);
                </script>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())
    
    def log_message(self, format, *args):
        """Override to prevent logging every request to stdout"""
        logger.debug(f"AuthCallbackHandler: {format % args}")


class CallbackServerThread(QThread):
    """Thread to run the callback server"""
    callback_received = pyqtSignal(str)
    server_error = pyqtSignal(str)
    
    def __init__(self, port=9090):
        super().__init__()
        self.port = port
        self.server = None
    
    def run(self):
        """Run the local server to capture the OAuth callback"""
        try:
            # Reset the class variable in case of previous auth attempts
            AuthCallbackHandler.callback_url = None
            
            # Create the server
            self.server = socketserver.TCPServer(("localhost", self.port), AuthCallbackHandler)
            logger.info(f"Starting callback server on port {self.port}")
            
            # Set a timeout so it can be interrupted
            self.server.timeout = 1
            
            # Run the server until callback is received
            while AuthCallbackHandler.callback_url is None:
                self.server.handle_request()
                if self.isInterruptionRequested():
                    logger.info("Callback server thread interrupted")
                    return
            
            # Emit signal with the callback URL
            if AuthCallbackHandler.callback_url:
                self.callback_received.emit(AuthCallbackHandler.callback_url)
                
        except Exception as e:
            error_msg = f"Error in callback server: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.server_error.emit(error_msg)
        finally:
            if self.server:
                self.server.server_close()


class JDAuthDialog(QDialog):
    """Dialog for John Deere API authentication"""
    
    auth_completed = pyqtSignal(bool, str)
    
    def __init__(self, jd_auth_manager, parent=None):
        super().__init__(parent)
        self.jd_auth_manager = jd_auth_manager
        self.callback_thread = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("John Deere API Authentication")
        self.setMinimumWidth(450)
        self.setMinimumHeight(250)
        
        layout = QVBoxLayout()
        
        # Title and instructions
        title_label = QLabel("Connect to John Deere API")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        instructions = QLabel(
            "To use John Deere integration features, you need to authenticate "
            "with your John Deere account. Click the button below to begin "
            "the authentication process."
        )
        instructions.setWordWrap(True)
        
        # Status label
        self.status_label = QLabel("Ready to authenticate")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Auth button
        self.auth_button = QPushButton("Start Authentication")
        self.auth_button.clicked.connect(self.start_authentication)
        
        # Close button
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        
        # Add widgets to layout
        layout.addWidget(title_label)
        layout.addSpacing(10)
        layout.addWidget(instructions)
        layout.addSpacing(20)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addSpacing(10)
        layout.addWidget(self.auth_button)
        layout.addWidget(self.close_button)
        
        self.setLayout(layout)
    
    def start_authentication(self):
        """Start the authentication process"""
        if not self.jd_auth_manager.is_operational:
            QMessageBox.critical(
                self, 
                "Authentication Error", 
                "John Deere API authentication is not properly configured. "
                "Please check your settings and try again."
            )
            return
        
        # Update UI
        self.auth_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText("Starting authentication process...")
        
        # Parse the redirect URI to get the port
        redirect_uri = self.jd_auth_manager.redirect_uri
        try:
            # Parse the URI and get the port number
            parsed_uri = urllib.parse.urlparse(redirect_uri)
            port = parsed_uri.port or 9090
            
            # Start the callback server
            self.callback_thread = CallbackServerThread(port=port)
            self.callback_thread.callback_received.connect(self.handle_callback_url)
            self.callback_thread.server_error.connect(self.handle_server_error)
            self.callback_thread.start()
            
            # Get the authorization URL with state parameter
            auth_url = self.jd_auth_manager.get_authorization_url()
            if not auth_url:
                raise Exception("Failed to generate authorization URL")
            
            # Open the browser
            self.status_label.setText("Opening browser for authentication...")
            webbrowser.open(auth_url)
            
            self.status_label.setText("Waiting for authentication... (Check your browser)")
        
        except Exception as e:
            logger.error(f"Error starting authentication: {e}", exc_info=True)
            self.handle_server_error(f"Error starting authentication: {str(e)}")
    
    def handle_callback_url(self, callback_url):
        """Handle the received callback URL with proper state validation"""
        self.status_label.setText("Callback received. Processing authentication...")
        
        try:
            # Process the callback URL through the auth manager (which handles state validation)
            token_response = self.jd_auth_manager.handle_callback(callback_url)
            
            if token_response and token_response.get("access_token"):
                self.status_label.setText("Authentication successful!")
                self.progress_bar.setVisible(False)
                
                # Show success message
                QMessageBox.information(
                    self,
                    "Authentication Successful",
                    "You have successfully authenticated with the John Deere API."
                )
                
                # Emit signal
                self.auth_completed.emit(True, "Authentication successful")
                self.accept()
            else:
                raise Exception("Failed to obtain access token")
                
        except Exception as e:
            logger.error(f"Error processing authentication callback: {e}", exc_info=True)
            error_message = f"Failed to complete authentication: {str(e)}"
            self.handle_server_error(error_message)
    
    def handle_server_error(self, error_message):
        """Handle errors from the server thread"""
        self.status_label.setText("Authentication failed!")
        self.progress_bar.setVisible(False)
        self.auth_button.setEnabled(True)
        
        QMessageBox.critical(
            self,
            "Authentication Error",
            f"{error_message}\n\nPlease try again or contact support."
        )
        
        # Emit signal
        self.auth_completed.emit(False, error_message)
        
        # Stop the server thread if running
        if self.callback_thread and self.callback_thread.isRunning():
            self.callback_thread.requestInterruption()
            self.callback_thread.wait()
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        # Stop the server thread if running
        if self.callback_thread and self.callback_thread.isRunning():
            self.callback_thread.requestInterruption()
            self.callback_thread.wait()
        
        super().closeEvent(event)