import requests
import json
from datetime import datetime

class MaintainQuoteClient:
    """
    Client for interacting with the John Deere Maintain Quote API
    """
    
    def __init__(self, oauth_client, base_url=None):
        """
        Initialize the Maintain Quote API client
        
        Args:
            oauth_client: OAuth client for authentication
            base_url (str, optional): Base URL for API requests. Defaults to sandbox URL.
        """
        self.oauth_client = oauth_client
        self.base_url = base_url or "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote"
    
    def _make_request(self, method, endpoint, params=None, data=None):
        """
        Make an API request
        
        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint
            params (dict, optional): Query parameters
            data (dict, optional): Request body data
            
        Returns:
            dict: JSON response data
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.oauth_client.get_auth_header()
        
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, params=params, json=data)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, params=params, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, params=params, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        if response.status_code >= 400:
            raise Exception(f"API request failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    def create_quote(self, quote_data):
        """
        Create a new quote
        
        Args:
            quote_data (dict): Quote data
            
        Returns:
            dict: Created quote information
        """
        return self._make_request("POST", "/api/v1/maintain-quotes", data=quote_data)
    
    def add_equipment(self, quote_id, equipment_data):
        """
        Add equipment to a quote
        
        Args:
            quote_id (str): Quote ID
            equipment_data (dict): Equipment data
            
        Returns:
            dict: Response data
        """
        return self._make_request("POST", f"/api/v1/quotes/{quote_id}/equipments", data=equipment_data)
    
    def add_master_quote(self, quote_id, master_quote_data):
        """
        Add a master quote to a quote
        
        Args:
            quote_id (str): Quote ID
            master_quote_data (dict): Master quote data
            
        Returns:
            dict: Response data
        """
        return self._make_request("POST", f"/api/v1/quotes/{quote_id}/master-quotes", data=master_quote_data)
    
    def copy_quote(self, quote_id, copy_data):
        """
        Copy a quote
        
        Args:
            quote_id (str): Quote ID to copy
            copy_data (dict): Copy options
            
        Returns:
            dict: Copied quote information
        """
        return self._make_request("POST", f"/api/v1/quotes/{quote_id}/copy-quote", data=copy_data)
    
    def delete_equipment(self, quote_id, equipment_data):
        """
        Delete equipment from a quote
        
        Args:
            quote_id (str): Quote ID
            equipment_data (dict): Equipment data to delete
            
        Returns:
            dict: Response data
        """
        return self._make_request("DELETE", f"/api/v1/quotes/{quote_id}/equipments", data=equipment_data)
    
    def get_quote_details(self, quote_id):
        """
        Get detailed information about a quote
        
        Args:
            quote_id (str): Quote ID
            
        Returns:
            dict: Quote details
        """
        return self._make_request("GET", f"/api/v1/quotes/{quote_id}/maintain-quote-details")
    
    def create_dealer_quote(self, dealer_id, quote_data):
        """
        Create a quote for a specific dealer
        
        Args:
            dealer_id (str): Dealer ID
            quote_data (dict): Quote data
            
        Returns:
            dict: Created quote information
        """
        return self._make_request("POST", f"/api/v1/dealers/{dealer_id}/quotes", data=quote_data)
    
    def update_expiration_date(self, quote_id, expiration_data):
        """
        Update the expiration date of a quote
        
        Args:
            quote_id (str): Quote ID
            expiration_data (dict): Expiration date data
            
        Returns:
            dict: Response data
        """
        return self._make_request("POST", f"/api/v1/quotes/{quote_id}/expiration-date", data=expiration_data)
    
    def create_dealer_maintain_quote(self, dealer_racf_id, quote_data):
        """
        Create a maintenance quote for a specific dealer
        
        Args:
            dealer_racf_id (str): Dealer RACF ID
            quote_data (dict): Quote data
            
        Returns:
            dict: Created quote information
        """
        return self._make_request("POST", f"/api/v1/dealers/{dealer_racf_id}/maintain-quotes", data=quote_data)
    
    def update_quote(self, quote_id, quote_data):
        """
        Update a quote
        
        Args:
            quote_id (str): Quote ID
            quote_data (dict): Updated quote data
            
        Returns:
            dict: Updated quote information
        """
        return self._make_request("PUT", f"/api/v1/quotes/{quote_id}/maintain-quotes", data=quote_data)
    
    def save_quote(self, quote_id, quote_data):
        """
        Save a quote
        
        Args:
            quote_id (str): Quote ID
            quote_data (dict): Quote data to save
            
        Returns:
            dict: Saved quote information
        """
        return self._make_request("POST", f"/api/v1/quotes/{quote_id}/save-quotes", data=quote_data)
    
    def add_trade_in(self, quote_id, trade_in_data):
        """
        Add trade-in information to a quote
        
        Args:
            quote_id (str): Quote ID
            trade_in_data (dict): Trade-in data
            
        Returns:
            dict: Response data
        """
        return self._make_request("POST", f"/api/v1/quotes/{quote_id}/trade-in", data=trade_in_data)
    
    def delete_quote(self, quote_id, dealer_id):
        """
        Delete a quote
        
        Args:
            quote_id (str): Quote ID
            dealer_id (str): Dealer ID
            
        Returns:
            dict: Response data
        """
        return self._make_request("DELETE", f"/api/v1/quotes/{quote_id}/dealers/{dealer_id}")