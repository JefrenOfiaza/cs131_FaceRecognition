"""
EDGE DEVICE - Face Detection
Run this: python3 edge_device.py
"""

import cv2
import face_recognition
import requests
import time
import sys

# CONFIG - change these for each device
FOG_URL = "http://localhost:5000"
CLOUD_URL = "http://localhost:5001"
DEVICE_ID = "edge_1"  # Change to "edge_2" on second device

# Performance settings - increase PROCESS_EVERY_N_FRAMES if laggy
PROCESS_EVERY_N_FRAMES = 5
SCALE_FACTOR = 0.25
SEND_COOLDOWN = 2.0

def print_status(status, message):
    """Print colored status"""
    if status == "GRANTED":
        print(f"\033[92m[✓] {message}\033[0m")
    elif status == "DENIED":
        print(f"\033[91m[✗] {message}\033[0m")
    elif status == "ERROR":
        print(f"\033[91m[ERROR] {message}\033[0m")
    elif status == "INFO":
        print(f"\033[94m[i] {message}\033[0m")
    else:
        print(f"[{status}] {message}")


def main():
    # State
    frame_count = 0
    last_send_time = 0
    last_result = None
    face_locations = []
    current_encoding = None
    
    print("=" * 50)
    print(f"EDGE DEVICE: {DEVICE_ID}")
    print("=" * 50)
    print(f"Fog server: {FOG_URL}")
    print(f"Cloud server: {CLOUD_URL}")
    print("=" * 50)
    
    # Register with fog
    try:
        requests.post(f"{FOG_URL}/register_edge", json={"device_id": DEVICE_ID}, timeout=5)
        print_status("INFO", "Registered with fog server")
    except:
        print_status("ERROR", "Fog server not available - start it first!")
    
    # Start camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print_status("ERROR", "Could not open camera")
        sys.exit(1)
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print_status("INFO", "Camera started")
    print("=" * 50)
    print("CONTROLS:")
    print("  q - Quit")
    print("  r - Register current face")
    print("  x - Remove a user")
    print("  l - List registered users")
    print("=" * 50)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print_status("ERROR", "Failed to grab frame")
            break
        
        frame_count += 1
        
        # Only process every N frames for performance
        if frame_count % PROCESS_EVERY_N_FRAMES == 0:
            small = cv2.resize(frame, (0, 0), fx=SCALE_FACTOR, fy=SCALE_FACTOR)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            
            face_locations = face_recognition.face_locations(rgb, model="hog")
            
            if face_locations:
                encodings = face_recognition.face_encodings(rgb, face_locations)
                if encodings:
                    current_encoding = encodings[0]
                    
                    # Check with server (with cooldown)
                    if time.time() - last_send_time >= SEND_COOLDOWN:
                        last_send_time = time.time()
                        try:
                            #start_time = time.time()

                            response = requests.post(
                                f"{FOG_URL}/check_access",
                                json={"device_id": DEVICE_ID, "encoding": current_encoding.tolist()},
                                timeout=5
                            )

                            #end_time = time.time()
                            #latency_ms = (end_time - start_time) * 1000
                            #print_status("INFO", f"System latency: {latency_ms:.2f} ms")
                            
                            decision = last_result.get('decision')
                            name = last_result.get('name')
                            
                            if decision == "GRANTED":
                                print_status("GRANTED", f"{name} - Access granted")
                            else:
                                print_status("DENIED", f"{name} - Access denied")
                                
                        except Exception as e:
                            print_status("ERROR", f"Server error: {e}")
            else:
                last_result = None
                current_encoding = None
        
        # Draw boxes on frame
        for (top, right, bottom, left) in face_locations:
            # Scale back up
            top = int(top / SCALE_FACTOR)
            right = int(right / SCALE_FACTOR)
            bottom = int(bottom / SCALE_FACTOR)
            left = int(left / SCALE_FACTOR)
            
            # Color based on result
            if last_result and last_result.get('decision') == "GRANTED":
                color = (0, 255, 0)  # Green
                label = f"{last_result.get('name')} - GRANTED"
            elif last_result:
                color = (0, 0, 255)  # Red
                label = f"{last_result.get('name')} - DENIED"
            else:
                color = (255, 255, 0)  # Cyan
                label = "Detecting..."
            
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(frame, (left, top - 35), (right, top), color, cv2.FILLED)
            cv2.putText(frame, label, (left + 6, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        # Show device ID on frame
        cv2.putText(frame, f"Device: {DEVICE_ID}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imshow(f'Edge Device - {DEVICE_ID}', frame)
        
        # Handle keys
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
            
        elif key == ord('r'):
            if current_encoding is not None:
                print("\n" + "=" * 50)
                print("REGISTER NEW FACE")
                print("=" * 50)
                name = input("Enter name: ").strip()
                if not name:
                    print_status("ERROR", "Name cannot be empty")
                    continue
                    
                role = input("Enter role (admin/user/guest): ").strip() or "guest"
                auth_input = input("Authorized for access? (y/n): ").strip().lower()
                authorized = auth_input == 'y'
                
                try:
                    response = requests.post(f"{CLOUD_URL}/add_face", json={
                        "name": name,
                        "encoding": current_encoding.tolist(),
                        "role": role,
                        "authorized": authorized
                    }, timeout=5)
                    
                    if response.json().get('success'):
                        print_status("INFO", f"Added {name} to database (role: {role}, authorized: {authorized})")
                    else:
                        print_status("ERROR", "Failed to add face")
                except Exception as e:
                    print_status("ERROR", f"Could not connect to cloud: {e}")
                print("=" * 50 + "\n")
            else:
                print_status("ERROR", "No face detected - look at camera first")

        elif key == ord('x'):
            print("\n" + "=" * 50)
            print("REMOVE USER")
            print("=" * 50)
            try:
                response = requests.get(f"{CLOUD_URL}/list_users", timeout=5)
                users = response.json().get('users', [])
                if not users:
                    print_status("ERROR", "No users registered")
                else:
                    for user in users:
                        auth_str = "✓" if user['authorized'] else "✗"
                        print(f"  {auth_str} {user['name']} ({user['role']})")
                    name = input("Enter name to remove: ").strip()
                    if not name:
                        print_status("ERROR", "Name cannot be empty")
                    else:
                        response = requests.post(f"{CLOUD_URL}/remove_face", json={"name": name}, timeout=5)
                        if response.json().get('success'):
                            print_status("INFO", f"Removed {name} from database")
                        else:
                            print_status("ERROR", f"User '{name}' not found")
            except Exception as e:
                print_status("ERROR", f"Could not connect to cloud: {e}")
            print("=" * 50 + "\n")
                
        elif key == ord('l'):
            print("\n" + "=" * 50)
            print("REGISTERED USERS")
            print("=" * 50)
            try:
                response = requests.get(f"{CLOUD_URL}/list_users", timeout=5)
                users = response.json().get('users', [])
                if users:
                    for user in users:
                        auth_str = "✓" if user['authorized'] else "✗"
                        print(f"  {auth_str} {user['name']} ({user['role']})")
                else:
                    print("  No users registered yet")
            except Exception as e:
                print_status("ERROR", f"Could not get users: {e}")
            print("=" * 50 + "\n")
    
    cap.release()
    cv2.destroyAllWindows()
    print_status("INFO", "Camera stopped")


if __name__ == '__main__':
    main()