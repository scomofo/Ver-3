#!/usr/bin/env python3
"""
Revised John Deere API Endpoint Test Script
Filename: jd_api_test_revised.py
"""

import argparse
import json
import os
import requests
import base64
from datetime import datetime, timedelta

# Base URLs - some adjustments based on API docs
QUOTE_DATA_BASE_URL = "https://jdquote2-api-sandbox.deere.com/om/cert/quotedata"
PO_DATA_BASE_URL = "https://jdquote2-api-sandbox.deere.com/om/cert/podata"
MAINTAIN_QUOTE_BASE_URL = "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote"
CUSTOMER_LINKAGE_BASE_URL = "https://sandboxapi.deere.com/platform"

def make_api_request(url, method="GET", headers=None, data=None, params=None):
    """Make an API request and return the response."""
    if headers is None:
        headers = {}
    
    try:
        print(f"\n{'-'*80}")
        print(f"Request: {method} {url}")
        if params:
            print(f"Params: {json.dumps(params, indent=2)}")
        if data:
            if isinstance(data, dict):
                print(f"Data: {json.dumps(data, indent=2)}")
            else:
                print(f"Data: {data}")
        
        # Print all headers except Auth (for security)
        printable_headers = {k: v for k, v in headers.items() if k.lower() != 'authorization'}
        print(f"Headers: {json.dumps(printable_headers, indent=2)}")
        print(f"Authorization: Bearer [token hidden]")
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data if isinstance(data, dict) else None,
            data=data if not isinstance(data, dict) else None,
            params=params,
            timeout=30
        )
        
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

def decode_jwt(token):
    """Decode and print JWT token information (without validation)"""
    try:
        # Split the token
        parts = token.split('.')
        if len(parts) != 3:
            print("Warning: Token does not appear to be a valid JWT (should have 3 parts)")
            return
        
        # Decode the payload
        payload_bytes = parts[1].encode()
        # Add padding if necessary
        payload_bytes += b'=' * (4 - (len(payload_bytes) % 4))
        
        # Decode the payload
        decoded = base64.b64decode(payload_bytes)
        payload = json.loads(decoded)
        
        # Extract important information
        print("\n=== Token Info ===")
        print(f"Issued at: {datetime.fromtimestamp(payload.get('iat', 0))}")
        print(f"Expires at: {datetime.fromtimestamp(payload.get('exp', 0))}")
        print(f"Scopes: {payload.get('scp', [])}")
        print(f"Issuer: {payload.get('iss', 'N/A')}")
        print(f"Subject: {payload.get('sub', 'N/A')}")
        print(f"Client ID: {payload.get('cid', 'N/A')}")
        
        # Check if token is expired
        if 'exp' in payload:
            exp_time = datetime.fromtimestamp(payload['exp'])
            now = datetime.now()
            if exp_time < now:
                print(f"WARNING: Token expired on {exp_time}")
            else:
                print(f"Token valid for {(exp_time - now).total_seconds()/60:.1f} more minutes")
    except Exception as e:
        print(f"Error decoding token: {e}")

def test_maintain_quotes_curl_equivalent(token, dealer_id="X731804"):
    """Test the Maintain Quotes API using a format similar to the curl example"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("\n=== Testing Maintain Quotes API (Curl Equivalent) ===")
    
    # This matches the curl example from your output
    data = {
        "dealerRacfID": dealer_id, 
        "startModifiedDate": "04-01-2025", 
        "endModifiedDate": "04-15-2025"
    }
    
    # Try with the exact URL from the curl example
    url = f"{MAINTAIN_QUOTE_BASE_URL}/api/v1/dealers/{dealer_id}/maintain-quotes"
    
    make_api_request(
        url=url,
        method="POST",
        headers=headers,
        data=data
    )
    
    # If we get a 401, try adding a specific scope test
    print("\n=== Note on Scopes ===")
    print("If you received 401 errors, you might need the 'axiom' scope.")
    print("Required scopes according to your documentation:")
    print("- Maintain Quotes API: 'axiom' scope")
    print("- PO Data API: 'axiom' scope")
    print("- Quote Data API: 'axiom' scope")
    print("- Customer Linkage API: 'axiom' scope")
    print("- For refresh tokens: 'offline_access' scope")
    print("\nYou may need to modify your token request to include multiple scopes.")

def test_direct_endpoint(token, dealer_id="X731804"):
    """Test a direct, simple endpoint"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    print("\n=== Testing Direct Endpoint ===")
    
    # Try accessing one of the simpler endpoints
    url = f"{MAINTAIN_QUOTE_BASE_URL}/api/v1/dealers/{dealer_id}/quotes"
    
    make_api_request(
        url=url,
        method="POST",
        headers=headers,
        data={"dealerRacfID": dealer_id}
    )

def main():
    """Main function to run the tests."""
    parser = argparse.ArgumentParser(description="Test John Deere API endpoints")
    parser.add_argument("--token", help="OAuth token to use for API calls")
    parser.add_argument("--dealer-id", help="Dealer ID to use for API calls", default="X731804")
    parser.add_argument("--prompt-token", action="store_true", help="Prompt for token input at runtime")
    args = parser.parse_args()
    
    # Get the token
    token = args.token
    if args.prompt_token:
        token = input("Please enter your John Deere OAuth token: ")
    
    if not token:
        print("Error: No token provided. Use --token or --prompt-token")
        return
    
    # Print token information (first few chars only for security)
    token_prefix = token[:10] if token else "None"
    print(f"Using token: {token_prefix}...")
    print(f"Using dealer ID: {args.dealer_id}")
    
    # Decode and check token
    decode_jwt(token)
    
    # Run the most minimal tests to troubleshoot
    test_maintain_quotes_curl_equivalent(token, args.dealer_id)
    test_direct_endpoint(token, args.dealer_id)
    
    print("\n=== Tests completed ===")

if __name__ == "__main__":
    main()