# app/main.py
import sys
import os
import logging
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure the project root is in sys.path
project_root_main = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root_main not in sys.path:
    sys.path.insert(0, project_root_main)

# PyQt6 imports (migrated from PyQt5)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QLabel, QStackedWidget, QListWidget, QHBoxLayout,
                             QMessageBox, QListWidgetItem, QSizePolicy, QListView, QDialog, QSplashScreen)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThreadPool, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap

# Core application components (modernized)
from app.core.config import get_config, BRIDealConfig
from app.core.logger_config import setup_logging
from app.core.app_auth_service import AppAuthService
from app.core.threading import get_task_manager, AsyncTaskManager
from app.core.exceptions import BRIDealException, AuthenticationError, ValidationError, ErrorSeverity
from app.core.security import SecureConfig
from app.core.performance import get_http_client_manager, get_performance_monitor, cleanup_performance_resources

# Utility imports
from app.utils.theme_manager import ThemeManager
from app.utils.cache_handler import CacheHandler
from app.utils.general_utils import set_app_user_model_id, get_resource_path
from app.utils.resource_checker import check_resources

# Service Imports (with enhanced error handling)
from app.services.integrations.token_handler import TokenHandler
try:
   from app.services.integrations.sharepoint_manager import SharePointExcelManager as SharePointManagerService
except ImportError:
   logging.getLogger(__name__).error(
       "Failed to import SharePointExcelManager. SharePoint features will be severely affected.", exc_info=True
   )
   SharePointManagerService = None

from app.services.api_clients.quote_builder import QuoteBuilder
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.services.api_clients.jd_quote_client import JDQuoteApiClient
from app.services.api_clients.maintain_quotes_api import MaintainQuotesAPI
from app.services.integrations.jd_quote_integration_service import JDQuoteIntegrationService

# View Module Imports
from app.views.modules.deal_form_view import DealFormView
from app.views.modules.recent_deals_view import RecentDealsView
from app.views.modules.price_book_view import PriceBookView
from app.views.modules.used_inventory_view import UsedInventoryView
from app.views.modules.receiving_view import ReceivingView
from app.views.modules.csv_editors_manager_view import CsvEditorsManagerView
from app.views.modules.calculator_view import CalculatorView
from app.views.modules.jd_external_quote_view import JDExternalQuoteView
from app.views.modules.invoice_module_view import InvoiceModuleView

# Main Window and Splash Screen
from app.views.main_window.splash_screen_view import SplashScreenView

