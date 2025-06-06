# File: app/views/modules/home_page_dashboard_view.py

import logging
import json
import requests
import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QApplication, QPushButton
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtGui import QFont, QColor, QPixmap

from app.views.modules.base_view_module import BaseViewModule
from app.utils.general_utils import get_resource_path

# --- Worker Classes ---
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(dict)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.context_key = kwargs.pop('city_key', kwargs.pop('context_key', None))

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            import traceback
            self.signals.error.emit((self.context_key, type(e), e, traceback.format_exc()))
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

AVAILABLE_CITIES_DETAILS: List[Dict[str, str]] = [ # Renamed from CITIES_DETAILS
    {"key": "Camrose", "display_name": "Camrose, AB", "query": "Camrose,CA"},
    {"key": "Wainwright", "display_name": "Wainwright, AB", "query": "Wainwright,CA"},
    {"key": "Killam", "display_name": "Killam, AB", "query": "Killam,CA"},
    {"key": "Provost", "display_name": "Provost, AB", "query": "Provost,CA"},
    {"key": "Edmonton", "display_name": "Edmonton, AB", "query": "Edmonton,CA"}, # Example additional city
    {"key": "Calgary", "display_name": "Calgary, AB", "query": "Calgary,CA"},   # Example additional city
]

DEFAULT_SELECTED_CITIES = [city['key'] for city in AVAILABLE_CITIES_DETAILS[:4]] # Default to first 4
DEFAULT_FINANCIAL_INSTRUMENTS = ["USD-CAD", "BTC-USD"]
DEFAULT_REFRESH_INTERVAL_MS = 3600 * 1000


