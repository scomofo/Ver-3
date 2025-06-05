import json
import requests
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('QuoteTest')

# Token from your file
token = "eyJraWQiOiJUSDEzd1d2UThHeGJjQkQ2djBGalhFNmJsRlZ5c0hBbmQxVkRkSGd2VGhFIiwiYWxnIjoiUlMyNTYifQ.eyJ2ZXIiOjEsImp0aSI6IkFULnNZRGRfQm5lQmM4YzlLYV9XQnFfWkoteXl1QVYxYVl2a0JCWU5Cd2poUEkiLCJpc3MiOiJodHRwczovL3NpZ25pbi5qb2huZGVlcmUuY29tL29hdXRoMi9hdXM3OHRubGF5c01yYUZoQzF0NyIsImF1ZCI6ImNvbS5kZWVyZS5pc2cuYXhpb20iLCJpYXQiOjE3NDY3MTczNDYsImV4cCI6MTc0Njc2MDU0NiwiY2lkIjoiMG9hbzVqbnRrNzFZRFVYOVE1ZDciLCJzY3AiOlsib2ZmbGluZV9hY2Nlc3MiLCJheGlvbSJdLCJzdWIiOiIwb2FvNWpudGs3MVlEVVg5UTVkNyIsImlzY3NjIjp0cnVlLCJ0aWVyIjoiU0FOREJPWCIsImNuYW1lIjoiNzMxODA0LUJhdHRsZVJpdmVyLUludGVsbGlEZWFsZXIiLCJjYXBpZCI6ImVjOTEzMTkxLTY0M2YtNDMxOS1iOTUwLTdmMWJkMTI4MGYwMCJ9.SlLIkNVtgHKaNLp_9tF8nJzbt_IMWvukPNVmXkmNz75HpEe0qvTEnSOpPuBUxfsAbJcV4LVRSHkNoOzJELGQPfkrtnuEnNjYOgLfCLVHStNiD0XUMyM9KIZw4iAmkGXMF-NeETnCmb7ApMB-PUKeCpW7Hr9pcuxaG1gfelYKaBsO3HhOanw4wUOQXIB8GjqZHqJJ0v6De7k42o91kzMte9__akc7zoCzp187HzEziRRLJGWGJ2wFhIh-MfM8XewMElOI5bnVJS06718bhjbCu-FqgbmHLaRIq8i_CTPq3BtsRvQZICNVV6EZ_oldfv9BoA24xx-kobh-pRjG86YQhQ"  # Replace with token from your cache file

# API endpoint
url = "https://jdquote2-api.deere.com/om/quotedata/api/v1/quote-data"

# Headers
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Data
data = {
    "beginDate": "2022-05-08",
    "endDate": "2025-05-08",
    "dealerAccountNumber": "731804"
}

# Make the request
try:
    logger.info(f"Sending request to {url}")
    response = requests.post(url, headers=headers, json=data)
    logger.info(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        logger.info("Request successful!")
        
        # Print full response
        with open("quote_response.json", "w") as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Response saved to quote_response.json")
        
        # Extract and print quotes
        if "body" in result and "quotes" in result["body"]:
            quotes = result["body"]["quotes"]
            logger.info(f"Found {len(quotes)} quotes")
            
            for i, quote in enumerate(quotes[:5]):  # Show first 5
                logger.info(f"Quote {i+1}: ID={quote.get('quoteId')}, Name={quote.get('quoteName')}")
        else:
            logger.warning("No quotes found in response")
    else:
        logger.error(f"Request failed: {response.text}")
except Exception as e:
    logger.error(f"Error: {str(e)}")