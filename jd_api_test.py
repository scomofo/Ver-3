#!/usr/bin/env python3
"""
John Deere API Endpoint Test Script
This script tests access to various John Deere API endpoints using a provided access token.
It attempts to call different endpoints from Quote Data, PO Data, Maintain Quotes, and Customer Linkage APIs.
"""

import argparse
import json
import os
import requests
from datetime import datetime, timedelta

# Base URLs
QUOTE_DATA_BASE_URL = "https://jdquote2-api-sandbox.deere.com/om/cert/quotedata"
PO_DATA_BASE_URL = "https://jdquote2-api-sandbox.deere.com/om/cert/podata"
MAINTAIN_QUOTE_BASE_URL = "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote"
CUSTOMER_LINKAGE_BASE_URL = "https://sandboxapi.deere.com/platform/api"

def load_token_from_file(token_file):
    """Load the token from a file."""
    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)
            return token_data.get("access_token")
    except Exception as e:
        print(f"Error loading token: {e}")
        return None

def make_api_request(url, method="GET", headers=None, data=None, params=None):
    """Make an API request and return the response."""
    if headers is None:
        headers = {}
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            params=params,
            timeout=30
        )
        
        # Print request details
        print(f"\n{'-'*80}")
        print(f"Request: {method} {url}")
        if params:
            print(f"Params: {json.dumps(params, indent=2)}")
        if data:
            print(f"Data: {json.dumps(data, indent=2)}")
        
        # Print response details
        print(f"Response Status: {response.status_code}")
        try:
            resp_json = response.json()
            print(f"Response: {json.dumps(resp_json, indent=2)}")
            return response.status_code, resp_json
        except ValueError:
            if response.text:
                print(f"Response Text: {response.text[:500]}...")
                if len(response.text) > 500:
                    print("(Response truncated for readability)")
            else:
                print("No response body")
            return response.status_code, response.text
    except Exception as e:
        print(f"Request failed: {e}")
        return None, str(e)

def test_quote_data_api(token, dealer_id="X731804"):
    """Test various endpoints of the Quote Data API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("\n=== Testing Quote Data API ===")
    
    # Test Search Quote
    search_data = {
        "dealerAccountNumber": "731804",
        "beginDate": datetime.now().strftime("%d-%b-%y"),
        "endDate": (datetime.now() + timedelta(days=30)).strftime("%d-%b-%y")
    }
    
    make_api_request(
        url=f"{QUOTE_DATA_BASE_URL}/api/v1/quote-data",
        method="POST",
        headers=headers,
        data=search_data
    )
    
    # Test Get Last Modified Date (you need a valid quoteId)
    # Commenting out as we need a valid quoteId - uncomment and add a valid ID when testing
    # make_api_request(
    #     url=f"{QUOTE_DATA_BASE_URL}/api/v1/quotes/22769888/last-modified-date",
    #     headers=headers
    # )

def test_po_data_api(token, dealer_id="X731804"):
    """Test various endpoints of the PO Data API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("\n=== Testing PO Data API ===")
    
    # Test Get Blank PO PDF
    make_api_request(
        url=f"{PO_DATA_BASE_URL}/api/v1/dealers/{dealer_id}/blank-po-pdf",
        headers=headers
    )
    
    # Test Search Purchase Order
    search_data = {
        "dealerAccNumber": "731804",
        "startModifiedDate": datetime.now().strftime("%m-%d-%Y"),
        "endModifiedDate": (datetime.now() + timedelta(days=30)).strftime("%m-%d-%Y")
    }
    
    make_api_request(
        url=f"{PO_DATA_BASE_URL}/api/v1/purchase-orders",
        method="POST",
        headers=headers,
        data=search_data
    )

def test_maintain_quotes_api(token, dealer_id="X731804"):
    """Test various endpoints of the Maintain Quotes API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("\n=== Testing Maintain Quotes API ===")
    
    # Test Get Quotes
    data = {
        "dealerRacfID": dealer_id, 
        "startModifiedDate": "04-01-2025", 
        "endModifiedDate": "04-18-2025"
    }
    
    make_api_request(
        url=f"{MAINTAIN_QUOTE_BASE_URL}/api/v1/dealers/{dealer_id}/maintain-quotes",
        method="POST",
        headers=headers,
        data=data
    )
    
    # Test Get Master Quotes
    make_api_request(
        url=f"{MAINTAIN_QUOTE_BASE_URL}/api/v1/dealers/{dealer_id}/quotes",
        method="POST",
        headers=headers,
        data={"dealerRacfID": dealer_id}
    )

def test_customer_linkage_api(token, dealer_id="X731804"):
    """Test various endpoints of the Customer Linkage API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "appId": "123"  # Required header for some endpoints
    }
    
    print("\n=== Testing Customer Linkage API ===")
    
    # Test Retrieve Linkages
    make_api_request(
        url=f"{CUSTOMER_LINKAGE_BASE_URL}/retrieveLinkages",
        headers=headers,
        params={"dealerId": dealer_id}
    )
    
    # Test Retrieve Dealer Xref
    make_api_request(
        url=f"{CUSTOMER_LINKAGE_BASE_URL}/retrieveDealerXref",
        headers=headers,
        params={"dealerId": dealer_id}
    )

def main():
    """Main function to run the tests."""
    parser = argparse.ArgumentParser(description="Test John Deere API endpoints")
    parser.add_argument("--token", help="OAuth token to use for API calls")
    parser.add_argument("--token-file", help="File containing the OAuth token", default="cache/jd_token.json")
    parser.add_argument("--dealer-id", help="Dealer ID to use for API calls", default="X731804")
    args = parser.parse_args()
    
    # Get the token
    token = args.token
    if not token and args.token_file:
        token = load_token_from_file(args.token_file)
    
    if not token:
        print("Error: No token provided. Use --token or --token-file")
        return
    
    # Print token information (first few chars only for security)
    token_prefix = token[:10] if token else "None"
    print(f"Using token: {token_prefix}...")
    print(f"Using dealer ID: {args.dealer_id}")
    
    # Run the tests
    test_quote_data_api(token, args.dealer_id)
    test_po_data_api(token, args.dealer_id)
    test_maintain_quotes_api(token, args.dealer_id)
    test_customer_linkage_api(token, args.dealer_id)
    
    print("\n=== All tests completed ===")

if __name__ == "__main__":
    main()