# Logger for this module, configured properly after setup_logging()
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
   """
   Enhanced main window with modern architecture, async support, and comprehensive error handling.
   Updated for PyQt6 compatibility.
   """
   
   # Signals for async communication
   authentication_required = pyqtSignal(str)  # Authentication type required
   service_status_changed = pyqtSignal(str, bool)  # Service name, operational status
   
   def __init__(self, 
                config: BRIDealConfig,
                cache_handler: CacheHandler,
                token_handler: TokenHandler,
                secure_config: SecureConfig,
                task_manager: AsyncTaskManager,
                sharepoint_manager: Optional[SharePointManagerService] = None,
                jd_auth_manager: Optional[JDAuthManager] = None,
                jd_quote_integration_service: Optional[JDQuoteIntegrationService] = None,
                parent: Optional[QWidget] = None):
       super().__init__(parent)
       
       # Core components
       self.config = config
       self.cache_handler = cache_handler
       self.token_handler = token_handler
       self.secure_config = secure_config
       self.task_manager = task_manager
       
       # Service components
       self.sharepoint_manager_service = sharepoint_manager
       self.jd_auth_manager_service = jd_auth_manager
       self.jd_quote_integration_service = jd_quote_integration_service
       
       # UI components
       self.theme_manager = None
       self.modules: Dict[str, QWidget] = {}
       self.module_icons_paths: Dict[str, str] = {}
       
       # Performance monitoring
       self.performance_monitor = get_performance_monitor()
       self.http_client_manager = get_http_client_manager()
       
       # Status tracking
       self.service_status: Dict[str, bool] = {}
       self.last_error: Optional[BRIDealException] = None
       
       # Timers for periodic tasks
       self.status_check_timer = QTimer()
       self.performance_report_timer = QTimer()
       
       # Initialize logger for this instance
       self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
       self.logger.info(f"MainWindow initializing with config: {config.app_name} v{config.app_version}")
       
       # Connect signals
       self.authentication_required.connect(self._handle_authentication_required)
       self.service_status_changed.connect(self._handle_service_status_change)
       
       try:
           self._init_ui()
           self._setup_periodic_tasks()
           self._load_modules()
           self._check_initial_service_status()
           
           self.logger.info(f"{config.app_name} v{config.app_version} MainWindow initialized successfully.")
           self.show_status_message(f"Welcome to {config.app_name}!", "info")
           
       except Exception as e:
           error_context = BRIDealException.create_context(
               code="MAINWINDOW_INIT_ERROR",
               message=f"Failed to initialize main window: {str(e)}",
               severity=ErrorSeverity.CRITICAL,
               details={"exception_type": type(e).__name__}
           )
           self._handle_critical_error(BRIDealException(error_context))

   def _init_ui(self):
       """Initialize the user interface with enhanced error handling and PyQt6 updates"""
       try:
           # Window configuration
           self.setWindowTitle(f"{self.config.app_name} - v{self.config.app_version}")
           self.setGeometry(100, 100, self.config.window_width, self.config.window_height)
           
           # Initialize theme manager
           self.theme_manager = ThemeManager(
               config=self.config, 
               resource_path_base=self.config.resources_dir
           )
           self.theme_manager.apply_theme(self.config.theme)
           
           # Set application icon
           self._set_application_icon()
           
           # Create main layout
           central_widget = QWidget()
           self.setCentralWidget(central_widget)
           main_layout = QHBoxLayout(central_widget)
           
           # Create navigation panel
           nav_panel = self._create_navigation_panel()
           main_layout.addWidget(nav_panel)
           
           # Create content area
           self.stacked_widget = QStackedWidget()
           main_layout.addWidget(self.stacked_widget, 1)
           
           # Initialize status bar
           self.statusBar().showMessage("Ready")
           
           self.logger.info("UI initialized successfully")
           
       except Exception as e:
           self.logger.error(f"Failed to initialize UI: {e}", exc_info=True)
           raise

   def _set_application_icon(self):
       """Set application icon with fallback handling"""
       try:
           app_icon_path = get_resource_path(
               self.config.get("APP_ICON_PATH", "icons/app_icon.png"), 
               self.config
           )
           
           if app_icon_path and Path(app_icon_path).exists():
               self.setWindowIcon(QIcon(app_icon_path))
               self.logger.info(f"Application icon set from: {app_icon_path}")
           else:
               self.logger.warning(f"Application icon not found at: {app_icon_path}")
               
       except Exception as e:
           self.logger.warning(f"Failed to set application icon: {e}")

   def _create_navigation_panel(self) -> QWidget:
       """Create the navigation panel with improved layout and PyQt6 updates"""
       nav_panel = QWidget()
       
       nav_panel_width = 130  # Adjusted panel width for icon-over-text
       nav_panel.setFixedWidth(nav_panel_width)
       
       nav_layout = QVBoxLayout(nav_panel)
       nav_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
       
       # Application title
       app_title_label = QLabel(self.config.app_name)
       app_title_font = QFont("Arial", 16, QFont.Weight.Bold)
       app_title_label.setFont(app_title_font)
       app_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
       app_title_label.setWordWrap(True)
       nav_layout.addWidget(app_title_label)
       
       # Version and status info
       version_label = QLabel(f"Version {self.config.app_version}")
       version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
       version_label.setStyleSheet("color: gray; font-size: 10px;")
       nav_layout.addWidget(version_label)
       
       # Navigation list
       self.nav_list = QListWidget()
       self.nav_list.itemClicked.connect(self._on_nav_item_selected)
       
       self.nav_list.setViewMode(QListView.ViewMode.IconMode)
       
       # Configure IconMode for vertical stacking with text below icons
       self.nav_list.setFlow(QListView.Flow.TopToBottom)
       self.nav_list.setWrapping(False)
       self.nav_list.setResizeMode(QListView.ResizeMode.Adjust)
       self.nav_list.setMovement(QListView.Movement.Static)

       icon_dimension = 48 
       self.nav_list.setIconSize(QSize(icon_dimension, icon_dimension))

       grid_item_width = nav_panel_width - 16 
       grid_item_height = icon_dimension + 30 + 10 
       self.nav_list.setGridSize(QSize(grid_item_width, grid_item_height))
       
       self.nav_list.setSpacing(8) 
       
       nav_layout.addWidget(self.nav_list)
       
       # Service status panel
       status_panel = self._create_service_status_panel()
       nav_layout.addWidget(status_panel)
       # nav_layout.addStretch(1) # Optional: if you want status panel pushed to bottom
       
       return nav_panel

   def _create_service_status_panel(self) -> QWidget:
       """Create service status monitoring panel"""
       status_panel = QWidget()
       status_layout = QVBoxLayout(status_panel)
       
       status_title = QLabel("Service Status")
       status_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
       status_layout.addWidget(status_title)
       
       # Service status indicators
       self.jd_status_label = QLabel("JD API: Checking...")
       self.sharepoint_status_label = QLabel("SharePoint: Checking...")
       self.database_status_label = QLabel("Database: Checking...")
       
       status_layout.addWidget(self.jd_status_label)
       status_layout.addWidget(self.sharepoint_status_label)
       status_layout.addWidget(self.database_status_label)
       
       return status_panel

   def _setup_periodic_tasks(self):
       """Setup periodic maintenance tasks"""
       # Service status check every 5 minutes
       self.status_check_timer.timeout.connect(self._check_service_status)
       self.status_check_timer.start(300000)  # 5 minutes
       
       # Performance report every 30 minutes
       self.performance_report_timer.timeout.connect(self._generate_performance_report)
       self.performance_report_timer.start(1800000)  # 30 minutes
       
       self.logger.info("Periodic tasks configured")

   async def _check_service_status_async(self, *args, **kwargs):
       """Asynchronously check service status - fixed to accept parameters"""
       # Ignore any extra parameters passed by Worker
       try:
           # Check JD API status
           if self.jd_auth_manager_service and self.jd_auth_manager_service.is_operational:
               try:
                   # Handle both sync and async get_access_token methods
                   if asyncio.iscoroutinefunction(self.jd_auth_manager_service.get_access_token):
                       token = await self.jd_auth_manager_service.get_access_token()
                   else:
                       token = self.jd_auth_manager_service.get_access_token()
                   jd_status = token is not None
               except Exception:
                   jd_status = False
           else:
               jd_status = False
           
           self.service_status["jd_api"] = jd_status
           self.service_status_changed.emit("jd_api", jd_status)
           
           # Check SharePoint status
           if self.sharepoint_manager_service and hasattr(self.sharepoint_manager_service, 'is_operational'):
               sp_status = self.sharepoint_manager_service.is_operational
           else:
               sp_status = False
           
           self.service_status["sharepoint"] = sp_status
           self.service_status_changed.emit("sharepoint", sp_status)
           
           # Check database status (if configured)
           db_status = True  # Assume healthy if no database configured
           if hasattr(self.config, 'database_url') and self.config.database_url:
               # TODO: Implement actual database health check
               pass
           
           self.service_status["database"] = db_status
           self.service_status_changed.emit("database", db_status)
           
       except Exception as e:
           self.logger.error(f"Error checking service status: {e}", exc_info=True)

   def _check_service_status(self):
       """Check service status (Qt slot)"""
       try:
           task_id = self.task_manager.run_async_task(
               self._check_service_status_async,
               "Service Status Check"
           )
           self.logger.debug(f"Started service status check task: {task_id}")
       except Exception as e:
           self.logger.error(f"Error starting service status check: {e}", exc_info=True)

   def _check_initial_service_status(self):
       """Check service status on startup"""
       self._check_service_status()

   def _generate_performance_report(self):
       """Generate and log performance report - fixed KeyError issue"""
       try:
           report = self.performance_monitor.get_performance_report()
           slow_functions = self.performance_monitor.get_slow_functions(threshold=0.5)
           
           if slow_functions:
               self.logger.warning(f"Slow functions detected: {slow_functions}")
           
           # Log summary with better error handling
           if report and isinstance(report, dict):
               try:
                   total_calls = sum(
                       data.get('call_count', 0) 
                       for data in report.values() 
                       if isinstance(data, dict) and 'call_count' in data
                   )
                   self.logger.info(f"Performance summary: {len(report)} functions monitored, {total_calls} total calls")
               except (KeyError, TypeError, AttributeError) as e:
                   self.logger.warning(f"Performance report format issue: {e}")
                   self.logger.info(f"Performance summary: {len(report)} functions monitored")
           else:
               self.logger.info("Performance report not available or empty")
           
       except Exception as e:
           self.logger.error(f"Error generating performance report: {e}", exc_info=True)

   def _add_module_to_stack(self, name: str, widget: QWidget, icon_name: Optional[str] = None):
       """Add module to the navigation stack with enhanced error handling"""
       try:
           item = QListWidgetItem(name)
           item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter) # Center text for IconMode
           
           # Get icon
           actual_icon_name = icon_name
           if hasattr(widget, 'get_icon_name') and callable(widget.get_icon_name):
               mod_icon_name = widget.get_icon_name()
               if mod_icon_name:
                   actual_icon_name = mod_icon_name
           
           # Set icon if available
           if actual_icon_name:
               icon_path = self.module_icons_paths.get(actual_icon_name)
               if not icon_path:
                   icons_dir = get_resource_path("icons", self.config)
                   icon_path = os.path.join(icons_dir, actual_icon_name)
               
               if icon_path and os.path.exists(icon_path):
                   item.setIcon(QIcon(icon_path))
                   self.logger.debug(f"Icon loaded for module '{name}': {actual_icon_name}")
               else:
                   self.logger.warning(f"Icon not found for module '{name}': {actual_icon_name}")
           
           # Add to navigation
           self.nav_list.addItem(item)
           self.stacked_widget.addWidget(widget)
           self.modules[name] = widget
           
           self.logger.debug(f"Module '{name}' added successfully")
           
       except Exception as e:
           self.logger.error(f"Failed to add module '{name}': {e}", exc_info=True)
           # Continue with other modules even if one fails

   def _load_modules(self):
       """Load application modules with comprehensive error handling"""
       try:
           self.modules.clear()
           self.module_icons_paths.clear()
           
           # Pre-resolve icon paths
           self._preload_module_icons()
           
           # Load modules with error isolation
           modules_to_load = [
               ("deal_form", self._create_deal_form_view, "New Deal"),
               ("recent_deals", self._create_recent_deals_view, "Recent Deals"),
               ("price_book", self._create_price_book_view, "Price Book"),
               ("used_inventory", self._create_used_inventory_view, "Used Inventory"),
               ("receiving", self._create_receiving_view, "Receiving"),
               ("csv_editors", self._create_csv_editors_view, "Data Editors"),
               ("calculator", self._create_calculator_view, "Calculator"),
                ("jd_quote", self._create_jd_quote_view, "JD External Quote"), # module_key is "jd_quote"
               ("invoice", self._create_invoice_view, "Invoice")
           ]
           
           loaded_modules = 0
           for module_key, module_factory, display_name in modules_to_load:
               try:
                   module_widget = module_factory()
                   if module_widget:
                       # Get display name from module if available
                       actual_display_name = getattr(module_widget, 'MODULE_DISPLAY_NAME', display_name)
                       loaded_modules += 1
                       expected_icon_name = f"{module_key}_icon.png" 
                       self._add_module_to_stack(actual_display_name, module_widget, icon_name=expected_icon_name) # Pass it

                   else:
                       self.logger.warning(f"Module factory returned None for: {module_key}")
                       
               except Exception as e:
                   self.logger.error(f"Failed to load module '{module_key}': {e}", exc_info=True)
                   # Continue loading other modules
           
           self.logger.info(f"Loaded {loaded_modules}/{len(modules_to_load)} modules successfully")
           
           # Set default view
           self._set_default_view()
           
       except Exception as e:
           self.logger.error(f"Critical error loading modules: {e}", exc_info=True)
           self._handle_critical_error(BRIDealException.create_context(
               code="MODULE_LOAD_ERROR",
               message=f"Failed to load application modules: {str(e)}",
               severity=ErrorSeverity.HIGH
           ))

   def _preload_module_icons(self):
       """Preload module icon paths for better performance"""
       known_icon_files = [
           "new_deal_icon.png", "recent_deals_icon.png", "price_book_icon.png",
           "used_inventory_icon.png", "receiving_icon.png", "data_editors_icon.png",
           "calculator_icon.png", "jd_quote_icon.png", "invoice_icon.png"
       ]
       
       for icon_file in known_icon_files:
           try:
               path = get_resource_path(os.path.join("icons", icon_file), self.config)
               if path and os.path.exists(path):
                   self.module_icons_paths[icon_file] = path
               else:
                   self.logger.debug(f"Icon not found during preload: {icon_file}")
           except Exception as e:
               self.logger.warning(f"Error preloading icon {icon_file}: {e}")

   # Module factory methods with error handling
   def _create_deal_form_view(self) -> Optional[DealFormView]:
       """Create deal form view with error handling"""
       try:
           return DealFormView(
               config=self.config,
               main_window=self,
               jd_quote_service=self.jd_quote_integration_service,
               sharepoint_manager=self.sharepoint_manager_service,
               logger_instance=logging.getLogger("DealFormViewLogger")
           )
       except Exception as e:
           self.logger.error(f"Failed to create DealFormView: {e}", exc_info=True)
           return None

   def _create_recent_deals_view(self) -> Optional[RecentDealsView]:
       """Create recent deals view with error handling"""
       try:
           return RecentDealsView(
               config=self.config,
               main_window=self,
               logger_instance=logging.getLogger("RecentDealsViewLogger")
           )
       except Exception as e:
           self.logger.error(f"Failed to create RecentDealsView: {e}", exc_info=True)
           return None

   def _create_price_book_view(self) -> Optional[PriceBookView]:
       """Create price book view with error handling"""
       try:
           return PriceBookView(
               config=self.config,
               main_window=self,
               sharepoint_manager=self.sharepoint_manager_service,
               logger_instance=logging.getLogger("PriceBookViewLogger")
           )
       except Exception as e:
           self.logger.error(f"Failed to create PriceBookView: {e}", exc_info=True)
           return None

   def _create_used_inventory_view(self) -> Optional[UsedInventoryView]:
       """Create used inventory view with error handling"""
       try:
           return UsedInventoryView(
               config=self.config,
               main_window=self,
               sharepoint_manager=self.sharepoint_manager_service,
               logger_instance=logging.getLogger("UsedInventoryViewLogger")
           )
       except Exception as e:
           self.logger.error(f"Failed to create UsedInventoryView: {e}", exc_info=True)
           return None

   def _create_receiving_view(self) -> Optional[ReceivingView]:
       """Create receiving view with error handling"""
       try:
           return ReceivingView(
               config=self.config,
               logger_instance=logging.getLogger("ReceivingViewLogger"),
               thread_pool=self.task_manager.thread_pool if hasattr(self.task_manager, 'thread_pool') else QThreadPool.globalInstance(),
               notification_manager=None,  # TODO: Implement notification manager
               main_window=self
           )
       except Exception as e:
           self.logger.error(f"Failed to create ReceivingView: {e}", exc_info=True)
           return None

   def _create_csv_editors_view(self) -> Optional[CsvEditorsManagerView]:
       """Create CSV editors view with error handling"""
       try:
           return CsvEditorsManagerView(
               config=self.config,
               main_window=self,
               logger_instance=logging.getLogger("CsvEditorsManagerLogger")
           )
       except Exception as e:
           self.logger.error(f"Failed to create CsvEditorsManagerView: {e}", exc_info=True)
           return None

   def _create_calculator_view(self) -> Optional[CalculatorView]:
       """Create calculator view with error handling"""
       try:
           return CalculatorView(
               config=self.config,
               main_window=self,
               logger_instance=logging.getLogger("CalculatorViewLogger")
           )
       except Exception as e:
           self.logger.error(f"Failed to create CalculatorView: {e}", exc_info=True)
           return None

   def _create_jd_quote_view(self) -> Optional[JDExternalQuoteView]:
       """Create JD external quote view with error handling"""
       try:
           return JDExternalQuoteView(
               config=self.config,
               main_window=self,
               jd_quote_integration_service=self.jd_quote_integration_service,
               logger_instance=logging.getLogger("JDExternalQuoteViewLogger")
           )
       except Exception as e:
           self.logger.error(f"Failed to create JDExternalQuoteView: {e}", exc_info=True)
           return None

   def _create_invoice_view(self) -> Optional[InvoiceModuleView]:
       """Create invoice view with error handling"""
       try:
           return InvoiceModuleView(
               config=self.config,
               main_window=self,
               jd_quote_integration_service=self.jd_quote_integration_service,
               logger_instance=logging.getLogger("InvoiceModuleViewLogger")
           )
       except Exception as e:
           self.logger.error(f"Failed to create InvoiceModuleView: {e}", exc_info=True)
           return None

   def _set_default_view(self):
       """Set the default view with error handling"""
       try:
           if self.nav_list.count() > 0:
               # Try to find the default module
               default_module_title = "New Deal"
               items = self.nav_list.findItems(default_module_title, Qt.MatchFlag.MatchExactly)  # Updated for PyQt6
               
               if items:
                   self.nav_list.setCurrentItem(items[0])
                   self._on_nav_item_selected(items[0])
               else:
                   # Fallback to first item
                   self.nav_list.setCurrentRow(0)
                   if self.nav_list.currentItem():
                       self._on_nav_item_selected(self.nav_list.currentItem())
                   self.logger.warning(f"Default module '{default_module_title}' not found. Using first available module.")
           else:
               self.logger.warning("No modules available for default view")
               
       except Exception as e:
           self.logger.error(f"Failed to set default view: {e}", exc_info=True)

   def _on_nav_item_selected(self, item: QListWidgetItem):
       """Handle navigation item selection with error handling"""
       try:
           module_name = item.text()
           if module_name in self.modules:
               current_module_widget = self.modules[module_name]
               self.stacked_widget.setCurrentWidget(current_module_widget)
               
               self.logger.debug(f"Switched to module: {module_name}")
               self.show_status_message(f"Viewing: {module_name}", "info")
               
               # Load module data if available
               if hasattr(current_module_widget, 'load_module_data') and callable(current_module_widget.load_module_data):
                   try:
                       current_module_widget.load_module_data()
                   except Exception as e:
                       self.logger.error(f"Error loading data for module {module_name}: {e}", exc_info=True)
                       self.show_status_message(f"Warning: Failed to load data for {module_name}", "warning")
           else:
               self.logger.error(f"Module '{module_name}' not found in modules dictionary")
               
       except Exception as e:
           self.logger.error(f"Error switching to module: {e}", exc_info=True)

   def show_status_message(self, message: str, level: str = "info", duration: int = 5000):
       """Show status message with enhanced logging"""
       try:
           self.statusBar().showMessage(message, duration if duration > 0 else 0)
           
           # Log with appropriate level
           log_func = getattr(self.logger, level, self.logger.info)
           log_func(f"Status: {message}")
           
       except Exception as e:
           self.logger.error(f"Error showing status message: {e}")

   def navigate_to_invoice(self, quote_id: str, dealer_account_no: str):
       """Navigate to invoice view with enhanced error handling"""
       try:
           self.logger.info(f"Navigating to invoice view for quote ID: {quote_id}")
           
           # Find invoice module
           invoice_module_key = None
           invoice_module = None
           
           for name, module_instance in self.modules.items():
               if isinstance(module_instance, InvoiceModuleView):
                   invoice_module_key = name
                   invoice_module = module_instance
                   break
           
           if not invoice_module:
               raise ValidationError("invoice_module", "Invoice module not available")
           
           # Navigate to invoice module
           items = self.nav_list.findItems(invoice_module_key, Qt.MatchFlag.MatchExactly)  # Updated for PyQt6
           if items:
               self.nav_list.setCurrentItem(items[0])
               self._on_nav_item_selected(items[0])
           else:
               self.stacked_widget.setCurrentWidget(invoice_module)
               if hasattr(invoice_module, 'load_module_data'):
                   invoice_module.load_module_data()
           
           # Initiate invoice creation
           if hasattr(invoice_module, 'initiate_invoice_from_quote'):
               invoice_module.initiate_invoice_from_quote(quote_id, dealer_account_no)
           
           self.show_status_message(f"Viewing invoice for Quote ID: {quote_id}", "info")
           
       except Exception as e:
           error_msg = f"Failed to navigate to invoice for quote {quote_id}: {str(e)}"
           self.logger.error(error_msg, exc_info=True)
           QMessageBox.warning(self, "Navigation Error", error_msg)

   def check_jd_authentication(self) -> bool:
       """Check John Deere API authentication with enhanced error handling"""
       try:
           if not self.jd_auth_manager_service:
               self.logger.warning("JD Auth Manager not available for authentication check")
               return False
           
           if not self.jd_auth_manager_service.is_operational:
               self.logger.warning("JD Auth Manager is not operational")
               return False
           
           # Check for valid token
           token = self.jd_auth_manager_service.get_access_token()
           if token:
               self.logger.info("JD API authentication token is available and valid")
               return True
           
           # No valid token - prompt for authentication
           self.logger.info("No valid JD API token found, showing authentication dialog")
           return self._prompt_jd_authentication()
           
       except Exception as e:
           self.logger.error(f"Error checking JD authentication: {e}", exc_info=True)
           return False

   def _prompt_jd_authentication(self) -> bool:
       """Prompt user for JD authentication with PyQt6 updates"""
       try:
           result = QMessageBox.question(
               self,
               "John Deere API Authentication",
               "John Deere API authentication is required for quoting features. "
               "Would you like to authenticate now?",
               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No  # Updated for PyQt6
           )
           
           if result == QMessageBox.StandardButton.Yes:  # Updated for PyQt6
               from app.views.dialogs.jd_auth_dialog import JDAuthDialog
               auth_dialog = JDAuthDialog(self.jd_auth_manager_service, self)
               auth_dialog.auth_completed.connect(self.on_jd_auth_completed)
               return auth_dialog.exec() == QDialog.DialogCode.Accepted  # Updated for PyQt6
           
           return False
           
       except ImportError:
           self.logger.error("JDAuthDialog not available")
           QMessageBox.critical(self, "Error", "Authentication dialog is not available.")
           return False
       except Exception as e:
           self.logger.error(f"Error prompting for JD authentication: {e}", exc_info=True)
           return False

   def on_jd_auth_completed(self, success: bool, message: str):
       """Handle JD API authentication completion"""
       try:
           if success:
               self.logger.info("JD API authentication completed successfully")
               self.show_status_message("John Deere API connection established", "info")
               
               # Update service status
               self.service_status["jd_api"] = True
               self.service_status_changed.emit("jd_api", True)
               
               # Update integration service operational status
               if self.jd_quote_integration_service:
                   self.jd_quote_integration_service.is_operational = True
           else:
               self.logger.warning(f"JD API authentication failed: {message}")
               self.show_status_message("John Deere API authentication failed", "warning")
               
               # Update service status
               self.service_status["jd_api"] = False
               self.service_status_changed.emit("jd_api", False)
               
       except Exception as e:
           self.logger.error(f"Error handling JD auth completion: {e}", exc_info=True)

   def _handle_authentication_required(self, auth_type: str):
       """Handle authentication required signal"""
       try:
           if auth_type == "jd_api":
               self.check_jd_authentication()
           else:
               self.logger.warning(f"Unknown authentication type requested: {auth_type}")
               
       except Exception as e:
           self.logger.error(f"Error handling authentication requirement: {e}", exc_info=True)

   def _handle_service_status_change(self, service_name: str, is_operational: bool):
       """Handle service status change"""
       try:
           status_text = "✓ Online" if is_operational else "✗ Offline"
           status_color = "green" if is_operational else "red"
           
           if service_name == "jd_api":
               self.jd_status_label.setText(f"JD API: {status_text}")
               self.jd_status_label.setStyleSheet(f"color: {status_color};")
           elif service_name == "sharepoint":
               self.sharepoint_status_label.setText(f"SharePoint: {status_text}")
               self.sharepoint_status_label.setStyleSheet(f"color: {status_color};")
           elif service_name == "database":
               self.database_status_label.setText(f"Database: {status_text}")
               self.database_status_label.setStyleSheet(f"color: {status_color};")
           
           self.logger.debug(f"Service status updated: {service_name} = {is_operational}")
           
       except Exception as e:
           self.logger.error(f"Error updating service status display: {e}", exc_info=True)

   def _handle_critical_error(self, error: BRIDealException):
       """Handle critical errors that may require application shutdown"""
       try:
           self.last_error = error
           self.logger.critical(f"Critical error: {error.context.message}", extra={"error_context": error.context})
           
           # Show critical error dialog
           QMessageBox.critical(
               self,
               "Critical Application Error",
               f"A critical error has occurred:\n\n{error.context.user_message or error.context.message}\n\n"
               f"The application may not function properly. Please restart the application."
           )
           
           # Optionally trigger graceful shutdown
           if error.context.severity == ErrorSeverity.CRITICAL:
               self.logger.critical("Initiating graceful shutdown due to critical error")
               QTimer.singleShot(1000, self.close)  # Delay to allow user to read message
               
       except Exception as e:
           self.logger.error(f"Error handling critical error: {e}", exc_info=True)

   def closeEvent(self, event):
       """Enhanced close event with proper cleanup"""
       try:
           self.logger.info("MainWindow closing. Performing enhanced cleanup...")
           
           # Stop periodic timers
           self.status_check_timer.stop()
           self.performance_report_timer.stop()
           
           # Shutdown task manager
           if self.task_manager:
               self.task_manager.shutdown()
           
           # Generate final performance report
           try:
               self._generate_performance_report()
           except Exception as e:
               self.logger.warning(f"Error generating final performance report: {e}")
           
           # Save configuration if needed
           try:
               if hasattr(self.config, 'save_user_preferences'):
                   self.config.save_user_preferences()
           except Exception as e:
               self.logger.warning(f"Error saving user preferences: {e}")
           
           self.logger.info("MainWindow cleanup completed successfully")
           event.accept()
           
       except Exception as e:
           self.logger.error(f"Error during application shutdown: {e}", exc_info=True)
           event.accept()  # Always accept to prevent hanging


