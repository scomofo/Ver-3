import os
import sys
import json

# Print header
print("=" * 50)
print("John Deere API Credentials Test")
print("=" * 50)

# Check environment variables
print("\nEnvironment Variables:")
jd_client_id = os.environ.get('JD_CLIENT_ID')
deere_client_secret = os.environ.get('DEERE_CLIENT_SECRET')

print(f"JD_CLIENT_ID: {'SET' if jd_client_id else 'NOT SET'}")
if jd_client_id:
    print(f"  Value: {jd_client_id}")

print(f"DEERE_CLIENT_SECRET: {'SET' if deere_client_secret else 'NOT SET'}")
if deere_client_secret:
    print(f"  Value: {'*' * min(len(deere_client_secret), 10)}")

# Check config file
config_file = "jd_quote_config.json"
print(f"\nChecking for config file: {config_file}")

if os.path.exists(config_file):
    print(f"Config file exists: {os.path.abspath(config_file)}")
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Check for credentials in config
        config_client_id = config.get('jd_client_id')
        config_client_secret = config.get('jd_client_secret')
        
        print(f"Config contains jd_client_id: {'YES' if config_client_id else 'NO'}")
        print(f"Config contains jd_client_secret: {'YES' if config_client_secret else 'NO'}")
        
        # Check for credentials in 'auth' section if it exists
        auth_section = config.get('auth', {})
        auth_client_id = auth_section.get('client_id')
        auth_client_secret = auth_section.get('client_secret')
        
        if auth_section:
            print(f"Config contains auth section with client_id: {'YES' if auth_client_id else 'NO'}")
            print(f"Config contains auth section with client_secret: {'YES' if auth_client_secret else 'NO'}")
        
        # Check for jd section
        jd_section = config.get('jd', {})
        if jd_section:
            print(f"Config contains jd section:")
            print(f"  quote_api_base_url: {'SET' if 'quote_api_base_url' in jd_section else 'NOT SET'}")
            print(f"  dealer_account_number: {'SET' if 'dealer_account_number' in jd_section else 'NOT SET'}")
            print(f"  dealer_id: {'SET' if 'dealer_id' in jd_section else 'NOT SET'}")
    
    except Exception as e:
        print(f"Error reading config file: {str(e)}")
else:
    print(f"Config file does not exist at: {os.path.abspath(config_file)}")

# Check for the application
print("\nChecking for required files:")
required_files = [
    "jd_quote_app_fixed.py",
    "auth/jd_oauth_client.py",
    "api/jd_quote_client.py"
]

for file in required_files:
    if os.path.exists(file):
        print(f"✓ {file} exists")
    else:
        print(f"✗ {file} does not exist")

# Check directory permissions
print("\nChecking directory permissions:")
current_dir = os.getcwd()
print(f"Current directory: {current_dir}")
print(f"Writable: {'YES' if os.access(current_dir, os.W_OK) else 'NO'}")

# Print summary
print("\n" + "=" * 50)
print("Summary:")
if jd_client_id or config_client_id or auth_client_id:
    print("✓ Client ID is available (either in environment or config)")
else:
    print("✗ Client ID is not set anywhere")

if deere_client_secret or config_client_secret or auth_client_secret:
    print("✓ Client Secret is available (either in environment or config)")
else:
    print("✗ Client Secret is not set anywhere")

print("\nTo fix credential issues:")
print("1. Set environment variables directly:")
print("   set JD_CLIENT_ID=your_client_id")
print("   set DEERE_CLIENT_SECRET=your_client_secret")
print("2. Or use the application's Settings tab to save credentials")
print("=" * 50)

input("\nPress Enter to exit...")
