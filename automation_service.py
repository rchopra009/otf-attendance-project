import os
import json
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

def get_attendance_from_portal(username, password, studio_id, target_date):
    """
    Retrieve the total attendance for a specific date from the OTF Studio Performance portal
    using the browser-use Pro API.
    
    Args:
        username (str): OTF portal username
        password (str): OTF portal password
        studio_id (str): Studio ID (e.g., "0134" for Clearwater)
        target_date (str): Date in YYYY-MM-DD format
        
    Returns:
        int: The total attendance figure
        
    Raises:
        ConnectionError: If there's a problem connecting to the browser-use API
        ValueError: If attendance data cannot be retrieved or parsed
    """
    # Get browser-use API configuration from environment variables
    api_endpoint = os.environ.get('BROWSER_USE_API_ENDPOINT')
    api_key = os.environ.get('BROWSER_USE_API_KEY')
    
    # Verify required configuration is available
    if not api_endpoint or not api_key:
        raise ValueError("Missing browser-use API configuration")
    
    # Format the date for display in the portal (assuming MM/DD/YYYY format)
    display_date = datetime.strptime(target_date, '%Y-%m-%d').strftime('%m/%d/%Y')
    
    # Define the steps for the browser-use Pro API to execute
    automation_steps = [
        # Step 1: Navigate to Microsoft SSO login page
        {
            "action": "navigate",
            "url": os.environ.get('OTF_LOGIN_START_URL', 'https://myapplications.microsoft.com/')
        },
        
        # Step 2: Enter username and continue
        {
            "action": "type",
            "selector": "#i0116",  # Email input field (verify this selector)
            "text": username
        },
        {
            "action": "click",
            "selector": "#idSIButton9"  # Next button (verify this selector)
        },
        
        # Step 3: Enter password and sign in
        {
            "action": "type",
            "selector": "#i0118",  # Password input field (verify this selector)
            "text": password
        },
        {
            "action": "click",
            "selector": "#idSIButton9"  # Sign in button (verify this selector)
        },
        
        # Step 4: Handle "Stay signed in?" prompt if it appears
        {
            "action": "click",
            "selector": "#idSIButton9",  # Yes button (verify this selector)
            "optional": True  # This step might not be needed if already signed in
        },
        
        # Step 5: Navigate to Studio Performance page (may need to adjust if SSO lands on a different page)
        {
            "action": "navigate",
            "url": os.environ.get('OTF_STUDIO_PERFORMANCE_URL', 'https://otfstudioportal.orangetheory.com/studio-performance')
        },
        
        # Step 6: Select the studio (if needed)
        {
            "action": "click",
            "selector": "#studio-selector",  # Studio dropdown (verify this selector)
            "optional": True
        },
        {
            "action": "click",
            "selector": f"option[value='{studio_id}']",  # Studio option (verify this selector format)
            "optional": True
        },
        
        # Step 7: Select the date (assuming there's a date picker)
        {
            "action": "click",
            "selector": "#date-picker",  # Date picker (verify this selector)
            "optional": True
        },
        {
            "action": "type",
            "selector": "#date-input",  # Date input field (verify this selector)
            "text": display_date,
            "optional": True
        },
        {
            "action": "click",
            "selector": "#apply-date",  # Apply date button (verify this selector)
            "optional": True
        },
        
        # Step 8: Wait for the data to load
        {
            "action": "wait",
            "time": 3000  # Wait 3 seconds for data to load
        },
        
        # Step 9: Extract the total attendance value
        {
            "action": "extract",
            "selector": "#total-attendance-value",  # Total attendance element (verify this selector)
            "attribute": "textContent",
            "output": "attendance"
        }
    ]
    
    # Prepare the API request payload
    payload = {
        "steps": automation_steps
    }
    
    # Prepare the headers with authentication
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        # Make the API request to browser-use Pro
        logger.info(f"Calling browser-use API to retrieve attendance for {target_date}")
        response = requests.post(api_endpoint, headers=headers, json=payload)
        
        # Check for successful response
        response.raise_for_status()
        
        # Parse the JSON response
        result = response.json()
        
        # Check if the automation was successful
        if result.get("status") != "success":
            error_message = result.get("error", "Unknown automation error")
            logger.error(f"browser-use API reported an error: {error_message}")
            raise ValueError(f"Automation failed: {error_message}")
        
        # Extract the attendance value from the result
        attendance_text = result.get("outputs", {}).get("attendance")
        
        if not attendance_text:
            logger.error("Attendance value not found in the API response")
            raise ValueError("Attendance value not found in the portal")
        
        # Clean and convert the attendance value to an integer
        # Remove any non-numeric characters (e.g., commas, spaces)
        attendance = ''.join(c for c in attendance_text if c.isdigit())
        
        if not attendance:
            logger.error(f"Failed to parse attendance value: '{attendance_text}'")
            raise ValueError(f"Failed to parse attendance value: '{attendance_text}'")
        
        return int(attendance)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to browser-use API: {str(e)}")
        raise ConnectionError(f"Failed to connect to automation service: {str(e)}")
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse API response: {str(e)}")
        raise ValueError(f"Failed to parse automation service response: {str(e)}")