async def run_application():
   """
   Enhanced application runner with modern async architecture and comprehensive error handling.
   Updated for PyQt6 compatibility.
   """
   try:
       # Initialize configuration
       config = get_config()
       
       # Setup logging as early as possible
       setup_logging(config)
       logger.info(f"Starting {config.app_name} v{config.app_version}")
       logger.info(f"Environment: {config.environment}")
       logger.info(f"Debug mode: {config.debug}")
       
       # Resource checks
       logger.info("Starting resource checks...")
       check_resources(config)
       
       # Set application ID for Windows
       app_id = config.get("APP_USER_MODEL_ID", f"BRIDeal.{config.app_version}")
       set_app_user_model_id(app_id)
       
       # Initialize security
       secure_config = SecureConfig(config.app_name)
       logger.info("Secure configuration initialized")
       
       # Initialize performance monitoring
       performance_monitor = get_performance_monitor()
       http_client_manager = get_http_client_manager()
       logger.info("Performance monitoring initialized")
       
       # Initialize core services
       app_auth_service = AppAuthService(config=config)
       logger.info(f"Current application user: {app_auth_service.get_current_user_name()}")
       
       cache_handler = CacheHandler(config=config)
       token_handler = TokenHandler(config=config, cache_handler=cache_handler)
       task_manager = get_task_manager()
       
       # Initialize SharePoint service with enhanced error handling
       sharepoint_service_instance = await _initialize_sharepoint_service()
       
       # Initialize John Deere services
       quote_builder = QuoteBuilder(config=config)
       jd_auth_manager = JDAuthManager(config=config, token_handler=token_handler)
       jd_quote_api_client = JDQuoteApiClient(config=config, auth_manager=jd_auth_manager)
       maintain_quotes_api = MaintainQuotesAPI(config=config, jd_quote_api_client=jd_quote_api_client)
       jd_quote_integration_service = JDQuoteIntegrationService(
           config=config,
           maintain_quotes_api=maintain_quotes_api,
           quote_builder=quote_builder
       )
       
       # Fix potential authentication configuration issues
       try:
           await _fix_authentication_config(config, jd_auth_manager)
       except Exception as e:
           logger.warning(f"Error fixing authentication config: {e}")
       
       # Create Qt application
       qt_app = QApplication.instance()
       if qt_app is None:
           qt_app = QApplication(sys.argv)
       
       # Configure Qt application
       qt_app.setApplicationName(config.app_name)
       qt_app.setApplicationVersion(config.app_version)
       qt_app.setOrganizationName(config.get("ORGANIZATION_NAME", "BRIDeal"))
       
       # Set application icon
       await _set_qt_application_icon(qt_app, config)
       
       # Show splash screen
       splash_screen = await _create_splash_screen(qt_app, config)
       
       try:
           # Create and show main window
           splash_screen.showMessage("Loading main interface...", Qt.AlignmentFlag.AlignBottom)  # Updated for PyQt6
           qt_app.processEvents()
           
           main_window = MainWindow(
               config=config,
               cache_handler=cache_handler,
               token_handler=token_handler,
               secure_config=secure_config,
               task_manager=task_manager,
               sharepoint_manager=sharepoint_service_instance,
               jd_auth_manager=jd_auth_manager,
               jd_quote_integration_service=jd_quote_integration_service
           )
           
           main_window.show()
           splash_screen.finish(main_window)
           
           logger.info("Application startup completed successfully")
           
           # Run application
           exit_code = qt_app.exec()  # Updated for PyQt6 (removed underscore)
           
           # Cleanup
           await _cleanup_application_resources()
           
           logger.info(f"Application exited with code: {exit_code}")
           return exit_code
           
       except Exception as e:
           splash_screen.close()
           logger.critical(f"Failed to initialize main window: {e}", exc_info=True)
           
           QMessageBox.critical(
               None,
               "Application Initialization Error",
               f"A critical error occurred while loading the main application:\n\n{e}\n\n"
               "Please check the logs for more details and restart the application."
           )
           return 1
           
   except Exception as e:
       logger.critical(f"Critical application startup failure: {e}", exc_info=True)
       
       try:
           # Try to show error dialog even on critical failure
           app_temp = QApplication.instance()
           if not app_temp:
               app_temp = QApplication(sys.argv)
           
           QMessageBox.critical(
               None,
               "Critical Application Failure",
               f"The application failed to start due to a critical error:\n\n{e}\n\n"
               "Please check the system requirements and try again."
           )
       except Exception as dialog_error:
           print(f"CRITICAL ERROR: {e}", file=sys.stderr)
           print(f"Failed to show error dialog: {dialog_error}", file=sys.stderr)
       
       return 1


