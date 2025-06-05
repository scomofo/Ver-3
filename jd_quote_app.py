import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
import os
import sys
import logging
from datetime import datetime, timedelta
import tempfile
import threading
import requests

# Set up basic logging with more detail
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('JDQuoteApp')

print("Starting JD Quote Application with Real API (Fixed Version)...")
print(f"Current directory: {os.getcwd()}")

# Important fix: Make sure we include the current directory in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
    print(f"Added {current_dir} to Python path")

# Print module search paths for debugging
print("Python module search paths:")
for path in sys.path:
    print(f" - {path}")

# Try to import real API clients
try:
    from auth.jd_oauth_client import JDOAuthClient
    from api.jd_quote_client import MaintainQuoteClient
    logger.info("Successfully imported real API clients")
except ImportError as e:
    logger.warning(f"Could not import real API clients: {str(e)}")
    
    # Simple mock implementations as fallback
    class JDOAuthClient:
        def __init__(self, client_id, client_secret, token_url=None, token_cache_path=None):
            self.client_id = client_id
            self.client_secret = client_secret
            self.token_url = token_url
            logger.info(f"Mock OAuth client created with ID: {client_id}")
            
        def get_auth_header(self):
            if not self.client_id or not self.client_secret:
                logger.error("Mock Auth: Missing credentials")
                raise ValueError("Client ID and Client Secret are required")
            return {"Authorization": "Bearer dummy_token"}
    
    class MaintainQuoteClient:
        def __init__(self, oauth_client, base_url=None):
            self.oauth_client = oauth_client
            self.base_url = base_url
            logger.info(f"Mock Quote client created with URL: {base_url}")
            
        def search_quotes(self, search_criteria):
            logger.warning("Using mock search_quotes - not connected to real API")
            return {"body": []}
            
        def get_quote_details(self, quote_id):
            """
            Get detailed information about a quote
            
            Args:
                quote_id (str): Quote ID
                
            Returns:
                dict: API response with quote details
            """
            logger.info(f"Getting details for quote {quote_id}")
            
            # For Quote Data API, try the quote-detail endpoint instead
            if "/quotedata" in self.base_url.lower():
                endpoint = f"/api/v1/quotes/{quote_id}/quote-detail"
            else:
                # Original Maintain Quote API endpoint
                endpoint = f"/api/v1/quotes/{quote_id}/maintain-quote-details"
                    
            return self._make_request("GET", endpoint)
            
        def create_quote(self, quote_data):
            logger.warning("Using mock create_quote - not connected to real API")
            return {"body": {"quoteID": "12345"}}

# Try to import PDF handling libraries
try:
    import fitz  # PyMuPDF
    HAS_PDF_PREVIEW = True
except ImportError:
    logger.warning("PyMuPDF not found, PDF preview will be limited")
    HAS_PDF_PREVIEW = False

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    logger.warning("PIL not found, image handling will be limited")
    HAS_PIL = False

# Simplified ConfigManager - but with better debugging
class SimpleConfig:
    """Simple configuration manager with debugging."""
    
    def __init__(self, config_file="jd_quote_config.json"):
        self.config_file = config_file
        self.config = {}
        
        logger.info(f"Initializing SimpleConfig with file: {self.config_file}")
        self._load_from_file()
    
    def _load_from_file(self):
        """Load configuration from file with detailed logging."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded config from {self.config_file}")
                # Log config (without sensitive details)
                safe_config = self.config.copy()
                if 'jd_client_secret' in safe_config:
                    safe_config['jd_client_secret'] = '[HIDDEN]'
                logger.debug(f"Config contents: {json.dumps(safe_config)}")
            except Exception as e:
                logger.error(f"Error loading config file: {str(e)}")
        else:
            logger.info(f"Config file {self.config_file} not found, using empty config")
    
    def get_setting(self, key, default=None):
        """Get setting with better logging."""
        # Check direct config value first
        if key in self.config:
            value = self.config[key]
            # Don't log client secret values
            if 'secret' in key.lower():
                logger.debug(f"Retrieved setting {key}: [HIDDEN]")
            else:
                logger.debug(f"Retrieved setting {key}: {value}")
            return value
        
        # Check environment variables
        env_value = os.environ.get(key.upper()) or os.environ.get(key)
        if env_value is not None:
            if 'secret' in key.lower():
                logger.debug(f"Retrieved setting {key} from env: [HIDDEN]")
            else:
                logger.debug(f"Retrieved setting {key} from env: {env_value}")
            return env_value
        
        # Check dotted notation
        if '.' in key:
            parts = key.split('.')
            current = self.config
            for part in parts:
                if part not in current:
                    logger.debug(f"Setting {key} not found, returning default: {default}")
                    return default
                current = current[part]
            logger.debug(f"Retrieved nested setting {key}: {current}")
            return current
        
        # Not found
        logger.debug(f"Setting {key} not found, returning default: {default}")
        return default
    
    def set_setting(self, key, value):
        """Set setting with better logging."""
        # Prevent logging sensitive values
        log_value = '[HIDDEN]' if 'secret' in key.lower() else value
        logger.debug(f"Setting {key} = {log_value}")
        
        if '.' in key:
            parts = key.split('.')
            current = self.config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                if not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        else:
            self.config[key] = value
        
        # Save immediately to ensure values are persisted
        self.save_settings()
        return True
    
    def save_settings(self):
        """Save settings with better error handling."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(self.config_file)), exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Saved settings to {self.config_file}")
            
            # Verify file was written
            if os.path.exists(self.config_file):
                file_size = os.path.getsize(self.config_file)
                logger.debug(f"Config file size: {file_size} bytes")
                if file_size == 0:
                    logger.warning("Config file was created but is empty!")
            else:
                logger.warning("Config file was not created successfully!")
                
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {str(e)}")
            return False
    
    # Alias for compatibility
    get = get_setting
    save = save_settings

