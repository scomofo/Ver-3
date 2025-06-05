# utils/config.py - Adapter integrating existing Config with main.py requirements
import os
import json
import logging
from dotenv import load_dotenv

# Get logger
logger = logging.getLogger('BCApp.Config')

class Config:
    """Application configuration manager."""

    # Default configuration
    DEFAULTS = {
        'weather_refresh_interval': 1,  # hours
        'exchange_refresh_interval': 6,  # hours
        'commodities_refresh_interval': 4,  # hours
        'api_timeout': 15,  # seconds
        'ui_theme': 'light',
        'enable_high_dpi': True,
        'log_level': 'INFO',
        'splash_image': 'splash.png', # Default splash image name
        'app_icon': 'app_icon.png',   # Default app icon name
        'app_title': 'BRIDeal', # Default app title
        'window_width': 1200,
        'window_height': 800,
        'toolbar_icon_size':72,
        # Add defaults needed by main.py
        'window_geometry': {
            'width': 1200,
            'height': 800,
            'maximized': False
        },
        'theme': 'Light',
        'last_module': 'Home',
        'show_splash_screen': True,
        'jd_auth': {
            'remember_credentials': False
        },
        'sharepoint': {
            'auto_sync': True,
            'sync_interval_minutes': 60
        },
        'logging': {
            'level': 'INFO',
            'max_file_size_mb': 5,
            'backup_count': 3
        }
    }

    def __init__(self, base_path=None):
        """Initialize the configuration manager."""
        # Load environment variables first
        try:
            dotenv_path = os.path.expanduser("~/.env")
            loaded = load_dotenv(dotenv_path)
            logger.debug(f"Attempted to load .env from '{dotenv_path}'. Loaded: {loaded}")
        except Exception as e:
            logger.warning(f"Error loading .env file from {dotenv_path}: {e}")

        # Set base path
        self.base_path = base_path or os.getcwd()
        logger.debug(f"Config using base path: {self.base_path}")

        # Initialize with default values
        self.config = self.DEFAULTS.copy()

        # Try to load from config file (config.json)
        self._load_from_file() # Handles its own errors

        # Create derived paths
        try:
            logger.debug("Setting up paths")
            self._setup_paths()
            logger.debug("Paths setup complete")
        except Exception as e:
            logger.critical(f"Error during _setup_paths: {e}")
            raise

        # Load API credentials
        try:
            logger.debug("Loading credentials")
            self._load_credentials()
            logger.debug("Credentials loaded")
        except Exception as e:
            logger.critical(f"Error during _load_credentials: {e}")
            raise

        # Set up settings file for main.py compatibility
        self.settings_file = os.path.join(self.base_path, 'config.json')
        self.settings = self.config

        # Log initialized configuration
        self._log_config()

    def _load_from_file(self):
        """Load configuration from JSON file."""
        config_file = os.path.join(self.base_path, 'config.json')
        logger.debug(f"Checking for config file at: {config_file}")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                self.config.update(loaded_config)
                logger.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.error(f"Error loading config file {config_file}: {str(e)}")
        else:
            logger.debug(f"Config file {config_file} not found, using defaults and environment variables.")


    def _setup_paths(self):
        """Setup application paths using consistent _dir suffix."""
        logger.debug(f"Setting up paths based on base_path: {self.base_path}")
        # Main directories
        self.data_dir = os.path.join(self.base_path, 'data')
        self.log_dir = os.path.join(self.base_path, 'logs')
        self.cache_dir = os.path.join(self.base_path, 'cache')
        self.assets_dir = os.path.join(self.base_path, 'assets')
        self.resources_dir = os.path.join(self.base_path, 'resources')

        # Create modules/exports directory for exports
        self.exports_dir = os.path.join(self.base_path, 'modules', 'exports')
        logger.debug(f"Calculated paths - data: {self.data_dir}, log: {self.log_dir}, cache: {self.cache_dir}, assets: {self.assets_dir}, resources: {self.resources_dir}, exports: {self.exports_dir}")

        # Ensure directories exist
        paths_to_check = [self.data_dir, self.log_dir, self.cache_dir,
                          self.assets_dir, self.resources_dir, self.exports_dir]
        logger.debug(f"Ensuring directories exist: {paths_to_check}")
        for path in paths_to_check:
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                logger.error(f"Failed to create directory {path}: {e}")


    def _load_credentials(self):
        """Load API credentials from environment variables."""
        # SharePoint/Azure credentials
        logger.debug("Loading Azure/SharePoint credentials...")
        self.azure_client_id = os.getenv('AZURE_CLIENT_ID')
        self.azure_client_secret = os.getenv('AZURE_CLIENT_SECRET')
        self.azure_tenant_id = os.getenv('AZURE_TENANT_ID')
        self.sharepoint_site_id = os.getenv('SHAREPOINT_SITE_ID')
        self.sharepoint_site_name = os.getenv('SHAREPOINT_SITE_NAME')
        self.sharepoint_file_path = os.getenv('FILE_PATH')
        
        # For main.py compatibility, also set these in the environment
        if self.azure_tenant_id:
            os.environ['TENANT_ID'] = self.azure_tenant_id
        if self.azure_client_id:
            os.environ['CLIENT_ID'] = self.azure_client_id
        if self.azure_client_secret:
            os.environ['CLIENT_SECRET'] = self.azure_client_secret

        # John Deere Credentials
        logger.debug("Loading John Deere credentials...")
        self.jd_client_id = os.getenv('JD_CLIENT_ID')
        self.jd_client_secret = os.getenv('DEERE_CLIENT_SECRET') 

        # Other API keys
        logger.debug("Loading other API keys...")
        self.finnhub_api_key = os.getenv('FINNHUB_API_KEY')

        # Check for required credentials
        self._check_required_credentials()


    def _check_required_credentials(self):
        """Check if required credentials are present."""
        # Define required variables based on expected environment variable names
        required_vars = [
            'AZURE_CLIENT_ID',
            'AZURE_CLIENT_SECRET',
            'AZURE_TENANT_ID',
            'SHAREPOINT_SITE_ID',
            'SHAREPOINT_SITE_NAME',
            'FILE_PATH',
            'JD_CLIENT_ID',
            'DEERE_CLIENT_SECRET',
        ]

        missing_vars = []
        for var_name in required_vars:
            # Check if the corresponding attribute on self is None or empty
            attribute_name = var_name.lower()
            if not getattr(self, attribute_name, None):
                # Check if the environment variable itself was missing
                if not os.getenv(var_name):
                    missing_vars.append(var_name)

        if missing_vars:
            logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")
        else:
            logger.debug("All checked required environment variables are present.")


    def _log_config(self):
        """Log configuration summary."""
        logger.info("--- Configuration Summary ---")
        logger.info(f"Base Directory: {getattr(self, 'base_path', 'N/A')}")
        logger.info(f"Data Directory: {getattr(self, 'data_dir', 'N/A')}")
        logger.info(f"Log Directory: {getattr(self, 'log_dir', 'N/A')}")
        logger.info(f"Cache Directory: {getattr(self, 'cache_dir', 'N/A')}")
        logger.info(f"Assets Directory: {getattr(self, 'assets_dir', 'N/A')}")
        logger.info(f"Resources Directory: {getattr(self, 'resources_dir', 'N/A')}")
        logger.info(f"Exports Directory: {getattr(self, 'exports_dir', 'N/A')}")
        logger.info("--- End Configuration Summary ---")

    # Methods needed by main.py
    def get_setting(self, key, default=None):
        """Get a setting value with dot notation support.
        
        Args:
            key: Setting key (can use dot notation for nested settings)
            default: Default value to return if setting not found
            
        Returns:
            Setting value or default if not found
        """
        # First check if we have a direct attribute (legacy access)
        if hasattr(self, key):
            return getattr(self, key)
            
        # Check environment variables first (convention: uppercase)
        env_value = os.getenv(key.upper())
        if env_value is not None:
            # Basic type casting based on default type if available
            if default is not None:
                default_type = type(default)
                if default_type is bool:
                    return env_value.lower() in ('true', '1', 'yes', 'y')
                elif default_type is int:
                    try: return int(env_value)
                    except ValueError: pass
                elif default_type is float:
                    try: return float(env_value)
                    except ValueError: pass
            return env_value

        # Handle nested keys with dot notation
        if '.' in key:
            parts = key.split('.')
            current = self.config
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    return default
                current = current[part]
            
            return current.get(parts[-1], default)
        else:
            # Fallback to the config dictionary
            return self.config.get(key, default)

    def set_setting(self, key, value):
        """Set a setting value with dot notation support.
        
        Args:
            key: Setting key (can use dot notation for nested settings)
            value: Value to set
            
        Returns:
            True if setting was set successfully, False otherwise
        """
        try:
            # Handle nested keys with dot notation
            if '.' in key:
                parts = key.split('.')
                current = self.config
                
                # Create nested dicts if they don't exist
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    elif not isinstance(current[part], dict):
                        current[part] = {}
                    current = current[part]
                
                current[parts[-1]] = value
            else:
                self.config[key] = value
            
            return True
        except Exception as e:
            logger.error(f"Error setting '{key}' to '{value}': {str(e)}")
            return False

    def get(self, key, default=None):
        """Legacy get method for backward compatibility.
        
        Args:
            key: The configuration key
            default: Default value if key not found
            
        Returns:
            The configuration value
        """
        return self.get_setting(key, default)

    def save_settings(self):
        """Save the current configuration to file."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {self.settings_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False

    # Alias for compatibility with original code
    save = save_settings