async def _initialize_sharepoint_service() -> Optional[SharePointManagerService]:
   """Initialize SharePoint service with proper error handling"""
   sharepoint_service_instance = None
   
   try:
       if SharePointManagerService:
           logger.info("Attempting to initialize SharePoint service...")
           sharepoint_service_instance = SharePointManagerService()
           
           if hasattr(sharepoint_service_instance, 'is_operational'):
               if sharepoint_service_instance.is_operational:
                   logger.info("SharePoint service initialized and operational")
               else:
                   logger.warning("SharePoint service initialized but not operational")
           else:
               logger.warning("SharePoint service lacks operational status indicator")
       else:
           logger.error("SharePoint service class not available")
           
   except Exception as e:
       logger.error(f"Failed to initialize SharePoint service: {e}", exc_info=True)
       sharepoint_service_instance = None
   
   return sharepoint_service_instance


async def _fix_authentication_config(config: BRIDealConfig, jd_auth_manager: JDAuthManager):
   """Fix potential authentication configuration issues"""
   try:
       from app.services.integrations.jd_auth_manager_improvements import (
           check_and_fix_redirect_uri, 
           ensure_auth_persistence
       )
       
       redirect_uri_fixed = check_and_fix_redirect_uri(config)
       persistence_enabled = ensure_auth_persistence(config)
       
       if redirect_uri_fixed or persistence_enabled:
           logger.info("Fixed John Deere API authentication configuration issues")
       
       # Check authentication status
       if jd_auth_manager and jd_auth_manager.is_operational:
           logger.info("Checking JD API authentication status on startup")
           token = jd_auth_manager.get_access_token()
           if asyncio.iscoroutinefunction(jd_auth_manager.get_access_token):
               token = await jd_auth_manager.get_access_token()
           else:
               token = jd_auth_manager.get_access_token()
           if not token:
               logger.info("No valid JD API token found at startup")
       
   except ImportError:
       logger.warning("JD auth improvements module not available")
   except Exception as e:
       logger.warning(f"Error checking/fixing authentication configuration: {e}", exc_info=True)


