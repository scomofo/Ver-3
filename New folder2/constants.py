"""Constants used throughout the application."""

# --- Application Information ---
APP_NAME = "BC Application"
APP_VERSION = "1.0.0"
COMPANY_NAME = "BC Company"
WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION}"
APP_ICON_NAME = "app_icon.png"

# --- Module names ---
MODULE_HOME = "Home"
MODULE_DEAL_FORM = "DealForm"
MODULE_RECENT_DEALS = "RecentDeals"
MODULE_PRICE_BOOK = "PriceBook"
MODULE_USED_INVENTORY = "UsedInventory"
MODULE_CALCULATOR = "Calculator"
MODULE_CALENDAR = "Calendar"
MODULE_JD_QUOTES = "JDQuotes"
MODULE_RECEIVING = "Receiving"

# --- SharePoint sheet names ---
SHEET_USED_AMS = "Used AMS"
SHEET_PRODUCTS = "Products"
SHEET_CUSTOMERS = "Customers"

# --- CSV file names ---
FILE_PRODUCTS = "products.csv"
FILE_PARTS = "parts.csv"
FILE_CUSTOMERS = "customers.csv"
FILE_SALESMEN = "salesmen.csv"

# --- UI Constants ---
UI_SIDEBAR_WIDTH = 200
UI_STATUSBAR_TIMEOUT = 5000  # ms
DEFAULT_WINDOW_WIDTH = 1024
DEFAULT_WINDOW_HEIGHT = 768
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
STATUS_BAR_MSG_DURATION = UI_STATUSBAR_TIMEOUT  # Use your existing timeout value

# --- Resources ---
SPLASH_IMAGE_NAME = "splash.png"
NAV_ICON_DIR = "icons/nav"

# --- Dialog Messages ---
EXIT_CONFIRMATION_TITLE = "Confirm Exit"
EXIT_CONFIRMATION_MSG = "Are you sure you want to exit the application?"

# --- Splash Screen ---
SPLASH_DURATION_MS = 2000  # 2 seconds

# --- Configuration Keys ---
CONFIG_WINDOW_GEOMETRY = "window_geometry"
CONFIG_THEME = "theme"

# --- Module Status Codes ---
MODULE_STATUS_READY = "ready"
MODULE_STATUS_LOADING = "loading"
MODULE_STATUS_ERROR = "error"
MODULE_STATUS_DISABLED = "disabled"

# --- Error Levels ---
ERROR_LEVEL_INFO = 0
ERROR_LEVEL_WARNING = 1
ERROR_LEVEL_ERROR = 2
ERROR_LEVEL_CRITICAL = 3

# --- File Paths ---
CONFIG_FILE_NAME = "config.json"
LOG_FILE_NAME = "application.log"

# --- Date/Time Formats ---
DATE_FORMAT_UI = "%m/%d/%Y"
TIME_FORMAT_UI = "%I:%M %p"
DATETIME_FORMAT_UI = f"{DATE_FORMAT_UI} {TIME_FORMAT_UI}"
DATE_FORMAT_ISO = "%Y-%m-%d"
DATETIME_FORMAT_ISO = "%Y-%m-%dT%H:%M:%S"

# --- Authentication ---
AUTH_TIMEOUT_SECONDS = 3600  # 1 hour
REFRESH_TOKEN_BEFORE_SECONDS = 300  # 5 minutes before expiry

# --- Data Sources ---
SHAREPOINT_SITE_NAME = "BCCompany"

# --- Network ---
API_TIMEOUT_SECONDS = 30
RETRY_COUNT = 3
RETRY_DELAY_SECONDS = 2