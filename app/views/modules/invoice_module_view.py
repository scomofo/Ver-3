# app/views/modules/invoice_module_view.py
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QMessageBox, QFormLayout, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QInputDialog
)
from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFont

from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig, get_config
from app.core.threading import AsyncWorker # Changed Worker to AsyncWorker
from app.services.integrations.jd_quote_integration_service import JDQuoteIntegrationService

logger = logging.getLogger(__name__)

class InvoiceModuleView(BaseViewModule):
    """
    Module for displaying and processing invoice information based on John Deere quotes.
    """
    
    def __init__(self, config: BRIDealConfig, 
                 logger_instance: Optional[logging.Logger] = None,
                 main_window: Optional[QWidget] = None,
                 jd_quote_integration_service: Optional[JDQuoteIntegrationService] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(
            module_name="Invoice Module",
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )
        
        self.jd_quote_service = jd_quote_integration_service
        self.thread_pool = QThreadPool.globalInstance()
        
        self.current_quote_id = None
        self.current_dealer_account_no = None
        self.quote_details = None
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        title_label = QLabel("Invoice from Quote")
        title_font = QFont("Arial", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        main_layout.addWidget(title_label)
        
        # Quote info section
        quote_info_group = QGroupBox("Quote Information")
        quote_info_layout = QFormLayout()
        
        self.quote_id_field = QLineEdit()
        self.quote_id_field.setReadOnly(True)
        
        self.customer_name_field = QLineEdit()
        self.customer_name_field.setReadOnly(True)
        
        self.salesperson_field = QLineEdit()
        self.salesperson_field.setReadOnly(True)
        
        self.creation_date_field = QLineEdit()
        self.creation_date_field.setReadOnly(True)
        
        quote_info_layout.addRow("Quote ID:", self.quote_id_field)
        quote_info_layout.addRow("Customer:", self.customer_name_field)
        quote_info_layout.addRow("Salesperson:", self.salesperson_field)
        quote_info_layout.addRow("Created:", self.creation_date_field)
        
        quote_info_group.setLayout(quote_info_layout)
        main_layout.addWidget(quote_info_group)
        
        # Equipment section
        equipment_group = QGroupBox("Equipment")
        equipment_layout = QVBoxLayout()
        
        self.equipment_table = QTableWidget(0, 4)  # rows, columns
        self.equipment_table.setHorizontalHeaderLabels(["Model", "Serial #", "Order #", "Price"])
        self.equipment_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.equipment_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.equipment_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.equipment_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        equipment_layout.addWidget(self.equipment_table)
        equipment_group.setLayout(equipment_layout)
        main_layout.addWidget(equipment_group)
        
        # Trade-ins section
        tradein_group = QGroupBox("Trade-ins")
        tradein_layout = QVBoxLayout()
        
        self.tradein_table = QTableWidget(0, 3)  # rows, columns
        self.tradein_table.setHorizontalHeaderLabels(["Model", "Serial #", "Value"])
        self.tradein_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tradein_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tradein_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        tradein_layout.addWidget(self.tradein_table)
        tradein_group.setLayout(tradein_layout)
        main_layout.addWidget(tradein_group)
        
        # Notes section
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout()
        
        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setMinimumHeight(80)
        
        notes_layout.addWidget(self.notes_text)
        notes_group.setLayout(notes_layout)
        main_layout.addWidget(notes_group)
        
        # Buttons section
        buttons_layout = QHBoxLayout()
        
        self.fetch_quote_btn = QPushButton("Fetch Quote Details")
        self.fetch_quote_btn.setToolTip("Fetch the details for the current quote")
        self.fetch_quote_btn.clicked.connect(self._fetch_quote_details)
        
        self.print_invoice_btn = QPushButton("Print Invoice")
        self.print_invoice_btn.setToolTip("Print the current invoice")
        self.print_invoice_btn.clicked.connect(self._print_invoice)
        self.print_invoice_btn.setEnabled(False)  # Disabled until data is loaded
        
        self.save_pdf_btn = QPushButton("Save as PDF")
        self.save_pdf_btn.setToolTip("Save the current invoice as a PDF file")
        self.save_pdf_btn.clicked.connect(self._save_as_pdf)
        self.save_pdf_btn.setEnabled(False)  # Disabled until data is loaded
        
        buttons_layout.addWidget(self.fetch_quote_btn)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.print_invoice_btn)
        buttons_layout.addWidget(self.save_pdf_btn)
        
        main_layout.addLayout(buttons_layout)
        
        self.setLayout(main_layout)
    
    def initiate_invoice_from_quote(self, quote_id: str, dealer_account_no: str):
        """
        Initialize the invoice view with a quote ID and dealer account number.
        
        Args:
            quote_id (str): The ID of the quote to load
            dealer_account_no (str): The dealer's account number
        """
        self.logger.info(f"Initiating invoice from quote ID: {quote_id}")
        self.current_quote_id = quote_id
        self.current_dealer_account_no = dealer_account_no
        
        # Set the quote ID field
        self.quote_id_field.setText(quote_id)
        
        # Auto-fetch details if we have a valid quote ID and account number
        if quote_id and dealer_account_no:
            self._fetch_quote_details()
    
    def _fetch_quote_details(self):
        """Fetch the details for the current quote."""
        if not self.current_quote_id or not self.current_dealer_account_no:
            # If we don't have a quote ID, prompt for one
            quote_id, ok = QInputDialog.getText(self, "Enter Quote ID", "Please enter the quote ID:")
            if not ok or not quote_id:
                return
            
            dealer_account = self.config.get("JD_DEALER_ACCOUNT_NUMBER", "731804")
            if not dealer_account:
                QMessageBox.warning(self, "Missing Configuration", 
                                  "Dealer Account Number is not configured.")
                return
            
            self.current_quote_id = quote_id
            self.current_dealer_account_no = dealer_account
            self.quote_id_field.setText(quote_id)
        
        # Check if JD quote service is available
        if not self.jd_quote_service or not self.jd_quote_service.is_operational:
            QMessageBox.warning(self, "Service Unavailable", 
                              "John Deere Quote API integration is not available.")
            return
        
        # Update UI
        self.fetch_quote_btn.setEnabled(False)
        self._show_status_message("Fetching quote details...")
        
        # Fetch quote details using AsyncWorker
        self.logger.info(f"InvoiceModuleView: Attempting to create AsyncWorker for get_quote_details_via_api with quote_id: {self.current_quote_id}, dealer_account_no: {self.current_dealer_account_no}")
        async_worker = AsyncWorker(
            self.jd_quote_service.get_quote_details_via_api,
            self.current_quote_id,
            self.current_dealer_account_no
        )
        self.logger.info(f"InvoiceModuleView: AsyncWorker instance created: {async_worker}")

        self.logger.info("InvoiceModuleView: Connecting AsyncWorker signals...")
        async_worker.result_ready.connect(self._handle_quote_details_result)
        async_worker.error_occurred.connect(self._handle_quote_details_error)
        self.logger.info("InvoiceModuleView: AsyncWorker signals connected.")

        self.logger.info("InvoiceModuleView: Attempting to start AsyncWorker.")
        async_worker.start()
        self.logger.info("InvoiceModuleView: AsyncWorker start method called.")
    
    def _handle_quote_details_result(self, response_data: dict):
        """Handle the result of the quote details API call."""
        # Re-enable button
        self.fetch_quote_btn.setEnabled(True)
        
        # Check for success
        if response_data.get("type") == "SUCCESS" and response_data.get("body"):
            self.quote_details = response_data.get("body")
            self.logger.info(f"Successfully retrieved quote details for quote ID: {self.current_quote_id}")
            
            # Update UI with quote details
            self._update_ui_with_quote_details()
            
            # Enable print/save buttons
            self.print_invoice_btn.setEnabled(True)
            self.save_pdf_btn.setEnabled(True)
            
            self._show_status_message("Quote details loaded successfully")
        else:
            # Handle error case
            error_msg = response_data.get("body", {}).get("errorMessage", "Unknown API error.")
            self.logger.error(f"Quote details retrieval failed: {error_msg}")
            QMessageBox.critical(self, "Quote Details Failed", 
                              f"Could not retrieve quote details.\nError: {error_msg}")
    
    def _handle_quote_details_error(self, exception_obj: Exception):
        """Handle errors from the AsyncWorker thread when fetching quote details."""
        # Re-enable button
        self.fetch_quote_btn.setEnabled(True)
        
        error_msg = str(exception_obj)
        
        # Log the error
        self.logger.error(f"Error fetching quote details: {error_msg}", exc_info=exception_obj)
        
        # Show appropriate error message based on error type
        if "404" in error_msg:
            QMessageBox.warning(self, "Quote Not Found", 
                             f"The quote ID {self.current_quote_id} was not found in the John Deere system. Please verify the ID and try again.")
        elif "401" in error_msg or "403" in error_msg:
            QMessageBox.critical(self, "Authentication Error", 
                              "Your session has expired or you don't have permission to access this quote. Please log in again.")
        else:
            QMessageBox.critical(self, "System Error", 
                              f"An error occurred while trying to fetch quote details: {error_msg}")
    
    def _update_ui_with_quote_details(self):
        """Update the UI with the loaded quote details."""
        if not self.quote_details:
            return
        
        # Update customer and quote info
        customer_data = self.quote_details.get("customerData", {})
        customer_name = f"{customer_data.get('customerFirstName', '')} {customer_data.get('customerLastName', '')}".strip()
        self.customer_name_field.setText(customer_name)
        
        self.salesperson_field.setText(self.quote_details.get("salesPerson", ""))
        self.creation_date_field.setText(self.quote_details.get("creationDate", ""))
        
        # Update notes
        self.notes_text.setText(self.quote_details.get("custNotes", ""))
        
        # Update equipment table
        equipment_data = self.quote_details.get("equipmentData", [])
        self.equipment_table.setRowCount(len(equipment_data))
        
        for row, equipment in enumerate(equipment_data):
            model_item = QTableWidgetItem(equipment.get("dealerSpecifiedModel", ""))
            serial_item = QTableWidgetItem(equipment.get("serialNo", ""))
            order_item = QTableWidgetItem(equipment.get("dealerOrderNumber", ""))
            
            # Format price
            price = equipment.get("listPrice", 0)
            price_item = QTableWidgetItem(f"${price:,.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            self.equipment_table.setItem(row, 0, model_item)
            self.equipment_table.setItem(row, 1, serial_item)
            self.equipment_table.setItem(row, 2, order_item)
            self.equipment_table.setItem(row, 3, price_item)
        
        # Update trade-in table
        tradein_data = self.quote_details.get("tradeInEquipmentData", [])
        self.tradein_table.setRowCount(len(tradein_data))
        
        for row, tradein in enumerate(tradein_data):
            model_item = QTableWidgetItem(tradein.get("dealerSpecifiedModel", ""))
            serial_item = QTableWidgetItem(tradein.get("serialNo", ""))
            
            # Format value
            value = tradein.get("netTradeValue", 0)
            value_item = QTableWidgetItem(f"${value:,.2f}")
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            self.tradein_table.setItem(row, 0, model_item)
            self.tradein_table.setItem(row, 1, serial_item)
            self.tradein_table.setItem(row, 2, value_item)
    
    def _generate_invoice(self) -> Dict[str, Any]:
        """Generate an invoice object from the current quote details."""
        if not self.quote_details:
            return {}
        
        # Extract customer information
        customer_data = self.quote_details.get("customerData", {})
        customer_name = f"{customer_data.get('customerFirstName', '')} {customer_data.get('customerLastName', '')}".strip()
        
        # Extract equipment items
        equipment_items = []
        for equip in self.quote_details.get("equipmentData", []):
            equipment_items.append({
                "model": equip.get("dealerSpecifiedModel", ""),
                "serial_number": equip.get("serialNo", ""),
                "order_number": equip.get("dealerOrderNumber", ""),
                "price": equip.get("listPrice", 0)
            })
        
        # Calculate totals
        subtotal = sum(item["price"] for item in equipment_items)
        tax_rate = 0.07  # Example tax rate, should be configurable
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        
        # Add trade-in credits
        trade_in_items = []
        trade_in_total = 0
        for trade in self.quote_details.get("tradeInEquipmentData", []):
            trade_value = trade.get("netTradeValue", 0)
            trade_in_total += trade_value
            trade_in_items.append({
                "model": trade.get("dealerSpecifiedModel", ""),
                "serial_number": trade.get("serialNo", ""),
                "value": trade_value
            })
        
        # Final amount due
        amount_due = total - trade_in_total
        
        # Create the invoice object
        invoice = {
            "invoice_number": f"INV-{self.current_quote_id}-{datetime.now().strftime('%Y%m%d')}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "quote_id": self.current_quote_id,
            "customer": {
                "name": customer_name,
                "address": customer_data.get("customerAddr1", ""),
                "city": customer_data.get("customerCity", ""),
                "state": customer_data.get("customerState", ""),
                "zip": customer_data.get("customerZipCode", ""),
                "phone": customer_data.get("customerPhone", ""),
                "email": customer_data.get("customerEmail", "")
            },
            "salesperson": self.quote_details.get("salesPerson", ""),
            "items": equipment_items,
            "trade_ins": trade_in_items,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "trade_in_total": trade_in_total,
            "total": total,
            "amount_due": amount_due,
            "notes": self.quote_details.get("custNotes", "")
        }
        
        return invoice
    
    def _print_invoice(self):
        """Print the current invoice."""
        if not self.quote_details:
            QMessageBox.warning(self, "No Data", "No quote details available to print.")
            return
        
        # Generate the invoice object
        invoice = self._generate_invoice()
        if not invoice:
            QMessageBox.warning(self, "Error", "Failed to generate invoice data.")
            return
        
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
            
            # Create printer
            printer = QPrinter(QPrinter.Mode.HighResolution)
            printer.setPageSize(QPrinter.PageSize.Letter)
            
            # Show print preview dialog
            preview = QPrintPreviewDialog(printer, self)
            preview.paintRequested.connect(lambda p: self._print_invoice_to_printer(p, invoice))
            
            if preview.exec() == QPrintPreviewDialog.DialogCode.Accepted:
                self.logger.info("Print preview accepted")
            else:
                self.logger.info("Print preview cancelled")
        
        except Exception as e:
            self.logger.error(f"Error printing invoice: {str(e)}")
            QMessageBox.critical(self, "Print Error", f"Failed to print: {str(e)}")
    
    def _print_invoice_to_printer(self, printer, invoice):
        """Renders the invoice to the printer."""
        from PyQt6.QtGui import QTextDocument, QFont
        from PyQt6.QtCore import QSizeF, Qt
        
        # Create a document to print
        document = QTextDocument()
        
        # Generate HTML content for the invoice
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ color: #2c3e50; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .totals {{ margin-top: 20px; }}
                .notes {{ margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }}
            </style>
        </head>
        <body>
            <h1>INVOICE #{invoice['invoice_number']}</h1>
            <p>
                <strong>Date:</strong> {invoice['date']}<br>
                <strong>Quote ID:</strong> {invoice['quote_id']}
            </p>
            
            <h2>Customer Information</h2>
            <p>
                <strong>Name:</strong> {invoice['customer']['name']}<br>
                <strong>Address:</strong> {invoice['customer']['address']}<br>
                <strong>City:</strong> {invoice['customer']['city']}, <strong>State:</strong> {invoice['customer']['state']}, <strong>ZIP:</strong> {invoice['customer']['zip']}<br>
                <strong>Phone:</strong> {invoice['customer']['phone']}<br>
                <strong>Email:</strong> {invoice['customer']['email']}
            </p>
            
            <p><strong>Salesperson:</strong> {invoice['salesperson']}</p>
            
            <h2>Equipment</h2>
            <table>
                <tr>
                    <th>Model</th>
                    <th>Serial #</th>
                    <th>Order #</th>
                    <th>Price</th>
                </tr>
        """
        
        for item in invoice['items']:
            html_content += f"""
                <tr>
                    <td>{item['model']}</td>
                    <td>{item['serial_number']}</td>
                    <td>{item['order_number']}</td>
                    <td>${item['price']:,.2f}</td>
                </tr>
            """
        
        html_content += "</table>"
        
        if invoice['trade_ins']:
            html_content += f"""
            <h2>Trade-ins</h2>
            <table>
                <tr>
                    <th>Model</th>
                    <th>Serial #</th>
                    <th>Value</th>
                </tr>
            """
            
            for item in invoice['trade_ins']:
                html_content += f"""
                    <tr>
                        <td>{item['model']}</td>
                        <td>{item['serial_number']}</td>
                        <td>${item['value']:,.2f}</td>
                    </tr>
                """
            
            html_content += "</table>"
        
        html_content += f"""
            <div class="totals">
                <p>
                    <strong>Subtotal:</strong> ${invoice['subtotal']:,.2f}<br>
                    <strong>Tax Rate:</strong> {invoice['tax_rate'] * 100:.1f}%<br>
                    <strong>Tax Amount:</strong> ${invoice['tax_amount']:,.2f}<br>
                    <strong>Trade-in Total:</strong> ${invoice['trade_in_total']:,.2f}<br>
                    <strong>Total Due:</strong> ${invoice['amount_due']:,.2f}
                </p>
            </div>
        """
        
        if invoice['notes']:
            html_content += f"""
            <div class="notes">
                <h2>Notes</h2>
                <p>{invoice['notes']}</p>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        # Set the HTML content to the document
        document.setHtml(html_content)
        
        # Set the document size to match the printer page
        document.setPageSize(QSizeF(printer.pageRect().size()))
        
        # Print the document
        document.print(printer)
    
    def _save_as_pdf(self):
        """Save the current invoice as a PDF file."""
        if not self.quote_details:
            QMessageBox.warning(self, "No Data", "No quote details available to save as PDF.")
            return
        
        # Generate the invoice object
        invoice = self._generate_invoice()
        if not invoice:
            QMessageBox.warning(self, "Error", "Failed to generate invoice data.")
            return
        
        # Get a filename from the user
        customer_name = invoice["customer"]["name"].replace(" ", "_")
        suggested_filename = f"Invoice_{invoice['quote_id']}_{customer_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        options = QFileDialog.Option.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Invoice as PDF", suggested_filename,
            "PDF Files (*.pdf);;All Files (*)", options=options
        )
        
        if not filename:
            return  # User cancelled
        
        try:
            # Generate PDF using a PDF library like ReportLab or PyPDF2
            self._generate_pdf(filename, invoice)
            QMessageBox.information(self, "PDF Export", f"Invoice saved as {filename}.")
        except Exception as e:
            self.logger.error(f"Error saving PDF: {str(e)}")
            QMessageBox.critical(self, "PDF Error", f"Failed to save PDF: {str(e)}")
    
    def _generate_pdf(self, filename, invoice):
        """Generate a PDF invoice using ReportLab."""
        try:
            # This is a placeholder implementation. In a real scenario, you would use ReportLab or another PDF library.
            # This implementation just creates a simple text file with the invoice data
            self.logger.info(f"Generating PDF for invoice #{invoice['invoice_number']} to {filename}")
            
            with open(filename, 'w') as f:
                # Write invoice header
                f.write(f"INVOICE #{invoice['invoice_number']}\n")
                f.write(f"Date: {invoice['date']}\n")
                f.write(f"Quote ID: {invoice['quote_id']}\n\n")
                
                # Customer information
                f.write("CUSTOMER INFORMATION\n")
                f.write(f"Name: {invoice['customer']['name']}\n")
                f.write(f"Address: {invoice['customer']['address']}\n")
                f.write(f"City: {invoice['customer']['city']}, State: {invoice['customer']['state']}, ZIP: {invoice['customer']['zip']}\n")
                f.write(f"Phone: {invoice['customer']['phone']}\n")
                f.write(f"Email: {invoice['customer']['email']}\n\n")
                
                # Salesperson
                f.write(f"Salesperson: {invoice['salesperson']}\n\n")
                
                # Equipment items
                f.write("EQUIPMENT\n")
                for item in invoice['items']:
                    f.write(f"Model: {item['model']}, Serial #: {item['serial_number']}, Order #: {item['order_number']}, Price: ${item['price']:,.2f}\n")
                f.write("\n")
                
                # Trade-ins
                if invoice['trade_ins']:
                    f.write("TRADE-INS\n")
                    for item in invoice['trade_ins']:
                        f.write(f"Model: {item['model']}, Serial #: {item['serial_number']}, Value: ${item['value']:,.2f}\n")
                    f.write("\n")
                
                # Totals
                f.write("TOTALS\n")
                f.write(f"Subtotal: ${invoice['subtotal']:,.2f}\n")
                f.write(f"Tax Rate: {invoice['tax_rate'] * 100:.1f}%\n")
                f.write(f"Tax Amount: ${invoice['tax_amount']:,.2f}\n")
                f.write(f"Trade-in Total: ${invoice['trade_in_total']:,.2f}\n")
                f.write(f"Total Due: ${invoice['amount_due']:,.2f}\n\n")
                
                # Notes
                if invoice['notes']:
                    f.write("NOTES\n")
                    f.write(f"{invoice['notes']}\n")
            
            self.logger.info(f"PDF generation complete for {filename}")
            
            # In a real implementation, you would import reportlab and use it to create a proper PDF
            """
            Example with ReportLab:
            
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            
            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Build the PDF content
            content = []
            
            # Add the invoice header
            content.append(Paragraph(f"INVOICE #{invoice['invoice_number']}", styles['Title']))
            content.append(Paragraph(f"Date: {invoice['date']}", styles['Normal']))
            content.append(Paragraph(f"Quote ID: {invoice['quote_id']}", styles['Normal']))
            content.append(Spacer(1, 12))
            
            # Add customer info
            # ... etc
            
            # Build the document
            doc.build(content)
            """
            
        except Exception as e:
            self.logger.error(f"Error generating PDF: {str(e)}", exc_info=True)
            raise
    
    def _show_status_message(self, message, timeout=5000):
        """Shows a status message in the main window's status bar if available."""
        if self.main_window and hasattr(self.main_window, 'statusBar'):
            try:
                status_bar = self.main_window.statusBar()
                status_bar.showMessage(message, timeout)
            except Exception as e:
                self.logger.error(f"Error showing status message: {e}")
                self.logger.info(f"Status: {message}")
        else:
            self.logger.info(f"Status: {message}")
    
    def get_title(self):
        """Returns the title of this module."""
        return "Invoice"
    
    def get_icon_name(self): return "invoice_icon.png"