class ToolTip:
    """Create tooltips for a given widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        # Create a toplevel window
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = ttk.Label(self.tooltip, text=self.text, 
                         background="#ffffe0", relief="solid", borderwidth=1,
                         wraplength=250, justify="left", padding=5)
        label.pack()
    
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class PDFPreviewDialog(tk.Toplevel):
    """Dialog for previewing PDFs."""
    
    def __init__(self, parent, pdf_data, title="PDF Preview"):
        """Initialize the PDF preview dialog."""
        super().__init__(parent)
        self.pdf_data = pdf_data
        self.title(title)
        self.geometry("800x600")
        self.minsize(600, 400)
        
        # Create layout
        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        # Add navigation buttons
        self.prev_btn = ttk.Button(self.toolbar, text="Previous Page", command=self._prev_page)
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        
        self.next_btn = ttk.Button(self.toolbar, text="Next Page", command=self._next_page)
        self.next_btn.pack(side=tk.LEFT, padx=5)
        
        # Page counter
        self.page_var = tk.StringVar(value="Page 1 of 1")
        ttk.Label(self.toolbar, textvariable=self.page_var).pack(side=tk.LEFT, padx=20)
        
        # Add zoom controls
        ttk.Label(self.toolbar, text="Zoom:").pack(side=tk.LEFT, padx=5)
        self.zoom_var = tk.StringVar(value="100%")
        self.zoom_combo = ttk.Combobox(self.toolbar, textvariable=self.zoom_var, 
                                      values=["50%", "75%", "100%", "125%", "150%", "200%"], width=5)
        self.zoom_combo.pack(side=tk.LEFT)
        self.zoom_combo.bind("<<ComboboxSelected>>", self._change_zoom)
        
        # Save button
        ttk.Button(self.toolbar, text="Save PDF", command=self._save_pdf).pack(side=tk.RIGHT, padx=5)
        
        # Print button (if application is running on a system with print capabilities)
        ttk.Button(self.toolbar, text="Print", command=self._print_pdf).pack(side=tk.RIGHT, padx=5)
        
        # Canvas for PDF display
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add scrollbars
        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Create canvas
        self.canvas = tk.Canvas(self.canvas_frame, bg="white", 
                             yscrollcommand=self.v_scrollbar.set,
                             xscrollcommand=self.h_scrollbar.set)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Configure scrollbars
        self.v_scrollbar.config(command=self.canvas.yview)
        self.h_scrollbar.config(command=self.canvas.xview)
        
        # Load PDF
        self.temp_file = None
        self.doc = None
        self.current_page = 0
        self.zoom_level = 1.0
        
        # Load the PDF - check for PyMuPDF
        if HAS_PDF_PREVIEW:
            # Load with PyMuPDF for full preview
            self._load_pdf_pymupdf()
        else:
            # Load with basic preview (just show first page)
            self._load_pdf_basic()
    
    def _load_pdf_pymupdf(self):
        """Load the PDF data into a temporary file and display it using PyMuPDF."""
        try:
            # Create a temporary file
            self.temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            self.temp_file.write(self.pdf_data)
            self.temp_file.close()
            
            # Open the PDF with PyMuPDF
            self.doc = fitz.open(self.temp_file.name)
            
            # Update page counter
            self.page_var.set(f"Page 1 of {len(self.doc)}")
            
            # Display first page
            self._display_page(0)
        except Exception as e:
            logger.error(f"Error loading PDF with PyMuPDF: {str(e)}")
            messagebox.showerror("Error", f"Failed to load PDF: {str(e)}")
            self.destroy()
    
    def _load_pdf_basic(self):
        """Basic PDF preview for when PyMuPDF is not available."""
        try:
            # Create a temporary file
            self.temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            self.temp_file.write(self.pdf_data)
            self.temp_file.close()
            
            # Show basic info
            self.page_var.set("PDF Preview")
            
            # Show message on canvas
            self.canvas.create_text(400, 300, text="PDF loaded successfully.\n\n"
                                               "For full preview capability,\n"
                                               "please install PyMuPDF package.")
            
            # Disable navigation and zoom
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)
            self.zoom_combo.config(state=tk.DISABLED)
        except Exception as e:
            logger.error(f"Error in basic PDF loading: {str(e)}")
            messagebox.showerror("Error", f"Failed to load PDF: {str(e)}")
            self.destroy()
    
    def _display_page(self, page_num):
        """Display a specific page of the PDF."""
        if not self.doc:
            return
            
        if page_num < 0 or page_num >= len(self.doc):
            return
            
        self.current_page = page_num
        
        # Get the page
        page = self.doc[page_num]
        
        # Apply zoom
        mat = fitz.Matrix(self.zoom_level, self.zoom_level)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PhotoImage
        if HAS_PIL:
            # Use PIL if available
            mode = "RGBA" if pix.alpha else "RGB"
            img_data = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            img = ImageTk.PhotoImage(img_data)
        else:
            # Fallback to tkinter's PhotoImage (limited formats)
            img_data = pix.tobytes("ppm")
            img = tk.PhotoImage(data=img_data)
        
        # Update canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img)
        self.canvas.image = img  # Keep a reference
        
        # Update scrollregion
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
        
        # Update page counter
        self.page_var.set(f"Page {page_num + 1} of {len(self.doc)}")
        
        # Update button states
        self.prev_btn.config(state=tk.NORMAL if page_num > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if page_num < len(self.doc) - 1 else tk.DISABLED)
    
    def _prev_page(self):
        """Display the previous page."""
        self._display_page(self.current_page - 1)
    
    def _next_page(self):
        """Display the next page."""
        self._display_page(self.current_page + 1)
    
    def _change_zoom(self, event=None):
        """Change the zoom level."""
        zoom_text = self.zoom_var.get().replace('%', '')
        try:
            self.zoom_level = float(zoom_text) / 100.0
            self._display_page(self.current_page)
        except ValueError:
            pass
    
    def _save_pdf(self):
        """Save the PDF to disk."""
        if not self.pdf_data:
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=f"quote_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    f.write(self.pdf_data)
                messagebox.showinfo("Success", f"PDF saved to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save PDF: {str(e)}")
    
    def _print_pdf(self):
        """Print the PDF."""
        if not self.temp_file or not os.path.exists(self.temp_file.name):
            return
            
        try:
            import subprocess
            import platform
            
            system = platform.system()
            if system == "Windows":
                os.startfile(self.temp_file.name, "print")
            elif system == "Darwin":  # macOS
                subprocess.call(["lpr", self.temp_file.name])
            else:  # Linux
                subprocess.call(["lpr", self.temp_file.name])
                
            messagebox.showinfo("Print", "Print job sent to the printer")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to print PDF: {str(e)}")
    
    def destroy(self):
        """Clean up resources before destroying the window."""
        if self.doc:
            self.doc.close()
        
        if self.temp_file and os.path.exists(self.temp_file.name):
            try:
                os.unlink(self.temp_file.name)
            except:
                pass
                
        super().destroy()

class CreateQuoteWizard:
    """Wizard for creating quotes with step-by-step guidance."""
    
    def __init__(self, parent, quote_client, config, on_complete=None):
        """Initialize the quote creation wizard."""
        self.parent = parent
        self.quote_client = quote_client
        self.config = config
        self.on_complete = on_complete
        
        self.current_step = 0
        self.steps = [
            "Customer Information",
            "Equipment Details",
            "Quote Options",
            "Review"
        ]
        
        # Data structures for the quote
        self.customer_data = {}
        self.equipment_data = []
        self.quote_data = {
            "quoteType": "2",  # Default to Purchase
            "quoteName": f"New Quote - {datetime.now().strftime('%Y-%m-%d')}",
            "dealerAccountNumber": self.config.get_setting('jd.dealer_account_number', '')
        }
        
        # Create the wizard dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Quote - Step 1: Customer Information")
        self.dialog.geometry("600x500")
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create the wizard interface
        self._create_ui()
        
        # Show the first step
        self._show_step(0)
    
    def _create_ui(self):
        """Create the wizard UI."""
        # Create main layout
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Steps indicator
        steps_frame = ttk.Frame(main_frame)
        steps_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.step_labels = []
        for i, step in enumerate(self.steps):
            label = ttk.Label(steps_frame, text=f"{i+1}. {step}")
            label.pack(side=tk.LEFT, padx=10)
            self.step_labels.append(label)
        
        # Separator
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=5)
        
        # Content frame
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.back_btn = ttk.Button(button_frame, text="Back", command=self._back_step)
        self.back_btn.pack(side=tk.LEFT, padx=5)
        
        self.next_btn = ttk.Button(button_frame, text="Next", command=self._next_step)
        self.next_btn.pack(side=tk.RIGHT, padx=5)
        
        self.cancel_btn = ttk.Button(button_frame, text="Cancel", command=self._on_close)
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)
    
    def _show_step(self, step_index):
        """Show a specific step of the wizard."""
        # Update current step
        self.current_step = step_index
        
        # Update step indicators
        for i, label in enumerate(self.step_labels):
            if i < step_index:
                label.config(foreground="green")
            elif i == step_index:
                label.config(foreground="blue", font=("", 10, "bold"))
            else:
                label.config(foreground="black", font=("", 10, "normal"))
        
        # Update dialog title
        self.dialog.title(f"Create Quote - Step {step_index + 1}: {self.steps[step_index]}")
        
        # Clear content frame
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Show step content
        if step_index == 0:
            self._show_customer_step()
        elif step_index == 1:
            self._show_equipment_step()
        elif step_index == 2:
            self._show_options_step()
        elif step_index == 3:
            self._show_review_step()
        
        # Update button states
        self.back_btn.config(state=tk.NORMAL if step_index > 0 else tk.DISABLED)
        
        if step_index == len(self.steps) - 1:
            self.next_btn.config(text="Create Quote", command=self._create_quote)
        else:
            self.next_btn.config(text="Next", command=self._next_step)
    
    def _show_customer_step(self):
        """Show the customer information step."""
        # Create form
        form = ttk.Frame(self.content_frame)
        form.pack(fill=tk.BOTH, expand=True)
        
        # Create form fields
        ttk.Label(form, text="Customer Information", font=("", 12, "bold")).grid(
            row=0, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        # First Name
        ttk.Label(form, text="First Name:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.first_name_var = tk.StringVar(value=self.customer_data.get("customerFirstName", ""))
        first_name_entry = ttk.Entry(form, textvariable=self.first_name_var, width=30)
        first_name_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(first_name_entry, "Customer's first name (required)")
        
        # Last Name
        ttk.Label(form, text="Last Name:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.last_name_var = tk.StringVar(value=self.customer_data.get("customerLastName", ""))
        last_name_entry = ttk.Entry(form, textvariable=self.last_name_var, width=30)
        last_name_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(last_name_entry, "Customer's last name (required)")
        
        # Business Name
        ttk.Label(form, text="Business Name:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.business_name_var = tk.StringVar(value=self.customer_data.get("customerBusinessName", ""))
        business_name_entry = ttk.Entry(form, textvariable=self.business_name_var, width=30)
        business_name_entry.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(business_name_entry, "Business or organization name (optional)")
        
        # Email
        ttk.Label(form, text="Email:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        self.email_var = tk.StringVar(value=self.customer_data.get("customerEmail", ""))
        email_entry = ttk.Entry(form, textvariable=self.email_var, width=30)
        email_entry.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(email_entry, "Customer's email address (optional)")
        
        # Phone
        ttk.Label(form, text="Phone:").grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)
        self.phone_var = tk.StringVar(value=self.customer_data.get("customerHomePhoneNumber", ""))
        phone_entry = ttk.Entry(form, textvariable=self.phone_var, width=30)
        phone_entry.grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(phone_entry, "Customer's phone number (optional)")
        
        # Address
        ttk.Label(form, text="Address:").grid(row=6, column=0, padx=5, pady=5, sticky=tk.W)
        self.address_var = tk.StringVar(value=self.customer_data.get("customerAddr1", ""))
        address_entry = ttk.Entry(form, textvariable=self.address_var, width=30)
        address_entry.grid(row=6, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(address_entry, "Street address (optional)")
        
        # City
        ttk.Label(form, text="City:").grid(row=7, column=0, padx=5, pady=5, sticky=tk.W)
        self.city_var = tk.StringVar(value=self.customer_data.get("customerCity", ""))
        city_entry = ttk.Entry(form, textvariable=self.city_var, width=30)
        city_entry.grid(row=7, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(city_entry, "City (optional)")
        
        # State
        ttk.Label(form, text="State:").grid(row=8, column=0, padx=5, pady=5, sticky=tk.W)
        self.state_var = tk.StringVar(value=self.customer_data.get("customerState", ""))
        state_entry = ttk.Entry(form, textvariable=self.state_var, width=30)
        state_entry.grid(row=8, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(state_entry, "State or province (optional)")
        
        # Zip
        ttk.Label(form, text="Zip Code:").grid(row=9, column=0, padx=5, pady=5, sticky=tk.W)
        self.zip_var = tk.StringVar(value=self.customer_data.get("customerZipCode", ""))
        zip_entry = ttk.Entry(form, textvariable=self.zip_var, width=30)
        zip_entry.grid(row=9, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(zip_entry, "Zip or postal code (optional)")
    
    def _show_equipment_step(self):
        """Show the equipment information step."""
        # Create form
        form = ttk.Frame(self.content_frame)
        form.pack(fill=tk.BOTH, expand=True)
        
        # Create form fields
        ttk.Label(form, text="Equipment Information", font=("", 12, "bold")).grid(
            row=0, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        # Equipment list
        ttk.Label(form, text="Equipment:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.NW)
        
        # Create equipment list frame
        list_frame = ttk.Frame(form)
        list_frame.grid(row=1, column=1, padx=5, pady=5, sticky=tk.NSEW)
        
        # Create equipment table
        columns = ("Model", "Description", "Quantity", "Price")
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=5)
        
        # Configure columns
        for col in columns:
            self.equipment_tree.heading(col, text=col)
            self.equipment_tree.column(col, width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack table and scrollbar
        self.equipment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add buttons
        button_frame = ttk.Frame(form)
        button_frame.grid(row=2, column=1, padx=5, pady=5, sticky=tk.EW)
        
        ttk.Button(button_frame, text="Add", command=self._add_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Edit", command=self._edit_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remove", command=self._remove_equipment).pack(side=tk.LEFT, padx=5)
        
        # Load existing equipment
        self._load_equipment_list()
    
    def _show_options_step(self):
        """Show the quote options step."""
        # Create form
        form = ttk.Frame(self.content_frame)
        form.pack(fill=tk.BOTH, expand=True)
        
        # Create form fields
        ttk.Label(form, text="Quote Options", font=("", 12, "bold")).grid(
            row=0, column=0, columnspan=3, pady=10, sticky=tk.W)
        
        # Quote Name
        ttk.Label(form, text="Quote Name:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.quote_name_var = tk.StringVar(value=self.quote_data.get("quoteName", ""))
        quote_name_entry = ttk.Entry(form, textvariable=self.quote_name_var, width=30)
        quote_name_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(quote_name_entry, "Name for the quote (required)")
        
        # Quote Type
        ttk.Label(form, text="Quote Type:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.quote_type_var = tk.StringVar(value=self.quote_data.get("quoteType", "2"))
        quote_type_combo = ttk.Combobox(form, textvariable=self.quote_type_var, 
                    values=["1", "2", "3", "4"], width=5)
        quote_type_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(form, text="(1: Purchase, 2: Lease, 3: Rental, 4: Service)").grid(
            row=2, column=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(quote_type_combo, "Type of quote: 1=Purchase, 2=Lease, 3=Rental, 4=Service")
        
        # Expiration Date
        ttk.Label(form, text="Expiration Date:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        default_expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        self.expiry_var = tk.StringVar(value=self.quote_data.get("expirationDate", default_expiry))
        expiry_entry = ttk.Entry(form, textvariable=self.expiry_var, width=15)
        expiry_entry.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(form, text="(YYYY-MM-DD)").grid(
            row=3, column=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(expiry_entry, "Date when quote expires (format: YYYY-MM-DD)")
        
        # Sales Person
        ttk.Label(form, text="Sales Person:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        self.sales_person_var = tk.StringVar(value=self.quote_data.get("salesPerson", ""))
        sales_person_entry = ttk.Entry(form, textvariable=self.sales_person_var, width=30)
        sales_person_entry.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(sales_person_entry, "Name or ID of the salesperson")
        
        # Notes
        ttk.Label(form, text="Notes:").grid(row=5, column=0, padx=5, pady=5, sticky=tk.NW)
        self.notes_var = tk.StringVar(value=self.quote_data.get("custNotes", ""))
        notes_entry = ttk.Entry(form, textvariable=self.notes_var, width=40)
        notes_entry.grid(row=5, column=1, columnspan=2, padx=5, pady=5, sticky=tk.EW)
        ToolTip(notes_entry, "Additional notes for the quote")
    
    def _show_review_step(self):
        """Show the review step."""
        # Create review frame
        review_frame = ttk.Frame(self.content_frame)
        review_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrolled text for review
        review_text = scrolledtext.ScrolledText(review_frame, wrap=tk.WORD, width=60, height=20)
        review_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Collect all data
        self._collect_customer_data()
        self._collect_quote_options()
        
        # Format review text
        review_text.insert(tk.END, "QUOTE SUMMARY\n\n", "header")
        
        # Quote info
        review_text.insert(tk.END, "Quote Information\n", "section")
        review_text.insert(tk.END, f"Quote Name: {self.quote_data.get('quoteName', '')}\n")
        
        quote_type_map = {"1": "Purchase", "2": "Lease", "3": "Rental", "4": "Service"}
        quote_type = quote_type_map.get(self.quote_data.get("quoteType", ""), "Unknown")
        review_text.insert(tk.END, f"Quote Type: {quote_type}\n")
        
        review_text.insert(tk.END, f"Expiration Date: {self.quote_data.get('expirationDate', '')}\n")
        review_text.insert(tk.END, f"Sales Person: {self.quote_data.get('salesPerson', '')}\n\n")
        
        # Customer info
        review_text.insert(tk.END, "Customer Information\n", "section")
        review_text.insert(tk.END, f"Name: {self.customer_data.get('customerFirstName', '')} {self.customer_data.get('customerLastName', '')}\n")
        
        if self.customer_data.get("customerBusinessName"):
            review_text.insert(tk.END, f"Business: {self.customer_data.get('customerBusinessName', '')}\n")
            
        if self.customer_data.get("customerEmail"):
            review_text.insert(tk.END, f"Email: {self.customer_data.get('customerEmail', '')}\n")
            
        if self.customer_data.get("customerHomePhoneNumber"):
            review_text.insert(tk.END, f"Phone: {self.customer_data.get('customerHomePhoneNumber', '')}\n")
        
        # Address if provided
        if any(self.customer_data.get(f, '') for f in ['customerAddr1', 'customerCity', 'customerState']):
            address = []
            if self.customer_data.get('customerAddr1'):
                address.append(self.customer_data.get('customerAddr1'))
            
            city_state = []
            if self.customer_data.get('customerCity'):
                city_state.append(self.customer_data.get('customerCity'))
            if self.customer_data.get('customerState'):
                city_state.append(self.customer_data.get('customerState'))
            
            if city_state:
                address.append(", ".join(city_state))
                
            if self.customer_data.get('customerZipCode'):
                address.append(self.customer_data.get('customerZipCode'))
                
            review_text.insert(tk.END, f"Address: {', '.join(address)}\n")
        
        review_text.insert(tk.END, "\n")
        
        # Equipment
        review_text.insert(tk.END, "Equipment\n", "section")
        
        if self.equipment_data:
            for i, equipment in enumerate(self.equipment_data, 1):
                review_text.insert(tk.END, f"{i}. {equipment.get('dealerSpecifiedModel', 'Unknown')}\n")
                review_text.insert(tk.END, f"   Quantity: {equipment.get('quantity', 1)}\n")
                
                # Format price
                try:
                    price = float(equipment.get('listPrice', 0))
                    review_text.insert(tk.END, f"   Price: ${price:,.2f}\n")
                except:
                    review_text.insert(tk.END, f"   Price: ${equipment.get('listPrice', 0)}\n")
                
                review_text.insert(tk.END, "\n")
        else:
            review_text.insert(tk.END, "No equipment added.\n\n")
        
        # Notes
        if self.quote_data.get('custNotes'):
            review_text.insert(tk.END, "Notes\n", "section")
            review_text.insert(tk.END, f"{self.quote_data.get('custNotes', '')}\n\n")
        
        # Configure tags
        review_text.tag_configure("header", font=("", 14, "bold"))
        review_text.tag_configure("section", font=("", 12, "bold"))
        
        # Make read-only
        review_text.config(state=tk.DISABLED)
    
    def _back_step(self):
        """Move to the previous step."""
        if self.current_step > 0:
            self._show_step(self.current_step - 1)
    
    def _next_step(self):
        """Move to the next step."""
        # Validate current step
        if self.current_step == 0:  # Customer info
            if not self._validate_customer_step():
                return
            self._collect_customer_data()
        elif self.current_step == 1:  # Equipment
            if not self._validate_equipment_step():
                return
        elif self.current_step == 2:  # Options
            if not self._validate_options_step():
                return
            self._collect_quote_options()
        
        # Show next step
        if self.current_step < len(self.steps) - 1:
            self._show_step(self.current_step + 1)
    
    def _validate_customer_step(self):
        """Validate the customer information step."""
        errors = []
        
        # Check required fields
        if not self.first_name_var.get().strip():
            errors.append("First Name is required")
            
        if not self.last_name_var.get().strip():
            errors.append("Last Name is required")
        
        # Email validation if provided
        email = self.email_var.get().strip()
        if email and '@' not in email:
            errors.append("Invalid email address format")
        
        # Show all errors if any
        if errors:
            messagebox.showwarning("Validation Errors", 
                                  "Please correct the following issues:\n\n" + 
                                  "\n".join(f"• {error}" for error in errors))
            return False
        
        return True
    
    def _validate_equipment_step(self):
        """Validate the equipment step."""
        # Check if at least one equipment is added
        if not self.equipment_tree.get_children():
            messagebox.showwarning("Validation Error", "Please add at least one equipment item")
            return False
        
        return True
    
    def _validate_options_step(self):
        """Validate the quote options step."""
        errors = []
        
        # Check required fields
        if not self.quote_name_var.get().strip():
            errors.append("Quote Name is required")
            
        if not self.quote_type_var.get():
            errors.append("Quote Type is required")
        
        # Validate date format
        try:
            expiry_date = self.expiry_var.get().strip()
            if expiry_date:
                datetime.strptime(expiry_date, "%Y-%m-%d")
        except ValueError:
            errors.append("Expiration Date must be in YYYY-MM-DD format")
        
        # Show all errors if any
        if errors:
            messagebox.showwarning("Validation Errors", 
                                  "Please correct the following issues:\n\n" + 
                                  "\n".join(f"• {error}" for error in errors))
            return False
        
        return True
    
    def _collect_customer_data(self):
        """Collect customer data from form."""
        self.customer_data = {
            "customerFirstName": self.first_name_var.get().strip(),
            "customerLastName": self.last_name_var.get().strip(),
            "customerBusinessName": self.business_name_var.get().strip(),
            "customerEmail": self.email_var.get().strip(),
            "customerHomePhoneNumber": self.phone_var.get().strip(),
            "customerAddr1": self.address_var.get().strip(),
            "customerCity": self.city_var.get().strip(),
            "customerState": self.state_var.get().strip(),
            "customerZipCode": self.zip_var.get().strip(),
            "customerCountry": "US"  # Default
        }
    
    def _collect_quote_options(self):
        """Collect quote options from form."""
        self.quote_data.update({
            "quoteName": self.quote_name_var.get().strip(),
            "quoteType": self.quote_type_var.get(),
            "expirationDate": self.expiry_var.get().strip(),
            "salesPerson": self.sales_person_var.get().strip(),
            "custNotes": self.notes_var.get(),
            "quoteStatusId": 1  # Default to Draft
        })
    
    def _create_quote(self):
        """Create the quote with the API."""
        try:
            # Show wait cursor
            self.dialog.config(cursor="wait")
            self.dialog.update()
            
            # Prepare quote data
            quote_data = {
                **self.quote_data,
                "customerData": self.customer_data,
                "equipmentData": self.equipment_data,
                "dealerAccountNumber": self.config.get_setting('jd.dealer_account_number', '')
            }
            
            # Call API
            result = self.quote_client.create_quote(quote_data)
            
            # Process result
            if "body" in result and "quoteID" in result["body"]:
                quote_id = result["body"]["quoteID"]
                messagebox.showinfo("Success", f"Quote created successfully!\nQuote ID: {quote_id}")
                
                # Close dialog
                self.dialog.destroy()
                
                # Call completion callback if provided
                if self.on_complete:
                    self.on_complete(quote_id)
            else:
                messagebox.showerror("Error", "Failed to create quote - invalid response from API")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create quote: {str(e)}")
        finally:
            # Restore cursor
            self.dialog.config(cursor="")
    
    def _load_equipment_list(self):
        """Load equipment data into the list."""
        # Clear list
        for item in self.equipment_tree.get_children():
            self.equipment_tree.delete(item)
            
        # Add equipment items
        for equipment in self.equipment_data:
            # Format price
            try:
                price = float(equipment.get('listPrice', 0))
                price_str = f"${price:,.2f}"
            except:
                price_str = f"${equipment.get('listPrice', 0)}"
                
            self.equipment_tree.insert("", tk.END, values=(
                equipment.get('dealerSpecifiedModel', ''),
                equipment.get('description', ''),
                equipment.get('quantity', 1),
                price_str
            ))
    
    def _add_equipment(self):
        """Show dialog to add equipment."""
        # Create equipment dialog
        dialog = tk.Toplevel(self.dialog)
        dialog.title("Add Equipment")
        dialog.geometry("400x300")
        dialog.transient(self.dialog)
        dialog.grab_set()
        
        # Create form
        form = ttk.Frame(dialog, padding=10)
        form.pack(fill=tk.BOTH, expand=True)
        
        # Model
        ttk.Label(form, text="Model:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        model_var = tk.StringVar()
        model_entry = ttk.Entry(form, textvariable=model_var, width=30)
        model_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(model_entry, "Model name/number (required)")
        
        # Description
        ttk.Label(form, text="Description:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        desc_var = tk.StringVar()
        desc_entry = ttk.Entry(form, textvariable=desc_var, width=30)
        desc_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(desc_entry, "Brief description of equipment")
        
        # Quantity
        ttk.Label(form, text="Quantity:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        qty_var = tk.StringVar(value="1")
        qty_spin = ttk.Spinbox(form, from_=1, to=100, textvariable=qty_var, width=5)
        qty_spin.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(qty_spin, "Number of units")
        
        # Price
        ttk.Label(form, text="Price:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        price_var = tk.StringVar(value="0.00")
        price_entry = ttk.Entry(form, textvariable=price_var, width=15)
        price_entry.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        ToolTip(price_entry, "Price per unit")
        
        # Buttons
        button_frame = ttk.Frame(form)
        button_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=10)
        
        # Function to add equipment
        def add_equipment():
            # Validate inputs
            if not model_var.get().strip():
                messagebox.showwarning("Validation Error", "Model is required")
                return
                
            try:
                quantity = int(qty_var.get())
                if quantity <= 0:
                    messagebox.showwarning("Validation Error", "Quantity must be greater than zero")
                    return
            except ValueError:
                messagebox.showwarning("Validation Error", "Quantity must be a valid number")
                return
                
            try:
                price = float(price_var.get().replace(',', ''))
                if price < 0:
                    messagebox.showwarning("Validation Error", "Price cannot be negative")
                    return
            except ValueError:
                messagebox.showwarning("Validation Error", "Price must be a valid number")
                return
                
            # Create equipment data
            equipment = {
                "dealerSpecifiedModel": model_var.get().strip(),
                "description": desc_var.get().strip(),
                "quantity": quantity,
                "listPrice": price,
                "makeID": 1,  # Default to John Deere
                "includeInRecapProposal": True
            }
            
            # Add to equipment data
            self.equipment_data.append(equipment)
            
            # Reload equipment list
            self._load_equipment_list()
            
            # Close dialog
            dialog.destroy()
        
        ttk.Button(button_frame, text="Add", command=add_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def _edit_equipment(self):
        """Edit the selected equipment."""
        # Get selected equipment
        selection = self.equipment_tree.selection()
        if not selection:
            messagebox.showinfo("Information", "Please select an equipment item to edit")
            return
            
        # Get index of selected equipment
        index = self.equipment_tree.index(selection[0])
        if index >= len(self.equipment_data):
            messagebox.showerror("Error", "Selected equipment not found in data")
            return
            
        equipment = self.equipment_data[index]
        
        # Create equipment dialog
        dialog = tk.Toplevel(self.dialog)
        dialog.title("Edit Equipment")
        dialog.geometry("400x300")
        dialog.transient(self.dialog)
        dialog.grab_set()
        
        # Create form
        form = ttk.Frame(dialog, padding=10)
        form.pack(fill=tk.BOTH, expand=True)
        
        # Model
        ttk.Label(form, text="Model:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        model_var = tk.StringVar(value=equipment.get("dealerSpecifiedModel", ""))
        ttk.Entry(form, textvariable=model_var, width=30).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Description
        ttk.Label(form, text="Description:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        desc_var = tk.StringVar(value=equipment.get("description", ""))
        ttk.Entry(form, textvariable=desc_var, width=30).grid(
            row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Quantity
        ttk.Label(form, text="Quantity:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        qty_var = tk.StringVar(value=str(equipment.get("quantity", 1)))
        ttk.Spinbox(form, from_=1, to=100, textvariable=qty_var, width=5).grid(
            row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Price
        ttk.Label(form, text="Price:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        price_var = tk.StringVar(value=str(equipment.get("listPrice", 0)))
        ttk.Entry(form, textvariable=price_var, width=15).grid(
            row=3, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(form)
        button_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=10)
        
        # Function to save equipment
        def save_equipment():
            # Validate inputs
            if not model_var.get().strip():
                messagebox.showwarning("Validation Error", "Model is required")
                return
                
            try:
                quantity = int(qty_var.get())
                if quantity <= 0:
                    messagebox.showwarning("Validation Error", "Quantity must be greater than zero")
                    return
            except ValueError:
                messagebox.showwarning("Validation Error", "Quantity must be a valid number")
                return
                
            try:
                price = float(price_var.get().replace(',', ''))
                if price < 0:
                    messagebox.showwarning("Validation Error", "Price cannot be negative")
                    return
            except ValueError:
                messagebox.showwarning("Validation Error", "Price must be a valid number")
                return
                
            # Update equipment data
            equipment["dealerSpecifiedModel"] = model_var.get().strip()
            equipment["description"] = desc_var.get().strip()
            equipment["quantity"] = quantity
            equipment["listPrice"] = price
            
            # Reload equipment list
            self._load_equipment_list()
            
            # Close dialog
            dialog.destroy()
        
        ttk.Button(button_frame, text="Save", command=save_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def _remove_equipment(self):
        """Remove the selected equipment."""
        # Get selected equipment
        selection = self.equipment_tree.selection()
        if not selection:
            messagebox.showinfo("Information", "Please select an equipment item to remove")
            return
            
        # Confirm removal
        if not messagebox.askyesno("Confirm", "Are you sure you want to remove this equipment?"):
            return
            
        # Get index of selected equipment
        index = self.equipment_tree.index(selection[0])
        if index >= len(self.equipment_data):
            messagebox.showerror("Error", "Selected equipment not found in data")
            return
            
        # Remove equipment
        del self.equipment_data[index]
        
        # Reload equipment list
        self._load_equipment_list()
    
    def _on_close(self):
        """Handle dialog close."""
        if messagebox.askyesno("Confirm", "Are you sure you want to cancel quote creation?"):
            self.dialog.destroy()

# Main application class - with better debugging
class JDQuoteApp:
    """JD Quote Application with improved debugging."""
    
    def __init__(self, root, config):
        """Initialize the application."""
        logger.info("Initializing JDQuoteApp")
        self.root = root
        self.config = config
        
        # Set window properties
        self.root.title("John Deere Quote Manager (Enhanced)")
        self.root.geometry("1000x700")
        
        # Debug: print all configuration info
        logger.debug("Current configuration:")
        for key in ['jd_client_id', 'jd.dealer_account_number', 'jd.dealer_id']:
            logger.debug(f" - {key}: {self.config.get_setting(key, 'Not set')}")
        # Don't log the secret
        logger.debug(f" - jd_client_secret: {'[SET]' if self.config.get_setting('jd_client_secret') else 'Not set'}")
        
        # Set up API clients with real implementation
        self._setup_api_clients()
        
        # Set up the UI
        self._setup_ui()
        
        # Add tooltips
        self._add_tooltips()
        
        logger.info("JDQuoteApp initialization complete")
    
    def _setup_api_clients(self):
        """Set up API clients for JD APIs."""
        # Get credentials from config with explicit logging
        client_id = self.config.get_setting('jd_client_id', '')
        client_secret = self.config.get_setting('jd_client_secret', '')
        
        logger.info(f"Setting up API clients with JD credentials: {bool(client_id)} / {bool(client_secret)}")
        if not client_id:
            logger.warning("Client ID is not set")
        if not client_secret:
            logger.warning("Client Secret is not set")
        
        # Get token cache path
        # We'll store it in a directory that makes sense for the application
        app_data_dir = os.path.join(os.path.expanduser("~"), ".jd_quote_app")
        os.makedirs(app_data_dir, exist_ok=True)
        token_cache_path = os.path.join(app_data_dir, "token_cache.json")
        logger.debug(f"Token cache path: {token_cache_path}")
        
        # Create OAuth client
        self.oauth_client = JDOAuthClient(client_id, client_secret, token_cache_path=token_cache_path)
        
        # Create Maintain Quote client
        base_url = self.config.get_setting('jd.quote_api_base_url', 
                                          "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote")
        logger.debug(f"Using API base URL: {base_url}")
        self.quote_client = MaintainQuoteClient(self.oauth_client, base_url)
    
    def _setup_ui(self):
        """Set up the user interface."""
        logger.debug("Setting up UI")
        
        # Create frame for the main content
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.settings_tab = ttk.Frame(self.notebook)  # Put settings first for initial setup
        self.create_tab = ttk.Frame(self.notebook)
        self.search_tab = ttk.Frame(self.notebook)
        self.edit_tab = ttk.Frame(self.notebook)  # New tab for editing quotes
        
        self.notebook.add(self.settings_tab, text="JD Settings")  # Make settings the first tab
        self.notebook.add(self.create_tab, text="Create Quote")
        self.notebook.add(self.search_tab, text="Search Quotes")
        self.notebook.add(self.edit_tab, text="Edit Quote")  # Add the new tab
        
        # Set up each tab
        self._setup_settings_tab()  # Do settings first
        self._setup_create_tab()
        self._setup_search_tab()
        self._setup_edit_quote_tab()  # Setup the new tab
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Add progress bar for long operations
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, 
                                          length=100, mode='indeterminate',
                                          variable=self.progress_var)
        self.progress_bar.pack(side=tk.BOTTOM, fill=tk.X, before=self.status_bar)
        self.progress_bar.pack_forget()  # Hide initially
        
        logger.debug("UI setup complete")
        
        # Suggest setting up credentials if not set
        if not self.config.get_setting('jd_client_id') or not self.config.get_setting('jd_client_secret'):
            self.status_var.set("Please enter your John Deere API credentials in the Settings tab")
            messagebox.showinfo("Setup Required", "Please enter your John Deere API credentials in the Settings tab")
    
    def _add_tooltips(self):
        """Add tooltips to form fields."""
        # Create tabs tooltips
        tooltips = {
            'settings_tab': "Configure API settings and credentials",
            'create_tab': "Create a new quote",
            'search_tab': "Search and view existing quotes",
            'edit_tab': "Edit an existing quote"
        }
        
        # Find each tab and add tooltip
        for tab_id, tab in [('settings_tab', self.settings_tab), 
                           ('create_tab', self.create_tab), 
                           ('search_tab', self.search_tab), 
                           ('edit_tab', self.edit_tab)]:
            ToolTip(tab, tooltips[tab_id])
    
    def _setup_create_tab(self):
        """Set up the Create Quote tab."""
        # Main frame
        frame = ttk.Frame(self.create_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(frame, text="Create a New John Deere Quote", font=("", 14, "bold")).grid(
            row=0, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        # New Wizard button
        ttk.Button(frame, text="Launch Quote Creation Wizard", 
                  command=self._launch_quote_wizard).grid(
            row=1, column=0, columnspan=2, pady=20, padx=20, sticky=tk.NSEW)
        
        # Create basic quote form
        ttk.Label(frame, text="Quick quote creation form:", font=("", 10, "bold")).grid(
            row=2, column=0, columnspan=2, pady=(20,10), sticky=tk.W)
        
        # Quote information section
        quote_frame = ttk.LabelFrame(frame, text="Quote Information")
        quote_frame.grid(row=3, column=0, padx=5, pady=5, sticky=tk.NSEW)
        
        # Quote Name
        ttk.Label(quote_frame, text="Quote Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.quote_name_var = tk.StringVar()
        self.quote_name_var_entry = ttk.Entry(quote_frame, textvariable=self.quote_name_var, width=30)
        self.quote_name_var_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Quote Type
        ttk.Label(quote_frame, text="Quote Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.quote_type_var = tk.StringVar()
        self.quote_type_combo = ttk.Combobox(quote_frame, textvariable=self.quote_type_var, 
                    values=["Purchase", "Lease", "Rental", "Service"], width=15)
        self.quote_type_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Dealer Account Number
        ttk.Label(quote_frame, text="Dealer Account #:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        dealer_account = self.config.get_setting('jd.dealer_account_number', '')
        self.dealer_account_var = tk.StringVar(value=dealer_account)
        self.dealer_account_entry = ttk.Entry(quote_frame, textvariable=self.dealer_account_var, width=10)
        self.dealer_account_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Customer information section
        customer_frame = ttk.LabelFrame(frame, text="Customer Information")
        customer_frame.grid(row=3, column=1, padx=5, pady=5, sticky=tk.NSEW)
        
        # Customer First Name
        ttk.Label(customer_frame, text="First Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.first_name_var = tk.StringVar()
        self.first_name_entry = ttk.Entry(customer_frame, textvariable=self.first_name_var, width=20)
        self.first_name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Customer Last Name
        ttk.Label(customer_frame, text="Last Name:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.last_name_var = tk.StringVar()
        self.last_name_entry = ttk.Entry(customer_frame, textvariable=self.last_name_var, width=20)
        self.last_name_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Business Name
        ttk.Label(customer_frame, text="Business Name:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.business_name_var = tk.StringVar()
        self.business_name_entry = ttk.Entry(customer_frame, textvariable=self.business_name_var, width=30)
        self.business_name_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Equipment section (simplified)
        equipment_frame = ttk.LabelFrame(frame, text="Equipment Information")
        equipment_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky=tk.NSEW)
        
        # Model Name
        ttk.Label(equipment_frame, text="Model Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_name_var = tk.StringVar()
        self.model_name_entry = ttk.Entry(equipment_frame, textvariable=self.model_name_var, width=20)
        self.model_name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Description
        ttk.Label(equipment_frame, text="Description:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.description_var = tk.StringVar()
        self.description_entry = ttk.Entry(equipment_frame, textvariable=self.description_var, width=30)
        self.description_entry.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Quantity
        ttk.Label(equipment_frame, text="Quantity:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.quantity_var = tk.StringVar(value="1")
        self.quantity_spinbox = ttk.Spinbox(equipment_frame, from_=1, to=100, textvariable=self.quantity_var, width=5)
        self.quantity_spinbox.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Price
        ttk.Label(equipment_frame, text="Price:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.price_var = tk.StringVar(value="0.00")
        self.price_entry = ttk.Entry(equipment_frame, textvariable=self.price_var, width=10)
        self.price_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Actions section
        actions_frame = ttk.Frame(frame)
        actions_frame.grid(row=5, column=0, columnspan=2, padx=5, pady=15, sticky=tk.E)
        
        # Create Quote Button
        ttk.Button(actions_frame, text="Create Quote", command=self._create_quote).pack(side=tk.RIGHT, padx=5)
        
        # Clear Form Button
        ttk.Button(actions_frame, text="Clear Form", command=self._clear_create_form).pack(side=tk.RIGHT, padx=5)
        
        # Configure grid weights for resizing
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)
        
        # Add tooltips
        ToolTip(self.quote_name_var_entry, "Name of the quote for identification")
        ToolTip(self.quote_type_combo, "Type of quote (Purchase, Lease, Rental, Service)")
        ToolTip(self.dealer_account_entry, "Your John Deere dealer account number")
        ToolTip(self.first_name_entry, "Customer's first name")
        ToolTip(self.last_name_entry, "Customer's last name")
        ToolTip(self.business_name_entry, "Customer's business name (if applicable)")
        ToolTip(self.model_name_entry, "Model name or number of the equipment")
        ToolTip(self.description_entry, "Description of the equipment")
        ToolTip(self.quantity_spinbox, "Number of units")
        ToolTip(self.price_entry, "Price per unit")
    
    def _launch_quote_wizard(self):
        """Launch the quote creation wizard."""
        CreateQuoteWizard(
            parent=self.root,
            quote_client=self.quote_client,
            config=self.config,
            on_complete=self._on_quote_created
        )
    
    def _on_quote_created(self, quote_id):
        """Handle completion of quote creation."""
        self.status_var.set(f"Created quote {quote_id}")
        
        # Ask if user wants to view the quote
        if messagebox.askyesno("Quote Created", 
                              f"Quote {quote_id} created successfully!\n\nDo you want to search for this quote?"):
            # Switch to search tab
            self.notebook.select(self.search_tab)
            
            # Set search criteria to find the new quote
            self.search_quote_id_var.set(quote_id)
            
            # Search for the quote
            self._search_quotes()
    
    def _setup_search_tab(self):
        """Set up the Search Quotes tab."""
        # Main frame
        frame = ttk.Frame(self.search_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(frame, text="Search John Deere Quotes", font=("", 14, "bold")).grid(
            row=0, column=0, columnspan=3, pady=10, sticky=tk.W)
        
        # Search criteria section
        search_frame = ttk.LabelFrame(frame, text="Search Criteria")
        search_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky=tk.EW)
        
        # Create a grid for search fields (2 columns)
        # Column 1
        ttk.Label(search_frame, text="Quote ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.search_quote_id_var = tk.StringVar()
        self.search_quote_id_entry = ttk.Entry(search_frame, textvariable=self.search_quote_id_var, width=15)
        self.search_quote_id_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.search_quote_id_entry, "Enter specific quote ID to find")
        
        ttk.Label(search_frame, text="Quote Name:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.search_quote_name_var = tk.StringVar()
        self.search_quote_name_entry = ttk.Entry(search_frame, textvariable=self.search_quote_name_var, width=25)
        self.search_quote_name_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.search_quote_name_entry, "Search by quote name")
        
        ttk.Label(search_frame, text="Quote Type:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.search_quote_type_var = tk.StringVar()
        self.search_quote_type_combo = ttk.Combobox(search_frame, textvariable=self.search_quote_type_var, 
                   values=["", "Purchase", "Lease", "Rental", "Service"], width=15)
        self.search_quote_type_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.search_quote_type_combo, "Filter by quote type")
        
        # Column 2
        ttk.Label(search_frame, text="Customer Name:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.search_customer_name_var = tk.StringVar()
        self.search_customer_name_entry = ttk.Entry(search_frame, textvariable=self.search_customer_name_var, width=25)
        self.search_customer_name_entry.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.search_customer_name_entry, "Search by customer name")
        
        ttk.Label(search_frame, text="Business Name:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.search_business_name_var = tk.StringVar()
        self.search_business_name_entry = ttk.Entry(search_frame, textvariable=self.search_business_name_var, width=25)
        self.search_business_name_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.search_business_name_entry, "Search by business name")
        
        # Date range
        date_range_frame = ttk.Frame(search_frame)
        date_range_frame.grid(row=2, column=2, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(date_range_frame, text="Date Range:").pack(side=tk.LEFT, padx=2)
        
        self.search_date_from_var = tk.StringVar()
        self.search_date_from_entry = ttk.Entry(date_range_frame, textvariable=self.search_date_from_var, width=10)
        self.search_date_from_entry.pack(side=tk.LEFT, padx=2)
        ToolTip(self.search_date_from_entry, "Start date (YYYY-MM-DD)")
        
        ttk.Label(date_range_frame, text="to").pack(side=tk.LEFT, padx=2)
        
        self.search_date_to_var = tk.StringVar()
        self.search_date_to_entry = ttk.Entry(date_range_frame, textvariable=self.search_date_to_var, width=10)
        self.search_date_to_entry.pack(side=tk.LEFT, padx=2)
        ToolTip(self.search_date_to_entry, "End date (YYYY-MM-DD)")
        
        # Today button (sets date range to today)
        self.today_button = ttk.Button(date_range_frame, text="Today", command=self._set_today_date_range, width=6)
        self.today_button.pack(side=tk.LEFT, padx=10)
        ToolTip(self.today_button, "Set date range to today")
        
        # Search and Clear buttons
        button_frame = ttk.Frame(search_frame)
        button_frame.grid(row=3, column=0, columnspan=4, sticky=tk.E, padx=5, pady=10)
        
        self.search_button = ttk.Button(button_frame, text="Search", command=self._search_quotes)
        self.search_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.search_button, "Search for quotes matching criteria")
        
        self.clear_search_button = ttk.Button(button_frame, text="Clear", command=self._clear_search_form)
        self.clear_search_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.clear_search_button, "Clear search form")
        
        # Results area
        # First create a frame for the results table (top)
        results_table_frame = ttk.LabelFrame(frame, text="Search Results")
        results_table_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky=tk.NSEW)
        
        # Create the treeview for search results
        columns = ("Quote ID", "Date", "Quote Name", "Type", "Customer", "Business", "Amount")
        self.results_tree = ttk.Treeview(results_table_frame, columns=columns, show="headings", height=8)
        
        # Configure the columns
        self.results_tree.column("Quote ID", width=70, anchor=tk.W)
        self.results_tree.column("Date", width=90, anchor=tk.W)
        self.results_tree.column("Quote Name", width=150, anchor=tk.W)
        self.results_tree.column("Type", width=80, anchor=tk.W)
        self.results_tree.column("Customer", width=120, anchor=tk.W)
        self.results_tree.column("Business", width=150, anchor=tk.W)
        self.results_tree.column("Amount", width=90, anchor=tk.E)
        
        # Set column headings
        for col in columns:
            self.results_tree.heading(col, text=col)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(results_table_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=y_scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add binding for selection
        self.results_tree.bind("<<TreeviewSelect>>", self._on_result_select)
        
        # Then create a frame for the details pane (bottom)
        details_frame = ttk.LabelFrame(frame, text="Quote Details")
        details_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky=tk.NSEW)
        
        # Split the details area into text (left) and actions (right)
        details_content_frame = ttk.Frame(details_frame)
        details_content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        details_actions_frame = ttk.Frame(details_frame)
        details_actions_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        # Quote details text widget
        self.details_text = scrolledtext.ScrolledText(details_content_frame, wrap=tk.WORD, width=80, height=10)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        
        # Add action buttons for the selected quote
        ttk.Label(details_actions_frame, text="Actions:").pack(anchor=tk.W, pady=5)
        
        self.view_proposal_button = ttk.Button(details_actions_frame, text="View Proposal PDF", 
                  command=lambda: self._get_pdf("proposal"))
        self.view_proposal_button.pack(fill=tk.X, pady=2)
        ToolTip(self.view_proposal_button, "View and save the proposal PDF")
        
        self.view_order_button = ttk.Button(details_actions_frame, text="View Order Form PDF", 
                  command=lambda: self._get_pdf("orderform"))
        self.view_order_button.pack(fill=tk.X, pady=2)
        ToolTip(self.view_order_button, "View and save the order form PDF")
        
        self.view_recap_button = ttk.Button(details_actions_frame, text="View Recap PDF", 
                  command=lambda: self._get_pdf("recap"))
        self.view_recap_button.pack(fill=tk.X, pady=2)
        ToolTip(self.view_recap_button, "View and save the recap PDF")
        
        self.delete_quote_button = ttk.Button(details_actions_frame, text="Delete Quote", 
                  command=self._delete_selected_quote)
        self.delete_quote_button.pack(fill=tk.X, pady=2)
        ToolTip(self.delete_quote_button, "Delete the selected quote")
        
        # Configure grid weights for resizing
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)  # Results table gets more space
        frame.rowconfigure(3, weight=2)  # Details pane gets even more space
    
    def _setup_settings_tab(self):
        """Set up the Settings tab."""
        # Main frame
        frame = ttk.Frame(self.settings_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(frame, text="John Deere API Settings", font=("", 14, "bold")).grid(
            row=0, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(frame, text="API Credentials")
        settings_frame.grid(row=1, column=0, padx=5, pady=5, sticky=tk.NSEW)
        
        # Client ID
        ttk.Label(settings_frame, text="Client ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.client_id_var = tk.StringVar(value=self.config.get_setting('jd_client_id', ''))
        self.client_id_entry = ttk.Entry(settings_frame, textvariable=self.client_id_var, width=40)
        self.client_id_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.client_id_entry, "Your John Deere API client ID")
        
        # Client Secret
        ttk.Label(settings_frame, text="Client Secret:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.client_secret_var = tk.StringVar(value=self.config.get_setting('jd_client_secret', ''))
        self.client_secret_entry = ttk.Entry(settings_frame, textvariable=self.client_secret_var, width=40, show="•")
        self.client_secret_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.client_secret_entry, "Your John Deere API client secret")
        
        # API URL
        ttk.Label(settings_frame, text="API URL:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        api_url = self.config.get_setting('jd.quote_api_base_url', 
                                         "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote")
        self.api_url_var = tk.StringVar(value=api_url)
        self.api_url_entry = ttk.Entry(settings_frame, textvariable=self.api_url_var, width=60)
        self.api_url_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.api_url_entry, "John Deere API endpoint URL")
        
        # Dealer Account
        ttk.Label(settings_frame, text="Dealer Account #:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        dealer_account = self.config.get_setting('jd.dealer_account_number', '')
        self.settings_dealer_account_var = tk.StringVar(value=dealer_account)
        self.settings_dealer_account_entry = ttk.Entry(settings_frame, textvariable=self.settings_dealer_account_var, width=10)
        self.settings_dealer_account_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.settings_dealer_account_entry, "Your dealer account number")
        
        # Dealer ID (RACF ID)
        ttk.Label(settings_frame, text="Dealer ID (RACF):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        dealer_id = self.config.get_setting('jd.dealer_id', '')
        self.settings_dealer_id_var = tk.StringVar(value=dealer_id)
        self.settings_dealer_id_entry = ttk.Entry(settings_frame, textvariable=self.settings_dealer_id_var, width=10)
        self.settings_dealer_id_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.settings_dealer_id_entry, "Your dealer RACF ID")
        
        # Environment selection
        ttk.Label(settings_frame, text="Environment:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        environment_frame = ttk.Frame(settings_frame)
        environment_frame.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.environment_var = tk.StringVar(value="sandbox")
        self.sandbox_radio = ttk.Radiobutton(environment_frame, text="Sandbox", variable=self.environment_var, 
                       value="sandbox")
        self.sandbox_radio.pack(side=tk.LEFT, padx=5)
        ToolTip(self.sandbox_radio, "Use sandbox environment for testing")
        
        self.production_radio = ttk.Radiobutton(environment_frame, text="Production", variable=self.environment_var,
                       value="production")
        self.production_radio.pack(side=tk.LEFT, padx=5)
        ToolTip(self.production_radio, "Use production environment")
        
        # Actions frame
        actions_frame = ttk.Frame(frame)
        actions_frame.grid(row=2, column=0, padx=5, pady=10, sticky=tk.E)
        
        # Save Settings Button
        self.save_settings_button = ttk.Button(actions_frame, text="Save Settings", command=self._save_settings)
        self.save_settings_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.save_settings_button, "Save settings to config file")
        
        # Test Connection Button
        self.test_connection_button = ttk.Button(actions_frame, text="Test Connection", command=self._test_connection)
        self.test_connection_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.test_connection_button, "Test API connection")
        
        # Config File Button (new)
        self.show_config_button = ttk.Button(actions_frame, text="Show Config File", command=self._show_config_file)
        self.show_config_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.show_config_button, "Show config file location and contents")
        
        # Help section
        help_frame = ttk.LabelFrame(frame, text="Connection Status")
        help_frame.grid(row=1, column=1, rowspan=2, padx=5, pady=5, sticky=tk.NSEW)
        
        self.connection_text = scrolledtext.ScrolledText(help_frame, wrap=tk.WORD, width=40, height=15)
        self.connection_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Show connection info
        self.connection_text.insert(tk.END, "John Deere API Integration\n\n", "header")
        self.connection_text.insert(tk.END, "Status: ")
        
        # Check if we have credentials
        if self.client_id_var.get() and self.client_secret_var.get():
            self.connection_text.insert(tk.END, "Credentials configured\n\n", "green")
        else:
            self.connection_text.insert(tk.END, "Credentials missing\n\n", "red")
        
        self.connection_text.insert(tk.END, "Environment: ")
        self.connection_text.insert(tk.END, "Sandbox\n\n")
        
        # Show config file location
        self.connection_text.insert(tk.END, f"Config file: {os.path.abspath(self.config.config_file)}\n\n")
        
        # Show help text
        self.connection_text.insert(tk.END, """
