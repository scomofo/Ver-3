# list_quotes.py - Simplified version that tries multiple endpoints
import os
import json
import requests
import sys
from datetime import datetime

def load_token():
    """Load token from cache."""
    cache_path = os.path.join("cache", "jd_token.json")
    
    if not os.path.exists(cache_path):
        print("Error: No token found. Please run debug_jd_auth.py first.")
        return None
    
    try:
        with open(cache_path, 'r') as f:
            token_data = json.load(f)
        
        if 'access_token' not in token_data:
            print("Error: Invalid token data - missing access_token")
            return None
        
        if 'expires_at' in token_data and token_data['expires_at'] < datetime.now().timestamp():
            print("Error: Token is expired. Please run debug_jd_auth.py to get a new token.")
            return None
        
        return token_data['access_token']
    except Exception as e:
        print(f"Error loading token: {str(e)}")
        return None

def list_quotes():
    """List quotes using the token."""
    token = load_token()
    if not token:
        return
    
    print(f"Using token (first 10 chars): {token[:10]}...")
    
    # Try different endpoints
    endpoints = [
        {
            "url": "https://jdquote2-api-sandbox.deere.com/om/cert/quotedata/api/v1/quote-data",
            "data": {"dealerAccountNumber": "731804"}
        },
        {
            "url": "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote/api/v1/dealers/X950700/maintain-quotes",
            "data": {
                "dealerRacfID": "X950700",
                "startModifiedDate": "03/01/2025",
                "endModifiedDate": "04/15/2025"
            }
        }
    ]
    
    for i, endpoint in enumerate(endpoints):
        url = endpoint["url"]
        data = endpoint["data"]
        
        print(f"\nAttempting endpoint {i+1}: {url}")
        print(f"Request data: {json.dumps(data)}")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                print("Success!")
                
                # Parse response
                response_json = response.json()
                
                if 'body' in response_json and isinstance(response_json['body'], list):
                    quotes = response_json['body']
                    print(f"Found {len(quotes)} quotes:")
                    
                    # Display quote summary
                    for idx, quote in enumerate(quotes[:5]):  # Show first 5 quotes
                        quote_id = quote.get('quoteID', 'Unknown ID')
                        quote_name = quote.get('quoteName', 'Unnamed Quote')
                        print(f"{idx+1}. Quote ID: {quote_id}, Name: {quote_name}")
                    
                    if len(quotes) > 5:
                        print(f"...and {len(quotes) - 5} more")
                else:
                    print(f"Response format unexpected:")
                    print(json.dumps(response_json, indent=2)[:500])  # Show first 500 chars
                
                # Successfully found quotes with this endpoint
                return
            else:
                print(f"Request failed: {response.text}")
        except Exception as e:
            print(f"Exception: {str(e)}")
    
    print("\nAll endpoints failed. Please check your token and try again.")

if __name__ == "__main__":
    list_quotes()