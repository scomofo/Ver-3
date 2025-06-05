# regenerate_token.py - Regenerates the JD token using environment variables
import os
import base64
import json
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

# --- Start of Corrections ---

# Load environment variables from .env file FIRST
load_dotenv()

# Get credentials consistently from environment variables
# Make sure these variable names EXACTLY match your .env file (e.g., JD_CLIENT_ID=..., JD_CLIENT_SECRET=...)
CLIENT_ID = os.getenv('JD_CLIENT_ID')
CLIENT_SECRET = os.getenv('JD_CLIENT_SECRET') # Use the same name consistently

# Check if credentials were loaded successfully
if not CLIENT_ID:
    raise ValueError("JD_CLIENT_ID not found in environment variables. Check .env file and variable name.")
if not CLIENT_SECRET:
    raise ValueError("JD_CLIENT_SECRET not found in environment variables. Check .env file and variable name.")

print(f"Using JD_CLIENT_ID from environment: {CLIENT_ID}")
print("Using JD_CLIENT_SECRET from environment")

# --- End of Corrections ---


# Token endpoint
TOKEN_URL = "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token"

# Determine cache path
cache_path = os.path.join("cache")
os.makedirs(cache_path, exist_ok=True)
token_file = os.path.join(cache_path, "jd_token.json")

print(f"Token will be saved to: {token_file}")

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

# --- Correction: Update Scopes ---
# Using the scope provided by the user.
# NOTE: If other scopes like 'offline_access' are *also* needed, list them space-separated
# e.g., REQUIRED_SCOPES = "axiom offline_access"
REQUIRED_SCOPES = "axiom" # <-- Updated Scope
# --- End Correction ---

data = {
    "grant_type": "client_credentials",
    "scope": REQUIRED_SCOPES
}

print("\nRequesting token...")
try:
    response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    print(f"Response status: {response.status_code}")

    if response.status_code == 200:
        token_data = response.json()

        # Add expiry timestamp
        if 'expires_in' in token_data:
            token_data['expires_at'] = time.time() + token_data['expires_in']
            expires_at = datetime.fromtimestamp(token_data['expires_at'])
            print(f"Token expires at: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")

        # Check token
        if 'access_token' in token_data:
            token = token_data['access_token']
            print(f"Token received! Length: {len(token)} chars")
            print(f"First 10 chars: {token[:10]}...")
        else:
            print("ERROR: No access_token in response")
            print(f"Response: {response.text}")
            exit(1)

        # Save token to cache
        with open(token_file, 'w') as f:
            json.dump(token_data, f, indent=2)

        print(f"SUCCESS! Token saved to {token_file}")

        # Test with quotes data API
        token = token_data['access_token']

        # Try different endpoints
        endpoints = [
            {
                "name": "Quote Data API",
                "url": "https://jdquote2-api-sandbox.deere.com/om/cert/quotedata/api/v1/quote-data",
                "data": {"dealerAccountNumber": "731804"}
            },
            {
                "name": "Maintain Quote API",
                "url": "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote/api/v1/dealers/X950700/maintain-quotes",
                "data": {
                    "dealerRacfID": "X950700",
                    "startModifiedDate": "03/01/2025",
                    "endModifiedDate": "04/15/2025"
                }
            }
        ]

        for endpoint in endpoints:
            test_url = endpoint["url"]
            test_data = endpoint["data"]

            print(f"\nTesting token with {endpoint['name']}...")
            print(f"URL: {test_url}")
            print(f"Data: {json.dumps(test_data)}")

            test_headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

            test_response = requests.post(test_url, headers=test_headers, json=test_data, timeout=30)
            print(f"Test response status: {test_response.status_code}")

            if test_response.status_code == 200:
                print(f"SUCCESS! Token works with {endpoint['name']}")

                # Print some response data
                try:
                    response_json = test_response.json()
                    # Attempt to handle different possible successful response structures
                    if isinstance(response_json, dict):
                        if 'body' in response_json and isinstance(response_json['body'], list):
                            items = response_json['body']
                            print(f"Found {len(items)} items in body list")
                            if items:
                                first_item_info = items[0].get('quoteID', items[0].get('id', 'unknown ID'))
                                print(f"First item ID: {first_item_info}")
                        elif 'links' in response_json: # Common in Deere API responses
                             print(f"Response contains links: {response_json['links']}")
                        else:
                             print(f"Response type: {response_json.get('type', 'unknown')}, Keys: {list(response_json.keys())}")
                    elif isinstance(response_json, list):
                        print(f"Received a list response with {len(response_json)} items.")
                        if response_json:
                            print(f"First item: {response_json[0]}")
                    else:
                        print(f"Received non-dict/list JSON response: {response_json}")

                except Exception as parse_err:
                    print(f"Could not parse successful JSON response: {parse_err}")
                    print(f"Raw successful response: {test_response.text[:500]}...") # Print beginning of raw text

            else:
                print(f"FAILED with {endpoint['name']}: {test_response.text}")
    else:
        print(f"Failed to get token: {response.status_code}")
        print(f"Response: {response.text}") # Print error from token endpoint
except Exception as e:
    print(f"An error occurred: {str(e)}")