# generate_jd_token.py - Using the correct date format
import os
import base64
import json
import requests
import time
from datetime import datetime

# Hardcoded credentials for direct troubleshooting
CLIENT_ID = "0oao5jntk71YDUX9Q5d7"
CLIENT_SECRET = "ktdM8YGvalnKpzriyn4zaZioIInMpsGaiy4oN0H3gPDMQhJvKtTBpfsElA1zyCUu"

# Correct dealer information
DEALER_RACF_ID = "X950700"
DEALER_NUMBER = "731804"

print(f"Using Client ID: {CLIENT_ID}")
print(f"Using Client Secret: {CLIENT_SECRET[:10]}...")
print(f"Using Dealer RACF ID: {DEALER_RACF_ID}")
print(f"Using Dealer Number: {DEALER_NUMBER}")

# Token endpoint from JD OAuth
TOKEN_URL = "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token"

# Set up cache path
cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(cache_dir, exist_ok=True)
token_file = os.path.join(cache_dir, "jd_token.json")

# Create authorization header
auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
auth_bytes = auth_string.encode('ascii')
auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

# Set up headers and data
headers = {
    "Authorization": f"Basic {auth_b64}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}

# Use only the scopes that worked before
data = {
    "grant_type": "client_credentials",
    "scope": "offline_access axiom"
}

print(f"Requesting token from {TOKEN_URL}...")
try:
    response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    print(f"Response status: {response.status_code}")
    print(f"Response content: {response.text[:500]}...")
    
    if response.status_code == 200:
        token_data = response.json()
        
        # Add expiry timestamp
        if 'expires_in' in token_data:
            token_data['expires_at'] = time.time() + token_data['expires_in']
        
        # Save token to file
        with open(token_file, 'w') as f:
            json.dump(token_data, f)
        
        print(f"SUCCESS! Token saved to {token_file}")
        print(f"Token expires in: {token_data.get('expires_in', 'unknown')} seconds")
        
        # Display complete token for copy/paste
        print("\nCOMPLETE TOKEN FOR COPY/PASTE:")
        print(token_data['access_token'])
        
        # Check which scopes were granted
        if 'scope' in token_data:
            print(f"\nGranted scopes: {token_data['scope']}")
        
        # Decode token to show expiration
        try:
            import base64
            import json
            
            # Split the token
            parts = token_data['access_token'].split('.')
            if len(parts) == 3:
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
                print(f"Subject: {payload.get('sub', 'N/A')}")
                print(f"Client ID: {payload.get('cid', 'N/A')}")
                
                # Print full payload for analysis
                print("\nFull token payload:")
                print(json.dumps(payload, indent=2))
        except Exception as e:
            print(f"Error decoding token: {e}")
        
        # Test with Production Quote Data API using the CORRECT date format (yyyy-MM-dd)
        quote_url_prod = "https://jdquote2-api.deere.com/om/quotedata/api/v1/quote-data"
        test_headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Format dates correctly in yyyy-MM-dd format
        today = datetime.now().strftime("%Y-%m-%d")  # Changed format to yyyy-MM-dd
        end_date = "2025-12-31"  # Changed format to yyyy-MM-dd
        
        quote_data = {
            "dealerAccountNumber": DEALER_NUMBER,
            "beginDate": today,
            "endDate": end_date
        }
        
        print("\nTesting token with Production Quote Data API...")
        print(f"URL: {quote_url_prod}")
        print(f"Headers: {test_headers}")
        print(f"Data: {quote_data}")
        
        try:
            quote_response = requests.post(quote_url_prod, headers=test_headers, json=quote_data, timeout=30)
            print(f"Quote API response status: {quote_response.status_code}")
            print(f"Quote API response headers: {quote_response.headers}")
            
            if quote_response.status_code == 200:
                print(f"Quote API response content: {quote_response.text[:1000]}...")
            else:
                print(f"Quote API response error: {quote_response.text}")
        except Exception as e:
            print(f"Error with Production Quote Data API: {e}")
        
        # Try Sandbox URL as well with correct date format
        quote_url_sandbox = "https://jdquote2-api-sandbox.deere.com/om/cert/quotedata/api/v1/quote-data"
        
        print("\nTesting token with Sandbox Quote Data API...")
        print(f"URL: {quote_url_sandbox}")
        
        try:
            quote_response = requests.post(quote_url_sandbox, headers=test_headers, json=quote_data, timeout=30)
            print(f"Quote API response status: {quote_response.status_code}")
            
            if quote_response.status_code == 200:
                print(f"Quote API response content: {quote_response.text[:1000]}...")
            else:
                print(f"Quote API response error: {quote_response.text}")
        except Exception as e:
            print(f"Error with Sandbox Quote Data API: {e}")
        
        # Generate curl command for manual testing
        auth_header = f"Bearer {token_data['access_token']}"
        print("\nCURL command for manual testing Production API:")
        print(f'curl -X POST "{quote_url_prod}" \\')
        print(f'  -H "Authorization: {auth_header}" \\')
        print(f'  -H "Content-Type: application/json" \\')
        print(f'  -H "Accept: application/json" \\')
        print(f'  -d \'{{"dealerAccountNumber": "{DEALER_NUMBER}", "beginDate": "{today}", "endDate": "{end_date}"}}\'')
    else:
        print(f"Failed to get token: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Error: {str(e)}")