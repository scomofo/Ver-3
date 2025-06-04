# app/views/modules/jd_external_quote_view.py
import functools
import logging
import subprocess # For launching the external Tkinter app
import sys
import os
import json # For data exchange if using temp files
from datetime import datetime # For unique temp file names
from typing import Optional, Dict, Any, List # Added List for type hinting
import asyncio # For async operations in authenticate_jd_api
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFont

# Refactored local imports
from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig, get_config # Provided by BaseViewModule
from app.core.threading import Worker
# Assuming JDQuoteIntegrationService is used to prepare data or handle results
from app.services.integrations.jd_quote_integration_service import JDQuoteIntegrationService

logger = logging.getLogger(__name__)

# Configuration keys related to the external JD Quote App
CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH = "JD_QUOTE_TKINTER_APP_SCRIPT_PATH"
CONFIG_KEY_PYTHON_EXECUTABLE_PATH = "PYTHON_EXECUTABLE_FOR_TK_APP"
CONFIG_KEY_TEMP_DIR = "TEMP_DIR" # For temporary data exchange files

class JDExternalQuoteView(BaseViewModule):
    """
    A view module to launch and manage interaction with an external
    John Deere quoting application (e.g., a Tkinter-based one).
    Adapts functionality based on service availability and configuration.
    """
    quote_process_finished_signal = pyqtSignal(dict) # Emits result data from external app
    # Removed redundant add_auth_button method, integrating its logic into _init_ui

    def authenticate_jd_api(self):
        """Authenticate with JD API"""
        try:
            if hasattr(self.main_window, 'check_jd_authentication'):
                # The async warning comes from inside check_jd_authentication, 
                # but it still returns the correct boolean result
                is_authenticated = self.main_window.check_jd_authentication()
                
                if is_authenticated:
                    self.logger.info("JD API authentication successful")
                else:
                    self.logger.warning("JD API authentication failed")
                    
                # Call _update_ui_status without parameters (as it expects)
                self._update_ui_status()
                
                return is_authenticated
            else:
                self.logger.error("check_jd_authentication method not available")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during JD API authentication: {e}")
            return False
    def __init__(self, config: BRIDealConfig, logger_instance: Optional[logging.Logger] = None,
                 main_window: Optional[QWidget] = None, # QMainWindow or relevant parent
                 jd_quote_integration_service: Optional[JDQuoteIntegrationService] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(
            module_name="JDExternalQuoteTool",
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )

        self.jd_quote_integration_service = jd_quote_integration_service
        self.thread_pool = QThreadPool.globalInstance()
        self.current_deal_context: Optional[Dict[str, Any]] = None
        self.temp_input_file_path: Optional[str] = None # To store path of temp file for cleanup

        self._init_ui() # Initializes UI elements including self.launch_button and self.auth_button

        # Adapt UI based on JD service status and Tkinter app path configuration
        self._update_ui_status()

    def _update_ui_status(self):
        """Updates the UI elements based on service and configuration status."""
        # Ensure UI elements exist before trying to update them.
        # self.auth_button is now created in _init_ui
        if not hasattr(self, 'launch_button') or not hasattr(self, 'auth_button'):
            return

        service_operational = self.jd_quote_integration_service and self.jd_quote_integration_service.is_operational
        tkinter_app_script_path = self.config.get(CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH)

        if not service_operational:
            self.logger.warning(
                f"{self.module_name}: JDQuoteIntegrationService is not available or not operational. "
                "External JD quoting tool launch will be disabled."
            )
            self.launch_button.setToolTip(
                "John Deere API integration is not configured or unavailable. "
                "Cannot launch external quoting tool."
            )
            self.launch_button.setEnabled(False)
            self.output_text_edit.setText("John Deere API integration is not configured. Cannot launch external quoting tool.")
        elif not tkinter_app_script_path:
            self.logger.warning(
                f"{self.module_name}: Path to the JD Quote (Tkinter) application script "
                f"({CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH}) is not configured. Launch disabled."
            )
            self.launch_button.setToolTip(
                f"Path to the external JD Quote application script ({CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH}) "
                "is not configured in the application settings."
            )
            self.launch_button.setEnabled(False)
            self.output_text_edit.setText(
                 "Configuration Error: The path to the external John Deere quoting application is not set.\n"
                 "Please configure JD_QUOTE_TKINTER_APP_SCRIPT_PATH in the .env file or application settings."
            )
            self.auth_button.setEnabled(True) # Auth button can be enabled even if Tkinter path is missing
        else:
            self.logger.info(f"{self.module_name}: Ready to launch external JD quoting tool.")
            self.launch_button.setEnabled(True)
            self.auth_button.setEnabled(True)
            self.launch_button.setToolTip("Launches the external John Deere quoting application.")
            self.output_text_edit.setPlaceholderText("Output from the external application will appear here...")
            # Clear previous status messages if placeholder is desired
            if self.output_text_edit.toPlainText().startswith("Configuration Error") or self.output_text_edit.toPlainText().startswith("John Deere API integration is not configured"):
                self.output_text_edit.clear()


    def _init_ui(self):
        """Initialize the user interface components."""
        # main_layout = QVBoxLayout(self) # Changed
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        title_label = QLabel("John Deere Quoting Tool")
        title_font = QFont("Arial", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        main_layout.addWidget(title_label)

        description_label = QLabel(
            "Use this section to launch the external John Deere quoting application. "
            "Ensure any relevant deal information is prepared or saved before launching. "
            "The application will attempt to pass the current deal context if available."
        )
        description_label.setWordWrap(True)
        main_layout.addWidget(description_label)

        launch_group = QGroupBox("Launch External Quoting Tool")
        launch_layout = QVBoxLayout()

        self.launch_button = QPushButton("Launch JD Quote Application")
        self.launch_button.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.launch_button.setStyleSheet("background-color: #0078d7; color: white; padding: 8px;")
        self.launch_button.clicked.connect(self._launch_external_quote_app)
        launch_layout.addWidget(self.launch_button)

        launch_group.setLayout(launch_layout)
        main_layout.addWidget(launch_group)

        output_group = QGroupBox("Process Output / Results")
        output_layout = QVBoxLayout()
        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        self.output_text_edit.setMinimumHeight(100)
        output_layout.addWidget(self.output_text_edit)
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        # Create and add auth_button here
        self.auth_button = QPushButton("Connect to John Deere API")
        self.auth_button.setToolTip("Authenticate with John Deere API to enable quote features")
        self.auth_button.clicked.connect(self.authenticate_jd_api)
        # Add to a new QHBoxLayout for better alignment if needed, or directly
        auth_button_layout = QHBoxLayout()
        auth_button_layout.addStretch()
        auth_button_layout.addWidget(self.auth_button)
        auth_button_layout.addStretch()
        main_layout.addLayout(auth_button_layout) # Add to main_layout

        main_layout.addStretch(1)
        # self.setLayout(main_layout) # Removed

        content_area = self.get_content_container()
        if not content_area.layout():
            content_area.setLayout(main_layout)
        else:
            old_layout = content_area.layout()
            if old_layout:
                while old_layout.count():
                    item = old_layout.takeAt(0)
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
                old_layout.deleteLater()
            content_area.setLayout(main_layout)
    
    def set_deal_context(self, deal_data: Optional[Dict[str, Any]]):
        """
        Sets the current deal data that might be passed to the external app.
        """
        self.current_deal_context = deal_data
        if deal_data:
            self.logger.info(f"Deal context set for external quote app: {deal_data.get('deal_id', 'N/A')}")
            self.show_notification("Deal context updated. Ready to launch external quote tool if configured.", "info")
            self.output_text_edit.append(f"Deal context for '{deal_data.get('deal_name', deal_data.get('deal_id', 'current deal'))}' loaded and ready to be passed.")
        else:
            self.logger.info("Deal context cleared.")
            self.output_text_edit.append("Deal context cleared.")


    def _prepare_input_data_file(self) -> Optional[str]:
        """Prepares a temporary JSON file with input data for the external app."""
        if not self.current_deal_context:
            self.logger.debug("No deal context to prepare for external app.")
            return None

        # Use JDQuoteIntegrationService to prepare data if it has a specific method,
        # otherwise, use a generic payload from QuoteBuilder or pass current_deal_context.
        payload_for_external_app = self.current_deal_context # Default to passing the whole context
        if self.jd_quote_integration_service and hasattr(self.jd_quote_integration_service, 'prepare_payload_for_tkinter_app'):
            # This assumes prepare_payload_for_tkinter_app is a method in JDQuoteIntegrationService
            # Or use the more generic one if it's suitable:
            # payload_for_external_app = self.jd_quote_integration_service.prepare_quote_payload_for_external_app(self.current_deal_context)
            # For now, let's assume self.current_deal_context is what we want to pass or QuoteBuilder handles it.
            if self.jd_quote_integration_service.quote_builder:
                 payload_for_external_app = self.jd_quote_integration_service.quote_builder.build_payload_from_deal(
                     self.current_deal_context, target_system="jd_tkinter_app" # Example target
                 )
            else: # Fallback if quote_builder is not available on the service
                payload_for_external_app = self.current_deal_context


        if not payload_for_external_app:
            logger.warning("Payload preparation for external app resulted in None.")
            return None

        try:
            base_temp_dir = self.config.get(CONFIG_KEY_TEMP_DIR, "temp") # Default to "temp" subdirectory
            if not os.path.isabs(base_temp_dir):
                # Assuming project root is parent of 'app' dir
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
                temp_dir = os.path.join(project_root, base_temp_dir)
            else:
                temp_dir = base_temp_dir

            os.makedirs(temp_dir, exist_ok=True)
            # Use a more unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            input_file_name = f"jd_quote_input_{timestamp}.json"
            self.temp_input_file_path = os.path.join(temp_dir, input_file_name)

            with open(self.temp_input_file_path, 'w', encoding='utf-8') as f:
                json.dump(payload_for_external_app, f, indent=4)
            self.logger.info(f"Prepared input data for external app at: {self.temp_input_file_path}")
            return self.temp_input_file_path
        except Exception as e:
            self.logger.error(f"Failed to write input data for external app: {e}", exc_info=True)
            QMessageBox.warning(self, "File Error", f"Could not create temporary input file for external app: {e}")
            self.temp_input_file_path = None
            return None


    def _launch_external_quote_app(self):
        """
        Launches the external Tkinter-based JD quote application as a subprocess.
        """
        # Double-check status before launch attempt
        if not (self.jd_quote_integration_service and self.jd_quote_integration_service.is_operational):
            QMessageBox.critical(self, "Service Error",
                                 "John Deere Integration Service is not operational. Cannot launch external app.")
            return

        tkinter_app_script_rel_path = self.config.get(CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH)
        if not tkinter_app_script_rel_path:
            QMessageBox.critical(self, "Configuration Error",
                                 f"Path to the JD Quote (Tkinter) application script ({CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH}) is not configured.")
            return

        python_executable = self.config.get(CONFIG_KEY_PYTHON_EXECUTABLE_PATH, sys.executable)

        # Resolve script path (assuming it might be relative to project root)
        if not os.path.isabs(tkinter_app_script_rel_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            tkinter_app_script_abs_path = os.path.join(project_root, tkinter_app_script_rel_path)
        else:
            tkinter_app_script_abs_path = tkinter_app_script_rel_path

        if not os.path.exists(tkinter_app_script_abs_path):
            QMessageBox.critical(self, "File Not Found",
                                 f"The JD Quote application script was not found at: {tkinter_app_script_abs_path}\n"
                                 f"(Original configured path: {tkinter_app_script_rel_path})")
            self.logger.error(f"External app script not found: {tkinter_app_script_abs_path}")
            return

        self.logger.info(f"Launching external JD Quote app: {python_executable} {tkinter_app_script_abs_path}")
        self.output_text_edit.clear()
        self.output_text_edit.append(f"Attempting to launch: {os.path.basename(tkinter_app_script_abs_path)}...")
        self.launch_button.setEnabled(False)

        input_data_file = self._prepare_input_data_file() # Prepare data and get path

        cmd_args: List[str] = [python_executable, tkinter_app_script_abs_path]
        if input_data_file:
            # Pass the input file path as a command-line argument to the Tkinter script
            cmd_args.extend(["--input-file", input_data_file])

        worker = Worker(None)  # Initialize fn as None temporarily

        # Create a partial function that includes the status_callback
        # self._run_subprocess_and_get_output expects (self, cmd_args_list, status_callback)
        # The Worker will call fn(self, *args), so args for fn should be (cmd_args_list,)
        # The partial will effectively make it so that when worker calls:
        #   partial_fn(cmd_args)
        # it translates to:
        #   self._run_subprocess_and_get_output(cmd_args, status_callback=worker.signals.status)

        partial_fn = functools.partial(self._run_subprocess_and_get_output, status_callback=worker.signals.status)

        worker.fn = partial_fn
        worker.args = (cmd_args,) # Pass cmd_args as a tuple for the *args in worker's run method
        worker.signals.result.connect(self._handle_external_app_result)
        worker.signals.error.connect(self._handle_external_app_error)
        worker.signals.status.connect(lambda msg: self.output_text_edit.append(msg)) # For live stdout/stderr from worker
        self.thread_pool.start(worker)


    def _run_subprocess_and_get_output(self, cmd_args_list: List[str], status_callback: pyqtSignal):
        """
        Runs the subprocess and captures its stdout and stderr.
        This function is executed by the Worker thread.
        """
        status_callback.emit(f"Starting subprocess: {' '.join(cmd_args_list)}")
        self.logger.debug(f"Executing command: {' '.join(cmd_args_list)}")
        process = None
        try:
            process = subprocess.Popen(
                cmd_args_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, # Decodes stdout/stderr as text
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            # Stream output for live updates (optional, can be complex)
            # For simplicity, communicate() waits for completion.
            # If you need live streaming, you'd read process.stdout and process.stderr line by line.
            # Example for streaming (needs to be adapted if used):
            # while True:
            #     output = process.stdout.readline()
            #     if output == '' and process.poll() is not None:
            #         break
            #     if output:
            #         status_callback.emit(output.strip())
            # stderr_output = process.stderr.read() # Read all stderr at the end or stream it too

            stdout, stderr = process.communicate(timeout=300) # 5-minute timeout for external app
            return_code = process.returncode
            status_callback.emit(f"Subprocess finished with code: {return_code}")

        except subprocess.TimeoutExpired:
            status_callback.emit("Subprocess timed out.")
            logger.error("External application subprocess timed out.")
            if process: process.kill() # Ensure process is killed
            stdout, stderr = process.communicate() if process else ("", "Timeout Error")
            return {"return_code": -1, "stdout": stdout, "stderr": "Process timed out after 300 seconds.", "parsed_output": None}
        except FileNotFoundError: # Handle if python_executable or script is not found at Popen stage
            status_callback.emit(f"Error: Command not found - {' '.join(cmd_args_list)}. Check Python path and script path.")
            logger.error(f"Command not found during Popen: {cmd_args_list}")
            return {"return_code": -2, "stdout": "", "stderr": "Command or script not found.", "parsed_output": None}
        except Exception as e: # Catch other Popen or communicate errors
            status_callback.emit(f"Error running subprocess: {e}")
            logger.error(f"Exception in _run_subprocess_and_get_output: {e}", exc_info=True)
            return {"return_code": -3, "stdout": "", "stderr": str(e), "parsed_output": None}


        result_data = {
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "parsed_output": None
        }

        if stdout:
            # Attempt to parse the entire stdout as JSON if the Tkinter app is designed to output JSON upon closing.
            # The Tkinter app should print its JSON result *only* at the very end.
            # Any other prints (like debug statements) might interfere.
            try:
                # Find the last JSON object in stdout if there are multiple prints
                last_json_output = None
                for line in stdout.strip().splitlines():
                    try:
                        potential_json = json.loads(line)
                        last_json_output = potential_json # Keep overwriting with the last valid JSON line
                    except json.JSONDecodeError:
                        continue # Ignore lines that are not JSON

                if last_json_output:
                    result_data["parsed_output"] = last_json_output
                    status_callback.emit("Successfully parsed JSON output from subprocess.")
                elif stdout.strip(): # If no JSON, but there is stdout, treat it as general output
                     status_callback.emit("Subprocess stdout was not valid JSON (or no JSON found). Using raw stdout if needed.")
            except Exception as e: # Catch any error during this custom parsing
                status_callback.emit(f"Error trying to parse stdout for JSON: {e}")
                logger.warning(f"Could not parse stdout as JSON: {e}. stdout was: {stdout[:200]}...") # Log snippet

        return result_data


    def _handle_external_app_result(self, result: Dict[str, Any]):
        """Handles the result from the external application worker."""
        self.launch_button.setEnabled(True) # Re-enable button
        self.output_text_edit.append("\n--- External Application Finished ---")
        self.output_text_edit.append(f"Return Code: {result.get('return_code')}")

        if result.get('stdout'):
            self.output_text_edit.append("\nStandard Output from External App:")
            self.output_text_edit.append(result['stdout'])
        if result.get('stderr'):
            self.output_text_edit.append("\nStandard Error from External App:")
            self.output_text_edit.append(result['stderr'])

        parsed_output = result.get('parsed_output')
        if result.get('return_code') == 0:
            if parsed_output:
                QMessageBox.information(self, "Quote Tool Success",
                                        "External quote tool finished successfully and returned data.")
                self.logger.info(f"External app success. Parsed output: {parsed_output}")
                self.quote_process_finished_signal.emit(parsed_output)
                # Example: self.jd_quote_integration_service.process_external_tool_output(parsed_output)
            else:
                QMessageBox.information(self, "Quote Tool Finished",
                                        "External quote tool finished successfully (no specific JSON data returned or parsed).")
                self.logger.info("External app success (no specific JSON data parsed from stdout).")
                self.quote_process_finished_signal.emit({"status": "success", "message": "Process completed."})
        else:
            error_msg = result.get('stderr', 'Unknown error.')
            if result.get('return_code') == -1: error_msg = "Process timed out."
            elif result.get('return_code') == -2: error_msg = "Command or script not found."

            QMessageBox.warning(self, "Quote Tool Error",
                                f"External quote tool exited with code {result.get('return_code')}.\n"
                                f"Details: {error_msg}\nCheck output log for more.")
            self.logger.error(f"External app error. Code: {result.get('return_code')}, Stderr: {result.get('stderr')}")
            # Emit a signal with error information if needed
            self.quote_process_finished_signal.emit({"status": "error", "code": result.get('return_code'), "message": error_msg})

        self._cleanup_temp_file()

    def _handle_external_app_error(self, exception_obj: Exception):
        """Handles errors from the worker running the external application (e.g., worker thread crashed)."""
        self.launch_button.setEnabled(True)

        # Log the full exception info (including traceback)
        self.logger.error(
            f"Error launching/running external quote app worker: {type(exception_obj).__name__} - {exception_obj}",
            exc_info=exception_obj
        )

        error_message = str(exception_obj)
        self.output_text_edit.append(f"\n--- Error in Worker Thread for External App ---\n{error_message}") # Escaped newline
        QMessageBox.critical(
            self,
            "Launch Error",
            f"A worker thread error occurred while trying to run the external quote application: {error_message}"
        )
        self._cleanup_temp_file()

    def _cleanup_temp_file(self):
        """Deletes the temporary input file if it was created."""
        if self.temp_input_file_path and os.path.exists(self.temp_input_file_path):
            try:
                os.remove(self.temp_input_file_path)
                self.logger.info(f"Cleaned up temporary input file: {self.temp_input_file_path}")
            except OSError as e:
                self.logger.error(f"Error deleting temporary input file {self.temp_input_file_path}: {e}")
        self.temp_input_file_path = None # Reset path

    def load_module_data(self):
        """Called when the module becomes active. Updates UI status."""
        super().load_module_data()
        self._update_ui_status() # Re-check service status when module is shown


# Example Usage (for testing this module standalone)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
    app = QApplication(sys.argv)

    class MockJDExternalConfig(Config):
        def __init__(self, script_path_val=None, python_exec_val=None):
            self.settings = {}
            if script_path_val:
                self.settings[CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH] = script_path_val
            if python_exec_val:
                self.settings[CONFIG_KEY_PYTHON_EXECUTABLE_PATH] = python_exec_val
            self.settings["TEMP_DIR"] = "temp_jd_ext_test" # For test temp files

            super().__init__(env_path=".env.test_jd_ext_quote") # For superclass init
            # Ensure settings override anything from a dummy .env if it existed
            if script_path_val: self.settings[CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH] = script_path_val
            if python_exec_val: self.settings[CONFIG_KEY_PYTHON_EXECUTABLE_PATH] = python_exec_val
            self.settings["TEMP_DIR"] = "temp_jd_ext_test"

            os.makedirs(self.settings["TEMP_DIR"], exist_ok=True)


        def cleanup(self):
            temp_dir_to_clean = self.settings.get("TEMP_DIR")
            if temp_dir_to_clean and os.path.exists(temp_dir_to_clean) and "temp_jd_ext_test" in temp_dir_to_clean :
                import shutil
                shutil.rmtree(temp_dir_to_clean)
                logger.info(f"Cleaned up test temp directory: {temp_dir_to_clean}")
            if os.path.exists(".env.test_jd_ext_quote"): os.remove(".env.test_jd_ext_quote")


    # Create a dummy Tkinter script for testing
    dummy_tk_script_content = """
import tkinter as tk
import sys, json, time, argparse

print(f'Dummy Tkinter App launched with args: {sys.argv}') # Debug print

parser = argparse.ArgumentParser()
parser.add_argument('--input-file', help='Path to JSON input file')
args = parser.parse_args()

input_data_content = "No input file provided or error reading it."
if args.input_file:
    print(f'Input file argument provided: {args.input_file}')
    try:
        with open(args.input_file, 'r') as infile:
            data = json.load(infile)
            print(f'Input data from file: {data}') # Debug print
            input_data_content = f"Received data: {data.get('deal_id', 'N/A')}"
    except Exception as e:
        print(f'Error reading input file {args.input_file}: {e}') # Debug print
        input_data_content = f"Error reading input file: {e}"
else:
    print("No --input-file argument provided.") # Debug print

root = tk.Tk()
root.title('Dummy JD Quote Tool')
tk.Label(root, text=f'This is a dummy Tkinter JD Quote App.\\nClose this window to simulate finishing.\\n{input_data_content}').pack(padx=20, pady=20)

def on_close():
    print('Dummy Tkinter App closing.') # Debug print
    # Simulate outputting a JSON result to stdout
    result = {'quote_id': 'TK-QUOTE-SUCCESS-123', 'pdf_path': '/path/to/dummy_quote.pdf', 'status': 'success_from_tk'}
    print(json.dumps(result)) # This line should be the primary JSON output
    root.destroy()

root.protocol('WM_DELETE_WINDOW', on_close)
# time.sleep(1) # Simulate some work
root.mainloop()
"""
    dummy_tk_script_name = "dummy_jd_quote_tk_app_test.py"
    with open(dummy_tk_script_name, "w") as f:
        f.write(dummy_tk_script_content)


    mock_config_instance = MockJDExternalConfig(script_path_val=dummy_tk_script_name, python_exec_val=sys.executable)

    class MockJDQuoteIntServiceExt:
        def __init__(self, operational=True):
            self.is_operational = operational
            self.quote_builder = None # Can be added if needed for testing _prepare_input_data_file
            self.logger = logging.getLogger("MockJDIntServiceExt")
            if not self.is_operational: self.logger.warning("MockJDQuoteIntServiceExt set to non-operational.")

    class DummyMainWindowForExternalQuote(QWidget):
        def __init__(self, config_ref, jd_q_int_service_ref):
            super().__init__()
            self.config = config_ref
            self.jd_quote_integration_service = jd_q_int_service_ref
            self.cache_handler = None # Not used by this view directly

        def handle_quote_finished(self, result_data):
            logger.info(f"MAIN WINDOW (Test): External quote process finished. Result: {result_data}")
            QMessageBox.information(self, "External Process Done (Test)",
                                    f"Quote tool output: {result_data.get('quote_id', 'N/A')}")

    # --- Test Case 1: Service and Script Path OK ---
    print("\n--- Test Case 1: Service and Script OK ---")
    mock_jd_service_ok = MockJDQuoteIntServiceExt(operational=True)
    dummy_main_ok = DummyMainWindowForExternalQuote(mock_config_instance, mock_jd_service_ok)
    view_ok = JDExternalQuoteView(
        config=mock_config_instance, main_window=dummy_main_ok, jd_quote_integration_service=mock_jd_service_ok
    )
    view_ok.quote_process_finished_signal.connect(dummy_main_ok.handle_quote_finished)
    view_ok.set_deal_context({"deal_id": "DEAL-TEST-007", "customer_name": "Tkinter Test Farm"})
    view_ok.setWindowTitle("JD Ext Quote - Test (Operational)")
    view_ok.setGeometry(200, 200, 700, 500)
    view_ok.show()


    # --- Test Case 2: Service NOT Operational ---
    # print("\n--- Test Case 2: Service NOT Operational ---")
    # mock_jd_service_not_ok = MockJDQuoteIntServiceExt(operational=False)
    # dummy_main_not_ok_svc = DummyMainWindowForExternalQuote(mock_config_instance, mock_jd_service_not_ok)
    # view_not_ok_svc = JDExternalQuoteView(
    #     config=mock_config_instance, main_window=dummy_main_not_ok_svc, jd_quote_integration_service=mock_jd_service_not_ok
    # )
    # view_not_ok_svc.setWindowTitle("JD Ext Quote - Test (Service Not Op)")
    # view_not_ok_svc.setGeometry(250, 250, 700, 500) # Offset
    # view_not_ok_svc.show()


    # --- Test Case 3: Script Path Missing ---
    # print("\n--- Test Case 3: Script Path Missing ---")
    # mock_config_no_script = MockJDExternalConfig(script_path_val=None, python_exec_val=sys.executable) # No script path
    # dummy_main_no_script = DummyMainWindowForExternalQuote(mock_config_no_script, mock_jd_service_ok) # Service is OK
    # view_no_script = JDExternalQuoteView(
    #     config=mock_config_no_script, main_window=dummy_main_no_script, jd_quote_integration_service=mock_jd_service_ok
    # )
    # view_no_script.setWindowTitle("JD Ext Quote - Test (No Script Path)")
    # view_no_script.setGeometry(300, 300, 700, 500) # Offset
    # view_no_script.show()
    

    exit_code = app.exec()
    # Cleanup
    if os.path.exists(dummy_tk_script_name): os.remove(dummy_tk_script_name)
    mock_config_instance.cleanup()
    sys.exit(exit_code)
