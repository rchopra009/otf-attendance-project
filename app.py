# app.py
# Flask API server for Trisha AI MVP V1

import os
import datetime
import logging
from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, ServiceUnavailable, InternalServerError
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()  # Load from .env file if present.  Crucial for local dev.

# --- Import the Automation Service ---
try:
    # Assumes automation_service.py is in the same directory
    from automation_service import get_attendance_via_playwright
except ImportError:
    logging.error("CRITICAL: Could not import 'automation_service'. Backend cannot function.")
    def get_attendance_via_playwright(*args, **kwargs): # Fallback
        raise ServiceUnavailable("Automation service module not found or failed to import.")

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
TARGET_STUDIO_ID = os.environ.get("TARGET_STUDIO_ID", "0134") # Default to Clearwater
TARGET_STUDIO_NAME = os.environ.get("TARGET_STUDIO_NAME", "Clearwater, FL")
# Load OTF Credentials securely from environment variables
OTF_USERNAME = os.environ.get("OTF_USERNAME")
OTF_PASSWORD = os.environ.get("OTF_PASSWORD")

if not OTF_USERNAME or not OTF_PASSWORD:
    logging.error("OTF credentials not found in environment variables.")

# --- API Routes ---
@app.route('/api/attendance/yesterday', methods=['GET'])
def get_yesterday_attendance_route():
    """ API endpoint to retrieve yesterday's total attendance. """
    app.logger.info(f"Request received for /api/attendance/yesterday")

    if not OTF_USERNAME or not OTF_PASSWORD:
        app.logger.error("Missing OTF_USERNAME or OTF_PASSWORD environment variables.")
        raise InternalServerError("Backend credentials not configured.  Set OTF_USERNAME and OTF_PASSWORD.")

    yesterday_date = datetime.date.today() - datetime.timedelta(days=1)
    date_str = yesterday_date.strftime('%Y-%m-%d')
    studio_id_req = request.args.get('studio_id', TARGET_STUDIO_ID)

    if studio_id_req != TARGET_STUDIO_ID:
        app.logger.warning(f"Request for unsupported studio ID: {studio_id_req}")
        raise BadRequest(f"MVP currently only supports Studio ID {TARGET_STUDIO_ID}")

    try:
        app.logger.info(f"Calling automation service for studio {studio_id_req}, date {date_str}")
        attendance = get_attendance_via_playwright(
            username=OTF_USERNAME,
            password=OTF_PASSWORD,
            studio_id=studio_id_req,
            target_date=yesterday_date
        )
        response_data = {
            "date": date_str,
            "studio_id": studio_id_req,
            "studio_name": TARGET_STUDIO_NAME,
            "total_attendance": attendance,
            "retrieved_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        app.logger.info(f"Successfully retrieved attendance: {attendance}")
        return jsonify(response_data), 200

    except (BadRequest, ServiceUnavailable, InternalServerError) as specific_error:
        # Re-raise specific known errors for Flask to handle standard responses
        raise specific_error
    except ConnectionError as ce:
        app.logger.error(f"Automation Connection Error: {ce}")
        raise ServiceUnavailable(f"Failed to retrieve data from OTF Portal. Reason: {ce}")
    except ValueError as ve:
        app.logger.error(f"Data processing error: {ve}")
        # Treat as internal error unless specific handling needed
        raise InternalServerError(f"Error processing retrieved data: {ve}")
    except Exception as e:
        app.logger.exception(f"Unexpected Internal Server Error: {e}")
        raise InternalServerError("An unexpected server error occurred.")

# Basic health check endpoint
@app.route('/')
def health_check_route():
    app.logger.debug("Health check requested.")
    return jsonify({"status": "Trisha AI MVP Backend is running!"}), 200

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    host = '0.0.0.0' # Listen on all available network interfaces
    app.logger.info(f"Starting Flask server on {host}:{port} | Debug mode: {debug_mode}")
    app.run(host=host, port=port, debug=debug_mode)
