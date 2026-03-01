"""
FOG SERVER - Coordinator with Alerts
Run this second: python3 fog_server.py
Runs on port 5000
"""

from flask import Flask, request, jsonify
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

app = Flask(__name__)

CLOUD_URL = "http://localhost:5001"

# Email config - UPDATE THESE if you want email alerts
EMAIL_ENABLED = False
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"
ALERT_RECIPIENT = "alert_recipient@gmail.com"

edge_devices = {}
access_log = []


def print_alert(alert_type, message):
    """Print colored alert to terminal"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if alert_type == "GRANTED":
        print(f"\033[92m[{timestamp}] ✓ ACCESS GRANTED: {message}\033[0m")
    elif alert_type == "DENIED":
        print(f"\033[91m[{timestamp}] ✗ ACCESS DENIED: {message}\033[0m")
        print(f"\033[91m{'!' * 50}\033[0m")
        print(f"\033[91m!!! ALERT: UNAUTHORIZED ACCESS ATTEMPT !!!\033[0m")
        print(f"\033[91m{'!' * 50}\033[0m")
    elif alert_type == "UNKNOWN":
        print(f"\033[93m[{timestamp}] ? UNKNOWN PERSON: {message}\033[0m")
        print(f"\033[93m{'!' * 50}\033[0m")
        print(f"\033[93m!!! ALERT: UNKNOWN PERSON DETECTED !!!\033[0m")
        print(f"\033[93m{'!' * 50}\033[0m")
    else:
        print(f"[{timestamp}] {message}")


def send_alert_email(device_id, message):
    if not EMAIL_ENABLED:
        return
    
    try:
        msg = MIMEText(message)
        msg['Subject'] = "SECURITY ALERT - Unauthorized Access"
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = ALERT_RECIPIENT
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, ALERT_RECIPIENT, msg.as_string())
        server.quit()
        print_alert("INFO", "Email alert sent!")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


@app.route('/register_edge', methods=['POST'])
def register_edge():
    data = request.json
    device_id = data.get('device_id', 'unknown')
    edge_devices[device_id] = {"registered_at": datetime.now().isoformat()}
    print_alert("INFO", f"Edge device registered: {device_id}")
    return jsonify({"success": True})


@app.route('/check_access', methods=['POST'])
def check_access():
    data = request.json
    device_id = data.get('device_id', 'unknown')
    encoding = data.get('encoding')
    
    # Query cloud
    try:
        response = requests.post(f"{CLOUD_URL}/check_face", json={"encoding": encoding}, timeout=5)
        result = response.json()
    except Exception as e:
        print(f"[ERROR] Cloud error: {e}")
        return jsonify({"error": "Cloud unavailable", "decision": "DENY"}), 503
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Determine access decision
    if result.get('matched') and result.get('authorized'):
        decision = "GRANTED"
        print_alert("GRANTED", f"{result['name']} ({result['role']}) at {device_id}")
    elif result.get('matched') and not result.get('authorized'):
        decision = "DENIED"
        print_alert("DENIED", f"{result['name']} ({result['role']}) - NOT AUTHORIZED at {device_id}")
        send_alert_email(device_id, f"Unauthorized person {result['name']} tried to access at {device_id}")
    else:
        decision = "DENIED"
        print_alert("UNKNOWN", f"Unrecognized face at {device_id}")
        send_alert_email(device_id, f"Unknown person detected at {device_id}")
    
    # Log access attempt
    log_entry = {
        "timestamp": timestamp,
        "device_id": device_id,
        "name": result.get('name', 'Unknown'),
        "decision": decision
    }
    access_log.append(log_entry)
    
    # Keep only last 100 entries
    if len(access_log) > 100:
        access_log.pop(0)
    
    return jsonify({
        "decision": decision,
        "name": result.get('name', 'Unknown'),
        "role": result.get('role'),
        "timestamp": timestamp
    })


@app.route('/get_log', methods=['GET'])
def get_log():
    return jsonify({"log": access_log[-20:]})  # Last 20 entries


@app.route('/get_status', methods=['GET'])
def get_status():
    return jsonify({
        "edge_devices": list(edge_devices.keys()),
        "total_access_attempts": len(access_log),
        "email_enabled": EMAIL_ENABLED
    })


if __name__ == '__main__':
    print("=" * 50)
    print("FOG SERVER - Security Coordinator")
    print("=" * 50)
    print("Running on http://localhost:5000")
    print(f"Cloud server: {CLOUD_URL}")
    print(f"Email alerts: {'ENABLED' if EMAIL_ENABLED else 'DISABLED'}")
    print("=" * 50)
    print("Waiting for access attempts...")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)