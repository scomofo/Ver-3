import requests
import logging
import json
import base64
import time
from datetime import datetime
from functools import wraps

# Set up logging
logger = logging.getLogger('JDQuoteApp.QuoteClient')

def retry_on_error(max_retries=3, backoff_factor=0.5, error_codes=(408, 429, 500, 502, 503, 504)):
    """Retry decorator for API calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    # Check if we should retry based on status code
                    if hasattr(e, 'response') and e.response is not None:
                        if e.response.status_code not in error_codes:
                            raise  # Don't retry for unspecified status codes
                            
                    # Increment retries and calculate delay
                    retries += 1
                    if retries >= max_retries:
                        raise  # Max retries reached, re-raise the exception
                        
                    # Calculate delay with exponential backoff
                    delay = backoff_factor * (2 ** (retries - 1))
                    logger.warning(f"Request failed, retrying in {delay:.2f} seconds... ({retries}/{max_retries})")
                    time.sleep(delay)
            
            # This should never be reached
            raise Exception("Unexpected error in retry logic")
        return wrapper
    return decorator

class MaintainQuoteClient:
    """Client for interacting with John Deere Quote APIs."""
    
    def __init__(self, oauth_client, base_url=None):
        """
        Initialize the quote client
        
        Args:
            oauth_client: OAuth client for authentication
            base_url (str): Base URL for the API
        """
        self.oauth_client = oauth_client
        self.base_url = base_url or "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote"
        logger.info(f"Quote client initialized with URL: {self.base_url}")
    
    @retry_on_error()
    def _make_request(self, method, endpoint, data=None, params=None, timeout=60):
        """
        Make a request to the API
        
        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint
            data (dict): Data to send with the request
            params (dict): Query parameters
            timeout (int): Request timeout in seconds
            
        Returns:
            dict: API response
        """
        # Get the auth header from the OAuth client
        auth_header = self.oauth_client.get_auth_header()
        
        # Set up headers
        headers = {
            "Authorization": auth_header if auth_header.startswith("Bearer ") else f"Bearer {auth_header}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Construct the URL - ensure we have the right format
        if endpoint.startswith('/'):
            url = f"{self.base_url}{endpoint}"
        else:
            url = f"{self.base_url}/{endpoint}"
        
        # Make the request
        logger.debug(f"Making {method} request to {url}")
        if data:
            logger.debug(f"With data payload: {json.dumps(data, default=str)[:1000]}...")
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=timeout)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=timeout, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check for errors
            if response.status_code >= 400:
                error_message = f"API request failed: {response.status_code}"
                try:
                    error_data = response.json()
                    if "errorMessage" in error_data:
                        error_message = f"{error_message} - {error_data['errorMessage']}"
                except:
                    if response.text:
                        error_message = f"{error_message} - {response.text[:500]}"
                        
                logger.error(error_message)
                response.raise_for_status()
            
            # Return the response
            try:
                return response.json()
            except ValueError:
                # If the response is not JSON, return the raw content
                return {"body": response.text}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise
    
    @retry_on_error()
    def search_quotes(self, search_criteria):
        """
        Search for quotes with the given criteria
        
        Args:
            search_criteria (dict): Search criteria
                
        Returns:
            dict: API response with quotes
        """
        logger.info(f"Searching quotes with criteria: {json.dumps(search_criteria)}")
        
        # Prepare the request data
        data = {}
        
        # Add dealer account number
        if "dealerAccountNumber" not in search_criteria:
            from_config = True
            # Try to get dealer account number from config
            import os
            config_file = os.path.join(os.getcwd(), "jd_quote_config.json")
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                dealer_account = config.get("jd", {}).get("dealer_account_number")
                if dealer_account:
                    data["dealerAccountNumber"] = dealer_account
            except:
                pass
        
        # Format date range if provided
        if "dateRange" in search_criteria:
            date_range = search_criteria["dateRange"]
            
            if "from" in date_range:
                # Convert from YYYY-MM-DD to API format
                data["beginDate"] = date_range["from"]
            
            if "to" in date_range:
                # API expects endDate to be 30 days after the specified date
                # So we just use the provided date
                data["endDate"] = date_range["to"]
            
            # If no end date, use current date + 30 days
            if "from" in date_range and "to" not in date_range:
                from datetime import datetime, timedelta
                end_date = datetime.now() + timedelta(days=30)
                data["endDate"] = end_date.strftime("%Y-%m-%d")
        
        # Add other search criteria
        for key, value in search_criteria.items():
            if key != "dateRange":
                data[key] = value
                
        # Debug formatted criteria
        logger.debug(f"Formatted criteria being sent to API: {json.dumps(data, default=str)}")
        
        # For Quote Data API, try the quote-data endpoint instead
        if "/quotedata" in self.base_url.lower():
            endpoint = "/api/v1/quote-data"
        else:
            # Original Maintain Quote API endpoint
            endpoint = "/api/v1/quotes"
            
        return self._make_request("POST", endpoint, data)
    
    @retry_on_error()
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
    
    @retry_on_error()
    def create_quote(self, quote_data):
        """
        Create a new quote
        
        Args:
            quote_data (dict): Quote data
                
        Returns:
            dict: API response with created quote ID
        """
        logger.info("Creating a new quote")
        
        # Ensure date formats are correct
        if "expirationDate" in quote_data:
            try:
                # Try to parse and format the date if needed
                date_str = quote_data["expirationDate"]
                if "-" in date_str:  # YYYY-MM-DD format
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    quote_data["expirationDate"] = date_obj.strftime("%m/%d/%Y")
            except Exception as e:
                logger.warning(f"Error formatting expiration date: {str(e)}")
        
        # For Quote Data API, use the quotes endpoint
        if "/quotedata" in self.base_url.lower():
            endpoint = "/api/v1/quotes"
        else:
            # Original Maintain Quote API endpoint
            endpoint = "/api/v1/maintain-quotes"
                
        return self._make_request("POST", endpoint, quote_data)
    
    @retry_on_error()
    def update_quote(self, quote_id, quote_data):
        """
        Update an existing quote
        
        Args:
            quote_id (str): Quote ID 
            quote_data (dict): Quote data to update
                
        Returns:
            dict: API response
        """
        logger.info(f"Updating quote {quote_id}")
        
        # Ensure date formats are correct
        if "expirationDate" in quote_data:
            try:
                # Try to parse and format the date if needed
                date_str = quote_data["expirationDate"]
                if "-" in date_str:  # YYYY-MM-DD format
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    quote_data["expirationDate"] = date_obj.strftime("%m/%d/%Y")
            except Exception as e:
                logger.warning(f"Error formatting expiration date: {str(e)}")
        
        # For Quote Data API, use the quotes endpoint
        if "/quotedata" in self.base_url.lower():
            endpoint = f"/api/v1/quotes/{quote_id}"
        else:
            # Original Maintain Quote API endpoint
            endpoint = f"/api/v1/quotes/{quote_id}/maintain-quotes"
                
        return self._make_request("PUT", endpoint, quote_data)
    
    @retry_on_error()
    def copy_quote(self, quote_id, dealer_id, expiration_date=None):
        """
        Create a copy of an existing quote
        
        Args:
            quote_id (str): Quote ID to copy
            dealer_id (str): Dealer ID
            expiration_date (str, optional): Expiration date for the new quote
                
        Returns:
            dict: API response with new quote ID
        """
        logger.info(f"Copying quote {quote_id}")
        
        data = {
            "dealerID": dealer_id,
            "quoteID": quote_id
        }
        
        if expiration_date:
            # Ensure date format is correct
            try:
                if "-" in expiration_date:  # YYYY-MM-DD format
                    date_obj = datetime.strptime(expiration_date, "%Y-%m-%d")
                    expiration_date = date_obj.strftime("%m/%d/%Y")
            except Exception as e:
                logger.warning(f"Error formatting expiration date: {str(e)}")
                
            data["expirationDate"] = expiration_date
        
        endpoint = f"/api/v1/quotes/{quote_id}/copy-quote"
                
        return self._make_request("POST", endpoint, data)
    
    @retry_on_error()
    def set_expiration_date(self, quote_id, expiration_date, racf_id):
        """
        Set expiration date for a quote
        
        Args:
            quote_id (str): Quote ID
            expiration_date (str): Expiration date in format YYYY-MM-DD
            racf_id (str): RACF ID
                
        Returns:
            dict: API response
        """
        logger.info(f"Setting expiration date for quote {quote_id}")
        
        # Ensure date format is correct
        try:
            if "-" in expiration_date:  # YYYY-MM-DD format
                date_obj = datetime.strptime(expiration_date, "%Y-%m-%d")
                expiration_date = date_obj.strftime("%m/%d/%Y")
        except Exception as e:
            logger.warning(f"Error formatting expiration date: {str(e)}")
        
        data = {
            "quoteId": quote_id,
            "expirationDate": expiration_date,
            "racfId": racf_id
        }
        
        endpoint = f"/api/v1/quotes/{quote_id}/expiration-date"
                
        return self._make_request("POST", endpoint, data)
    
    @retry_on_error(max_retries=2, backoff_factor=1.0)
    def get_proposal_pdf(self, quote_id):
        """
        Get proposal PDF for a quote with improved error handling.
        
        Args:
            quote_id (str): Quote ID
            
        Returns:
            bytes: PDF binary data
            
        Raises:
            Exception: If API request fails or PDF data is invalid
        """
        logger.info(f"Getting proposal PDF for quote {quote_id}")
        
        # Configure headers correctly for PDF retrieval
        auth_header = self.oauth_client.get_auth_header()
        headers = {
            "Authorization": auth_header if auth_header.startswith("Bearer ") else f"Bearer {auth_header}",
            "Accept": "application/pdf, application/octet-stream, */*"  # Accept both direct PDF and JSON formats
        }
        
        endpoint = f"/api/v1/quotes/{quote_id}/proposal-pdf"
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.debug(f"Making PDF request to {url}")
            response = requests.get(url, headers=headers, timeout=60)  # Longer timeout for PDF generation
            
            # Check for errors
            if response.status_code != 200:
                logger.error(f"PDF API request failed: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get PDF: HTTP {response.status_code}")
            
            # Check the content type
            content_type = response.headers.get('Content-Type', '')
            
            # Handle direct PDF response
            if 'application/pdf' in content_type or 'application/octet-stream' in content_type:
                logger.debug(f"Received direct PDF response, {len(response.content)} bytes")
                return response.content
            
            # Handle JSON response with embedded PDF
            if 'application/json' in content_type:
                try:
                    data = response.json()
                    logger.debug(f"Received JSON response, extracting PDF data")
                    
                    # Extract PDF data using a more robust approach
                    if "body" in data:
                        body = data["body"]
                        
                        # Try different possible PDF field locations
                        if isinstance(body, dict):
                            # Option 1: PDF directly in body
                            if "pdf" in body and isinstance(body["pdf"], str):
                                try:
                                    return base64.b64decode(body["pdf"])
                                except:
                                    logger.warning("Failed to decode PDF data from 'body.pdf' field")
                            
                            # Option 2: PDF in nested object
                            if "pdf" in body and isinstance(body["pdf"], dict):
                                pdf_obj = body["pdf"]
                                for field in ["value", "content", "data", "file", "bytes"]:
                                    if field in pdf_obj and isinstance(pdf_obj[field], str):
                                        try:
                                            return base64.b64decode(pdf_obj[field])
                                        except:
                                            logger.warning(f"Failed to decode PDF data from 'body.pdf.{field}' field")
                    
                    # If we reached here, we couldn't extract the PDF data
                    logger.error("Could not extract PDF data from JSON response")
                    logger.debug(f"Response data structure: {json.dumps(data, indent=2)[:1000]}...")
                    raise Exception("Could not extract PDF data from response")
                    
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON response")
                    raise Exception("Invalid response format")
            
            # Unknown format
            logger.error(f"Unrecognized response content type: {content_type}")
            raise Exception(f"Unrecognized response format: {content_type}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error getting PDF: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting PDF: {str(e)}")
            raise
    
    @retry_on_error(max_retries=2, backoff_factor=1.0)
    def get_order_form_pdf(self, quote_id):
        """
        Get order form PDF for a quote with improved error handling.
        
        Args:
            quote_id (str): Quote ID
            
        Returns:
            bytes: PDF binary data
        """
        logger.info(f"Getting order form PDF for quote {quote_id}")
        endpoint = f"/api/v1/quotes/{quote_id}/order-form-pdf"
        
        # Configure headers correctly for PDF retrieval
        auth_header = self.oauth_client.get_auth_header()
        headers = {
            "Authorization": auth_header if auth_header.startswith("Bearer ") else f"Bearer {auth_header}",
            "Accept": "application/pdf, application/octet-stream, */*"  # Accept both direct PDF and JSON formats
        }
        
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"Making PDF request to {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=60)  # Longer timeout for PDF generation
            
            # Check for errors
            if response.status_code != 200:
                logger.error(f"PDF API request failed: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get PDF: HTTP {response.status_code}")
            
            # Check the content type
            content_type = response.headers.get('Content-Type', '')
            
            # Handle direct PDF response
            if 'application/pdf' in content_type or 'application/octet-stream' in content_type:
                logger.debug(f"Received direct PDF response, {len(response.content)} bytes")
                return response.content
            
            # Handle JSON response with embedded PDF
            if 'application/json' in content_type:
                try:
                    data = response.json()
                    logger.debug(f"Received JSON response, extracting PDF data")
                    
                    # Extract PDF data using a more robust approach
                    if "body" in data:
                        body = data["body"]
                        
                        # Try different possible PDF field locations
                        if isinstance(body, dict):
                            # Option 1: PDF directly in body
                            if "pdf" in body and isinstance(body["pdf"], str):
                                try:
                                    return base64.b64decode(body["pdf"])
                                except:
                                    logger.warning("Failed to decode PDF data from 'body.pdf' field")
                            
                            # Option 2: PDF in nested object
                            if "pdf" in body and isinstance(body["pdf"], dict):
                                pdf_obj = body["pdf"]
                                for field in ["value", "content", "data", "file", "bytes"]:
                                    if field in pdf_obj and isinstance(pdf_obj[field], str):
                                        try:
                                            return base64.b64decode(pdf_obj[field])
                                        except:
                                            logger.warning(f"Failed to decode PDF data from 'body.pdf.{field}' field")
                    
                    # If we reached here, we couldn't extract the PDF data
                    logger.error("Could not extract PDF data from JSON response")
                    logger.debug(f"Response data structure: {json.dumps(data, indent=2)[:1000]}...")
                    raise Exception("Could not extract PDF data from response")
                    
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON response")
                    raise Exception("Invalid response format")
            
            # Unknown format
            logger.error(f"Unrecognized response content type: {content_type}")
            raise Exception(f"Unrecognized response format: {content_type}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error getting PDF: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting PDF: {str(e)}")
            raise
    
    @retry_on_error(max_retries=2, backoff_factor=1.0)
    def get_recap_pdf(self, quote_id):
        """
        Get recap PDF for a quote with improved error handling.
        
        Args:
            quote_id (str): Quote ID
            
        Returns:
            bytes: PDF binary data
        """
        logger.info(f"Getting recap PDF for quote {quote_id}")
        endpoint = f"/api/v1/quotes/{quote_id}/recap-pdf"
        
        # Configure headers correctly for PDF retrieval
        auth_header = self.oauth_client.get_auth_header()
        headers = {
            "Authorization": auth_header if auth_header.startswith("Bearer ") else f"Bearer {auth_header}",
            "Accept": "application/pdf, application/octet-stream, */*"  # Accept both direct PDF and JSON formats
        }
        
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"Making PDF request to {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=60)  # Longer timeout for PDF generation
            
            # Check for errors
            if response.status_code != 200:
                logger.error(f"PDF API request failed: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get PDF: HTTP {response.status_code}")
            
            # Check the content type
            content_type = response.headers.get('Content-Type', '')
            
            # Handle direct PDF response
            if 'application/pdf' in content_type or 'application/octet-stream' in content_type:
                logger.debug(f"Received direct PDF response, {len(response.content)} bytes")
                return response.content
            
            # Handle JSON response with embedded PDF
            if 'application/json' in content_type:
                try:
                    data = response.json()
                    logger.debug(f"Received JSON response, extracting PDF data")
                    
                    # Extract PDF data using a more robust approach
                    if "body" in data:
                        body = data["body"]
                        
                        # Try different possible PDF field locations
                        if isinstance(body, dict):
                            # Option 1: PDF directly in body
                            if "pdf" in body and isinstance(body["pdf"], str):
                                try:
                                    return base64.b64decode(body["pdf"])
                                except:
                                    logger.warning("Failed to decode PDF data from 'body.pdf' field")
                            
                            # Option 2: PDF in nested object
                            if "pdf" in body and isinstance(body["pdf"], dict):
                                pdf_obj = body["pdf"]
                                for field in ["value", "content", "data", "file", "bytes"]:
                                    if field in pdf_obj and isinstance(pdf_obj[field], str):
                                        try:
                                            return base64.b64decode(pdf_obj[field])
                                        except:
                                            logger.warning(f"Failed to decode PDF data from 'body.pdf.{field}' field")
                    
                    # If we reached here, we couldn't extract the PDF data
                    logger.error("Could not extract PDF data from JSON response")
                    logger.debug(f"Response data structure: {json.dumps(data, indent=2)[:1000]}...")
                    raise Exception("Could not extract PDF data from response")
                    
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON response")
                    raise Exception("Invalid response format")
            
            # Unknown format
            logger.error(f"Unrecognized response content type: {content_type}")
            raise Exception(f"Unrecognized response format: {content_type}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error getting PDF: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting PDF: {str(e)}")
            raise
    
    @retry_on_error()
    def delete_quote(self, quote_id, dealer_id):
        """
        Delete a quote
        
        Args:
            quote_id (str): Quote ID
            dealer_id (str): Dealer ID
                
        Returns:
            dict: API response
        """
        logger.info(f"Deleting quote {quote_id} for dealer {dealer_id}")
        
        # For Quote Data API, use the quotes endpoint with dealer ID
        if "/quotedata" in self.base_url.lower():
            endpoint = f"/api/v1/quotes/{quote_id}/dealers/{dealer_id}"
        else:
            # Original Maintain Quote API endpoint
            endpoint = f"/api/v1/quotes/{quote_id}/dealers/{dealer_id}"
                
        return self._make_request("DELETE", endpoint)