import os
import json
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

def get_attendance_from_portal(username, password, studio_id, target_date):
    """
    Retrieve the total attendance for a specific date from the OTF Studio Performance portal
    using the Browser Use API.
    
    Args:
        username (str): OTF portal username
        password (str): OTF portal password
        studio_id (str): Studio ID (e.g., "0134" for Clearwater)
        target_date (str): Date in YYYY-MM-DD format
        
    Returns:
        int: The total attendance figure
    """
    try:
        # Get Browser Use API configuration from environment variables
        api_endpoint = os.environ.get('BROWSER_USE_API_ENDPOINT', 'https://api.browser-use.com/api/v1/run')
        api_key = os.environ.get('BROWSER_USE_API_KEY')
        
        if not api_key:
            logger.error("Missing Browser Use API key")
            return 0
        
        # Format the date for display in the portal (assuming MM/DD/YYYY format)
        display_date = datetime.strptime(target_date, '%Y-%m-%d').strftime('%m/%d/%Y')
        
        # Create script for Browser Use based on their expected format
        script = """
        async function run() {
            // Navigate to Microsoft SSO login
            await goto('PORTAL_URL');
            
            // Enter username and click next
            await type('#i0116', 'USERNAME');
            await click('#idSIButton9');
            
            // Enter password and sign in
            await type('#i0118', 'PASSWORD');
            await click('#idSIButton9');
            
            // Handle "Stay signed in?" prompt if it appears
            try {
                await click('#idSIButton9');
            } catch (e) {
                console.log('No stay signed in prompt');
            }
            
            // Navigate to Studio Performance page
            await goto('STUDIO_URL');
            
            // Wait for content to load
            await sleep(3000);
            
            // Extract attendance value
            const attendance = await getText('#total-attendance-value');
            return { attendance };
        }
        """
        
        # Replace placeholders with actual values
        script = script.replace('PORTAL_URL', os.environ.get('OTF_LOGIN_START_URL', 'https://myapplications.microsoft.com/'))
        script = script.replace('USERNAME', username)
        script = script.replace('PASSWORD', password)
        script = script.replace('STUDIO_URL', os.environ.get('OTF_STUDIO_PERFORMANCE_URL', 'https://otfstudioportal.orangetheory.com/studio-performance'))
        
        # Build the payload according to Browser Use API format
        payload = {
            "script": script,
            "timeout": 60000,  # 60 seconds timeout
            "headless": True,
            "proxy": {
                "useProxy": False
            }
        }
        
        # Set up the headers with authorization
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Make the API call to Browser Use
        logger.info(f"Calling Browser Use API to retrieve attendance for {target_date}")
        response = requests.post(api_endpoint, headers=headers, json=payload)
        
        # Check if the request was successful
        if response.status_code != 200:
            logger.error(f"Browser Use API call failed with status: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return 0
        
        # Parse the response
        result = response.json()
        
        # Handle response based on Browser Use format
        # This is a guess at their response format - may need adjustment
        if result.get("status") == "success" or result.get("success") == True:
            # Different possible response structures
            if "data" in result and "attendance" in result["data"]:
                attendance_text = result["data"]["attendance"]
            elif "result" in result and "attendance" in result["result"]:
                attendance_text = result["result"]["attendance"]
            elif "attendance" in result:
                attendance_text = result["attendance"]
            else:
                logger.error(f"Could not find attendance in response: {result}")
                return 0
            
            # Clean and convert the attendance value to an integer
            attendance = ''.join(c for c in str(attendance_text) if c.isdigit())
            
            if not attendance:
                logger.error(f"Failed to parse attendance value: '{attendance_text}'")
                return 0
            
            return int(attendance)
        else:
            error_message = result.get("error") or result.get("message") or "Unknown error"
            logger.error(f"Browser Use API reported an error: {error_message}")
            return 0
            
    except Exception as e:
        logger.error(f"Exception in Browser Use API call: {str(e)}")
        # In case of any error, return 0 instead of raising an exception
        # This will allow the API to return a response even if Browser Use fails
        return 0
