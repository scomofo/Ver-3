# utils/jd_auth_manager.py - Modified for compatibility with main.py
import os
import logging
import time
import hashlib
import json
import base64
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QFormLayout, QMessageBox, QApplication)
from PyQt5.QtCore import Qt
import requests

# Initialize logger 
logger = logging.getLogger('BCApp.JDAuthManager')

# Check if OAuth client is available
try:
    from .oauth_client import JohnDeereOAuthClient
    HAS_OAUTH_CLIENT = True
except ImportError:
    logger.warning("JohnDeereOAuthClient not found, using fallback authentication mechanism")
    HAS_OAUTH_CLIENT = False

class JDAuthManager:
    """Manager for John Deere API authentication."""
    
    def __init__(self, config=None, logger=None):
        """Initialize the auth manager.
        
        Args:
            config: Application configuration
            logger: Logger instance
        """
        self.config = config
        self.logger = logger or logging.getLogger('BCApp.JDAuthManager')
        
        # Set up auth state properties
        self.authenticated = False
        self.auth_token = None
        self.auth_expiry = 0
        self.user_id = None
        self.dealer_id = None
        
        # Get credentials from environment or config
        self.client_id = os.getenv('JD_CLIENT_ID', '')
        self.client_secret = os.getenv('DEERE_CLIENT_SECRET', '')
        
        # Override with config if available
        if config:
            # Try to get credentials from different possible attribute names
            if hasattr(config, 'jd_client_id') and config.jd_client_id:
                self.client_id = config.jd_client_id
            if hasattr(config, 'jd_client_secret') and config.jd_client_secret:
                self.client_secret = config.jd_client_secret
                
            # Also try using get_setting for dictionary-based access
            if hasattr(config, 'get_setting'):
                if not self.client_id:
                    self.client_id = config.get_setting('jd_client_id', '')
                if not self.client_secret:
                    self.client_secret = config.get_setting('jd_client_secret', '')
                    
                # Also try nested settings
                if not self.client_id or not self.client_secret:
                    jd_auth = config.get_setting('jd_auth', {})
                    if isinstance(jd_auth, dict):
                        self.client_id = jd_auth.get('client_id', self.client_id)
                        self.client_secret = jd_auth.get('client_secret', self.client_secret)
                        
                        # Also check credentials sub-dictionary
                        credentials = jd_auth.get('credentials', {})
                        if isinstance(credentials, dict):
                            if not self.client_id:
                                self.client_id = credentials.get('client_id', '')
        
        # Set up cache path
        self.cache_path = self._get_token_cache_dir()
        
        # Initialize the OAuth client if available
        self.oauth_client = None
        if HAS_OAUTH_CLIENT and self.client_id and self.client_secret:
            try:
                self.oauth_client = JohnDeereOAuthClient(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    cache_path=self.cache_path,
                    logger=self.logger
                )
            except Exception as e:
                self.logger.error(f"Error initializing OAuth client: {str(e)}")
        
        # Try to load cached token
        self._load_cached_auth()
    
    def authenticate(self, username, password, remember=False):
        """
        Authenticate with John Deere API using username and password.
        
        Args:
            username: JD Dealer username (usually RACF ID)
            password: JD Dealer password
            remember: Whether to remember credentials for future use
            
        Returns:
            Tuple of (success, message)
        """
        if not username or not password:
            return False, "Username and password are required"
            
        # If we have OAuth client, use that
        if self.oauth_client:
            try:
                token = self.oauth_client.authenticate(username, password)
                if token:
                    self.auth_token = token
                    self.auth_expiry = time.time() + 3600  # Assume 1 hour validity
                    self.authenticated = True
                    
                    # Fetch additional info if available
                    self._fetch_user_info()
                    
                    # Save credentials if requested
                    if remember and self.config:
                        self._save_user_info(username, password)
                    
                    self.logger.info(f"OAuth authentication successful for {username}")
                    return True, "Authentication successful"
                else:
                    return False, "Authentication failed"
            except Exception as e:
                self.logger.error(f"OAuth authentication error: {str(e)}")
                return False, f"Authentication error: {str(e)}"
        
        # Fallback to direct API authentication
        try:
            self.logger.info(f"Authenticating user: {username}")
            
            # Build authentication request
            auth_url = "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote/api/v1/auth"
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Include client ID/secret if available
            if self.client_id and self.client_secret:
                auth_string = f"{self.client_id}:{self.client_secret}"
                encoded_auth = base64.b64encode(auth_string.encode()).decode()
                headers['Authorization'] = f"Basic {encoded_auth}"
            
            data = {
                'username': username,
                'password': password,
                'grantType': 'password'
            }
            
            # Send authentication request
            response = requests.post(auth_url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                # Parse response
                auth_data = response.json()
                
                # Check required fields
                if 'token' not in auth_data or 'user' not in auth_data:
                    self.logger.warning("Authentication response missing required fields")
                    return False, "Authentication response incomplete"
                
                # Extract token and user information
                self.auth_token = auth_data['token']
                self.auth_expiry = time.time() + auth_data.get('expiresIn', 43200)  # Default 12 hours
                self.user_id = auth_data['user'].get('userId')
                self.dealer_id = auth_data['user'].get('dealerId')
                
                # Cache token
                self._cache_token(self.auth_token, self.auth_expiry)
                
                # Save user info if remember is enabled
                if remember and self.config:
                    self._save_user_info(username, password if remember else None)
                
                self.authenticated = True
                self.logger.info(f"Authentication successful for user {username}")
                return True, "Authentication successful"
            else:
                error_msg = f"Authentication failed: {response.status_code}"
                if response.text:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('message', error_msg)
                    except:
                        error_msg = f"{error_msg} - {response.text}"
                
                self.logger.warning(f"Authentication failed: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Error connecting to JD API: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error during authentication: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def is_authenticated(self):
        """
        Check if the user is currently authenticated.
        
        Returns:
            True if authenticated and token is valid, False otherwise
        """
        # Check if we have a token and it's not expired (with 5-minute buffer)
        return (self.authenticated and self.auth_token and
                self.auth_expiry > time.time() + 300)
    
    def get_auth_header(self):
        """
        Get authentication header for API requests.
        
        Returns:
            Dictionary with Authorization header
        """
        if not self.is_authenticated():
            # Try to refresh from cache
            if self._load_cached_auth() and self.is_authenticated():
                pass  # Successfully refreshed
            else:
                self.logger.warning("Attempted to get auth header but not authenticated")
                return {}
        
        return {
            'Authorization': f"Bearer {self.auth_token}"
        }
    
    def logout(self):
        """
        Log out the current user and clear authentication data.
        
        Returns:
            True if logout was successful, False otherwise
        """
        try:
            # Clear local authentication state
            self.authenticated = False
            self.auth_token = None
            self.auth_expiry = 0
            
            # Clear cached token
            try:
                token_file = os.path.join(self.cache_path, "jd_token.json")
                if os.path.exists(token_file):
                    os.remove(token_file)
            except Exception as e:
                self.logger.warning(f"Error clearing token cache: {str(e)}")
            
            self.logger.info("User logged out successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error during logout: {str(e)}")
            return False
    
    def get_user_id(self):
        """
        Get the ID of the authenticated user.
        
        Returns:
            User ID if authenticated, None otherwise
        """
        return self.user_id if self.is_authenticated() else None
    
    def get_dealer_id(self):
        """
        Get the dealer ID of the authenticated user.
        
        Returns:
            Dealer ID if authenticated, None otherwise
        """
        return self.dealer_id if self.is_authenticated() else None
    
    def get_access_token(self, force_refresh=False):
        """
        Get an access token for John Deere API.
        Added for compatibility with existing JDAuthManager.
        
        Args:
            force_refresh: Whether to force refresh the token
            
        Returns:
            Access token string or None
        """
        if force_refresh:
            # If we have OAuth client, use it to refresh
            if self.oauth_client:
                try:
                    token = self.oauth_client.get_token(force_refresh=True)
                    if token:
                        self.auth_token = token
                        self.auth_expiry = time.time() + 3600  # Assume 1 hour validity
                        self.authenticated = True
                        return token
                except Exception as e:
                    self.logger.error(f"Error refreshing token: {str(e)}")
            
            # If OAuth refresh fails or not available, clear and return None
            self.authenticated = False
            self.auth_token = None
            self.auth_expiry = 0
            return None
                
        # Check if current token is valid
        if self.is_authenticated():
            return self.auth_token
            
        # Try to load from cache
        if self._load_cached_auth() and self.is_authenticated():
            return self.auth_token
            
        # No valid token available
        return None
    
    def make_api_request(self, method, endpoint, data=None, params=None, timeout=30):
        """
        Make an authenticated request to the JD API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/dealers/{dealer_id}/quotes")
            data: Request data (for POST/PUT) - will be JSON-encoded
            params: Query parameters (for GET)
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (success, response_data or error_message)
        """
        if not self.is_authenticated():
            return False, "Not authenticated"
        
        try:
            # Build request URL
            if endpoint.startswith('http'):
                url = endpoint  # Full URL provided
            else:
                # Strip leading slash if present
                if endpoint.startswith('/'):
                    endpoint = endpoint[1:]
                url = f"https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote/{endpoint}"
            
            # Prepare headers
            headers = {
                'Authorization': f"Bearer {self.auth_token}",
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Make request
            method = method.upper()
            self.logger.debug(f"Making {method} request to {url}")
            
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            else:
                return False, f"Unsupported HTTP method: {method}"
            
            # Handle response
            if response.status_code in (200, 201, 204):
                if response.status_code == 204 or not response.text:
                    return True, {}  # No content
                else:
                    try:
                        return True, response.json()
                    except ValueError:
                        return True, response.text
            else:
                error_msg = f"API request failed: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    if response.text:
                        error_msg = f"{error_msg} - {response.text}"
                
                self.logger.warning(f"API request failed: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Error connecting to JD API: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error during API request: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def _get_token_cache_dir(self):
        """
        Get the directory for caching authentication tokens.
        
        Returns:
            Path to the token cache directory
        """
        # Use user's home directory, under .bcapp/tokens
        cache_dir = os.path.join(os.path.expanduser('~'), '.bcapp', 'tokens')
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    
    def _cache_token(self, token, expiry_time):
        """
        Cache a token to file.
        
        Args:
            token: Token string
            expiry_time: Expiry time in seconds since epoch
            
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            token_file = os.path.join(self.cache_path, "jd_token.json")
            token_data = {
                'access_token': token,
                'expires_at': expiry_time,
                'saved_at': time.time()
            }
            
            with open(token_file, 'w') as f:
                json.dump(token_data, f)
                
            self.logger.info(f"Token cached to {token_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error caching token: {str(e)}")
            return False
    
    def _load_cached_auth(self):
        """
        Load authentication from cached token.
        
        Returns:
            True if authentication was loaded successfully, False otherwise
        """
        try:
            token_file = os.path.join(self.cache_path, "jd_token.json")
            if not os.path.exists(token_file):
                return False
                
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                
            # Check if token has expired (with 5-minute buffer)
            if 'expires_at' not in token_data or token_data['expires_at'] <= time.time() + 300:
                self.logger.info("Cached token has expired")
                return False
                
            # Get the token
            if 'access_token' not in token_data:
                self.logger.error("Cached token data is invalid (missing access_token)")
                return False
                
            self.auth_token = token_data['access_token']
            self.auth_expiry = token_data['expires_at']
            self.authenticated = True
            
            # Try to get user and dealer IDs if possible
            self._fetch_user_info()
            
            self.logger.info("Successfully authenticated using cached token")
            return True
                
        except Exception as e:
            self.logger.error(f"Error loading cached authentication: {str(e)}")
            return False
    
    def _fetch_user_info(self):
        """
        Fetch user information using the current token.
        
        Returns:
            True if user info was fetched successfully, False otherwise
        """
        try:
            # Only proceed if we have a token
            if not self.auth_token:
                return False
            
            # Make API request to get user info
            success, response = self.make_api_request(
                'GET', '/api/v1/user-info'
            )
            
            if success and isinstance(response, dict):
                self.user_id = response.get('userId')
                self.dealer_id = response.get('dealerId')
                self.logger.info(f"Fetched user info: userId={self.user_id}, dealerId={self.dealer_id}")
                return True
            else:
                self.logger.warning("Failed to fetch user information")
                return False
                
        except Exception as e:
            self.logger.error(f"Error fetching user information: {str(e)}")
            return False
    
    def _save_user_info(self, username, password=None):
        """
        Save user credentials to config if remember is enabled.
        
        Args:
            username: Username to save
            password: Password to save (None if not saving password)
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self.config:
            return False
            
        try:
            # Get current JD auth settings
            jd_auth = {}
            if hasattr(self.config, 'get_setting'):
                jd_auth = self.config.get_setting("jd_auth", {})
            
            # Update credentials
            credentials = {}
            credentials["username"] = username
            
            if password:
                # Simple encryption (not secure, but better than plaintext)
                salt = hashlib.sha256(username.encode()).hexdigest()[:16]
                hashed_pw = hashlib.pbkdf2_hmac(
                    'sha256', password.encode(), salt.encode(), 10000
                ).hex()
                credentials["password"] = hashed_pw
                credentials["salt"] = salt
            
            jd_auth["credentials"] = credentials
            jd_auth["remember_credentials"] = (password is not None)
            
            # Save to config
            if hasattr(self.config, 'set_setting'):
                self.config.set_setting("jd_auth", jd_auth)
                
                if hasattr(self.config, 'save_settings'):
                    self.config.save_settings()
                elif hasattr(self.config, 'save'):
                    self.config.save()
            
            self.logger.info(f"Saved user credentials for {username} (password: {'yes' if password else 'no'})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving user credentials: {str(e)}")
            return False
    
    def setup_api_client(self, api_client):
        """
        Set up an API client with authentication.
        Added for compatibility with your existing JDAuthManager.
        
        Args:
            api_client: API client instance to set up
            
        Returns:
            True if successful, False otherwise
        """
        if not api_client:
            self.logger.error("No API client provided")
            return False
        
        # Get an access token
        token = self.get_access_token()
        if not token:
            self.logger.error("Failed to get access token")
            return False
        
        # Set the token on the API client
        if hasattr(api_client, 'set_access_token'):
            api_client.set_access_token(token)
            return True
        else:
            self.logger.error("API client does not have set_access_token method")
            return False
    
    def cleanup(self):
        """Perform cleanup before application exit."""
        self.logger.debug("Performing JDAuthManager cleanup")
        # Nothing specific to clean up at the moment
        pass