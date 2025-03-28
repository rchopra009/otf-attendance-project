import os
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from automation_service import get_attendance_from_portal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/')
def health_check():
    """Simple health check endpoint."""
    return jsonify({"status": "ok", "service": "Trisha.AI MVP Backend"})

@app.route('/api/attendance/yesterday', methods=['GET'])
def get_yesterdays_attendance():
    """
    Endpoint to retrieve yesterday's total attendance from the OTF Studio Performance portal.
    """
    try:
        # Get credentials and configuration from environment variables
        username = os.environ.get('OTF_USERNAME')
        passw