async def _set_qt_application_icon(qt_app: QApplication, config: BRIDealConfig):
   """Set Qt application icon with fallback handling"""
   try:
       icon_path_config = config.get("APP_ICON_PATH", "icons/app_icon.png")
       icon_abs_path = get_resource_path(icon_path_config, config)
       
       if icon_abs_path and os.path.exists(icon_abs_path):
           qt_app.setWindowIcon(QIcon(icon_abs_path))
           logger.info(f"Qt application icon set from: {icon_abs_path}")
       else:
           logger.warning(f"Qt application icon not found: {icon_abs_path}")
           
   except Exception as e:
       logger.warning(f"Failed to set Qt application icon: {e}")


async def _create_splash_screen(qt_app: QApplication, config: BRIDealConfig) -> QSplashScreen:
   """Create and display splash screen with PyQt6 updates"""
   try:
       splash_image_config = config.get("SPLASH_IMAGE_MAIN", "images/splash_main.png")
       splash_image_path = get_resource_path(splash_image_config, config)
       
       if splash_image_path and os.path.exists(splash_image_path):
           pixmap = QPixmap(splash_image_path)
           splash_screen = QSplashScreen(pixmap)
       else:
           # Fallback to simple splash screen
           logger.warning(f"Splash image not found: {splash_image_path}")
           pixmap = QPixmap(400, 300)
           pixmap.fill(Qt.GlobalColor.darkBlue)  # Updated for PyQt6
           splash_screen = QSplashScreen(pixmap)
       
       splash_screen.show()
       splash_screen.showMessage(
           f"Starting {config.app_name} v{config.app_version}...",
           Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,  # Updated for PyQt6
           Qt.GlobalColor.white  # Updated for PyQt6
       )
       qt_app.processEvents()
       
       return splash_screen
       
   except Exception as e:
       logger.warning(f"Failed to create splash screen: {e}")
       # Return a minimal splash screen
       pixmap = QPixmap(400, 200)
       pixmap.fill(Qt.GlobalColor.gray)  # Updated for PyQt6
       return QSplashScreen(pixmap)


