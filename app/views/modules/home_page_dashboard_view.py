# File: app/views/modules/home_page_dashboard_view.py

import logging
import json
import requests # For making HTTP requests to weather API
import datetime # For handling dates for historical forex data
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer # Added QTimer
from PyQt6.QtGui import QFont

from app.views.modules.base_view_module import BaseViewModule
# Placeholder for API clients or services if needed in the future
# from app.services.weather_service import WeatherService
# from app.services.forex_service import ForexService
# from app.services.commodity_service import CommodityService
# from app.services.crypto_service import CryptoService

# --- Constants ---
# TODO: Replace "YOUR_API_KEY_HERE" with a real OpenWeatherMap API key.
# This key should ideally be loaded from a configuration file or environment variable.
OPENWEATHERMAP_API_KEY = "YOUR_API_KEY_HERE" # TODO: Replace with your OpenWeatherMap API key
OPENWEATHERMAP_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# TODO: Replace "YOUR_API_KEY_HERE" with a real ExchangeRate-API key.
# This key should ideally be loaded from a configuration file or environment variable.
EXCHANGERATE_API_KEY = "YOUR_API_KEY_HERE" # TODO: Replace with your ExchangeRate-API key
EXCHANGERATE_BASE_URL = "https://v6.exchangerate-api.com/v6/"

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3/"

# Define cities with details for querying and display
# Using "City,CountryCode" for q parameter in OpenWeatherMap. Province can be part of city name for specificity.
CITIES_DETAILS: List[Dict[str, str]] = [
    {"key": "Camrose", "display_name": "Camrose, AB", "query": "Camrose,CA"},
    {"key": "Wainwright", "display_name": "Wainwright, AB", "query": "Wainwright,CA"},
    {"key": "Killam", "display_name": "Killam, AB", "query": "Killam,CA"},
    {"key": "Provost", "display_name": "Provost, AB", "query": "Provost,CA"},
]

