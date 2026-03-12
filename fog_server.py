"""
FOG SERVER - Coordinator with Alerts
Run this second: python3 fog_server.py
Runs on port 5000
"""

from flask import Flask, request, jsonify
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

app = Flask(__name__)

CLOUD_URL = "http://localhost:5001"

# Email config - UPDATE THESE to enable email alerts
EMAIL_ENABLED = True
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "your_email@gmail.com" #sending email address
EMAIL_PASSWORD = "your_app_password" #choose your sending email app password (not given due to privacy)
ALERT_RECIPIENT = "alert_recipient@gmail.com" #recipient email address (not given)

edge_devices = {}
access_log = []
notified_detections = set()


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
    elif alert_type == "EMAIL":
        print(f"\033[96m[{timestamp}] ✉ EMAIL: {message}\033[0m")
    else:
        print(f"[{timestamp}] {message}")


def send_email(subject, body):
    """Send a generic email. Returns True on success, False on failure."""
    if not EMAIL_ENABLED:
        return False

    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = ALERT_RECIPIENT
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, ALERT_RECIPIENT, msg.as_string())
        server.quit()
        print_alert("EMAIL", f"Sent: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def send_new_user_email(name, role, authorized):
    """Email notification when a new face is registered."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    auth_str = "YES - Access Authorized" if authorized else "NO - Access Denied"

    subject = f"[Face System] New User Registered: {name}"
    body = (
        f"A new user has been added to the facial recognition system.\n\n"
        f"  Name:       {name}\n"
        f"  Role:       {role}\n"
        f"  Authorized: {auth_str}\n"
        f"  Registered: {timestamp}\n\n"
        f"No action required. This is an informational notice."
    )
    send_email(subject, body)


def send_first_detection_email(name, role, decision, device_id):
    """Email notification the FIRST time a person is detected (per fog server session)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if decision == "GRANTED":
        subject = f"[Face System] First Detection: {name} — Access GRANTED"
        body = (
            f"A registered user was detected for the first time this session.\n\n"
            f"  Name:     {name}\n"
            f"  Role:     {role}\n"
            f"  Decision: GRANTED\n"
            f"  Device:   {device_id}\n"
            f"  Time:     {timestamp}\n\n"
            f"Access was granted. No action required."
        )
    elif name == "Unknown":
        subject = f"[Face System] ALERT: Unknown Person Detected at {device_id}"
        body = (
            f"An unrecognized person was detected for the first time this session.\n\n"
            f"  Name:     Unknown\n"
            f"  Decision: DENIED\n"
            f"  Device:   {device_id}\n"
            f"  Time:     {timestamp}\n\n"
            f"Please review camera footage."
        )
    else:
        subject = f"[Face System] ALERT: Unauthorized Access Attempt by {name}"
        body = (
            f"A known but unauthorized user was detected for the first time this session.\n\n"
            f"  Name:     {name}\n"
            f"  Role:     {role}\n"
            f"  Decision: DENIED\n"
            f"  Device:   {device_id}\n"
            f"  Time:     {timestamp}\n\n"
            f"Please review camera footage."
        )

    send_email(subject, body)


@app.route('/register_edge', methods=['POST'])
def register_edge():
    data = request.json
    device_id = data.get('device_id', 'unknown')
    edge_devices[device_id] = {"registered_at": datetime.now().isoformat()}
    print_alert("INFO", f"Edge device registered: {device_id}")
    return jsonify({"success": True})


@app.route('/notify_user_added', methods=['POST'])
def notify_user_added():
    """Called by the cloud server when a new face is registered."""
    data = request.json
    name = data.get('name', 'Unknown')
    role = data.get('role', 'guest')
    authorized = data.get('authorized', False)

    print_alert("INFO", f"New user registered: {name} (role: {role}, authorized: {authorized})")
    send_new_user_email(name, role, authorized)

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
    name = result.get('name', 'Unknown')
    role = result.get('role')

    # Determine access decision
    if result.get('matched') and result.get('authorized'):
        decision = "GRANTED"
        print_alert("GRANTED", f"{name} ({role}) at {device_id}")
    elif result.get('matched') and not result.get('authorized'):
        decision = "DENIED"
        print_alert("DENIED", f"{name} ({role}) - NOT AUTHORIZED at {device_id}")
    else:
        decision = "DENIED"
        print_alert("UNKNOWN", f"Unrecognized face at {device_id}")

    # --- First-detection email (fires only once per person per session) ---
    detection_key = name  # Use name as key; "Unknown" treated as one group
    if detection_key not in notified_detections:
        notified_detections.add(detection_key)
        send_first_detection_email(name, role or "N/A", decision, device_id)

    # Log access attempt
    log_entry = {
        "timestamp": timestamp,
        "device_id": device_id,
        "name": name,
        "decision": decision
    }
    access_log.append(log_entry)

    # Keep only last 100 entries
    if len(access_log) > 100:
        access_log.pop(0)

    return jsonify({
        "decision": decision,
        "name": name,
        "role": role,
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
        "email_enabled": EMAIL_ENABLED,
        "notified_detections": list(notified_detections)
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