async def _cleanup_application_resources():
   """Cleanup application resources"""
   try:
       logger.info("Cleaning up application resources...")
       
       # Cleanup performance resources
       await cleanup_performance_resources()
       
       # Additional cleanup can be added here
       logger.info("Application resource cleanup completed")
       
   except Exception as e:
       logger.error(f"Error during resource cleanup: {e}", exc_info=True)


def main():
   """Main entry point for the application"""
   # Basic logging for pre-config errors
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(levelname)s - PRE_CONFIG - %(message)s'
   )
   
   try:
       # Run the async application
       exit_code = asyncio.run(run_application())
       sys.exit(exit_code)
       
   except KeyboardInterrupt:
       logger.info("Application interrupted by user")
       sys.exit(0)
   except Exception as e:
       # Last resort error handling
       critical_logger = logging.getLogger("critical_launch_error")
       critical_logger.critical(f"Unhandled exception during application launch: {e}", exc_info=True)
       
       try:
           app_temp = QApplication.instance()
           if not app_temp:
               app_temp = QApplication(sys.argv)
           
           QMessageBox.critical(
               None,
               "Critical Application Failure",
               f"An unhandled error occurred:\n\n{e}\n\n"
               "Please check logs and restart the application."
           )
       except Exception as dialog_error:
           print(f"CRITICAL ERROR: {e}", file=sys.stderr)
           print(f"Failed to show error dialog: {dialog_error}", file=sys.stderr)
       
       sys.exit(1)


if __name__ == '__main__':
   main()