# --- Weather Card Widget ---
class WeatherCardWidget(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("WeatherCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            #WeatherCard {
                background-color: #e9f5fd;
                border: 1px solid #d0e0f0;
                border-radius: 6px;
                padding: 10px;
                min-height: 150px;
                max-width: 200px;
            }
            QLabel {
                color: #2c3e50;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        self.city_name_label = QLabel("City")
        self.city_name_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.city_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.city_name_label)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setMinimumSize(50, 50)
        layout.addWidget(self.icon_label)

        self.temperature_label = QLabel("--°C")
        self.temperature_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.temperature_label.setStyleSheet("color: #1a5276;")
        self.temperature_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.temperature_label)

        self.condition_label = QLabel("Condition: --")
        self.condition_label.setFont(QFont("Arial", 9))
        self.condition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.condition_label.setWordWrap(True)
        layout.addWidget(self.condition_label)

        layout.addStretch()

        self.status_label = QLabel("Status: Initializing...")
        self.status_label.setFont(QFont("Arial", 8, QFont.Weight.Bold Italic))
        self.status_label.setStyleSheet("color: #566573;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.set_status_initializing()

    def update_data(self, city_name: str, temp: float, condition: str, icon_path: Optional[str]):
        self.city_name_label.setText(city_name)
        self.temperature_label.setText(f"{temp:.1f}°C")
        self.condition_label.setText(f"{condition.capitalize()}")

        self.icon_label.clear()

        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.icon_label.setText("Icon N/A")
                logging.getLogger(__name__).warning(f"Failed to load icon from path: {icon_path} for {city_name}")
        else:
            self.icon_label.setText("")

        self.status_label.setText("")
        self.status_label.setVisible(False)
        self.setStyleSheet("""
            #WeatherCard {
                background-color: #e9f5fd;
                border: 1px solid #d0e0f0;
                border-radius: 6px;
                padding: 10px;
            }""")

    def set_status_fetching(self, city_name: str):
        self.city_name_label.setText(city_name)
        self.temperature_label.setText("--°C")
        self.condition_label.setText("Condition: --")
        self.icon_label.clear()
        self.icon_label.setText("⏳")
        self.status_label.setText("Fetching data...")
        self.status_label.setStyleSheet("color: #1f618d;")
        self.status_label.setVisible(True)
        self.setStyleSheet("""
            #WeatherCard {
                background-color: #f4f6f6;
                border: 1px solid #d0e0f0;
                border-radius: 6px;
                padding: 10px;
            }""")

    def set_status_error(self, city_name: str, message: str, is_api_key_error: bool):
        self.city_name_label.setText(city_name)
        self.temperature_label.setText("ERR")
        self.condition_label.setText("Error")
        self.icon_label.clear()
        self.icon_label.setText("⚠️")
        self.status_label.setText(f"Error: {message[:30]}...")
        self.status_label.setVisible(True)

        if is_api_key_error:
            self.status_label.setStyleSheet("color: #c0392b; font-weight: bold;")
            self.setStyleSheet("""
                #WeatherCard {
                    background-color: #fadbd8;
                    border: 1px solid #f5b7b1;
                    border-radius: 6px;
                    padding: 10px;
                }
                QLabel { color: #78281f; }
            """)
        else:
            self.status_label.setStyleSheet("color: #d35400;")
            self.setStyleSheet("""
                #WeatherCard {
                    background-color: #feefea;
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
        self.icon_label.clear()
        self.icon_label.setText("⚙️")
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

        self.thread_pool = QThreadPool()
        self.logger.info(f"QThreadPool initialized. Max threads: {self.thread_pool.maxThreadCount()}")
        self.weather_cards: Dict[str, WeatherCardWidget] = {}
        self.forex_usdcad_label: Optional[QLabel] = None
        self.btc_price_label: Optional[QLabel] = None

        # --- Configuration Loading ---
        dashboard_settings = {}
        if self.config and hasattr(self.config, 'get') and callable(self.config.get):
            dashboard_settings = self.config.get("dashboard", {})
        elif isinstance(self.config, dict) : # Fallback for plain dict config
             dashboard_settings = self.config.get("dashboard", {})

        self.selected_city_keys = dashboard_settings.get("selected_cities", DEFAULT_SELECTED_CITIES)
        self.selected_financial_instruments = dashboard_settings.get("selected_financial_instruments", DEFAULT_FINANCIAL_INSTRUMENTS)
        refresh_interval_ms = dashboard_settings.get("refresh_interval_ms", DEFAULT_REFRESH_INTERVAL_MS)

        self.logger.info(f"Selected cities: {self.selected_city_keys}")
        self.logger.info(f"Selected financial instruments: {self.selected_financial_instruments}")
        self.logger.info(f"Refresh interval: {refresh_interval_ms} ms")

        self._init_ui() # UI must be initialized before load_module_data
        self.load_module_data()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all_data)
        self.refresh_timer.start(refresh_interval_ms)
        self.logger.info(f"Dashboard refresh timer started with interval: {refresh_interval_ms / 1000 / 60:.2f} minutes.")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20) # Adjusted spacing

        # --- Title and Settings Button ---
        header_layout = QHBoxLayout()
        title_label = QLabel(self.MODULE_DISPLAY_NAME)
        title_font = QFont("Arial", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label, 1) # Add stretch factor

        settings_button = QPushButton("⚙️") # Settings Icon
        settings_button.setToolTip("Dashboard Settings (Not Implemented)")
        settings_button.setEnabled(False) # Disabled for now
        settings_button.setFixedSize(30,30) # Small, square button
        settings_button.setStyleSheet("QPushButton { font-size: 14pt; }")
        header_layout.addWidget(settings_button)
        main_layout.addLayout(header_layout)


        # --- Main Grid for Sections (2 columns) ---
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)

        # --- Weather Section ---
        if self.selected_city_keys: # Only create weather section if cities are selected
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

            col_count = 0 # Max 2 columns for weather cards
            for city_config in AVAILABLE_CITIES_DETAILS:
                city_key = city_config['key']
                if city_key in self.selected_city_keys:
                    card = WeatherCardWidget()
                    # Initial status is set in card's __init__
                    self.weather_grid_layout.addWidget(card, col_count // 2, col_count % 2)
                    self.weather_cards[city_key] = card
                    col_count +=1

            weather_layout.addLayout(self.weather_grid_layout)
            weather_layout.addStretch()
            grid_layout.addWidget(weather_frame, 0, 0, 1, 1) # Span 1 row, 1 col

        # --- Financial Trends Section ---
        if self.selected_financial_instruments: # Only create if instruments are selected
            financial_frame = QFrame()
            financial_frame.setFrameShape(QFrame.Shape.StyledPanel)
            financial_frame.setObjectName("DashboardSectionFrame")
            financial_layout = QVBoxLayout(financial_frame)

            financial_title = QLabel("💹 Market Trends (Weekly)")
            financial_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            financial_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            financial_layout.addWidget(financial_title)

            if "USD-CAD" in self.selected_financial_instruments:
                self.forex_usdcad_label = QLabel("🇺🇸🇨🇦 USD-CAD: Initializing...")
                self.forex_usdcad_label.setFont(QFont("Arial", 11, QFont.Weight.Medium))
                financial_layout.addWidget(self.forex_usdcad_label)

            if "BTC-USD" in self.selected_financial_instruments:
                self.btc_price_label = QLabel("₿ BTC-USD: Initializing...")
                self.btc_price_label.setFont(QFont("Arial", 11, QFont.Weight.Medium))
                financial_layout.addWidget(self.btc_price_label)

            financial_layout.addStretch()
            # Place financial frame next to weather or at start if weather is empty
            grid_col = 1 if self.selected_city_keys else 0
            grid_layout.addWidget(financial_frame, 0, grid_col, 1, 1)


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
        if self.selected_city_keys and self.weather_cards: # Check if there are cities to fetch for
            self._fetch_weather_data()
        if "USD-CAD" in self.selected_financial_instruments and self.forex_usdcad_label:
            self._fetch_forex_data()
        if "BTC-USD" in self.selected_financial_instruments and self.btc_price_label:
            self._fetch_crypto_prices()

    def _refresh_all_data(self):
        self.logger.info("Timer triggered: Refreshing all dashboard data...")
        self._update_status("Refreshing data (timer)...")
        if self.selected_city_keys and self.weather_cards:
            self._fetch_weather_data()
        if "USD-CAD" in self.selected_financial_instruments and self.forex_usdcad_label:
            self._fetch_forex_data()
        if "BTC-USD" in self.selected_financial_instruments and self.btc_price_label:
            self._fetch_crypto_prices()
        self._update_status("Dashboard data refreshed (timer).")

    def _fetch_weather_for_city_worker(self, city_key: str, city_query: str, display_name: str) -> Dict[str, Any]:
        self.logger.info(f"Fetching weather for {display_name} ({city_key})...")
        icon_code: Optional[str] = None
        try:
            url = f"{OPENWEATHERMAP_BASE_URL}?q={city_query}&appid={OPENWEATHERMAP_API_KEY}&units=metric"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("cod") != 200:
                error_message = data.get("message", "Unknown API error")
                self.logger.error(f"API error for {display_name}: {error_message}")
                raise Exception(f"API Error: {error_message}")

            temp = data.get('main', {}).get('temp')
            condition = data.get('weather', [{}])[0].get('description', 'N/A')
            icon_code = data.get('weather', [{}])[0].get('icon', None)

            if temp is None:
                raise ValueError("Temperature data not found in API response.")

            return {'key': city_key, 'name': display_name, 'temp': temp, 'condition': condition, 'icon_code': icon_code}

        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout fetching weather for {display_name}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"RequestException for {display_name}: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONDecodeError for {display_name}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in _fetch_weather_for_city_worker for {display_name}: {e}")
            raise

    def _fetch_weather_data(self):
        if not self.selected_city_keys: # No selected cities, do nothing
            self.logger.info("No cities selected for weather display. Skipping fetch.")
            return

        self.logger.info("Initiating fetch for selected weather data...")
        self._update_status("Fetching selected weather data...")

        if OPENWEATHERMAP_API_KEY == "YOUR_API_KEY_HERE" or not OPENWEATHERMAP_API_KEY:
            self.logger.warning("OpenWeatherMap API key is not set. Weather data will not be fetched.")
            for city_key in self.selected_city_keys: # Iterate only selected cities
                card = self.weather_cards.get(city_key)
                if card:
                    # Find display name for the error message
                    city_display_name = city_key
                    for city_detail in AVAILABLE_CITIES_DETAILS:
                        if city_detail['key'] == city_key:
                            city_display_name = city_detail['display_name']
                            break
                    card.set_status_error(city_display_name, "API Key Not Configured", True)
            self._update_status("Weather: API Key Required")
            return

        for city_detail in AVAILABLE_CITIES_DETAILS: # Iterate all available to find matches
            city_key = city_detail['key']
            if city_key in self.selected_city_keys:
                city_query = city_detail['query']
                display_name = city_detail['display_name']

                card = self.weather_cards.get(city_key)
                if not card: # Should not happen if _init_ui was successful for selected cities
                    self.logger.error(f"Weather card for selected city key '{city_key}' not found.")
                    continue
                
                card.set_status_fetching(display_name)
                
                worker = Worker(self._fetch_weather_for_city_worker, city_key=city_key, city_query=city_query, display_name=display_name)
                worker.signals.result.connect(self._on_weather_data_received)
                worker.signals.error.connect(self._on_weather_data_error)
                self.thread_pool.start(worker)

    def _on_weather_data_received(self, result: dict):
        city_key = result.get('key')
        # Ensure this city is still meant to be displayed (in case config changed during fetch)
        if city_key not in self.selected_city_keys:
            self.logger.info(f"Weather data received for {city_key}, but it's no longer selected. Discarding.")
            return

        icon_code = result.get('icon_code')
        icon_path: Optional[str] = None

        if icon_code:
            icon_resource_name = f"icons/weather/{icon_code}.png"
            try:
                icon_path = get_resource_path(icon_resource_name, base_module_config=self.config)
                if not icon_path:
                     self.logger.warning(f"Resolved icon path is None for {icon_resource_name}. Icon might be missing.")
            except Exception as e:
                self.logger.error(f"Error resolving icon path for {icon_resource_name}: {e}")
                icon_path = None
        
        self.logger.info(f"Weather data received for city: {result.get('name', city_key)}. Icon path: {icon_path}")
        card = self.weather_cards.get(city_key)
        if card:
            card.update_data(
                city_name=result['name'],
                temp=result['temp'],
                condition=result['condition'],
                icon_path=icon_path
            )
        else:
            self.logger.warning(f"Received weather data for unknown or unselected city key: {city_key}")

    def _on_weather_data_error(self, error_info: tuple):
        context_key, exc_type, error_val, tb_str = error_info
        if context_key not in self.selected_city_keys:
            self.logger.info(f"Weather error for {context_key}, but it's no longer selected. Discarding.")
            return

        city_display_name = context_key
        for city_detail in AVAILABLE_CITIES_DETAILS:
            if city_detail['key'] == context_key:
                city_display_name = city_detail['display_name']
                break

        self.logger.error(f"Error fetching weather for {city_display_name} ({context_key}): {exc_type.__name__} - {error_val}\nTrace: {tb_str}")
        card = self.weather_cards.get(context_key)
        if card:
            card.set_status_error(city_display_name, str(error_val), False)
        else:
            self.logger.warning(f"Error received for unknown or unselected weather city key: {context_key}")

    # --- Forex Data Handling ---
    def _fetch_forex_data_worker(self) -> Dict[str, Optional[float]]:
        self.logger.info("Forex worker: Fetching USD-CAD data...")
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
                raise Exception(f"API error for latest rate: {data_latest.get('error-type', 'Unknown error')}")
        except Exception as e:
            self.logger.error(f"Forex worker: Error fetching latest USD-CAD rate: {e}", exc_info=True)

        try:
            date_7_days_ago = datetime.date.today() - datetime.timedelta(days=7)
            url_historical = f"{EXCHANGERATE_BASE_URL}{EXCHANGERATE_API_KEY}/history/USD/{date_7_days_ago.year}/{date_7_days_ago.month}/{date_7_days_ago.day}"
            response_historical = requests.get(url_historical, timeout=10)
            response_historical.raise_for_status()
            data_historical = response_historical.json()
            if data_historical.get("result") == "success" and 'conversion_rates' in data_historical:
                historical_rate = data_historical['conversion_rates'].get('CAD')
            else:
                raise Exception(f"API error for historical rate: {data_historical.get('error-type', 'Unknown error')}")
        except Exception as e:
            self.logger.error(f"Forex worker: Error fetching historical USD-CAD rate: {e}", exc_info=True)

        if current_rate is None and historical_rate is None:
             raise ConnectionError("Forex worker: Failed to fetch both current and historical rates.")

        return {"current_rate": current_rate, "historical_rate": historical_rate, "context_key": "forex"}


    def _fetch_forex_data(self):
        if "USD-CAD" not in self.selected_financial_instruments or not self.forex_usdcad_label:
            self.logger.info("USD-CAD not selected or label missing. Skipping fetch.")
            if self.forex_usdcad_label: self.forex_usdcad_label.setVisible(False) # Hide if exists but not selected
            return

        self.forex_usdcad_label.setVisible(True)
        self.logger.info("Dispatching Forex data fetch to worker...")
        if EXCHANGERATE_API_KEY == "YOUR_API_KEY_HERE" or not EXCHANGERATE_API_KEY:
            self.logger.warning("ExchangeRate-API key is not set. Forex data will not be fetched.")
            self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: API Key Required")
            self._update_status("Forex: API Key Required")
            return

        self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: Fetching...")
        self._update_status("Fetching USD-CAD data...")

        worker = Worker(self._fetch_forex_data_worker, context_key="forex")
        worker.signals.result.connect(self._on_forex_data_received)
        worker.signals.error.connect(self._on_forex_data_error)
        self.thread_pool.start(worker)

    def _on_forex_data_received(self, result: dict):
        if "USD-CAD" not in self.selected_financial_instruments or not self.forex_usdcad_label:
            return # In case config changed during fetch

        self.logger.info("Forex data received.")
        current_rate = result.get("current_rate")
        historical_rate = result.get("historical_rate")

        if current_rate is not None and historical_rate is not None:
            percentage_change = 0.0
            trend_color = "#808080"
            trend_arrow = "→"
            try:
                if historical_rate != 0:
                    percentage_change = ((current_rate - historical_rate) / historical_rate) * 100
                else:
                    percentage_change = float('inf') if current_rate > 0 else 0

                if percentage_change > 0.01:
                    trend_color = "green"
                    trend_arrow = "↑"
                elif percentage_change < -0.01:
                    trend_color = "red"
                    trend_arrow = "↓"
            except ZeroDivisionError:
                self.logger.warning("ZeroDivisionError while calculating forex percentage change.")
                percentage_change = float('inf')

            if percentage_change != float('inf'):
                text = (f"🇺🇸🇨🇦 USD-CAD: <b>{current_rate:.4f}</b> "
                        f"<font color='{trend_color}'>{trend_arrow}</font> "
                        f"({percentage_change:+.2f}%)")
            else:
                 text = f"🇺🇸🇨🇦 USD-CAD: <b>{current_rate:.4f}</b> (Prev: 0.0)"
            self.forex_usdcad_label.setText(text)
        elif current_rate is not None:
            self.forex_usdcad_label.setText(f"🇺🇸🇨🇦 USD-CAD: <b>{current_rate:.4f}</b> (Trend N/A)")
        else:
            self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: Data N/A")
        self._update_status("Forex data updated.")

    def _on_forex_data_error(self, error_info: tuple):
        if "USD-CAD" not in self.selected_financial_instruments or not self.forex_usdcad_label:
            return

        context_key, exc_type, error_val, tb_str = error_info
        self.logger.error(f"Error fetching Forex (USD-CAD) data ({context_key}): {exc_type.__name__} - {error_val}\nTrace: {tb_str}")
        self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: Error fetching data")
        self._update_status("Forex data: Error")


    # --- Crypto Data Handling ---
    def _fetch_crypto_prices_worker(self) -> Dict[str, Any]:
        self.logger.info("Crypto worker: Fetching BTC-USD data...")
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
                raise Exception("API response for current BTC price missing expected data.")
        except Exception as e:
            self.logger.error(f"Crypto worker: Error fetching current BTC price: {e}", exc_info=True)

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
                raise Exception("API response for historical BTC price missing expected data.")
        except Exception as e:
            self.logger.error(f"Crypto worker: Error fetching historical BTC price: {e}", exc_info=True)

        if current_btc_price is None and historical_btc_price is None:
            raise ConnectionError("Crypto worker: Failed to fetch both current and historical BTC prices.")
            
        return {"current_price": current_btc_price, "historical_price": historical_btc_price, "context_key": "crypto"}

    def _fetch_crypto_prices(self):
        if "BTC-USD" not in self.selected_financial_instruments or not self.btc_price_label:
            self.logger.info("BTC-USD not selected or label missing. Skipping fetch.")
            if self.btc_price_label: self.btc_price_label.setVisible(False) # Hide if exists but not selected
            return

        self.btc_price_label.setVisible(True)
        self.logger.info("Dispatching Crypto (BTC-USD) data fetch to worker...")
        self.btc_price_label.setText("₿ BTC-USD: Fetching...")
        self._update_status("Fetching BTC-USD data...")

        worker = Worker(self._fetch_crypto_prices_worker, context_key="crypto")
        worker.signals.result.connect(self._on_crypto_data_received)
        worker.signals.error.connect(self._on_crypto_data_error)
        self.thread_pool.start(worker)

    def _on_crypto_data_received(self, result: dict):
        if "BTC-USD" not in self.selected_financial_instruments or not self.btc_price_label:
            return

        self.logger.info("Crypto (BTC-USD) data received.")
        current_btc_price = result.get("current_price")
        historical_btc_price = result.get("historical_price")

        if current_btc_price is not None and historical_btc_price is not None:
            percentage_change = 0.0
            trend_color = "#808080"
            trend_arrow = "→"
            try:
                if historical_btc_price != 0:
                    percentage_change = ((current_btc_price - historical_btc_price) / historical_btc_price) * 100
                else:
                    percentage_change = float('inf') if current_btc_price > 0 else 0

                if percentage_change > 0.01:
                    trend_color = "green"
                    trend_arrow = "↑"
                elif percentage_change < -0.01:
                    trend_color = "red"
                    trend_arrow = "↓"
            except ZeroDivisionError:
                self.logger.warning("ZeroDivisionError while calculating BTC percentage change.")
                percentage_change = float('inf')

            if percentage_change != float('inf'):
                text = (f"₿ BTC-USD: <b>${current_btc_price:,.2f}</b> "
                        f"<font color='{trend_color}'>{trend_arrow}</font> "
                        f"({percentage_change:+.2f}%)")
            else:
                text = f"₿ BTC-USD: <b>${current_btc_price:,.2f}</b> (Prev: $0.00)"
            self.btc_price_label.setText(text)
        elif current_btc_price is not None:
            self.btc_price_label.setText(f"₿ BTC-USD: <b>${current_btc_price:,.2f}</b> (Trend N/A)")
        else:
            self.btc_price_label.setText("₿ BTC-USD: Data N/A")
        self._update_status("BTC price data updated.")

    def _on_crypto_data_error(self, error_info: tuple):
        if "BTC-USD" not in self.selected_financial_instruments or not self.btc_price_label:
            return
            
        context_key, exc_type, error_val, tb_str = error_info
        self.logger.error(f"Error fetching Crypto (BTC-USD) data ({context_key}): {exc_type.__name__} - {error_val}\nTrace: {tb_str}")
        self.btc_price_label.setText("₿ BTC-USD: Error fetching data")
        self._update_status("BTC price data: Error")

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
            self.config = { # Example config for testing
                "dashboard": {
                    "selected_cities": ["Camrose", "Edmonton"],
                    "selected_financial_instruments": ["USD-CAD", "BTC-USD"],
                    "refresh_interval_ms": 60000 # 1 minute for testing
                }
            }
            self.logger = logging.getLogger("TestLogger")
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
            self.main_window = self

        def statusBar(self):
            class MockStatusBar:
                def __init__(self, logger):
                    self.logger = logger
                def showMessage(self, msg, timeout):
                    self.logger.info(f"Status: {msg} (timeout {timeout})")
            return MockStatusBar(self.logger)
    
    BaseViewModule.__bases__ = (MinimalBaseViewModule,)

    app = QApplication(sys.argv)
    
    # test_config is now part of MinimalBaseViewModule for this test
    test_logger = logging.getLogger("DashboardTest")
    # logging.basicConfig(stream=sys.stdout, level=logging.INFO) # Already configured by MinimalBaseViewModule

    class TestMainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Test Dashboard Container")
            self.layout = QVBoxLayout(self)
            # The config is now provided by the mocked BaseViewModule
            self.dashboard_view = HomePageDashboardView(
                # config=test_config, # No longer needed here
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
