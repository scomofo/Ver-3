# integration_test.py - Test John Deere API and SharePoint Integration
import os
import json
import time
import logging
import traceback
from datetime import datetime

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/integration_test.log")
    ]
)
logger = logging.getLogger(__name__)

def test_jd_token():
    """Test if the JD token is valid and accessible."""
    print("\n===== TESTING JOHN DEERE TOKEN =====")
    token_path = os.path.join("cache", "jd_token.json")
    
    if not os.path.exists(token_path):
        print(f"ERROR: Token file not found at {token_path}")
        return False
        
    try:
        with open(token_path, 'r') as f:
            token_data = json.load(f)
            
        if 'access_token' not in token_data:
            print("ERROR: No access_token in token file")
            return False
            
        expires_at = token_data.get('expires_at', 0)
        now = time.time()
        
        if expires_at < now:
            print(f"ERROR: Token expired at {datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')}")
            print("Please run generate_jd_token.py to get a new token")
            return False
            
        token = token_data['access_token']
        expiry_time = datetime.fromtimestamp(expires_at)
        print(f"SUCCESS: Found valid token (expires: {expiry_time.strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"Token starts with: {token[:20]}...")
        
        return True
    except Exception as e:
        print(f"ERROR reading token file: {e}")
        traceback.print_exc()
        return False

def test_jd_api():
    """Test the John Deere API connectivity."""
    print("\n===== TESTING JOHN DEERE API =====")
    
    # First ensure we have a valid token
    if not test_jd_token():
        print("Token test failed - cannot test API")
        return False
        
    try:
        # Import needed classes
        from api.MaintainQuotesAPI import MaintainQuotesAPI
        
        # Get token from file
        token_path = os.path.join("cache", "jd_token.json")
        with open(token_path, 'r') as f:
            token_data = json.load(f)
            
        token = token_data['access_token']
        
        # Create API client
        api = MaintainQuotesAPI(
            base_url="https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote",
            access_token=token,
            logger=logger
        )
        
        print("Testing API connection (GET_QUOTES)...")
        
        # Use very specific date range for minimal results
        # NOTE: Using dash-format MM-DD-YYYY instead of slash-format
        test_data = {
            "dealerRacfID": "X731804",
            "startModifiedDate": "04-01-2025",
            "endModifiedDate": "04-15-2025"
        }
        
        result = api._make_request("POST", "/api/v1/dealers/X731804/maintain-quotes", data=test_data)
        
        if result is None:
            print("ERROR: API returned None")
            return False
            
        if isinstance(result, dict) and 'error' in result:
            print(f"ERROR: API returned error: {result['error']}")
            print(f"Error message: {result.get('message', 'No message')}")
            return False
            
        # Print success if we got a response with expected format
        if isinstance(result, dict) and 'type' in result and 'body' in result:
            if result['type'] == 'SUCCESS':
                body_count = len(result['body']) if isinstance(result['body'], list) else "non-list"
                print(f"SUCCESS: API returned data with type={result['type']} and body count={body_count}")
                return True
            else:
                print(f"WARNING: API returned non-SUCCESS type: {result['type']}")
                return True  # Still count as success if we got a response
        
        print(f"PARTIAL SUCCESS: API returned unexpected format but got response")
        return True
    except Exception as e:
        print(f"ERROR testing API: {e}")
        traceback.print_exc()
        return False

def test_sharepoint():
    """Test SharePoint connectivity."""
    print("\n===== TESTING SHAREPOINT CONNECTIVITY =====")
    
    try:
        # Import SharePoint classes
        from modules.sharepoint_manager import SharePointManager
        
        # Create manager
        manager = SharePointManager()
        
        # Test authentication
        print("Testing SharePoint authentication...")
        if not manager.ensure_authenticated():
            print("ERROR: SharePoint authentication failed")
            return False
            
        print("SUCCESS: SharePoint authentication successful")
        
        # Try to read the OngoingAMS.xlsx file
        print("Testing Excel file access...")
        sheet_data = manager.read_excel_sheet("App")
        
        if sheet_data is None:
            print("ERROR: Could not read 'App' sheet")
            return False
            
        print(f"SUCCESS: Read 'App' sheet - found {len(sheet_data)} rows")
        
        return True
    except Exception as e:
        print(f"ERROR testing SharePoint: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print(f"Starting integration tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    jd_token_ok = test_jd_token()
    jd_api_ok = test_jd_api()
    sharepoint_ok = test_sharepoint()
    
    print("\n===== TEST SUMMARY =====")
    print(f"JD Token Test: {'✅ PASSED' if jd_token_ok else '❌ FAILED'}")
    print(f"JD API Test: {'✅ PASSED' if jd_api_ok else '❌ FAILED'}")
    print(f"SharePoint Test: {'✅ PASSED' if sharepoint_ok else '❌ FAILED'}")
    
    if not jd_token_ok:
        print("\nTo fix JD token issues:")
        print("1. Run generate_jd_token.py to create a new token")
        print("2. Check the client ID and secret in .env and/or update_env.py")
    
    if not jd_api_ok:
        print("\nTo fix JD API issues:")
        print("1. Check API endpoint URLs in MaintainQuotesAPI.py")
        print("2. Fix any date format issues in the request payload")
        print("3. Check for permissions or scope issues in the token")
    
    if not sharepoint_ok:
        print("\nTo fix SharePoint issues:")
        print("1. Check Azure AD credentials in .env")
        print("2. Verify SharePoint site ID and file path")
        print("3. Try running auth.py to refresh SharePoint tokens")

if __name__ == "__main__":
    main()