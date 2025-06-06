# File: app/views/modules/home_page_dashboard_view.py

import logging
import json
import requests # For making HTTP requests to weather API
import datetime # For handling dates for historical forex data
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QRunnable, QThreadPool # Added QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtGui import QFont, QColor # Added QColor

from app.views.modules.base_view_module import BaseViewModule
# Placeholder for API clients or services if needed in the future
# from app.services.weather_service import WeatherService
# from app.services.forex_service import ForexService
# from app.services.commodity_service import CommodityService
# from app.services.crypto_service import CryptoService

# --- Worker Classes (Copied and adapted) ---
class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    Supported signals are:
    finished: No data
    error: tuple (city_key, exc_type, exception, traceback)
    result: object data returned from processing
    """
    finished = pyqtSignal()
    error = pyqtSignal(tuple)  # Now includes city_key
    result = pyqtSignal(dict)  # Assuming result is a dict

class Worker(QRunnable):
    """
    Worker thread
    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.
    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to callback function
    :param kwargs: Keywords to pass to callback function
    """
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Store city_key if provided in kwargs, to be emitted with error signal
        self.city_key = kwargs.get('city_key', None)

    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            import traceback
            # Emit error with city_key
            self.signals.error.emit((self.city_key, type(e), e, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

# --- Constants ---
OPENWEATHERMAP_API_KEY = "YOUR_API_KEY_HERE"
OPENWEATHERMAP_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
EXCHANGERATE_API_KEY = "YOUR_API_KEY_HERE"
EXCHANGERATE_BASE_URL = "https://v6.exchangerate-api.com/v6/"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3/"

CITIES_DETAILS: List[Dict[str, str]] = [
    {"key": "Camrose", "display_name": "Camrose, AB", "query": "Camrose,CA"},
    {"key": "Wainwright", "display_name": "Wainwright, AB", "query": "Wainwright,CA"},
    {"key": "Killam", "display_name": "Killam, AB", "query": "Killam,CA"},
    {"key": "Provost", "display_name": "Provost, AB", "query": "Provost,CA"},
]

# --- Weather Card Widget ---
class WeatherCardWidget(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("WeatherCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            #WeatherCard {
                background-color: #e9f5fd; /* Light blue background */
                border: 1px solid #d0e0f0;
                border-radius: 6px;
                padding: 10px;
                min-height: 120px; /* Ensure a minimum height */
            }
            QLabel {
                color: #2c3e50; /* Dark blue-grey text */
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        self.city_name_label = QLabel("City")
        self.city_name_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(self.city_name_label)

        self.temperature_label = QLabel("--°C")
        self.temperature_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.temperature_label.setStyleSheet("color: #1a5276;") # Darker blue for temp
        layout.addWidget(self.temperature_label)

        self.condition_label = QLabel("Condition: --")
        self.condition_label.setFont(QFont("Arial", 9))
        layout.addWidget(self.condition_label)

        self.icon_label = QLabel("Icon: --") # Placeholder for icon or code
        self.icon_label.setFont(QFont("Arial", 8))
        self.icon_label.setMinimumHeight(20) # Space for potential icon
        layout.addWidget(self.icon_label)

        layout.addStretch() # Push status label to the bottom

        self.status_label = QLabel("Status: Initializing...")
        self.status_label.setFont(QFont("Arial", 8, QFont.Weight.Bold Italic))
        self.status_label.setStyleSheet("color: #566573;") # Grey for status
        layout.addWidget(self.status_label)

        self.set_status_initializing()


    def update_data(self, city_name: str, temp: float, condition: str, icon_code: Optional[str]):
        self.city_name_label.setText(city_name)
        self.temperature_label.setText(f"{temp:.1f}°C")
        self.condition_label.setText(f"Condition: {condition.capitalize()}")
        if icon_code:
            self.icon_label.setText(f"Icon: {icon_code}")
            # In a future step, this could load an image:
            # self.icon_label.setPixmap(get_weather_icon_pixmap(icon_code))
        else:
            self.icon_label.setText("") # Clear if no icon
        self.status_label.setText("") # Clear status on successful update
        self.status_label.setVisible(False)
        self.setStyleSheet("""
            #WeatherCard {
                background-color: #e9f5fd;
                border: 1px solid #d0e0f0;
                border-radius: 6px;
                padding: 10px;
            }""")


    def set_status_fetching(self, city_name: str):
        self.city_name_label.setText(city_name) # Show city name even while fetching
        self.temperature_label.setText("--°C")
        self.condition_label.setText("Condition: --")
        self.icon_label.setText("")
        self.status_label.setText("⏳ Fetching data...")
        self.status_label.setStyleSheet("color: #1f618d;") # Blue for fetching
        self.status_label.setVisible(True)
        self.setStyleSheet("""
            #WeatherCard {
                background-color: #f4f6f6; /* Slightly muted while fetching */
                border: 1px solid #d0e0f0;
                border-radius: 6px;
                padding: 10px;
            }""")

    def set_status_error(self, city_name: str, message: str, is_api_key_error: bool):
        self.city_name_label.setText(city_name) # Show city name even on error
        self.temperature_label.setText("ERR")
        self.condition_label.setText("Condition: Error")
        self.icon_label.setText("")
        self.status_label.setText(f"⚠️ Error: {message}")
        self.status_label.setVisible(True)

        if is_api_key_error:
            self.status_label.setStyleSheet("color: #c0392b; font-weight: bold;") # Red, bold for API key error
            self.setStyleSheet("""
                #WeatherCard {
                    background-color: #fadbd8; /* Light red for API key error */
                    border: 1px solid #f5b7b1;
                    border-radius: 6px;
                    padding: 10px;
                }
                QLabel { color: #78281f; } /* Darker red text for API key error */
            """)
        else:
            self.status_label.setStyleSheet("color: #d35400;") # Orange for other errors
            self.setStyleSheet("""
                #WeatherCard {
                    background-color: #feefea; /* Light orange for other errors */
                    border: 1px solid #fAD7A0;
                    border-radius: 6px;
                    padding: 10px;
                }
                 QLabel { color: #b9770e; }
            """)

    def set_status_initializing(self):
        self.city_name_label.setText("Weather Card")
        self.temperature_label.setText("--°C")
        self.condition_label.setText("Condition: --")
        self.icon_label.setText("")
        self.status_label.setText("Initializing...")
        self.status_label.setStyleSheet("color: #566573;")
        self.status_label.setVisible(True)


class HomePageDashboardView(BaseViewModule):
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

        self.thread_pool = QThreadPool() # Initialize QThreadPool
        self.logger.info(f"QThreadPool initialized. Max threads: {self.thread_pool.maxThreadCount()}")

        self.weather_cards: Dict[str, WeatherCardWidget] = {} # For new weather cards

        self._init_ui()
        self.load_module_data()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all_data)
        
        refresh_interval_ms = 3600 * 1000
        if self.config and hasattr(self.config, 'get') and callable(self.config.get):
            refresh_interval_ms = self.config.get("DASHBOARD_REFRESH_INTERVAL_MS", refresh_interval_ms)
        elif isinstance(self.config, dict):
             refresh_interval_ms = self.config.get("DASHBOARD_REFRESH_INTERVAL_MS", refresh_interval_ms)
        else:
            self.logger.warning("Config object not available or 'get' method missing; using default refresh interval.")

        self.refresh_timer.start(refresh_interval_ms)
        self.logger.info(f"Dashboard refresh timer started with interval: {refresh_interval_ms / 1000 / 60:.2f} minutes.")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(25)

        title_label = QLabel(self.MODULE_DISPLAY_NAME)
        title_font = QFont("Arial", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)

        # --- Weather Section ---
        weather_frame = QFrame()
        weather_frame.setFrameShape(QFrame.Shape.StyledPanel)
        weather_frame.setObjectName("DashboardSectionFrame")
        weather_layout = QVBoxLayout(weather_frame)
        
        weather_title = QLabel("🌦️ Current Weather")
        weather_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        weather_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        weather_layout.addWidget(weather_title)

        self.weather_grid_layout = QGridLayout()
        self.weather_grid_layout.setSpacing(10)
        
        # Create WeatherCardWidgets
        for i, city_info in enumerate(CITIES_DETAILS):
            city_key = city_info['key']
            card = WeatherCardWidget()
            card.set_status_fetching(city_info['display_name']) # Initial status
            self.weather_grid_layout.addWidget(card, i // 2, i % 2) # 2 cards per row
            self.weather_cards[city_key] = card
        
        weather_layout.addLayout(self.weather_grid_layout)
        weather_layout.addStretch()
        grid_layout.addWidget(weather_frame, 0, 0)

        # --- Financial Trends Section (remains the same for now) ---
        financial_frame = QFrame()
        financial_frame.setFrameShape(QFrame.Shape.StyledPanel)
        financial_frame.setObjectName("DashboardSectionFrame")
        financial_layout = QVBoxLayout(financial_frame)

        financial_title = QLabel("💹 Market Trends (Weekly)")
        financial_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
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
        
        financial_layout.addStretch()
        grid_layout.addWidget(financial_frame, 0, 1)

        main_layout.addLayout(grid_layout)
        main_layout.addStretch()

        self.setStyleSheet("""
            #DashboardSectionFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
            }
            QLabel {
                color: #343a40;
            }
        """)

    def load_module_data(self):
        self.logger.info(f"'{self.MODULE_DISPLAY_NAME}' module data loading initiated.")
        self._update_status("Data loading initiated...")
        self._fetch_weather_data()
        self._fetch_forex_data()
        self._fetch_crypto_prices()
        self._fetch_commodity_prices()

    def _refresh_all_data(self):
        self.logger.info("Timer triggered: Refreshing all dashboard data...")
        self._update_status("Refreshing data (timer)...")
        self._fetch_weather_data()
        self._fetch_forex_data()
        self._fetch_crypto_prices()
        self._fetch_commodity_prices()
        self._update_status("Dashboard data refreshed (timer).")

    # --- Weather Data Handling ---
    def _fetch_weather_for_city_worker(self, city_key: str, city_query: str, display_name: str) -> Dict[str, Any]:
        """Fetches and processes weather data for a single city."""
        self.logger.info(f"Fetching weather for {display_name} ({city_key}) via worker...")
        try:
            url = f"{OPENWEATHERMAP_BASE_URL}?q={city_query}&appid={OPENWEATHERMAP_API_KEY}&units=metric"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("cod") != 200:
                error_message = data.get("message", "Unknown API error")
                self.logger.error(f"API error for {display_name}: {error_message}")
                raise Exception(f"API Error: {error_message}") # Worker will catch and emit this

            temp = data.get('main', {}).get('temp')
            condition = data.get('weather', [{}])[0].get('description', 'N/A')
            icon_code = data.get('weather', [{}])[0].get('icon', None)

            if temp is None:
                raise ValueError("Temperature data not found in API response.")

            return {'key': city_key, 'name': display_name, 'temp': temp, 'condition': condition, 'icon': icon_code}

        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout fetching weather for {display_name}: {e}")
            raise # Re-raise for worker to catch
        except requests.exceptions.RequestException as e:
            self.logger.error(f"RequestException for {display_name}: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONDecodeError for {display_name}: {e}")
            raise
        except Exception as e: # Catch any other unexpected errors
            self.logger.error(f"Unexpected error in _fetch_weather_for_city_worker for {display_name}: {e}")
            raise


    def _fetch_weather_data(self):
        self.logger.info("Initiating fetch for all weather data...")
        self._update_status("Fetching all weather data...")

        if OPENWEATHERMAP_API_KEY == "YOUR_API_KEY_HERE" or not OPENWEATHERMAP_API_KEY:
            self.logger.warning("OpenWeatherMap API key is not set. Weather data will not be fetched.")
            for city_info in CITIES_DETAILS:
                card = self.weather_cards.get(city_info['key'])
                if card:
                    card.set_status_error(city_info['display_name'], "API Key Not Configured", True)
            self._update_status("Weather: API Key Required")
            return

        for city_info in CITIES_DETAILS:
            city_key = city_info['key']
            city_query = city_info['query']
            display_name = city_info['display_name']
            
            card = self.weather_cards.get(city_key)
            if not card:
                self.logger.error(f"Weather card for city key '{city_key}' not found.")
                continue

            card.set_status_fetching(display_name)

            # Pass city_key to worker for error signal context
            worker = Worker(self._fetch_weather_for_city_worker, city_key=city_key, city_query=city_query, display_name=display_name)
            worker.signals.result.connect(self._on_weather_data_received)
            worker.signals.error.connect(self._on_weather_data_error)
            self.thread_pool.start(worker)

    def _on_weather_data_received(self, result: dict):
        city_key = result.get('key')
        self.logger.info(f"Weather data received for city: {result.get('name', city_key)}")
        card = self.weather_cards.get(city_key)
        if card:
            card.update_data(
                city_name=result['name'],
                temp=result['temp'],
                condition=result['condition'],
                icon_code=result.get('icon')
            )
        else:
            self.logger.warning(f"Received weather data for unknown city key: {city_key}")

    def _on_weather_data_error(self, error_info: tuple):
        # error_info is (city_key, exc_type, exception, traceback_str)
        city_key, exc_type, error_val, tb_str = error_info
        
        # Try to get display name for the error message
        city_display_name = city_key # Fallback to key if name not found
        for city_detail in CITIES_DETAILS:
            if city_detail['key'] == city_key:
                city_display_name = city_detail['display_name']
                break

        self.logger.error(f"Error fetching weather for {city_display_name} ({city_key}): {exc_type.__name__} - {error_val}\nTrace: {tb_str}")
        card = self.weather_cards.get(city_key)
        if card:
            card.set_status_error(city_display_name, str(error_val), False) # is_api_key_error is False for general errors
        else:
            self.logger.warning(f"Error received for unknown weather city key: {city_key}")


    # --- Other Data Fetching Methods (Forex, Commodity, Crypto) ---
    # These remain largely unchanged for now, but could be refactored similarly
    # to use threaded workers if they become too slow.

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

        if current_rate is not None and historical_rate is not None:
            if current_rate > historical_rate:
                trend_arrow = "↑"
            elif current_rate < historical_rate:
                trend_arrow = "↓"
            else:
                trend_arrow = "→"
            self.forex_usdcad_label.setText(f"🇺🇸🇨🇦 USD-CAD: {current_rate:.4f} {trend_arrow}")
        elif current_rate is not None:
            self.forex_usdcad_label.setText(f"🇺🇸🇨🇦 USD-CAD: {current_rate:.4f} (Trend N/A)")
        else:
            self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: Data N/A")
        
        self._update_status("Forex data fetch attempt complete.")

    def _fetch_commodity_prices(self):
        self.logger.info("Attempting to fetch commodity prices (e.g., Canola)...")
        self.canola_price_label.setText("🌾 Canola: Price Data N/A")
        self.logger.info("Canola price data is not integrated due to lack of a readily available free public API.")
        self._update_status("Canola Price: Data N/A")

    def _fetch_crypto_prices(self):
        self.logger.info("Fetching BTC-USD price data from CoinGecko...")
        self._update_status("Fetching BTC-USD data...")

        current_btc_price: Optional[float] = None
        historical_btc_price: Optional[float] = None

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

        try:
            date_7_days_ago = datetime.date.today() - datetime.timedelta(days=7)
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
        return "home_dashboard_icon.png"

    def _update_status(self, message: str):
        if hasattr(self.main_window, 'statusBar') and callable(getattr(self.main_window, 'statusBar')):
            try:
                self.main_window.statusBar().showMessage(f"{self.MODULE_DISPLAY_NAME}: {message}", 5000)
            except Exception as e:
                self.logger.debug(f"Could not update status bar: {e}")
        self.logger.info(message)

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys

    class MinimalBaseViewModule(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.config = {}
            self.logger = logging.getLogger("TestLogger")
            logging.basicConfig(level=logging.INFO)
            self.main_window = self

        def statusBar(self):
            class MockStatusBar:
                def showMessage(self, msg, timeout):
                    self.logger.info(f"Status: {msg} (timeout {timeout})")
            return MockStatusBar()
    
    BaseViewModule.__bases__ = (MinimalBaseViewModule,)

    app = QApplication(sys.argv)
    
    test_config = {"WEATHER_API_KEY": "test_weather_key", "FOREX_API_KEY": "test_forex_key"}
    test_logger = logging.getLogger("DashboardTest")
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    class TestMainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Test Dashboard Container")
            self.layout = QVBoxLayout(self)
            # Ensure QThreadPool is available globally or passed if needed by Worker
            # For this test, globalInstance should be fine.
            self.dashboard_view = HomePageDashboardView(
                config=test_config, 
                logger_instance=test_logger, 
                main_window=self
            )
            self.layout.addWidget(self.dashboard_view)
            self._status_bar = QLabel("Status bar placeholder")
            self.layout.addWidget(self._status_bar)
            self.resize(800, 600)

        def statusBar(self):
            class MockStatusBar:
                def __init__(self, label):
                    self.label = label
                def showMessage(self, message, timeout=0):
                    self.label.setText(message)
                    print(f"Status: {message} (timeout {timeout})")
            return MockStatusBar(self._status_bar)

    main_win = TestMainWindow()
    main_win.show()
    
    sys.exit(app.exec())