To use this module, you'll need:
1. John Deere Developer account
2. Client ID and Client Secret
3. Dealer Account Number

The API uses OAuth 2.0 authentication to securely access quote data. 

After entering your credentials, click "Save Settings" and then "Test Connection" to verify.

For assistance, contact the BRI support team.
        """)
        
        # Configure text tags
        self.connection_text.tag_configure("header", font=("", 10, "bold"))
        self.connection_text.tag_configure("green", foreground="green")
        self.connection_text.tag_configure("red", foreground="red")
        
        # Make connection text read-only
        self.connection_text.config(state=tk.DISABLED)
        
        # Configure grid weights for resizing
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=2)
        frame.rowconfigure(1, weight=1)
    
    def _setup_edit_quote_tab(self):
        """Set up the Edit Quote tab."""
        # Main frame
        frame = ttk.Frame(self.edit_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(frame, text="Edit John Deere Quote", font=("", 14, "bold")).grid(
            row=0, column=0, columnspan=3, pady=10, sticky=tk.W)
        
        # Quote selection section
        select_frame = ttk.LabelFrame(frame, text="Select Quote to Edit")
        select_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky=tk.EW)
        
        # Quote ID
        ttk.Label(select_frame, text="Quote ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_quote_id_var = tk.StringVar()
        self.edit_quote_id_entry = ttk.Entry(select_frame, textvariable=self.edit_quote_id_var, width=15)
        self.edit_quote_id_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_quote_id_entry, "Enter Quote ID to edit")
        
        # Load button
        self.load_quote_button = ttk.Button(select_frame, text="Load Quote", command=self._load_quote_for_edit)
        self.load_quote_button.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.load_quote_button, "Load quote for editing")
        
        # Create a notebook for quote details
        self.edit_notebook = ttk.Notebook(frame)
        self.edit_notebook.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky=tk.NSEW)
        
        # Create tabs for different parts of the quote
        self.edit_info_tab = ttk.Frame(self.edit_notebook)
        self.edit_customer_tab = ttk.Frame(self.edit_notebook)
        self.edit_equipment_tab = ttk.Frame(self.edit_notebook)
        self.edit_tradein_tab = ttk.Frame(self.edit_notebook)
        
        self.edit_notebook.add(self.edit_info_tab, text="Quote Info")
        self.edit_notebook.add(self.edit_customer_tab, text="Customer")
        self.edit_notebook.add(self.edit_equipment_tab, text="Equipment")
        self.edit_notebook.add(self.edit_tradein_tab, text="Trade-In")
        
        # Quote Info tab
        self._setup_edit_info_tab()
        
        # Customer tab
        self._setup_edit_customer_tab()
        
        # Equipment tab
        self._setup_edit_equipment_tab()
        
        # Trade-In tab
        self._setup_edit_tradein_tab()
        
        # Actions section
        actions_frame = ttk.Frame(frame)
        actions_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=15, sticky=tk.E)
        
        # Update Quote Button
        self.update_quote_button = ttk.Button(actions_frame, text="Update Quote", command=self._update_quote)
        self.update_quote_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.update_quote_button, "Save changes to quote")
        
        # Copy Quote Button
        self.copy_quote_button = ttk.Button(actions_frame, text="Copy Quote", command=self._copy_quote)
        self.copy_quote_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.copy_quote_button, "Create a copy of this quote")
        
        # Set Expiration Button
        self.set_expiration_button = ttk.Button(actions_frame, text="Set Expiration", command=self._set_quote_expiration)
        self.set_expiration_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.set_expiration_button, "Update quote expiration date")
        
        # Configure grid weights for resizing
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        
    def _setup_edit_info_tab(self):
        """Set up the Quote Info tab within the Edit Quote tab."""
        frame = ttk.Frame(self.edit_info_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Quote information fields
        ttk.Label(frame, text="Quote Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_quote_name_var = tk.StringVar()
        self.edit_quote_name_entry = ttk.Entry(frame, textvariable=self.edit_quote_name_var, width=30)
        self.edit_quote_name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_quote_name_entry, "Name of the quote")
        
        ttk.Label(frame, text="Quote Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_quote_type_var = tk.StringVar()
        self.edit_quote_type_combo = ttk.Combobox(frame, textvariable=self.edit_quote_type_var, 
                    values=["1", "2", "3", "4"], width=5)
        self.edit_quote_type_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(frame, text="(1: Purchase, 2: Lease, 3: Rental, 4: Service)").grid(
            row=1, column=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_quote_type_combo, "Type of quote: 1=Purchase, 2=Lease, 3=Rental, 4=Service")
        
        ttk.Label(frame, text="Sales Person:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_sales_person_var = tk.StringVar()
        self.edit_sales_person_entry = ttk.Entry(frame, textvariable=self.edit_sales_person_var, width=20)
        self.edit_sales_person_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_sales_person_entry, "Name or ID of the salesperson")
        
        ttk.Label(frame, text="Expiration Date:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_expiration_date_var = tk.StringVar()
        self.edit_expiration_date_entry = ttk.Entry(frame, textvariable=self.edit_expiration_date_var, width=15)
        self.edit_expiration_date_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(frame, text="(YYYY-MM-DD)").grid(row=3, column=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_expiration_date_entry, "Date when quote expires (format: YYYY-MM-DD)")
        
        ttk.Label(frame, text="Customer Notes:").grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        self.edit_cust_notes_var = tk.StringVar()
        self.edit_cust_notes_entry = ttk.Entry(frame, textvariable=self.edit_cust_notes_var, width=50)
        self.edit_cust_notes_entry.grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_cust_notes_entry, "Additional notes for the customer")
        
        # Quote status
        ttk.Label(frame, text="Quote Status:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_quote_status_var = tk.StringVar()
        self.edit_quote_status_combo = ttk.Combobox(frame, textvariable=self.edit_quote_status_var, 
                    values=["1", "2", "3", "4", "5"], width=5)
        self.edit_quote_status_combo.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(frame, text="(1: Draft, 2: Submitted, 3: Accepted, 4: Rejected, 5: Expired)").grid(
            row=5, column=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_quote_status_combo, "Status of the quote: 1=Draft, 2=Submitted, 3=Accepted, 4=Rejected, 5=Expired")

    def _setup_edit_customer_tab(self):
        """Set up the Customer tab within the Edit Quote tab."""
        frame = ttk.Frame(self.edit_customer_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Customer information fields
        # Column 1
        ttk.Label(frame, text="First Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_first_name_var = tk.StringVar()
        self.edit_customer_first_name_entry = ttk.Entry(frame, textvariable=self.edit_customer_first_name_var, width=20)
        self.edit_customer_first_name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_first_name_entry, "Customer's first name")
        
        ttk.Label(frame, text="Last Name:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_last_name_var = tk.StringVar()
        self.edit_customer_last_name_entry = ttk.Entry(frame, textvariable=self.edit_customer_last_name_var, width=20)
        self.edit_customer_last_name_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_last_name_entry, "Customer's last name")
        
        ttk.Label(frame, text="Business Name:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_business_name_var = tk.StringVar()
        self.edit_customer_business_name_entry = ttk.Entry(frame, textvariable=self.edit_customer_business_name_var, width=30)
        self.edit_customer_business_name_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_business_name_entry, "Customer's business name")
        
        ttk.Label(frame, text="Email:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_email_var = tk.StringVar()
        self.edit_customer_email_entry = ttk.Entry(frame, textvariable=self.edit_customer_email_var, width=30)
        self.edit_customer_email_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_email_entry, "Customer's email address")
        
        # Column 2
        ttk.Label(frame, text="Address 1:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_addr1_var = tk.StringVar()
        self.edit_customer_addr1_entry = ttk.Entry(frame, textvariable=self.edit_customer_addr1_var, width=30)
        self.edit_customer_addr1_entry.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_addr1_entry, "First line of address")
        
        ttk.Label(frame, text="Address 2:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_addr2_var = tk.StringVar()
        self.edit_customer_addr2_entry = ttk.Entry(frame, textvariable=self.edit_customer_addr2_var, width=30)
        self.edit_customer_addr2_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_addr2_entry, "Second line of address")
        
        ttk.Label(frame, text="City:").grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_city_var = tk.StringVar()
        self.edit_customer_city_entry = ttk.Entry(frame, textvariable=self.edit_customer_city_var, width=20)
        self.edit_customer_city_entry.grid(row=2, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_city_entry, "City")
        
        # Column 3
        ttk.Label(frame, text="State:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_state_var = tk.StringVar()
        self.edit_customer_state_entry = ttk.Entry(frame, textvariable=self.edit_customer_state_var, width=15)
        self.edit_customer_state_entry.grid(row=0, column=5, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_state_entry, "State or province")
        
        ttk.Label(frame, text="Zip Code:").grid(row=1, column=4, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_zip_var = tk.StringVar()
        self.edit_customer_zip_entry = ttk.Entry(frame, textvariable=self.edit_customer_zip_var, width=10)
        self.edit_customer_zip_entry.grid(row=1, column=5, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_zip_entry, "Zip/postal code")
        
        ttk.Label(frame, text="Country:").grid(row=2, column=4, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_country_var = tk.StringVar(value="US")
        self.edit_customer_country_entry = ttk.Entry(frame, textvariable=self.edit_customer_country_var, width=10)
        self.edit_customer_country_entry.grid(row=2, column=5, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_country_entry, "Two-letter country code")
        
        # Phone numbers
        ttk.Label(frame, text="Phone:").grid(row=3, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_phone_var = tk.StringVar()
        self.edit_customer_phone_entry = ttk.Entry(frame, textvariable=self.edit_customer_phone_var, width=15)
        self.edit_customer_phone_entry.grid(row=3, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_phone_entry, "Customer's phone number")
        
        ttk.Label(frame, text="Business Phone:").grid(row=3, column=4, sticky=tk.W, padx=5, pady=5)
        self.edit_customer_business_phone_var = tk.StringVar()
        self.edit_customer_business_phone_entry = ttk.Entry(frame, textvariable=self.edit_customer_business_phone_var, width=15)
        self.edit_customer_business_phone_entry.grid(row=3, column=5, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_customer_business_phone_entry, "Customer's business phone")

    def _setup_edit_equipment_tab(self):
        """Set up the Equipment tab within the Edit Quote tab."""
        frame = ttk.Frame(self.edit_equipment_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Equipment list section
        list_frame = ttk.LabelFrame(frame, text="Equipment")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create the treeview for equipment
        columns = ("ID", "Make", "Model", "Description", "Quantity", "List Price")
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=6)
        
        # Configure the columns
        self.equipment_tree.column("ID", width=70, anchor=tk.W)
        self.equipment_tree.column("Make", width=80, anchor=tk.W)
        self.equipment_tree.column("Model", width=120, anchor=tk.W)
        self.equipment_tree.column("Description", width=200, anchor=tk.W)
        self.equipment_tree.column("Quantity", width=60, anchor=tk.CENTER)
        self.equipment_tree.column("List Price", width=90, anchor=tk.E)
        
        # Set column headings
        for col in columns:
            self.equipment_tree.heading(col, text=col)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=y_scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.equipment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection event
        self.equipment_tree.bind("<<TreeviewSelect>>", self._on_equipment_select)
        
        # Equipment actions frame
        actions_frame = ttk.Frame(frame)
        actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Equipment actions
        self.add_equipment_button = ttk.Button(actions_frame, text="Add Equipment", command=self._add_equipment_dialog)
        self.add_equipment_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.add_equipment_button, "Add equipment to quote")
        
        self.edit_equipment_button = ttk.Button(actions_frame, text="Edit Selected", command=self._edit_equipment_dialog)
        self.edit_equipment_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.edit_equipment_button, "Edit selected equipment")
        
        self.remove_equipment_button = ttk.Button(actions_frame, text="Remove Selected", command=self._remove_equipment)
        self.remove_equipment_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.remove_equipment_button, "Remove selected equipment")
        
        # Equipment detail frame
        detail_frame = ttk.LabelFrame(frame, text="Equipment Details")
        detail_frame.pack(fill=tk.BOTH, padx=5, pady=5)
        
        # Detail fields - row 1
        ttk.Label(detail_frame, text="Model:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_equipment_model_var = tk.StringVar()
        self.edit_equipment_model_entry = ttk.Entry(detail_frame, textvariable=self.edit_equipment_model_var, width=20)
        self.edit_equipment_model_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_equipment_model_entry, "Equipment model name/number")
        
        ttk.Label(detail_frame, text="Make:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_equipment_make_var = tk.StringVar()
        self.edit_equipment_make_combo = ttk.Combobox(detail_frame, textvariable=self.edit_equipment_make_var, 
                    values=["1", "2", "3"], width=5)
        self.edit_equipment_make_combo.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        ttk.Label(detail_frame, text="(1: John Deere, 2: Competitor, 3: Other)").grid(
            row=0, column=4, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_equipment_make_combo, "Equipment make: 1=John Deere, 2=Competitor, 3=Other")
        
        # Detail fields - row 2
        ttk.Label(detail_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_equipment_desc_var = tk.StringVar()
        self.edit_equipment_desc_entry = ttk.Entry(detail_frame, textvariable=self.edit_equipment_desc_var, width=50)
        self.edit_equipment_desc_entry.grid(row=1, column=1, columnspan=4, sticky=tk.EW, padx=5, pady=5)
        ToolTip(self.edit_equipment_desc_entry, "Description of equipment")
        
        # Detail fields - row 3
        ttk.Label(detail_frame, text="Quantity:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_equipment_quantity_var = tk.StringVar(value="1")
        self.edit_equipment_quantity_spinbox = ttk.Spinbox(detail_frame, from_=1, to=100, textvariable=self.edit_equipment_quantity_var, width=5)
        self.edit_equipment_quantity_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_equipment_quantity_spinbox, "Number of units")
        
        ttk.Label(detail_frame, text="List Price:").grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_equipment_price_var = tk.StringVar(value="0.00")
        self.edit_equipment_price_entry = ttk.Entry(detail_frame, textvariable=self.edit_equipment_price_var, width=15)
        self.edit_equipment_price_entry.grid(row=2, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_equipment_price_entry, "Price per unit")
        
        # Detail fields - row 4
        ttk.Label(detail_frame, text="Serial Number:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_equipment_serialno_var = tk.StringVar()
        self.edit_equipment_serialno_entry = ttk.Entry(detail_frame, textvariable=self.edit_equipment_serialno_var, width=20)
        self.edit_equipment_serialno_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_equipment_serialno_entry, "Equipment serial number")
        
        ttk.Label(detail_frame, text="Stock Number:").grid(row=3, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_equipment_stockno_var = tk.StringVar()
        self.edit_equipment_stockno_entry = ttk.Entry(detail_frame, textvariable=self.edit_equipment_stockno_var, width=15)
        self.edit_equipment_stockno_entry.grid(row=3, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_equipment_stockno_entry, "Equipment stock number")
        
        # Detail fields - row 5
        ttk.Label(detail_frame, text="Year:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        current_year = datetime.now().year
        self.edit_equipment_year_var = tk.StringVar(value=str(current_year))
        self.edit_equipment_year_combo = ttk.Combobox(detail_frame, textvariable=self.edit_equipment_year_var, 
                    values=[str(y) for y in range(current_year-10, current_year+2)], width=6)
        self.edit_equipment_year_combo.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_equipment_year_combo, "Year of manufacture")
        
        ttk.Label(detail_frame, text="Include in Recap:").grid(row=4, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_equipment_include_recap_var = tk.BooleanVar(value=True)
        self.edit_equipment_include_recap_check = ttk.Checkbutton(detail_frame, variable=self.edit_equipment_include_recap_var)
        self.edit_equipment_include_recap_check.grid(row=4, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_equipment_include_recap_check, "Include this equipment in the recap")
        
        # Equipment notes
        ttk.Label(detail_frame, text="Notes:").grid(row=5, column=0, sticky=tk.NW, padx=5, pady=5)
        self.edit_equipment_notes_var = tk.StringVar()
        self.edit_equipment_notes_entry = ttk.Entry(detail_frame, textvariable=self.edit_equipment_notes_var, width=50)
        self.edit_equipment_notes_entry.grid(row=5, column=1, columnspan=4, sticky=tk.EW, padx=5, pady=5)
        ToolTip(self.edit_equipment_notes_entry, "Additional notes about this equipment")
        
        # Save equipment button
        self.save_equipment_button = ttk.Button(detail_frame, text="Save Equipment", command=self._save_equipment_details)
        self.save_equipment_button.grid(row=6, column=4, sticky=tk.E, padx=5, pady=5)
        ToolTip(self.save_equipment_button, "Save equipment details")

    def _setup_edit_tradein_tab(self):
        """Set up the Trade-In tab within the Edit Quote tab."""
        frame = ttk.Frame(self.edit_tradein_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Trade-In list section
        list_frame = ttk.LabelFrame(frame, text="Trade-In Equipment")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create the treeview for trade-ins
        columns = ("ID", "Make", "Model", "Description", "Year", "Net Value")
        self.tradein_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=6)
        
        # Configure the columns
        self.tradein_tree.column("ID", width=70, anchor=tk.W)
        self.tradein_tree.column("Make", width=80, anchor=tk.W)
        self.tradein_tree.column("Model", width=120, anchor=tk.W)
        self.tradein_tree.column("Description", width=200, anchor=tk.W)
        self.tradein_tree.column("Year", width=60, anchor=tk.CENTER)
        self.tradein_tree.column("Net Value", width=90, anchor=tk.E)
        
        # Set column headings
        for col in columns:
            self.tradein_tree.heading(col, text=col)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tradein_tree.yview)
        self.tradein_tree.configure(yscrollcommand=y_scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.tradein_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection event
        self.tradein_tree.bind("<<TreeviewSelect>>", self._on_tradein_select)
        
        # Trade-In actions frame
        actions_frame = ttk.Frame(frame)
        actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Trade-In actions
        self.add_tradein_button = ttk.Button(actions_frame, text="Add Trade-In", command=self._add_tradein_dialog)
        self.add_tradein_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.add_tradein_button, "Add trade-in equipment")
        
        self.edit_tradein_button = ttk.Button(actions_frame, text="Edit Selected", command=self._edit_tradein_dialog)
        self.edit_tradein_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.edit_tradein_button, "Edit selected trade-in")
        
        self.remove_tradein_button = ttk.Button(actions_frame, text="Remove Selected", command=self._remove_tradein)
        self.remove_tradein_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.remove_tradein_button, "Remove selected trade-in")
        
        # Trade-In detail frame
        detail_frame = ttk.LabelFrame(frame, text="Trade-In Details")
        detail_frame.pack(fill=tk.BOTH, padx=5, pady=5)
        
        # Detail fields - row 1
        ttk.Label(detail_frame, text="Make:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_tradein_make_var = tk.StringVar()
        self.edit_tradein_make_combo = ttk.Combobox(detail_frame, textvariable=self.edit_tradein_make_var, 
                    values=["1", "2", "3"], width=5)
        self.edit_tradein_make_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(detail_frame, text="(1: John Deere, 2: Competitor, 3: Other)").grid(
            row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_tradein_make_combo, "Trade-in make: 1=John Deere, 2=Competitor, 3=Other")
        
        ttk.Label(detail_frame, text="Model:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_tradein_model_var = tk.StringVar()
        self.edit_tradein_model_entry = ttk.Entry(detail_frame, textvariable=self.edit_tradein_model_var, width=20)
        self.edit_tradein_model_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_tradein_model_entry, "Trade-in model name/number")
        
        # Detail fields - row 2
        ttk.Label(detail_frame, text="Description:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_tradein_desc_var = tk.StringVar()
        self.edit_tradein_desc_entry = ttk.Entry(detail_frame, textvariable=self.edit_tradein_desc_var, width=50)
        self.edit_tradein_desc_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        ToolTip(self.edit_tradein_desc_entry, "Description of trade-in equipment")
        
        # Detail fields - row 3
        ttk.Label(detail_frame, text="Serial Number:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_tradein_serialno_var = tk.StringVar()
        self.edit_tradein_serialno_entry = ttk.Entry(detail_frame, textvariable=self.edit_tradein_serialno_var, width=20)
        self.edit_tradein_serialno_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_tradein_serialno_entry, "Trade-in serial number")
        
        # Detail fields - row 4
        ttk.Label(detail_frame, text="Year:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        current_year = datetime.now().year
        self.edit_tradein_year_var = tk.StringVar(value=str(current_year))
        self.edit_tradein_year_combo = ttk.Combobox(detail_frame, textvariable=self.edit_tradein_year_var, 
                    values=[str(y) for y in range(current_year-20, current_year+1)], width=6)
        self.edit_tradein_year_combo.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_tradein_year_combo, "Year of manufacture")
        
        # Detail fields - row 5
        ttk.Label(detail_frame, text="Hour Meter:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_tradein_hours_var = tk.StringVar(value="0")
        self.edit_tradein_hours_entry = ttk.Entry(detail_frame, textvariable=self.edit_tradein_hours_var, width=10)
        self.edit_tradein_hours_entry.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_tradein_hours_entry, "Equipment hour meter reading")
        
        # Detail fields - row 6
        ttk.Label(detail_frame, text="Net Value:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_tradein_value_var = tk.StringVar(value="0.00")
        self.edit_tradein_value_entry = ttk.Entry(detail_frame, textvariable=self.edit_tradein_value_var, width=15)
        self.edit_tradein_value_entry.grid(row=6, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_tradein_value_entry, "Net value of trade-in")
        
        ttk.Label(detail_frame, text="Include in Recap:").grid(row=6, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_tradein_include_recap_var = tk.BooleanVar(value=True)
        self.edit_tradein_include_recap_check = ttk.Checkbutton(detail_frame, variable=self.edit_tradein_include_recap_var)
        self.edit_tradein_include_recap_check.grid(row=6, column=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.edit_tradein_include_recap_check, "Include this trade-in in the recap")
        
        # Save trade-in button
        self.save_tradein_button = ttk.Button(detail_frame, text="Save Trade-In", command=self._save_tradein_details)
        self.save_tradein_button.grid(row=7, column=3, sticky=tk.E, padx=5, pady=5)
        ToolTip(self.save_tradein_button, "Save trade-in details")
    
    def _handle_api_error(self, operation, error, retry_callback=None):
        """Centralized error handler for API operations.
        
        Args:
            operation: Description of the operation that failed
            error: The exception or error message
            retry_callback: Optional callback function to retry the operation
        """
        # Log the error
        if isinstance(error, Exception):
            logger.error(f"Error during {operation}: {str(error)}")
        else:
            logger.error(f"Error during {operation}: {error}")
        
        # Hide progress if shown
        self._show_progress(False)
        
        # Create error message
        if isinstance(error, requests.exceptions.ConnectionError):
            message = "Could not connect to the server. Please check your internet connection."
        elif isinstance(error, requests.exceptions.Timeout):
            message = "The server took too long to respond. Please try again later."
        elif isinstance(error, requests.exceptions.RequestException):
            if hasattr(error, 'response') and error.response is not None:
                status_code = error.response.status_code
                if status_code == 401:
                    message = "Authentication error. Please check your credentials or re-login."
                    # Show login dialog
                    if self._show_login_dialog():
                        if retry_callback:
                            retry_callback()
                        return
                elif status_code == 403:
                    message = "You don't have permission to access this resource."
                elif status_code == 404:
                    message = "The requested resource was not found on the server."
                elif status_code >= 500:
                    message = f"Server error (HTTP {status_code}). Please try again later."
                else:
                    message = f"HTTP error: {status_code}"
            else:
                message = str(error)
        else:
            message = str(error)
        
        # Show error dialog
        messagebox.showerror("Error", f"Failed during {operation}:\n\n{message}")
        
        # Update status
        self.status_var.set(f"Error during {operation}")
    
    def _show_config_file(self):
        """Show the config file location and contents."""
        try:
            config_file = os.path.abspath(self.config.config_file)
            
            # Create a simple dialog to show config file info
            dialog = tk.Toplevel(self.root)
            dialog.title("Configuration File")
            dialog.geometry("600x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Add content
            frame = ttk.Frame(dialog, padding=10)
            frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(frame, text=f"Config File Location:", font=("", 10, "bold")).pack(anchor=tk.W)
            ttk.Label(frame, text=config_file).pack(anchor=tk.W, pady=(0, 10))
            
            ttk.Label(frame, text="Current Contents:", font=("", 10, "bold")).pack(anchor=tk.W)
            
            # Text widget for config contents
            text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=70, height=15)
            text.pack(fill=tk.BOTH, expand=True, pady=5)
            
            # Get config contents
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                    
                    # Hide secret
                    if 'jd_client_secret' in config_data:
                        config_data['jd_client_secret'] = '[HIDDEN FOR SECURITY]'
                    
                    # Format JSON
                    formatted_json = json.dumps(config_data, indent=4)
                    text.insert(tk.END, formatted_json)
                except Exception as e:
                    text.insert(tk.END, f"Error reading config file: {str(e)}")
            else:
                text.insert(tk.END, "Config file does not exist yet.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show config file: {str(e)}")

    def _show_progress(self, show=True):
        """Show or hide progress bar for long operations."""
        try:
            if show:
                self.progress_bar.pack(side=tk.BOTTOM, fill=tk.X, before=self.status_bar)  # Pack progress bar
                self.progress_bar.start(10)  # Start animation
                self.root.update_idletasks()  # Force UI update
            else:
                self.progress_bar.stop()  # Stop animation
                self.progress_bar.pack_forget()  # Hide progress bar
                self.root.update_idletasks()  # Force UI update
        except Exception as e:
            logger.error(f"Error in _show_progress: {str(e)}")
    
    def _create_quote(self):
        """Create a new quote."""
        try:
            # Validate form
            if not self._validate_create_form():
                return                    
            
            # Map quote type to API format
            quote_type_map = {"Purchase": "1", "Lease": "2", "Rental": "3", "Service": "4"}
            quote_type = quote_type_map.get(self.quote_type_var.get(), "2")  # Default to Lease
            
            # Build quote data
            quote_data = {
                "quoteName": self.quote_name_var.get(),
                "quoteType": quote_type,
                "dealerAccountNumber": self.dealer_account_var.get(),
                "customerData": {
                    "customerFirstName": self.first_name_var.get(),
                    "customerLastName": self.last_name_var.get(),
                    "customerBusinessName": self.business_name_var.get()
                },
                "equipmentData": [
                    {
                        "dealerSpecifiedModel": self.model_name_var.get(),
                        "description": self.description_var.get(),
                        "quantity": int(self.quantity_var.get()),
                        "listPrice": float(self.price_var.get().replace(',', '')),
                        "makeID": 1,  # Default to John Deere
                        "includeInRecapProposal": True
                    }
                ]
            }
            
            # Update status and show progress
            self.status_var.set("Creating quote...")
            self._show_progress(True)
            
            # Call API
            dealer_id = self.config.get_setting('jd.dealer_id', '')
            if dealer_id:
                # Use dealer-specific endpoint if we have a dealer ID
                quote_data["dealerRacfId"] = dealer_id
            
            result = self.quote_client.create_quote(quote_data)
            
            # Hide progress
            self._show_progress(False)
            
            # Process result
            if "body" in result and "quoteID" in result["body"]:
                quote_id = result["body"]["quoteID"]
                messagebox.showinfo("Success", f"Quote created successfully!\nQuote ID: {quote_id}")
                self.status_var.set(f"Created quote {quote_id}")
                self._clear_create_form()
                
                # Ask if user wants to view the quote
                if messagebox.askyesno("Quote Created", "Do you want to search for this quote?"):
                    # Switch to search tab
                    self.notebook.select(self.search_tab)
                    
                    # Set search criteria to find the new quote
                    self.search_quote_id_var.set(quote_id)
                    
                    # Search for the quote
                    self._search_quotes()
            else:
                messagebox.showerror("Error", "Failed to create quote - invalid response from API")
                self.status_var.set("Failed to create quote")
        
        except Exception as e:
            self._handle_api_error("creating quote", e, self._create_quote)
    
    def _validate_create_form(self):
        """Validate the create quote form with improved error messages."""
        errors = []
        
        # Check required fields
        if not self.quote_name_var.get().strip():
            errors.append("Quote Name is required")
        
        if not self.quote_type_var.get():
            errors.append("Quote Type is required")
        
        if not self.first_name_var.get().strip():
            errors.append("Customer First Name is required")
            
        if not self.last_name_var.get().strip():
            errors.append("Customer Last Name is required")
        
        if not self.dealer_account_var.get().strip():
            errors.append("Dealer Account Number is required")
        
        if not self.model_name_var.get().strip():
            errors.append("Equipment Model Name is required")
        
        # Validate numeric fields with proper formatting
        try:
            quantity = int(self.quantity_var.get())
            if quantity <= 0:
                errors.append("Quantity must be greater than zero")
        except ValueError:
            errors.append("Quantity must be a valid number")
        
        try:
            price = float(self.price_var.get().replace(',', ''))
            if price < 0:
                errors.append("Price cannot be negative")
        except ValueError:
            errors.append("Price must be a valid number (e.g., 1234.56)")
        
        # Show all errors if any
        if errors:
            messagebox.showwarning("Validation Errors", 
                                  "Please correct the following issues:\n\n" + 
                                  "\n".join(f"• {error}" for error in errors))
            return False
        
        return True
    
    def _clear_create_form(self):
        """Clear the create quote form."""
        self.quote_name_var.set("")
        self.quote_type_var.set("")
        self.first_name_var.set("")
        self.last_name_var.set("")
        self.business_name_var.set("")
        self.model_name_var.set("")
        self.description_var.set("")
        self.quantity_var.set("1")
        self.price_var.set("0.00")
        
        self.status_var.set("Form cleared")
    
    def _search_quotes(self):
        """Search for quotes based on criteria."""
        try:
            # Build search criteria
            search_criteria = {}
            
            if self.search_quote_id_var.get():
                search_criteria["quoteId"] = self.search_quote_id_var.get()
            
            if self.search_quote_name_var.get():
                search_criteria["quoteName"] = self.search_quote_name_var.get()
            
            if self.search_quote_type_var.get():
                # Map friendly names to API values
                quote_type_map = {"Purchase": "1", "Lease": "2", "Rental": "3", "Service": "4"}
                search_criteria["quoteType"] = quote_type_map.get(self.search_quote_type_var.get(), 
                                                                self.search_quote_type_var.get())
            
            if self.search_customer_name_var.get():
                search_criteria["customerName"] = self.search_customer_name_var.get()
            
            if self.search_business_name_var.get():
                search_criteria["businessName"] = self.search_business_name_var.get()
            
            if self.search_date_from_var.get() or self.search_date_to_var.get():
                date_range = {}
                if self.search_date_from_var.get():
                    date_range["from"] = self.search_date_from_var.get()
                if self.search_date_to_var.get():
                    date_range["to"] = self.search_date_to_var.get()
                search_criteria["dateRange"] = date_range
            
            # Add account number if available
            dealer_account = self.config.get_setting('jd.dealer_account_number', '')
            if dealer_account:
                search_criteria["dealerAccountNumber"] = dealer_account
            
            # Update status and show progress
            self.status_var.set("Searching quotes...")
            self._show_progress(True)
            
            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Call API
            result = self.quote_client.search_quotes(search_criteria)
            
            # Hide progress
            self._show_progress(False)
            
            # Process results
            quotes = []
            if "body" in result:
                if isinstance(result["body"], dict) and "quotes" in result["body"]:
                    quotes = result["body"]["quotes"]
                elif isinstance(result["body"], list):
                    quotes = result["body"]
                else:
                    quotes = []

                for quote in quotes:
                    normalized_quote = self._normalize_quote_data(quote)

                    # Format customer name
                    customer_name = f"{normalized_quote.get('customerFirstName', '')} {normalized_quote.get('customerLastName', '')}"

                    amount_str = normalized_quote.get('totalAmount', '0')
                    try:
                        amount = float(amount_str)
                        amount_formatted = f"${amount:,.2f}"
                    except (ValueError, TypeError):
                        amount_formatted = amount_str

                    self.results_tree.insert("", tk.END, values=(
                        normalized_quote.get("quoteId", ""),
                        normalized_quote.get("quoteDate", ""),
                        normalized_quote.get("quoteName", ""),
                        normalized_quote.get("quoteType", ""),
                        customer_name.strip(),
                        normalized_quote.get("customerBusinessName", ""),
                        amount_formatted
                    ))

                count = len(quotes)
                self.status_var.set(f"Found {count} quote{'s' if count != 1 else ''}")

                if count == 1:
                    item = self.results_tree.get_children()[0]
                    self.results_tree.selection_set(item)
                    self.results_tree.focus(item)
                    self._on_result_select(None)

            if not quotes:
                self.status_var.set("No quotes found matching your criteria")
        
        except Exception as e:
            self._handle_api_error("searching quotes", e, self._search_quotes)
    
    def _normalize_quote_data(self, quote):
        """Normalize quote data to handle different API formats."""
        normalized = {}
        
        # Map fields with different names
        field_mapping = {
            "quoteID": "quoteId",
            "quoteId": "quoteId",
            "quoteName": "quoteName",
            "quoteType": "quoteType",
            "quoteDate": "quoteDate",
            "creationDate": "quoteDate",  # Alternative name
            "customerFirstName": "customerFirstName",
            "customerLastName": "customerLastName",
            "customerBusinessName": "customerBusinessName",
            "totalQuoteAmount": "totalAmount",
            "totalAmount": "totalAmount"
        }
        
        # Copy fields with normalization
        for api_field, app_field in field_mapping.items():
            if api_field in quote:
                normalized[app_field] = quote[api_field]
        
        # Handle nested customer data if present
        if "customerData" in quote and isinstance(quote["customerData"], dict):
            customer_data = quote["customerData"]
            for customer_field in ["customerFirstName", "customerLastName", "customerBusinessName"]:
                if customer_field in customer_data:
                    normalized[customer_field] = customer_data[customer_field]
        
        # Map quote types to friendly names if applicable
        if "quoteType" in normalized:
            quote_type = normalized["quoteType"]
            if quote_type == "1" or quote_type == 1:
                normalized["quoteType"] = "Purchase"
            elif quote_type == "2" or quote_type == 2:
                normalized["quoteType"] = "Lease"
            elif quote_type == "3" or quote_type == 3:
                normalized["quoteType"] = "Rental"
            elif quote_type == "4" or quote_type == 4:
                normalized["quoteType"] = "Service"
        
        return normalized
    
    def _clear_search_form(self):
        """Clear the search form."""
        self.search_quote_id_var.set("")
        self.search_quote_name_var.set("")
        self.search_quote_type_var.set("")
        self.search_customer_name_var.set("")
        self.search_business_name_var.set("")
        self.search_date_from_var.set("")
        self.search_date_to_var.set("")
        
        # Clear results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Clear details
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        self.details_text.config(state=tk.DISABLED)
        
        self.status_var.set("Search form cleared")
    
    def _set_today_date_range(self):
        """Set the date range to today."""
        today = datetime.now().strftime("%Y-%m-%d")
        self.search_date_from_var.set(today)
        self.search_date_to_var.set(today)
    
    def _on_result_select(self, event):
        """Handle selection of a quote in the results tree."""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        # Get the quote ID from the selected item
        item = self.results_tree.item(selection[0])
        quote_id = item["values"][0]
        
        # Get quote details
        self._load_quote_details(quote_id)
    
    def _load_quote_details(self, quote_id):
        """Load and display quote details."""
        try:
            # Update status and show progress
            self.status_var.set(f"Loading details for quote {quote_id}...")
            self._show_progress(True)
            
            # Call API
            result = self.quote_client.get_quote_details(quote_id)
            
            # Hide progress
            self._show_progress(False)
            
            # Process result
            if "body" in result:
                quote_details = result["body"]
                
                # Enable editing of details text
                self.details_text.config(state=tk.NORMAL)
                self.details_text.delete(1.0, tk.END)
                
                # Display quote details
                self.details_text.insert(tk.END, f"QUOTE DETAILS: {quote_details.get('quoteName', '')}\n", "header")
                self.details_text.insert(tk.END, f"Quote ID: {quote_details.get('quoteID', quote_id)}\n")
                
                # Map quote type to friendly name
                quote_type_map = {"1": "Purchase", "2": "Lease", "3": "Rental", "4": "Service"}
                quote_type = quote_details.get("quoteType", "")
                if quote_type in quote_type_map:
                    quote_type = quote_type_map[quote_type]
                    
                self.details_text.insert(tk.END, f"Type: {quote_type}\n")
                self.details_text.insert(tk.END, f"Created: {quote_details.get('creationDate', '')}\n")
                self.details_text.insert(tk.END, f"Expires: {quote_details.get('expirationDate', '')}\n")
                
                if "salesPerson" in quote_details:
                    self.details_text.insert(tk.END, f"Sales Person: {quote_details.get('salesPerson', '')}\n")
                    
                self.details_text.insert(tk.END, "\n")
                
                # Add customer section
                self.details_text.insert(tk.END, "CUSTOMER INFORMATION\n", "section")
                
                customer_data = quote_details.get("customerData", {})
                customer_name = (f"{customer_data.get('customerFirstName', '')} "
                               f"{customer_data.get('customerLastName', '')}").strip()
                
                self.details_text.insert(tk.END, f"Name: {customer_name}\n")
                
                if customer_data.get("customerBusinessName"):
                    self.details_text.insert(tk.END, f"Business: {customer_data.get('customerBusinessName', '')}\n")
                    
                if customer_data.get("customerEmail"):
                    self.details_text.insert(tk.END, f"Email: {customer_data.get('customerEmail', '')}\n")
                    
                if customer_data.get("customerHomePhoneNumber"):
                    self.details_text.insert(tk.END, f"Phone: {customer_data.get('customerHomePhoneNumber', '')}\n")
                
                # Address if provided
                address_fields = ['customerAddr1', 'customerAddr2', 'customerCity', 
                                'customerState', 'customerZipCode', 'customerCountry']
                if any(customer_data.get(f) for f in address_fields):
                    address = []
                    if customer_data.get('customerAddr1'):
                        address.append(customer_data.get('customerAddr1'))
                    if customer_data.get('customerAddr2'):
                        address.append(customer_data.get('customerAddr2'))
                    
                    city_state = []
                    if customer_data.get('customerCity'):
                        city_state.append(customer_data.get('customerCity'))
                    if customer_data.get('customerState'):
                        city_state.append(customer_data.get('customerState'))
                    
                    if city_state:
                        address.append(", ".join(city_state))
                        
                    if customer_data.get('customerZipCode'):
                        address.append(customer_data.get('customerZipCode'))
                        
                    if customer_data.get('customerCountry'):
                        address.append(customer_data.get('customerCountry'))
                        
                    self.details_text.insert(tk.END, f"Address: {', '.join(address)}\n")
                
                self.details_text.insert(tk.END, "\n")
                
                # Equipment section
                self.details_text.insert(tk.END, "EQUIPMENT\n", "section")
                equipment_data = quote_details.get("equipmentData", [])
                
                if equipment_data:
                    for i, equipment in enumerate(equipment_data, 1):
                        model = equipment.get("dealerSpecifiedModel", "")
                        desc = ""
                        
                        # Try to find description in options
                        if "equipmentOptionData" in equipment and equipment["equipmentOptionData"]:
                            option_data = equipment["equipmentOptionData"]
                            for option in option_data:
                                if "optionDesc" in option:
                                    desc = option["optionDesc"]
                                    break
                        
                        self.details_text.insert(tk.END, f"{i}. {model}", "item")
                        if desc:
                            self.details_text.insert(tk.END, f" - {desc}")
                        self.details_text.insert(tk.END, "\n")
                        
                        # Show price
                        try:
                            price = float(equipment.get("listPrice", 0))
                            self.details_text.insert(tk.END, f"   Price: ${price:,.2f}\n")
                        except (ValueError, TypeError):
                            self.details_text.insert(tk.END, f"   Price: ${equipment.get('listPrice', 0)}\n")
                        
                        # Quantity
                        quantity = equipment.get("quantity", 1)
                        self.details_text.insert(tk.END, f"   Quantity: {quantity}\n")
                        
                        # Other details if available
                        if "serialNo" in equipment and equipment["serialNo"]:
                            self.details_text.insert(tk.END, f"   Serial #: {equipment['serialNo']}\n")
                        
                        if "yearOfManufacture" in equipment:
                            self.details_text.insert(tk.END, f"   Year: {equipment['yearOfManufacture']}\n")
                        
                        self.details_text.insert(tk.END, "\n")
                else:
                    self.details_text.insert(tk.END, "No equipment listed in this quote.\n\n")
                
                # Trade-in section if applicable
                tradein_data = quote_details.get("tradeInEquipmentData", [])
                if tradein_data:
                    self.details_text.insert(tk.END, "TRADE-INS\n", "section")
                    
                    for i, tradein in enumerate(tradein_data, 1):
                        model = tradein.get("dealerSpecifiedModel", "")
                        desc = tradein.get("description", "")
                        
                        self.details_text.insert(tk.END, f"{i}. {model}", "item")
                        if desc:
                            self.details_text.insert(tk.END, f" - {desc}")
                        self.details_text.insert(tk.END, "\n")
                        
                        # Show value
                        try:
                            value = float(tradein.get("netTradeValue", 0))
                            self.details_text.insert(tk.END, f"   Value: ${value:,.2f}\n")
                        except (ValueError, TypeError):
                            self.details_text.insert(tk.END, f"   Value: ${tradein.get('netTradeValue', 0)}\n")
                        
                        # Other details if available
                        if "serialNo" in tradein and tradein["serialNo"]:
                            self.details_text.insert(tk.END, f"   Serial #: {tradein['serialNo']}\n")
                        
                        if "yearOfManufacture" in tradein:
                            self.details_text.insert(tk.END, f"   Year: {tradein['yearOfManufacture']}\n")
                            
                        if "hourMeterReading" in tradein and tradein["hourMeterReading"]:
                            self.details_text.insert(tk.END, f"   Hours: {tradein['hourMeterReading']}\n")
                        
                        self.details_text.insert(tk.END, "\n")
                
                # Notes if available
                if "custNotes" in quote_details and quote_details["custNotes"]:
                    self.details_text.insert(tk.END, "NOTES\n", "section")
                    self.details_text.insert(tk.END, f"{quote_details['custNotes']}\n\n")
                
                # Add PDF links
                self.details_text.insert(tk.END, "DOCUMENTS\n", "section")
                self.details_text.insert(tk.END, "You can download the following documents for this quote:\n")
                self.details_text.insert(tk.END, "• Proposal PDF\n")
                self.details_text.insert(tk.END, "• Order Form PDF\n")
                self.details_text.insert(tk.END, "• Recap PDF\n\n")
                
                # Add total
                total_amount = 0
                for equipment in equipment_data:
                    try:
                        price = float(equipment.get("listPrice", 0))
                        quantity = int(equipment.get("quantity", 1))
                        total_amount += price * quantity
                    except (ValueError, TypeError):
                        pass
                
                # Subtract trade-ins
                for tradein in tradein_data:
                    try:
                        value = float(tradein.get("netTradeValue", 0))
                        total_amount -= value
                    except (ValueError, TypeError):
                        pass
                
                self.details_text.insert(tk.END, f"QUOTE TOTAL: ${total_amount:,.2f}\n", "total")
                
                # Make read-only again
                self.details_text.config(state=tk.DISABLED)
                
                # Configure tags for styling
                self.details_text.tag_configure("header", font=("", 12, "bold"))
                self.details_text.tag_configure("section", font=("", 10, "bold"))
                self.details_text.tag_configure("item", font=("", 9, "bold"))
                self.details_text.tag_configure("total", font=("", 10, "bold"))
                
                # Update status
                self.status_var.set(f"Loaded details for Quote ID: {quote_id}")
            else:
                messagebox.showerror("Error", "Failed to load quote details - invalid response from API")
                self.status_var.set("Failed to load quote details")
                
        except Exception as e:
            self._handle_api_error("loading quote details", e, lambda: self._load_quote_details(quote_id))
    
    def _get_pdf(self, pdf_type):
        """Get and display a PDF for the selected quote."""
        try:
            # Get the selected quote ID
            selection = self.results_tree.selection()
            if not selection:
                messagebox.showinfo("Information", "Please select a quote first")
                return
            
            quote_id = self.results_tree.item(selection[0], "values")[0]
            
            # Update status and show progress
            self.status_var.set(f"Getting {pdf_type} PDF for quote {quote_id}...")
            self._show_progress(True)
            
            # Request the PDF based on type
            if pdf_type == "proposal":
                pdf_data = self.quote_client.get_proposal_pdf(quote_id)
                title = f"Proposal PDF - Quote {quote_id}"
            elif pdf_type == "orderform":
                pdf_data = self.quote_client.get_order_form_pdf(quote_id)
                title = f"Order Form PDF - Quote {quote_id}"
            elif pdf_type == "recap":
                pdf_data = self.quote_client.get_recap_pdf(quote_id)
                title = f"Recap PDF - Quote {quote_id}"
            else:
                raise ValueError(f"Invalid PDF type: {pdf_type}")
            
            # Hide progress
            self._show_progress(False)
            
            # Check if we got a valid PDF
            if not pdf_data or len(pdf_data) < 100:  # Simple check for valid PDF content
                messagebox.showerror("Error", "Failed to retrieve a valid PDF")
                return
            
            # Show preview dialog
            preview_dialog = PDFPreviewDialog(self.root, pdf_data, title)
            
        except Exception as e:
            self._handle_api_error(f"getting {pdf_type} PDF", e, lambda: self._get_pdf(pdf_type))
    
    def _delete_selected_quote(self):
        """Delete the selected quote."""
        try:
            # Get the selected quote ID
            selection = self.results_tree.selection()
            if not selection:
                messagebox.showinfo("Information", "Please select a quote first")
                return
            
            quote_id = self.results_tree.item(selection[0], "values")[0]
            
            # Confirm deletion
            confirm = messagebox.askyesno("Confirm Deletion", 
                                         f"Are you sure you want to delete Quote {quote_id}?\n\nThis action cannot be undone.")
            if not confirm:
                return
            
            # Get dealer ID
            dealer_id = self.config.get_setting('jd.dealer_id', '')
            if not dealer_id:
                messagebox.showerror("Error", "Dealer ID is required to delete a quote. Please set it in the Settings tab.")
                return
            
            # Update status and show progress
            self.status_var.set(f"Deleting quote {quote_id}...")
            self._show_progress(True)
            
            # Call API
            self.quote_client.delete_quote(quote_id, dealer_id)
            
            # Hide progress
            self._show_progress(False)
            
            # Remove from results and clear details
            self.results_tree.delete(selection[0])
            
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.config(state=tk.DISABLED)
            
            # Update status
            messagebox.showinfo("Success", f"Quote {quote_id} has been deleted.")
            self.status_var.set(f"Deleted quote {quote_id}")
        
        except Exception as e:
            self._handle_api_error("deleting quote", e)
    
    def _save_settings(self):
        """Save the settings."""
        try:
            # Store original values for comparison
            old_client_id = self.config.get_setting('jd_client_id', '')
            old_client_secret = self.config.get_setting('jd_client_secret', '')
            old_api_url = self.config.get_setting('jd.quote_api_base_url', '')
            old_dealer_account = self.config.get_setting('jd.dealer_account_number', '')
            old_dealer_id = self.config.get_setting('jd.dealer_id', '')
            
            # Get new values
            new_client_id = self.client_id_var.get()
            new_client_secret = self.client_secret_var.get()
            new_api_url = self.api_url_var.get()
            new_dealer_account = self.settings_dealer_account_var.get()
            new_dealer_id = self.settings_dealer_id_var.get()
            
            # Check if settings have changed
            settings_changed = (
                old_client_id != new_client_id or
                old_client_secret != new_client_secret or
                old_api_url != new_api_url or
                old_dealer_account != new_dealer_account or
                old_dealer_id != new_dealer_id
            )
            
            # Debug log
            logger.debug("Settings changed: %s", settings_changed)
            if settings_changed:
                logger.debug("Changed settings:")
                if old_client_id != new_client_id:
                    logger.debug("- client_id changed")
                if old_client_secret != new_client_secret:
                    logger.debug("- client_secret changed")
                if old_api_url != new_api_url:
                    logger.debug("- api_url changed")
                if old_dealer_account != new_dealer_account:
                    logger.debug("- dealer_account changed")
                if old_dealer_id != new_dealer_id:
                    logger.debug("- dealer_id changed")
            
            # Update settings with explicit debugging
            logger.debug("Updating 'jd_client_id' setting")
            self.config.set_setting('jd_client_id', new_client_id)
            
            logger.debug("Updating 'jd_client_secret' setting")
            self.config.set_setting('jd_client_secret', new_client_secret)
            
            # Update API URL based on environment
            logger.debug("Updating API URL settings")
            if self.environment_var.get() == "production":
                # Adjust the URL to use production
                new_api_url = new_api_url.replace("sandbox", "").replace("cert/", "")
                logger.debug(f"Using production URL: {new_api_url}")
            
            # Create jd section if not exists
            if 'jd' not in self.config.config:
                logger.debug("Creating 'jd' section in config")
                self.config.config['jd'] = {}
            
            # Set nested settings
            logger.debug("Updating 'jd.quote_api_base_url' setting")
            self.config.config['jd']['quote_api_base_url'] = new_api_url
            
            logger.debug("Updating 'jd.dealer_account_number' setting")
            self.config.config['jd']['dealer_account_number'] = new_dealer_account
            
            logger.debug("Updating 'jd.dealer_id' setting")
            self.config.config['jd']['dealer_id'] = new_dealer_id
            
            # Save settings explicit
            logger.debug("Saving config file...")
            success = self.config.save_settings()
            logger.debug(f"Save success: {success}")
            
            # Verify saved settings
            logger.debug("Verifying saved settings")
            # Read the file directly to make sure it was saved
            if os.path.exists(self.config.config_file):
                with open(self.config.config_file, 'r') as f:
                    saved_config = json.load(f)
                logger.debug(f"Read saved config: {json.dumps(saved_config)}")
                
                # Check that our values were actually saved
                if saved_config.get('jd_client_id') != new_client_id:
                    logger.warning("client_id mismatch in saved config")
                if 'jd' not in saved_config:
                    logger.warning("'jd' section missing in saved config")
            else:
                logger.warning(f"Config file not created: {self.config.config_file}")
            
            # Update UI elements
            self.dealer_account_var.set(new_dealer_account)
            
            # Update connection status text
            self.connection_text.config(state=tk.NORMAL)
            self.connection_text.delete(1.0, tk.END)
            
            self.connection_text.insert(tk.END, "John Deere API Integration\n\n", "header")
            self.connection_text.insert(tk.END, "Status: ")
            
            if new_client_id and new_client_secret:
                self.connection_text.insert(tk.END, "Credentials configured\n\n", "green")
            else:
                self.connection_text.insert(tk.END, "Credentials missing\n\n", "red")
            
            self.connection_text.insert(tk.END, "Environment: ")
            env = "Production" if self.environment_var.get() == "production" else "Sandbox"
            self.connection_text.insert(tk.END, f"{env}\n\n")
            
            self.connection_text.insert(tk.END, f"Dealer Account: {new_dealer_account}\n")
            self.connection_text.insert(tk.END, f"Dealer ID: {new_dealer_id}\n\n")
            
            self.connection_text.insert(tk.END, f"Config file: {os.path.abspath(self.config.config_file)}\n\n")
            
            self.connection_text.insert(tk.END, """
