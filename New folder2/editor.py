# core/editor.py - Use Config for data path (Complete File - Fully Expanded)

import os
import csv
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QHeaderView, QMessageBox # Added QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt # Added Qt for status alignment etc if needed

# It might need BaseModule if using main_window features like status bar
try:
    from ui.base_module import BaseModule # Assuming BaseModule is QWidget based
except ImportError:
    print("WARNING: BaseModule not found in core.editor. Status updates might fail.")
    # Fallback BaseModule
    class BaseModule(QWidget):
         def __init__(self, main_window=None, *args, **kwargs):
              super().__init__(main_window) # Pass parent up to QWidget
              self.main_window = main_window # Store reference if needed

         # Add dummy methods if base class relies on them
         def update_status(self, msg, timeout=3000):
             print(f"STATUS (Fallback): {msg}")
         def show_notification(self, title, msg, notification_type="info", duration=5000):
             print(f"NOTIFICATION (Fallback) [{title}]: {msg}")

# Use getLogger to get the logger instance set up in main.py
# Using a generic name here, child loggers are created in main.py
logger = logging.getLogger("CSVEditorBase")

# Inherit from BaseModule to potentially access main_window for status/config
class CSVEditor(BaseModule):
    # Accept config, logger, etc. as keyword args from main.py
    # Keep parent=None for standard Qt hierarchy
    def __init__(self, filename, headers, config=None, logger=None, csv_handler=None, main_window=None, parent=None):
        # Pass parent (which is main_window in this case) up to BaseModule/QWidget
        # If subclasses call super(..., parent), that parent will be passed here.
        # If main_window needs to be the parent explicitly, adjust how it's passed.
        # For now, assume BaseModule handles main_window reference if needed.
        super().__init__(main_window=main_window) # Pass main_window ref to BaseModule

        self.filename_short = filename # Keep short name for messages
        self.headers = headers
        # Store config and logger passed from main.py
        self.config = config
        # Use passed logger or create a specific one
        self.logger = logger if logger else logging.getLogger(f"CSVEditor_{filename}")
        # self.main_window is set by BaseModule init

        # Construct full path using config's data_dir
        self.data_path = None
        if self.config and hasattr(self.config, 'data_dir'):
             self.data_path = getattr(self.config, 'data_dir')

        if self.data_path and self.filename_short:
            self.filename_full = os.path.join(self.data_path, self.filename_short)
            self.logger.info(f"Editor targeting file: {self.filename_full}")
        else:
            self.filename_full = self.filename_short # Fallback to relative path
            self.logger.error(f"Config or data_dir not available. Attempting to use relative path: {self.filename_full}")
            # Show a critical error via main_window if possible
            self._show_status(f"Error: Cannot find data directory for {self.filename_short}", 10000, color='red')


        # Setup UI
        self.layout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.table.setObjectName(f"table_{self.filename_short.split('.')[0]}")
        self.layout.addWidget(self.table)

        self._init_table()
        self._load_csv() # Load data using the full path

        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add Row")
        delete_btn = QPushButton("Delete Selected")
        save_btn = QPushButton("Save CSV")

        add_btn.clicked.connect(self.add_row)
        delete_btn.clicked.connect(self.delete_row)
        save_btn.clicked.connect(self.save_csv)

        button_layout.addWidget(add_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        self.layout.addLayout(button_layout)

    def _init_table(self):
        """Initialize table properties."""
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # Stretch columns
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectItems) # Allow cell selection
        self.table.setSelectionMode(QTableWidget.ExtendedSelection) # Allow multi-select
        self.logger.debug(f"Table initialized for {self.filename_short} with headers: {self.headers}")


    def _load_csv(self):
        """Load data from the CSV file using the full path."""
        self.table.setRowCount(0) # Clear table first
        # Check if path was determined correctly
        if not self.filename_full:
             self.logger.error(f"Cannot load CSV, full path for {self.filename_short} is not set.")
             return

        encodings = ['utf-8-sig', 'utf-8', 'latin1', 'windows-1252']
        loaded = False
        try:
            if not os.path.exists(self.filename_full):
                 self.logger.warning(f"CSV file not found: {self.filename_full}. Table will be empty.")
                 # Optionally create the file with headers
                 try:
                      with open(self.filename_full, 'w', newline='', encoding='utf-8') as f:
                           writer = csv.writer(f); writer.writerow(self.headers)
                      self.logger.info(f"Created empty CSV file: {self.filename_full}")
                 except Exception as create_e:
                      self.logger.error(f"Failed to create empty CSV file: {create_e}")
                      self._show_status(f"Error: Could not create {self.filename_short}", 5000, 'red')
                 return # Exit loading

            for encoding in encodings:
                try:
                    with open(self.filename_full, 'r', newline='', encoding=encoding) as f:
                        reader = csv.reader(f)
                        header = next(reader, None) # Read header row
                        # Basic header check (allow for case/space differences)
                        if not header or [h.strip().lower() for h in header] != [h.strip().lower() for h in self.headers]:
                             self.logger.warning(f"Header mismatch or missing in {self.filename_short} with encoding {encoding}. Expected: {self.headers}, Found: {header}. Skipping.")
                             continue

                        rows_loaded = 0
                        for row_data in reader:
                            row = self.table.rowCount()
                            self.table.insertRow(row)
                            # Ensure row_data has enough columns, pad if necessary
                            while len(row_data) < len(self.headers):
                                 row_data.append("")
                            for col, data in enumerate(row_data):
                                if col < len(self.headers): # Avoid index error if row has too many cols
                                     self.table.setItem(row, col, QTableWidgetItem(str(data)))
                                else:
                                     self.logger.warning(f"Row {row} in {self.filename_short} has more columns ({len(row_data)}) than headers ({len(self.headers)}). Ignoring extra data.")
                            rows_loaded += 1
                        loaded = True
                        self.logger.info(f"Loaded {rows_loaded} rows from {self.filename_short} using {encoding}.")
                        break # Success
                except UnicodeDecodeError:
                    self.logger.debug(f"Encoding {encoding} failed for {self.filename_short}, trying next...")
                    continue # Try next encoding
                except csv.Error as csv_e:
                     self.logger.error(f"CSV parsing error in {self.filename_short} with {encoding}: {csv_e}")
                     continue # Try next encoding if parsing fails
                except Exception as read_e:
                     self.logger.error(f"Error reading CSV {self.filename_short} with {encoding}: {read_e}")
                     continue # Try next encoding

            if not loaded:
                 self.logger.error(f"Failed to load {self.filename_short} with any supported encoding or headers mismatch.")
                 self._show_status(f"Error: Could not read {self.filename_short}", 5000, 'red')

        except Exception as e:
            self.logger.error(f"Failed to load CSV {self.filename_short}: {e}", exc_info=True)
            self._show_status(f"Error: Could not load {self.filename_short}", 5000, 'red')


    def add_row(self):
        """Add an empty row to the table."""
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        for col in range(self.table.columnCount()):
            self.table.setItem(row_count, col, QTableWidgetItem(""))
        self.table.scrollToBottom() # Scroll to the new row
        self.logger.debug("Added new empty row.")

    def delete_row(self):
        """Delete the currently selected row(s)."""
        selected = self.table.selectedIndexes()
        if not selected:
            self._show_status("Select a row (or cells in a row) to delete!", 3000)
            return
        # Get unique rows from selected cells, sort descending to delete from end
        rows = sorted(list(set(idx.row() for idx in selected)), reverse=True)
        for row in rows:
            self.table.removeRow(row)
        self._show_status(f"Deleted {len(rows)} row(s)", 3000)
        self.logger.info(f"Deleted {len(rows)} row(s).")

    def save_csv(self):
        """Save the current table data back to the CSV file."""
        if not self.filename_full:
             self.logger.error("Cannot save CSV, filename_full is not set.")
             self._show_status("Error: File path not set!", 5000, 'red')
             return

        try:
            # Check if directory exists, create if not
            dir_name = os.path.dirname(self.filename_full)
            if not os.path.exists(dir_name):
                try:
                    os.makedirs(dir_name, exist_ok=True)
                    self.logger.info(f"Created directory: {dir_name}")
                except OSError as dir_e:
                     self.logger.error(f"Failed to create directory {dir_name}: {dir_e}")
                     self._show_status(f"Error: Cannot create directory for save!", 5000, 'red')
                     return

            with open(self.filename_full, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL) # Quote all fields
                writer.writerow(self.headers) # Write headers first
                row_count = self.table.rowCount()
                saved_rows = 0
                for row in range(row_count):
                    row_data = []
                    is_row_empty = True # Check if row is completely empty
                    for col in range(self.table.columnCount()):
                         item = self.table.item(row, col)
                         text = item.text() if item else ""
                         row_data.append(text)
                         if text: is_row_empty = False # Mark not empty if any cell has text
                    if not is_row_empty: # Only save non-empty rows
                        writer.writerow(row_data)
                        saved_rows += 1

            self._show_status(f"Saved {self.filename_short} ({saved_rows} rows)", 3000, color='green')
            self.logger.info(f"Saved {saved_rows} rows to {self.filename_full}")
            # Optionally trigger a refresh in other modules if needed
            # if hasattr(self.main_window, 'module_needs_refresh'):
            #      self.main_window.module_needs_refresh(self.filename_short)

        except Exception as e:
            self.logger.error(f"Failed to save CSV {self.filename_short}: {e}", exc_info=True)
            self._show_status(f"Error saving {self.filename_short}!", 5000, color='red')
            # Show message box for critical save error
            QMessageBox.critical(self, "Save Error", f"Could not save {self.filename_short}:\n{e}")

    def _show_status(self, message, timeout=3000, color=None):
        """Helper to show status using main window's method."""
        # Check if main_window reference exists and has the method
        # Access via self.main_window set by BaseModule init
        if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'update_status'):
             try:
                 self.main_window.update_status(message, timeout)
                 # Note: Adding color requires modification to main_window.update_status
             except Exception as e:
                 self.logger.warning(f"Failed to update status via main_window: {e}")
        else:
             self.logger.info(f"Status (CSVEditor): {message}")

    # Add get_title method for consistency with other modules
    def get_title(self):
        """Return a display title for the editor."""
        # Generate title from filename
        return f"{self.filename_short.replace('.csv', '').replace('_', ' ').title()} Editor"

    # Add get_icon_name (optional, uses default from main.py otherwise)
    # def get_icon_name(self):
    #     return f"{self.filename_short.replace('.csv', '')}_icon.png"

    # Add refresh method (calls load_csv)
    def refresh(self):
        """Reloads data from the CSV file."""
        self.logger.info(f"Refreshing editor for {self.filename_short}")
        self._load_csv()