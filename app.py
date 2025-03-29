# app.py
# Flask API server for Trisha AI MVP V1 - With Claude Integration

import os
import datetime
import logging
from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, ServiceUnavailable, InternalServerError

# --- Import Anthropic Library ---
try:
    import anthropic
except ImportError:
    logging.error("Anthropic library not installed. Run 'pip install anthropic'")
    anthropic = None # Set to None if import fails

# --- Import the Automation Service ---
try:
    # Assumes automation_service.py is in the same directory
    # This function should now use the browser-use API as planned
    from automation_service import get_attendance_from_portal as get_attendance_via_browser_use_api
except ImportError:
    logging.error("CRITICAL: Could not import 'automation_service'. Backend cannot function.")
    # Fallback function to allow app startup but fail requests
    def get_attendance_via_browser_use_api(*args, **kwargs):
        raise ServiceUnavailable("Automation service module not found or failed to import.")

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
TARGET_STUDIO_ID = os.environ.get("TARGET_STUDIO_ID", "0134") # Default to Clearwater
TARGET_STUDIO_NAME = os.environ.get("TARGET_STUDIO_NAME", "Clearwater, FL")
# Load Credentials securely from environment variables
OTF_USERNAME = os.environ.get("OTF_USERNAME")
OTF_PASSWORD = os.environ.get("OTF_PASSWORD")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# --- Initialize Claude Client ---
claude_client = None
if anthropic and ANTHROPIC_API_KEY:
    try:
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        logging.info("Anthropic client initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Anthropic client: {e}")
elif not ANTHROPIC_API_KEY:
     logging.warning("ANTHROPIC_API_KEY environment variable not set. LLM features disabled.")
else: # anthropic library not installed
     logging.warning("Anthropic library not installed. LLM features disabled.")

# --- API Routes ---
@app.route('/api/attendance/yesterday', methods=['GET'])
def get_yesterday_attendance_route():
    """ API endpoint to retrieve yesterday's total attendance and generate response. """
    app.logger.info(f"Request received for /api/attendance/yesterday")
    if not OTF_USERNAME or not OTF_PASSWORD:
        app.logger.error("Missing OTF_USERNAME or OTF_PASSWORD environment variables.")
        raise InternalServerError("Backend OTF credentials not configured.")

    yesterday_date = datetime.date.today() - datetime.timedelta(days=1)
    date_str = yesterday_date.strftime('%Y-%m-%d')
    studio_id_req = request.args.get('studio_id', TARGET_STUDIO_ID)

    if studio_id_req != TARGET_STUDIO_ID:
         app.logger.warning(f"Request for unsupported studio ID: {studio_id_req}")
         raise BadRequest(f"MVP currently only supports Studio ID {TARGET_STUDIO_ID}")

    try:
        # --- Step 1: Call the automation service ---
        app.logger.info(f"Calling automation service for studio {studio_id_req}, date {date_str}")
        # This now calls the function designed to use the browser-use API
        attendance = get_attendance_via_browser_use_api(
            username=OTF_USERNAME,
            password=OTF_PASSWORD,
            studio_id=studio_id_req,
            target_date=yesterday_date
        )
        app.logger.info(f"Automation service returned attendance: {attendance}")

        # --- Step 2: Generate Natural Language Response using Claude ---
        natural_response = f"Okay, I found the number. Yesterday's ({date_str}) total attendance was {attendance}." # Default fallback

        if attendance is not None and claude_client: # Check if we got data AND client is ready
            try:
                app.logger.info(f"Constructing prompt for Claude with attendance: {attendance}")
                prompt = f"You are Trisha, a helpful AI assistant for an Orangetheory Fitness studio manager ({TARGET_STUDIO_NAME}). The manager wants to know yesterday's ({date_str}) total attendance. The number retrieved is: {attendance}. Please provide a brief, friendly, and encouraging response confirming this number. Keep it concise (1-2 sentences)."

                app.logger.info("Calling Claude API...")
                message_response = claude_client.messages.create(
                    model="claude-3-sonnet-20240229", # Or claude-3-opus-20240229, etc.
                    max_tokens=150,
                    messages=[{"role": "user", "content": prompt}]
                )

                if message_response.content and len(message_response.content) > 0:
                    natural_response = message_response.content[0].text # Extract text
                    app.logger.info(f"Received natural language response from Claude.")
                else:
                    app.logger.warning("Received empty content from Claude API. Using fallback response.")
                    # Keep the default fallback message defined above

            except Exception as llm_error:
                app.logger.error(f"Error calling Claude API or processing response: {llm_error}. Using fallback response.")
                # Keep the default fallback message defined above

        elif attendance is not None and not claude_client:
             app.logger.warning("Claude client not initialized. Using basic response.")
             # Keep the default fallback message defined above
        elif attendance is None:
             # Should have been caught by automation_service raising an error, but as safety net:
             raise ServiceUnavailable("Failed to retrieve attendance data from automation service.")


        # --- Step 3: Prepare and Return Final JSON Response ---
        response_data = {
            "message": natural_response, # Primarily use the natural language message
            "data": { # Optionally include raw data
                "date": date_str,
                "studio_id": studio_id_req,
                "studio_name": TARGET_STUDIO_NAME,
                "total_attendance": attendance # Include the raw number
            },
            "retrieved_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        return jsonify(response_data), 200

    # --- Error Handling Blocks (Catch errors from automation or unexpected issues) ---
    except BadRequest as e:
        app.logger.warning(f"Bad Request: {e.description}")
        return jsonify({"error": e.description}), 400
    except ServiceUnavailable as e:
         app.logger.error(f"Service Unavailable: {e.description}")
         return jsonify({"error": "Failed to retrieve data.", "details": e.description}), 503
    except InternalServerError as e:
         app.logger.error(f"Internal Server Error: {e.description}")
         return jsonify({"error": "Internal server configuration error."}), 500
    except ConnectionError as ce: # Catch specific errors from automation_service if raised
        app.logger.error(f"Automation Connection Error: {ce}")
        return jsonify({"error": "Failed to retrieve data from OTF Portal.", "details": str(ce)}), 503
    except ValueError as ve: # Catch specific errors from automation_service if raised
        app.logger.error(f"Data processing error: {ve}")
        return jsonify({"error": "Error processing retrieved data.", "details": str(ve)}), 500
    except Exception as e: # Generic fallback
        app.logger.exception(f"Unexpected Internal Server Error in route: {e}")
        return jsonify({"error": "An unexpected server error occurred."}), 500

# Basic health check endpoint
@app.route('/')
def health_check_route():
    app.logger.debug("Health check requested.")
    return jsonify({"status": "Trisha AI MVP Backend is running!"}), 200

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    # Listen on 0.0.0.0 to be accessible within Render network or locally if needed
    host = '0.0.0.0'
    app.logger.info(f"Starting Flask server on {host}:{port} | Debug mode: {debug_mode}")
    app.run(host=host, port=port, debug=debug_mode)