Settings saved. To use this module, you need:
1. John Deere Developer account
2. Client ID and Client Secret
3. Dealer Account Number and ID

For assistance, contact the BRI support team or visit the John Deere Developer portal.
            """)
            
            self.connection_text.config(state=tk.DISABLED)
            
            # Recreate API clients if settings changed
            if settings_changed:
                logger.debug("Settings changed, recreating API clients")
                self._setup_api_clients()
            
            # Show success message
            messagebox.showinfo("Success", "Settings saved successfully!")
            self.status_var.set("Settings saved")
        
        except Exception as e:
            logger.error(f"Error saving settings: {str(e)}")
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")
            self.status_var.set("Error saving settings")
    
    def _test_connection(self):
        """Test the connection to the JD API."""
        try:
            # Update status and show progress
            self.status_var.set("Testing connection...")
            self._show_progress(True)
            
            # Debug connection details
            logger.debug("Testing connection with the following credentials:")
            logger.debug(f"Client ID: {'[SET]' if self.oauth_client.client_id else '[NOT SET]'}")
            logger.debug(f"Client Secret: {'[SET]' if self.oauth_client.client_secret else '[NOT SET]'}")
            logger.debug(f"API URL: {self.quote_client.base_url}")
            
            # First test - get auth header which will request a token
            try:
                logger.debug("Attempting to get auth header...")
                headers = self.oauth_client.get_auth_header()
                logger.debug(f"Got auth header: {headers if isinstance(headers, dict) else 'Bearer token'}")
            except Exception as auth_error:
                logger.error(f"Auth error: {str(auth_error)}")
                raise Exception(f"Authentication failed: {str(auth_error)}")
            
            # Hide progress
            self._show_progress(False)
            
            # Update connection status
            self.connection_text.config(state=tk.NORMAL)
            
            # Find the Status line and update it
            content = self.connection_text.get(1.0, tk.END)
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                if line.startswith("Status:"):
                    # Clear from this line to the next blank line
                    lines[i] = "Status: Connected successfully\n"
                    break
            
            # Update the text
            self.connection_text.delete(1.0, tk.END)
            self.connection_text.insert(tk.END, '\n'.join(lines))
            
            # Make read-only again
            self.connection_text.config(state=tk.DISABLED)
            
            # Show success message
            messagebox.showinfo("Success", "Connection test successful!")
            self.status_var.set("Connection test successful")
        
        except Exception as e:
            self._show_progress(False)
            logger.error(f"Error testing connection: {str(e)}")
            
            # Update connection status
            self.connection_text.config(state=tk.NORMAL)
            
            # Find the Status line and update it
            content = self.connection_text.get(1.0, tk.END)
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                if line.startswith("Status:"):
                    # Clear from this line to the next blank line
                    lines[i] = f"Status: Connection failed\nError: {str(e)}\n"
                    break
            
            # Update the text
            self.connection_text.delete(1.0, tk.END)
            self.connection_text.insert(tk.END, '\n'.join(lines))
            
            # Make read-only again
            self.connection_text.config(state=tk.DISABLED)
            
            messagebox.showerror("Error", f"Connection test failed: {str(e)}")
            self.status_var.set("Connection test failed")
    
    def _load_quote_for_edit(self):
        """Load a quote for editing."""
        try:
            quote_id = self.edit_quote_id_var.get()
            if not quote_id:
                messagebox.showwarning("Input Error", "Please enter a Quote ID")
                return
            
            # Update status and show progress
            self.status_var.set(f"Loading quote {quote_id} for editing...")
            self._show_progress(True)
            
            # Get quote details
            result = self.quote_client.get_quote_details(quote_id)
            
            # Hide progress
            self._show_progress(False)
            
            # Process result
            if "body" in result:
                quote_data = result["body"]
                
                # Populate basic quote fields
                self.edit_quote_name_var.set(quote_data.get("quoteName", ""))
                self.edit_quote_type_var.set(str(quote_data.get("quoteType", "")))
                self.edit_sales_person_var.set(quote_data.get("salesPerson", ""))
                
                # Format expiration date if needed
                expiry_date = quote_data.get("expirationDate", "")
                if expiry_date and "/" in expiry_date:  # MM/DD/YYYY format
                    try:
                        date_obj = datetime.strptime(expiry_date, "%m/%d/%Y")
                        expiry_date = date_obj.strftime("%Y-%m-%d")
                    except ValueError:
                        pass
                        
                self.edit_expiration_date_var.set(expiry_date)
                self.edit_cust_notes_var.set(quote_data.get("custNotes", ""))
                self.edit_quote_status_var.set(str(quote_data.get("quoteStatusId", "1")))
                
                # Populate customer data
                customer_data = quote_data.get("customerData", {})
                self.edit_customer_first_name_var.set(customer_data.get("customerFirstName", ""))
                self.edit_customer_last_name_var.set(customer_data.get("customerLastName", ""))
                self.edit_customer_business_name_var.set(customer_data.get("customerBusinessName", ""))
                self.edit_customer_email_var.set(customer_data.get("customerEmail", ""))
                self.edit_customer_addr1_var.set(customer_data.get("customerAddr1", ""))
                self.edit_customer_addr2_var.set(customer_data.get("customerAddr2", ""))
                self.edit_customer_city_var.set(customer_data.get("customerCity", ""))
                self.edit_customer_state_var.set(customer_data.get("customerState", ""))
                self.edit_customer_zip_var.set(customer_data.get("customerZipCode", ""))
                self.edit_customer_country_var.set(customer_data.get("customerCountry", "US"))
                self.edit_customer_phone_var.set(customer_data.get("customerHomePhoneNumber", ""))
                self.edit_customer_business_phone_var.set(customer_data.get("customerBusinessPhoneNumber", ""))
                
                # Populate equipment data
                equipment_data = quote_data.get("equipmentData", [])
                for item in self.equipment_tree.get_children():
                    self.equipment_tree.delete(item)
                    
                for equip in equipment_data:
                    make_id = equip.get("makeID", "")
                    model = equip.get("dealerSpecifiedModel", "")
                    
                    # Find description in options if available
                    desc = ""
                    if "equipmentOptionData" in equip and equip["equipmentOptionData"]:
                        option_data = equip["equipmentOptionData"]
                        for option in option_data:
                            if "optionDesc" in option:
                                desc = option["optionDesc"]
                                break
                    
                    qty = equip.get("quantity", "1")
                    
                    # Format price for display
                    try:
                        price = float(equip.get("listPrice", 0))
                        price_str = f"${price:,.2f}"
                    except (ValueError, TypeError):
                        price_str = f"${equip.get('listPrice', '0')}"
                    
                    self.equipment_tree.insert("", tk.END, values=(
                        equip.get("equipmentID", ""),
                        make_id,
                        model,
                        desc,
                        qty,
                        price_str
                    ))
                
                # Populate trade-in data
                tradein_data = quote_data.get("tradeInEquipmentData", [])
                for item in self.tradein_tree.get_children():
                    self.tradein_tree.delete(item)
                    
                for trade in tradein_data:
                    make_id = trade.get("makeID", "")
                    model = trade.get("dealerSpecifiedModel", "")
                    desc = trade.get("description", "")
                    year = trade.get("yearOfManufacture", "")
                    
                    # Format value for display
                    try:
                        value = float(trade.get("netTradeValue", 0))
                        value_str = f"${value:,.2f}"
                    except (ValueError, TypeError):
                        value_str = f"${trade.get('netTradeValue', '0')}"
                    
                    self.tradein_tree.insert("", tk.END, values=(
                        trade.get("tradeInID", ""),
                        make_id,
                        model,
                        desc,
                        year,
                        value_str
                    ))
                
                # Update status
                self.status_var.set(f"Loaded quote {quote_id} for editing")
                
                # Switch to the first tab
                self.edit_notebook.select(0)
            else:
                messagebox.showerror("Error", "Failed to load quote details - invalid response from API")
                self.status_var.set("Failed to load quote details")
        
        except Exception as e:
            self._handle_api_error("loading quote for editing", e, self._load_quote_for_edit)

    def _update_quote(self):
        """Update the edited quote."""
        try:
            quote_id = self.edit_quote_id_var.get()
            if not quote_id:
                messagebox.showwarning("Input Error", "Please enter a Quote ID")
                return
            
            # Validate form
            if not self._validate_edit_form():
                return
            
            # Build quote data
            quote_data = self._build_quote_data_from_edit_form()
            
            # Update status and show progress
            self.status_var.set(f"Updating quote {quote_id}...")
            self._show_progress(True)
            
            # Call API
            result = self.quote_client.update_quote(quote_id, quote_data)
            
            # Hide progress
            self._show_progress(False)
            
            # Process result
            if "body" in result:
                messagebox.showinfo("Success", f"Quote {quote_id} updated successfully!")
                self.status_var.set(f"Updated quote {quote_id}")
            else:
                messagebox.showerror("Error", "Failed to update quote - invalid response from API")
                self.status_var.set("Failed to update quote")
        
        except Exception as e:
            self._handle_api_error("updating quote", e, self._update_quote)

    def _build_quote_data_from_edit_form(self):
        """Build quote data from edit form for API request."""
        # Get data from form
        quote_name = self.edit_quote_name_var.get()
        quote_type = self.edit_quote_type_var.get()
        sales_person = self.edit_sales_person_var.get()
        expiration_date = self.edit_expiration_date_var.get()
        
        # Convert expiration date format if needed
        if expiration_date and "-" in expiration_date:  # YYYY-MM-DD format
            try:
                date_obj = datetime.strptime(expiration_date, "%Y-%m-%d")
                expiration_date = date_obj.strftime("%m/%d/%Y")
            except ValueError:
                pass
                
        cust_notes = self.edit_cust_notes_var.get()
        quote_status = self.edit_quote_status_var.get()
        
        # Customer data
        customer_data = {
            "customerFirstName": self.edit_customer_first_name_var.get(),
            "customerLastName": self.edit_customer_last_name_var.get(),
            "customerBusinessName": self.edit_customer_business_name_var.get(),
            "customerEmail": self.edit_customer_email_var.get(),
            "customerAddr1": self.edit_customer_addr1_var.get(),
            "customerAddr2": self.edit_customer_addr2_var.get(),
            "customerCity": self.edit_customer_city_var.get(),
            "customerState": self.edit_customer_state_var.get(),
            "customerZipCode": self.edit_customer_zip_var.get(),
            "customerCountry": self.edit_customer_country_var.get(),
            "customerHomePhoneNumber": self.edit_customer_phone_var.get(),
            "customerBusinessPhoneNumber": self.edit_customer_business_phone_var.get()
        }
        
        # Equipment data
        equipment_data = []
        for item_id in self.equipment_tree.get_children():
            item = self.equipment_tree.item(item_id)
            values = item["values"]
            
            # Get equipment ID and details
            equipment_id = values[0]
            make_id = values[1]
            model = values[2]
            description = values[3]
            quantity = values[4]
            
            # Convert price string to float
            price_str = values[5].replace("$", "").replace(",", "")
            try:
                price = float(price_str)
            except (ValueError, TypeError):
                price = 0.0
            
            # Create equipment object
            equipment = {
                "equipmentID": equipment_id,
                "makeID": make_id,
                "dealerSpecifiedModel": model,
                "description": description,
                "quantity": quantity,
                "listPrice": price,
                "includeInRecapProposal": True
            }
            
            equipment_data.append(equipment)
        
        # Trade-in data
        tradein_data = []
        for item_id in self.tradein_tree.get_children():
            item = self.tradein_tree.item(item_id)
            values = item["values"]
            
            # Get trade-in ID and details
            tradein_id = values[0]
            make_id = values[1]
            model = values[2]
            description = values[3]
            year = values[4]
            
            # Convert value string to float
            value_str = values[5].replace("$", "").replace(",", "")
            try:
                value = float(value_str)
            except (ValueError, TypeError):
                value = 0.0
            
            # Create trade-in object
            tradein = {
                "tradeInID": tradein_id,
                "makeID": make_id,
                "dealerSpecifiedModel": model,
                "description": description,
                "yearOfManufacture": year,
                "netTradeValue": value,
                "includeInRecapProposal": True
            }
            
            tradein_data.append(tradein)
        
        # Build complete quote data
        quote_data = {
            "quoteName": quote_name,
            "quoteType": int(quote_type) if quote_type else 1,
            "salesPerson": sales_person,
            "expirationDate": expiration_date,
            "custNotes": cust_notes,
            "quoteStatusId": int(quote_status) if quote_status else 1,
            "customerData": customer_data,
            "equipmentData": equipment_data,
            "tradeInEquipmentData": tradein_data,
            "dealerRacfId": self.config.get_setting('jd.dealer_id', '')
        }
        
        return quote_data

    def _validate_edit_form(self):
        """Validate the edit quote form."""
        errors = []
        
        # Check required fields
        if not self.edit_quote_name_var.get().strip():
            errors.append("Quote Name is required")
        
        if not self.edit_quote_type_var.get():
            errors.append("Quote Type is required")
        
        if not self.edit_customer_first_name_var.get().strip() or not self.edit_customer_last_name_var.get().strip():
            errors.append("Customer First and Last Name are required")
        
        # Validate expiration date format
        expiry_date = self.edit_expiration_date_var.get().strip()
        if expiry_date:
            try:
                # Support both YYYY-MM-DD and MM/DD/YYYY formats
                if "-" in expiry_date:
                    datetime.strptime(expiry_date, "%Y-%m-%d")
                elif "/" in expiry_date:
                    datetime.strptime(expiry_date, "%m/%d/%Y")
                else:
                    errors.append("Expiration Date format is invalid (use YYYY-MM-DD)")
            except ValueError:
                errors.append("Expiration Date format is invalid (use YYYY-MM-DD)")
        
        # Show all errors if any
        if errors:
            messagebox.showwarning("Validation Errors", 
                                  "Please correct the following issues:\n\n" + 
                                  "\n".join(f"• {error}" for error in errors))
            return False
        
        return True

    def _copy_quote(self):
        """Create a copy of the current quote."""
        try:
            quote_id = self.edit_quote_id_var.get()
            if not quote_id:
                messagebox.showwarning("Input Error", "Please enter a Quote ID to copy")
                return
            
            # Get dealer ID
            dealer_id = self.config.get_setting('jd.dealer_id', '')
            if not dealer_id:
                messagebox.showerror("Error", "Dealer ID is required to copy a quote. Please set it in the Settings tab.")
                return
            
            # Ask for new expiration date
            expiration_date = self.edit_expiration_date_var.get()
            
            # Update status and show progress
            self.status_var.set(f"Copying quote {quote_id}...")
            self._show_progress(True)
            
            # Call API
            result = self.quote_client.copy_quote(quote_id, dealer_id, expiration_date)
            
            # Hide progress
            self._show_progress(False)
            
            # Process result
            if "body" in result and "quoteID" in result["body"]:
                new_quote_id = result["body"]["quoteID"]
                messagebox.showinfo("Success", f"Quote copied successfully!\nNew Quote ID: {new_quote_id}")
                self.status_var.set(f"Copied quote to {new_quote_id}")
                
                # Ask if user wants to load the new quote
                load_new = messagebox.askyesno("Load New Quote", "Do you want to load the new quote for editing?")
                if load_new:
                    self.edit_quote_id_var.set(new_quote_id)
                    self._load_quote_for_edit()
            else:
                messagebox.showerror("Error", "Failed to copy quote - invalid response from API")
                self.status_var.set("Failed to copy quote")
        
        except Exception as e:
            self._handle_api_error("copying quote", e, self._copy_quote)

    def _set_quote_expiration(self):
        """Set expiration date for the current quote."""
        try:
            quote_id = self.edit_quote_id_var.get()
            if not quote_id:
                messagebox.showwarning("Input Error", "Please enter a Quote ID")
                return
            
            # Get dealer ID
            dealer_id = self.config.get_setting('jd.dealer_id', '')
            if not dealer_id:
                messagebox.showerror("Error", "Dealer ID is required to set expiration date. Please set it in the Settings tab.")
                return
            
            # Get expiration date
            expiration_date = self.edit_expiration_date_var.get()
            if not expiration_date:
                messagebox.showwarning("Input Error", "Please enter an Expiration Date")
                return
            
            # Convert format if needed
            if "-" in expiration_date:  # YYYY-MM-DD format
                try:
                    date_obj = datetime.strptime(expiration_date, "%Y-%m-%d")
                    expiration_date = date_obj.strftime("%m/%d/%Y")
                except ValueError:
                    messagebox.showwarning("Input Error", "Invalid date format. Use YYYY-MM-DD.")
                    return
            
            # Update status and show progress
            self.status_var.set(f"Setting expiration date for quote {quote_id}...")
            self._show_progress(True)
            
            # Call API
            result = self.quote_client.set_expiration_date(quote_id, expiration_date, dealer_id)
            
            # Hide progress
            self._show_progress(False)
            
            # Process result
            if "body" in result and result["body"].get("expirationDateUpdateSuccess") == True:
                messagebox.showinfo("Success", f"Expiration date updated successfully!")
                self.status_var.set(f"Updated expiration date for quote {quote_id}")
            else:
                messagebox.showerror("Error", "Failed to update expiration date - invalid response from API")
                self.status_var.set("Failed to update expiration date")
        
        except Exception as e:
            self._handle_api_error("setting expiration date", e, self._set_quote_expiration)
            
    # Equipment-related methods
    def _on_equipment_select(self, event):
        """Handle equipment selection in edit tab."""
        selection = self.equipment_tree.selection()
        if not selection:
            return
            
        # Get data from selected item
        item = self.equipment_tree.item(selection[0])
        values = item["values"]
        
        # Fill in equipment details form
        self.edit_equipment_make_var.set(values[1])
        self.edit_equipment_model_var.set(values[2])
        self.edit_equipment_desc_var.set(values[3])
        
        # Handle quantity
        try:
            quantity = int(values[4])
        except (ValueError, TypeError):
            quantity = 1
        self.edit_equipment_quantity_var.set(str(quantity))
        
        # Handle price
        price_str = values[5].replace("$", "").replace(",", "")
        try:
            price = float(price_str)
            self.edit_equipment_price_var.set(f"{price:.2f}")
        except (ValueError, TypeError):
            self.edit_equipment_price_var.set("0.00")
        
        # Clear other fields
        self.edit_equipment_serialno_var.set("")
        self.edit_equipment_stockno_var.set("")
        self.edit_equipment_year_var.set(str(datetime.now().year))
        self.edit_equipment_include_recap_var.set(True)
        self.edit_equipment_notes_var.set("")
    
    def _add_equipment_dialog(self):
        """Show dialog to add new equipment."""
        # Clear form fields
        self.edit_equipment_make_var.set("1")  # Default to John Deere
        self.edit_equipment_model_var.set("")
        self.edit_equipment_desc_var.set("")
        self.edit_equipment_quantity_var.set("1")
        self.edit_equipment_price_var.set("0.00")
        self.edit_equipment_serialno_var.set("")
        self.edit_equipment_stockno_var.set("")
        self.edit_equipment_year_var.set(str(datetime.now().year))
        self.edit_equipment_include_recap_var.set(True)
        self.edit_equipment_notes_var.set("")
    
    def _edit_equipment_dialog(self):
        """Edit the selected equipment."""
        selection = self.equipment_tree.selection()
        if not selection:
            messagebox.showinfo("Information", "Please select an equipment item to edit")
            return
        
        # Equipment is already selected, so fields are populated by _on_equipment_select
        # Just focus on the first field to make it clear we're in edit mode
        self.edit_equipment_model_entry.focus_set()
    
    def _remove_equipment(self):
        """Remove the selected equipment."""
        selection = self.equipment_tree.selection()
        if not selection:
            messagebox.showinfo("Information", "Please select equipment to remove")
            return
            
        # Confirm removal
        confirm = messagebox.askyesno("Confirm Removal", 
                                     "Are you sure you want to remove this equipment?")
        if not confirm:
            return
            
        # Remove item from tree
        self.equipment_tree.delete(selection[0])
        
        # Clear form fields
        self.edit_equipment_make_var.set("1")
        self.edit_equipment_model_var.set("")
        self.edit_equipment_desc_var.set("")
        self.edit_equipment_quantity_var.set("1")
        self.edit_equipment_price_var.set("0.00")
        self.edit_equipment_serialno_var.set("")
        self.edit_equipment_stockno_var.set("")
        self.edit_equipment_year_var.set(str(datetime.now().year))
        self.edit_equipment_include_recap_var.set(True)
        self.edit_equipment_notes_var.set("")
    
    def _save_equipment_details(self):
        """Save the current equipment details."""
        # Validate form
        errors = []
        
        if not self.edit_equipment_model_var.get().strip():
            errors.append("Model is required")
            
        try:
            quantity = int(self.edit_equipment_quantity_var.get())
            if quantity <= 0:
                errors.append("Quantity must be greater than zero")
        except ValueError:
            errors.append("Quantity must be a valid number")
            
        try:
            price = float(self.edit_equipment_price_var.get().replace(',', ''))
            if price < 0:
                errors.append("Price cannot be negative")
        except ValueError:
            errors.append("Price must be a valid number")
            
        # Show all errors if any
        if errors:
            messagebox.showwarning("Validation Errors", 
                                  "Please correct the following issues:\n\n" + 
                                  "\n".join(f"• {error}" for error in errors))
            return
            
        # Check if we're editing existing equipment or adding new
        selection = self.equipment_tree.selection()
        
        if selection:
            # Update existing item
            item_id = selection[0]
            
            # Format price for display
            try:
                price = float(self.edit_equipment_price_var.get().replace(',', ''))
                price_str = f"${price:,.2f}"
            except (ValueError, TypeError):
                price_str = "$0.00"
                
            self.equipment_tree.item(item_id, values=(
                self.equipment_tree.item(item_id)["values"][0],  # Keep original ID
                self.edit_equipment_make_var.get(),
                self.edit_equipment_model_var.get(),
                self.edit_equipment_desc_var.get(),
                self.edit_equipment_quantity_var.get(),
                price_str
            ))
        else:
            # Add new item with a temporary ID
            new_id = f"NEW_{len(self.equipment_tree.get_children()) + 1}"
            
            # Format price for display
            try:
                price = float(self.edit_equipment_price_var.get().replace(',', ''))
                price_str = f"${price:,.2f}"
            except (ValueError, TypeError):
                price_str = "$0.00"
                
            self.equipment_tree.insert("", tk.END, values=(
                new_id,
                self.edit_equipment_make_var.get(),
                self.edit_equipment_model_var.get(),
                self.edit_equipment_desc_var.get(),
                self.edit_equipment_quantity_var.get(),
                price_str
            ))
            
        messagebox.showinfo("Success", "Equipment saved")
    
    # Trade-in related methods
    def _on_tradein_select(self, event):
        """Handle trade-in selection in edit tab."""
        selection = self.tradein_tree.selection()
        if not selection:
            return
            
        # Get data from selected item
        item = self.tradein_tree.item(selection[0])
        values = item["values"]
        
        # Fill in trade-in details form
        self.edit_tradein_make_var.set(values[1])
        self.edit_tradein_model_var.set(values[2])
        self.edit_tradein_desc_var.set(values[3])
        self.edit_tradein_year_var.set(values[4])
        
        # Handle value
        value_str = values[5].replace("$", "").replace(",", "")
        try:
            value = float(value_str)
            self.edit_tradein_value_var.set(f"{value:.2f}")
        except (ValueError, TypeError):
            self.edit_tradein_value_var.set("0.00")
        
        # Clear other fields
        self.edit_tradein_serialno_var.set("")
        self.edit_tradein_hours_var.set("0")
        self.edit_tradein_include_recap_var.set(True)
    
    def _add_tradein_dialog(self):
        """Show dialog to add new trade-in."""
        # Clear form fields
        self.edit_tradein_make_var.set("1")  # Default to John Deere
        self.edit_tradein_model_var.set("")
        self.edit_tradein_desc_var.set("")
        self.edit_tradein_serialno_var.set("")
        self.edit_tradein_year_var.set(str(datetime.now().year - 5))  # Default to 5 years old
        self.edit_tradein_hours_var.set("0")
        self.edit_tradein_value_var.set("0.00")
        self.edit_tradein_include_recap_var.set(True)
    
    def _edit_tradein_dialog(self):
        """Edit the selected trade-in."""
        selection = self.tradein_tree.selection()
        if not selection:
            messagebox.showinfo("Information", "Please select a trade-in item to edit")
            return
        
        # Trade-in is already selected, so fields are populated by _on_tradein_select
        # Just focus on the first field to make it clear we're in edit mode
        self.edit_tradein_model_entry.focus_set()
    
    def _remove_tradein(self):
        """Remove the selected trade-in."""
        selection = self.tradein_tree.selection()
        if not selection:
            messagebox.showinfo("Information", "Please select a trade-in to remove")
            return
            
        # Confirm removal
        confirm = messagebox.askyesno("Confirm Removal", 
                                     "Are you sure you want to remove this trade-in?")
        if not confirm:
            return
            
        # Remove item from tree
        self.tradein_tree.delete(selection[0])
        
        # Clear form fields
        self.edit_tradein_make_var.set("1")  # Default to John Deere
        self.edit_tradein_model_var.set("")
        self.edit_tradein_desc_var.set("")
        self.edit_tradein_serialno_var.set("")
        self.edit_tradein_year_var.set(str(datetime.now().year - 5))
        self.edit_tradein_hours_var.set("0")
        self.edit_tradein_value_var.set("0.00")
        self.edit_tradein_include_recap_var.set(True)
    
    def _save_tradein_details(self):
        """Save the current trade-in details."""
        # Validate form
        errors = []
        
        if not self.edit_tradein_model_var.get().strip():
            errors.append("Model is required")
            
        try:
            value = float(self.edit_tradein_value_var.get().replace(',', ''))
            if value < 0:
                errors.append("Value cannot be negative")
        except ValueError:
            errors.append("Value must be a valid number")
            
        # Show all errors if any
        if errors:
            messagebox.showwarning("Validation Errors", 
                                  "Please correct the following issues:\n\n" + 
                                  "\n".join(f"• {error}" for error in errors))
            return
            
        # Check if we're editing existing trade-in or adding new
        selection = self.tradein_tree.selection()
        
        if selection:
            # Update existing item
            item_id = selection[0]
            
            # Format value for display
            try:
                value = float(self.edit_tradein_value_var.get().replace(',', ''))
                value_str = f"${value:,.2f}"
            except (ValueError, TypeError):
                value_str = "$0.00"
                
            self.tradein_tree.item(item_id, values=(
                self.tradein_tree.item(item_id)["values"][0],  # Keep original ID
                self.edit_tradein_make_var.get(),
                self.edit_tradein_model_var.get(),
                self.edit_tradein_desc_var.get(),
                self.edit_tradein_year_var.get(),
                value_str
            ))
        else:
            # Add new item with a temporary ID
            new_id = f"NEW_{len(self.tradein_tree.get_children()) + 1}"
            
            # Format value for display
            try:
                value = float(self.edit_tradein_value_var.get().replace(',', ''))
                value_str = f"${value:,.2f}"
            except (ValueError, TypeError):
                value_str = "$0.00"
                
            self.tradein_tree.insert("", tk.END, values=(
                new_id,
                self.edit_tradein_make_var.get(),
                self.edit_tradein_model_var.get(),
                self.edit_tradein_desc_var.get(),
                self.edit_tradein_year_var.get(),
                value_str
            ))
            
        messagebox.showinfo("Success", "Trade-in saved")
    
    def _show_login_dialog(self):
        """Show a dialog to re-login if authentication fails."""
        # TODO: Implement authentication dialog
        # For now, just suggest updating credentials
        messagebox.showinfo("Authentication Required", 
                           "Please update your API credentials in the Settings tab.")
        
        # Switch to settings tab
        self.notebook.select(self.settings_tab)
        
        return False  # Return False to indicate login was not successful

# Main function
def main():
    """Main entry point for the application."""
    try:
        # Initialize logging
        logging.basicConfig(level=logging.DEBUG, 
                          format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger = logging.getLogger('JDQuoteApp')
        logger.info("Starting JD Quote Application")
        
        # Create configuration
        config = SimpleConfig()
        logger.info("Configuration loaded")
        
        # Create root window
        logger.info("Creating Tkinter root window")
        root = tk.Tk()
        
        # Set application icon if available
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "jd_icon.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Could not set application icon: {str(e)}")
        
        # Create application
        logger.info("Creating JDQuoteApp")
        app = JDQuoteApp(root, config)
        
        # Run the application
        logger.info("Starting main loop")
        root.mainloop()
        logger.info("Application closed")
    
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Try to show an error dialog
        try:
            import tkinter.messagebox as mb
            mb.showerror("Fatal Error", f"A fatal error occurred:\n\n{str(e)}\n\nSee logs for details.")
        except:
            pass

# Run the application
if __name__ == "__main__":
    main()