class HomePageDashboardView(BaseViewModule):
    """
    A dashboard view to display various information widgets like weather,
    forex, commodity prices, and cryptocurrency prices.
    """
    MODULE_DISPLAY_NAME = "Home Dashboard"

    def __init__(self,
                 config: Optional[dict] = None,
                 logger_instance: Optional[logging.Logger] = None,
                 main_window: Optional[QWidget] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(
            module_name=self.MODULE_DISPLAY_NAME,
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )

        # Initialize API clients - placeholders for now
        # self.weather_service = WeatherService(api_key=self.config.get("WEATHER_API_KEY"))
        # self.forex_service = ForexService(api_key=self.config.get("FOREX_API_KEY"))
        # self.commodity_service = CommodityService(api_key=self.config.get("COMMODITY_API_KEY"))
        # self.crypto_service = CryptoService() # Assuming it doesn't need API key for BTC

        self._init_ui()
        self.load_module_data() # Initial data load

        # Setup QTimer for periodic refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all_data)

        # Get refresh interval from config or use default (1 hour = 3600 * 1000 ms)
        # Note: self.config is available from BaseViewModule's __init__
        refresh_interval_ms = 3600 * 1000 # Default to 1 hour
        if self.config and hasattr(self.config, 'get') and callable(self.config.get):
            refresh_interval_ms = self.config.get("DASHBOARD_REFRESH_INTERVAL_MS", refresh_interval_ms)
        elif isinstance(self.config, dict): # Fallback if config is a dict but no .get method (less likely)
             refresh_interval_ms = self.config.get("DASHBOARD_REFRESH_INTERVAL_MS", refresh_interval_ms)
        else:
            self.logger.warning("Config object not available or 'get' method missing; using default refresh interval.")

        self.refresh_timer.start(refresh_interval_ms)
        self.logger.info(f"Dashboard refresh timer started with interval: {refresh_interval_ms / 1000 / 60:.2f} minutes.")

    def _init_ui(self):
        """Initialize the user interface of the dashboard."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15) # Increased margins
        main_layout.setSpacing(25) # Increased spacing

        # --- Title ---
        title_label = QLabel(self.MODULE_DISPLAY_NAME)
        title_font = QFont("Arial", 18, QFont.Weight.Bold) # Larger title font
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # --- Main Grid for Sections (2 columns) ---
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)

        # --- Weather Section ---
        weather_frame = QFrame()
        weather_frame.setFrameShape(QFrame.Shape.StyledPanel)
        weather_frame.setObjectName("DashboardSectionFrame") # For styling
        weather_layout = QVBoxLayout(weather_frame)

        weather_title = QLabel("🌦️ Current Weather")
        weather_title.setFont(QFont("Arial", 14, QFont.Weight.Bold)) # Section title font
        weather_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        weather_layout.addWidget(weather_title)

        self.weather_grid_layout = QGridLayout()
        self.weather_grid_layout.setSpacing(10)

        self.weather_labels: Dict[str, QLabel] = {}
        for i, city_info in enumerate(CITIES_DETAILS):
            label = QLabel(f"{city_info['display_name']}: Fetching...")
            label.setFont(QFont("Arial", 10))
            self.weather_grid_layout.addWidget(label, i // 2, i % 2) # 2 cities per row
            self.weather_labels[city_info['key']] = label

        weather_layout.addLayout(self.weather_grid_layout)
        weather_layout.addStretch() # Pushes content to top
        grid_layout.addWidget(weather_frame, 0, 0) # Add to main grid

        # --- Financial Trends Section ---
        financial_frame = QFrame()
        financial_frame.setFrameShape(QFrame.Shape.StyledPanel)
        financial_frame.setObjectName("DashboardSectionFrame") # For styling
        financial_layout = QVBoxLayout(financial_frame)

        financial_title = QLabel("💹 Market Trends (Weekly)")
        financial_title.setFont(QFont("Arial", 14, QFont.Weight.Bold)) # Section title font
        financial_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        financial_layout.addWidget(financial_title)

        self.forex_usdcad_label = QLabel("🇺🇸🇨🇦 USD-CAD: Fetching...")
        self.forex_usdcad_label.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        financial_layout.addWidget(self.forex_usdcad_label)

        self.canola_price_label = QLabel("🌾 Canola: Fetching...")
        self.canola_price_label.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        financial_layout.addWidget(self.canola_price_label)

        self.btc_price_label = QLabel("₿ BTC-USD: Fetching...")
        self.btc_price_label.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        financial_layout.addWidget(self.btc_price_label)

        financial_layout.addStretch() # Pushes content to top
        grid_layout.addWidget(financial_frame, 0, 1) # Add to main grid

        main_layout.addLayout(grid_layout)
        main_layout.addStretch() # Pushes sections to top

        # Example of how to apply a common stylesheet (can be expanded)
        self.setStyleSheet("""
            #DashboardSectionFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
            }
            QLabel {
                color: #343a40; /* Darker text for better readability */
            }
        """)

    def load_module_data(self):
        """
        Loads or triggers the loading of data for the dashboard widgets.
        """
        self.logger.info(f"'{self.MODULE_DISPLAY_NAME}' module data loading initiated.")
        self._update_status("Data loading initiated...")

        # Fetch weather data
        # TODO: Consider running network calls in a separate thread using self.thread_pool
        # from app.core.threading import Worker
        # worker = Worker(self._fetch_weather_data)
        # worker.signals.finished.connect(lambda: self.logger.info("Weather fetch thread finished.")) # Example
        # self.thread_pool.start(worker) # Assuming self.thread_pool is initialized in BaseViewModule or here
        self._fetch_weather_data()
        self._fetch_forex_data()
        self._fetch_crypto_prices()
        self._fetch_commodity_prices()

    def _refresh_all_data(self):
        """Slot for the QTimer to refresh all dashboard data."""
        self.logger.info("Timer triggered: Refreshing all dashboard data...")
        self._update_status("Refreshing data (timer)...")

        # Call all individual data fetching methods
        # TODO: Consider if these fetches should be done in separate threads
        # if they become too time-consuming and block the UI.
        self._fetch_weather_data()
        self._fetch_forex_data()
        self._fetch_crypto_prices()
        self._fetch_commodity_prices() # This will just update to N/A as per current implementation

        self._update_status("Dashboard data refreshed (timer).")

    def _fetch_weather_data(self):
        self.logger.info("Fetching weather data...")

        if OPENWEATHERMAP_API_KEY == "YOUR_API_KEY_HERE":
            self.logger.warning("OpenWeatherMap API key is not set. Weather data will not be fetched.")
            for city_info in CITIES_DETAILS:
                if city_info['key'] in self.weather_labels:
                    self.weather_labels[city_info['key']].setText(f"{city_info['display_name']}: API Key Required")
            self._update_status("Weather: API Key Required")
            return

        for city_info in CITIES_DETAILS:
            city_key = city_info['key']
            city_display_name = city_info['display_name']
            city_query = city_info['query']

            if city_key not in self.weather_labels:
                self.logger.warning(f"Label for city key '{city_key}' not found.")
                continue

            try:
                url = f"{OPENWEATHERMAP_BASE_URL}?q={city_query}&appid={OPENWEATHERMAP_API_KEY}&units=metric"
                response = requests.get(url, timeout=10) # Added timeout
                response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)

                data = response.json()

                if data.get("cod") != 200: # Check OpenWeatherMap specific error code
                    error_message = data.get("message", "Unknown API error")
                    self.logger.error(f"Error fetching weather for {city_display_name} from API: {error_message}")
                    self.weather_labels[city_key].setText(f"{city_display_name}: API Error")
                    continue

                temp = data.get('main', {}).get('temp')
                condition = data.get('weather', [{}])[0].get('description', 'N/A')

                if temp is not None:
                    self.weather_labels[city_key].setText(f"{city_display_name}: {temp:.1f}°C, {condition.capitalize()}")
                else:
                    self.weather_labels[city_key].setText(f"{city_display_name}: Data N/A")

            except requests.exceptions.Timeout:
                self.logger.error(f"Timeout fetching weather for {city_display_name}.")
                self.weather_labels[city_key].setText(f"{city_display_name}: Timeout")
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching weather for {city_display_name}: {e}", exc_info=True)
                self.weather_labels[city_key].setText(f"{city_display_name}: Network Error")
            except json.JSONDecodeError:
                self.logger.error(f"Error decoding JSON response for {city_display_name}.")
                self.weather_labels[city_key].setText(f"{city_display_name}: Data Error")
            except Exception as e:
                self.logger.error(f"Unexpected error processing weather for {city_display_name}: {e}", exc_info=True)
                self.weather_labels[city_key].setText(f"{city_display_name}: Error")

        self._update_status("Weather data fetch attempt complete.")

    def _fetch_forex_data(self):
        self.logger.info("Fetching USD-CAD forex data...")
        self._update_status("Fetching USD-CAD data...")

        if EXCHANGERATE_API_KEY == "YOUR_API_KEY_HERE":
            self.logger.warning("ExchangeRate-API key is not set. Forex data will not be fetched.")
            self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: API Key Required")
            self._update_status("Forex: API Key Required")
            return

        current_rate: Optional[float] = None
        historical_rate: Optional[float] = None

        # Fetch current rate
        try:
            url_latest = f"{EXCHANGERATE_BASE_URL}{EXCHANGERATE_API_KEY}/latest/USD"
            response_latest = requests.get(url_latest, timeout=10)
            response_latest.raise_for_status()
            data_latest = response_latest.json()

            if data_latest.get("result") == "success" and 'conversion_rates' in data_latest:
                current_rate = data_latest['conversion_rates'].get('CAD')
            else:
                error_msg = data_latest.get("error-type", "API error")
                self.logger.error(f"ExchangeRate-API error for latest rate: {error_msg}")
        except requests.exceptions.Timeout:
            self.logger.error("Timeout fetching latest USD-CAD rate.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching latest USD-CAD rate: {e}", exc_info=True)
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON for latest USD-CAD rate.")
        except Exception as e:
            self.logger.error(f"Unexpected error fetching latest USD-CAD rate: {e}", exc_info=True)


        # Fetch historical rate (7 days ago)
        try:
            date_7_days_ago = datetime.date.today() - datetime.timedelta(days=7)
            url_historical = f"{EXCHANGERATE_BASE_URL}{EXCHANGERATE_API_KEY}/history/USD/{date_7_days_ago.year}/{date_7_days_ago.month}/{date_7_days_ago.day}"
            response_historical = requests.get(url_historical, timeout=10)
            response_historical.raise_for_status()
            data_historical = response_historical.json()

            if data_historical.get("result") == "success" and 'conversion_rates' in data_historical:
                historical_rate = data_historical['conversion_rates'].get('CAD')
            else:
                error_msg = data_historical.get("error-type", "API error")
                self.logger.error(f"ExchangeRate-API error for historical rate: {error_msg}")
        except requests.exceptions.Timeout:
            self.logger.error("Timeout fetching historical USD-CAD rate.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching historical USD-CAD rate: {e}", exc_info=True)
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON for historical USD-CAD rate.")
        except Exception as e:
             self.logger.error(f"Unexpected error fetching historical USD-CAD rate: {e}", exc_info=True)

        # Update label
        if current_rate is not None and historical_rate is not None:
            if current_rate > historical_rate:
                trend_arrow = "↑"  # Up
            elif current_rate < historical_rate:
                trend_arrow = "↓"  # Down
            else:
                trend_arrow = "→"  # Stable
            self.forex_usdcad_label.setText(f"🇺🇸🇨🇦 USD-CAD: {current_rate:.4f} {trend_arrow}")
        elif current_rate is not None:
            self.forex_usdcad_label.setText(f"🇺🇸🇨🇦 USD-CAD: {current_rate:.4f} (Trend N/A)")
        else:
            self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: Data N/A")

        self._update_status("Forex data fetch attempt complete.")

    def _fetch_commodity_prices(self):
        self.logger.info("Attempting to fetch commodity prices (e.g., Canola)...")
        # TODO: Integrate a real Canola price API.
        # Finding a free, reliable public API for daily/weekly Canola spot/futures prices
        # is challenging. A dedicated agricultural data provider or a financial markets API
        # with commodity coverage (often paid) would likely be required.
        # For now, we are indicating that the data is not available.

        self.canola_price_label.setText("🌾 Canola: Price Data N/A")
        self.logger.info("Canola price data is not integrated due to lack of a readily available free public API.")
        self._update_status("Canola Price: Data N/A")

    def _fetch_crypto_prices(self):
        self.logger.info("Fetching BTC-USD price data from CoinGecko...")
        self._update_status("Fetching BTC-USD data...")

        current_btc_price: Optional[float] = None
        historical_btc_price: Optional[float] = None

        # Fetch current BTC price
        try:
            url_current_btc = f"{COINGECKO_BASE_URL}simple/price?ids=bitcoin&vs_currencies=usd"
            response_current_btc = requests.get(url_current_btc, timeout=10)
            response_current_btc.raise_for_status()
            data_current_btc = response_current_btc.json()

            if 'bitcoin' in data_current_btc and 'usd' in data_current_btc['bitcoin']:
                current_btc_price = data_current_btc['bitcoin']['usd']
            else:
                self.logger.error("CoinGecko API response for current price is missing expected data.")
        except requests.exceptions.Timeout:
            self.logger.error("Timeout fetching current BTC price from CoinGecko.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching current BTC price from CoinGecko: {e}", exc_info=True)
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON for current BTC price from CoinGecko.")
        except Exception as e:
            self.logger.error(f"Unexpected error fetching current BTC price: {e}", exc_info=True)

        # Fetch historical BTC price (7 days ago)
        try:
            date_7_days_ago = datetime.date.today() - datetime.timedelta(days=7)
            # CoinGecko API uses dd-mm-yyyy format for historical data
            formatted_date_7_days_ago = date_7_days_ago.strftime('%d-%m-%Y')

            url_historical_btc = f"{COINGECKO_BASE_URL}coins/bitcoin/history?date={formatted_date_7_days_ago}&localization=false"
            response_historical_btc = requests.get(url_historical_btc, timeout=10)
            response_historical_btc.raise_for_status()
            data_historical_btc = response_historical_btc.json()

            if 'market_data' in data_historical_btc and \
               'current_price' in data_historical_btc['market_data'] and \
               'usd' in data_historical_btc['market_data']['current_price']:
                historical_btc_price = data_historical_btc['market_data']['current_price']['usd']
            else:
                self.logger.error("CoinGecko API response for historical price is missing expected data.")
        except requests.exceptions.Timeout:
            self.logger.error("Timeout fetching historical BTC price from CoinGecko.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching historical BTC price from CoinGecko: {e}", exc_info=True)
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON for historical BTC price from CoinGecko.")
        except Exception as e:
            self.logger.error(f"Unexpected error fetching historical BTC price: {e}", exc_info=True)

        # Update label
        if current_btc_price is not None and historical_btc_price is not None:
            if current_btc_price > historical_btc_price:
                trend_arrow = "↑"
            elif current_btc_price < historical_btc_price:
                trend_arrow = "↓"
            else:
                trend_arrow = "→"
            self.btc_price_label.setText(f"₿ BTC-USD: ${current_btc_price:,.2f} {trend_arrow}")
        elif current_btc_price is not None:
            self.btc_price_label.setText(f"₿ BTC-USD: ${current_btc_price:,.2f} (Trend N/A)")
        else:
            self.btc_price_label.setText("₿ BTC-USD: Data N/A")

        self._update_status("BTC price data fetch attempt complete.")

    def get_icon_name(self) -> str:
        """Returns the icon filename for this module."""
        return "home_dashboard_icon.png" # Or "gauge.svg" / "dashboard.svg" etc.

    def _update_status(self, message: str):
        """Helper to update a status bar, if available from main_window."""
        if hasattr(self.main_window, 'statusBar') and callable(getattr(self.main_window, 'statusBar')):
            try:
                self.main_window.statusBar().showMessage(f"{self.MODULE_DISPLAY_NAME}: {message}", 5000) # Show for 5 seconds
            except Exception as e:
                self.logger.debug(f"Could not update status bar: {e}")
        self.logger.info(message)

if __name__ == '__main__':
    # This part is for testing the module independently
    from PyQt6.QtWidgets import QApplication
    import sys

    # Minimalistic BaseViewModule for testing
    class MinimalBaseViewModule(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.config = {} # Minimal config
            self.logger = logging.getLogger("TestLogger")
            logging.basicConfig(level=logging.INFO)
            self.main_window = self # Mock main_window

        def statusBar(self): # Mock statusBar
            class MockStatusBar:
                def showMessage(self, msg, timeout):
                    self.logger.info(f"Status: {msg} (timeout {timeout})")
            return MockStatusBar()

    BaseViewModule.__bases__ = (MinimalBaseViewModule,) # Temporarily rebase for testing

    app = QApplication(sys.argv)

    # Create a dummy main window for context if your module expects one
    # Or pass None if it can handle it. For this test, HomePageDashboardView
    # is the main widget being shown.

    # Mock config and logger
    test_config = {"WEATHER_API_KEY": "test_weather_key", "FOREX_API_KEY": "test_forex_key"}
    test_logger = logging.getLogger("DashboardTest")
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    # Instantiate the dashboard view
    # dashboard = HomePageDashboardView(config=test_config, logger_instance=test_logger, main_window=None)

    # For the test, we need a main window that can provide a status bar if _update_status is called.
    # Let's create a simple QMainWindow for testing.
    class TestMainWindow(QWidget): # Changed to QWidget to avoid QMainWindow specific features unless needed
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Test Dashboard Container")
            self.layout = QVBoxLayout(self)
            self.dashboard_view = HomePageDashboardView(
                config=test_config,
                logger_instance=test_logger,
                main_window=self # Pass self as main_window
            )
            self.layout.addWidget(self.dashboard_view)
            self._status_bar = QLabel("Status bar placeholder") # Mock status bar
            self.layout.addWidget(self._status_bar)
            self.resize(800, 600)

        def statusBar(self): # Mock method
            class MockStatusBar:
                def __init__(self, label):
                    self.label = label
                def showMessage(self, message, timeout=0):
                    self.label.setText(message)
                    print(f"Status: {message} (timeout {timeout})") # Also print to console
            return MockStatusBar(self._status_bar)


    # If BaseViewModule is QWidget based, it can be a top-level window
    # If it's QFrame or similar, it needs to be hosted.
    # Assuming BaseViewModule (and thus HomePageDashboardView) is a QWidget.

    # dashboard = HomePageDashboardView(config=test_config, logger_instance=test_logger, main_window=None)
    # dashboard.setWindowTitle("Home Dashboard Test")
    # dashboard.resize(800, 600)
    # dashboard.show()

    main_win = TestMainWindow()
    main_win.show()

    sys.exit(app.exec())
