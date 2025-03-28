import os
import json
import logging
import requests
from datetime import datetime, timedelta

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
        
        # Calculate yesterday's day of week (0 is Monday, 6 is Sunday)
        target_date_obj = datetime.strptime(target_date, '%Y-%m-%d')
        day_of_week = target_date_obj.weekday()
        
        # Map day_of_week to column index (1-based to match table)
        # Monday=1, Tuesday=2, Wednesday=3, Thursday=4, Friday=5, Saturday=6
        column_index = day_of_week + 1
        
        # Map to day name for logging
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_name = day_names[day_of_week]
        
        logger.info(f"Target date {target_date} is a {day_name}, using column index {column_index}")
        
        # Create script for Browser Use
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
            
            // Wait for login to complete
            await sleep(3000);
            
            // Navigate to Studio Performance app
            await goto('OTF_STUDIO_PERFORMANCE_URL');
            
            // Wait for page to load
            await sleep(5000);
            
            // Click on CLASS ATTENDANCE tab
            await click('text=CLASS ATTENDANCE');
            
            // Wait for tab content to load
            await sleep(3000);
            
            // Verify the studio is selected correctly
            // This might require adjustment based on actual UI
            
            // Find the "Workouts Taken" row in the Traffic by Day of Week table
            // and extract the value for the target day of week
            // We need to get the cell in the Workouts Taken row and the column for our day of week
            
            // This is a CSS selector for the table cell in the Workouts Taken row and
            // the column corresponding to our day of week
            const selector = `table tr:has(td:first-child:contains("Workouts Taken")) td:nth-child(DAY_COLUMN)`;
            const daySelector = selector.replace('DAY_COLUMN', 'COLUMN_INDEX');
            
            console.log('Looking for attendance with selector:', daySelector);
            
            // Extract the attendance value
            const attendance = await getText(daySelector);
            console.log('Found attendance value:', attendance);
            
            return { attendance };
        }
        """
        
        # Replace placeholders with actual values
        script = script.replace('PORTAL_URL', os.environ.get('OTF_LOGIN_START_URL', 'https://myapplications.microsoft.com/'))
        script = script.replace('USERNAME', username)
        script = script.replace('PASSWORD', password)
        script = script.replace('OTF_STUDIO_PERFORMANCE_URL', os.environ.get('OTF_STUDIO_PERFORMANCE_URL', 'https://portal.orangetheory.com/apps/studios/StudioPerformance?_embed=true'))
        script = script.replace('COLUMN_INDEX', str(column_index + 1))  # +1 because first column is the row label
        
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
