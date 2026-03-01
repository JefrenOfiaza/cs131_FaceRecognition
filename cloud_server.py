"""
CLOUD SERVER - Face Database with SQLite
Run this first: python3 cloud_server.py
Runs on port 5001
"""

from flask import Flask, request, jsonify
import numpy as np
import sqlite3
import json

app = Flask(__name__)

DB_FILE = "faces.db"
TOLERANCE = 0.6


def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                   (name TEXT PRIMARY KEY, 
                    encoding TEXT, 
                    role TEXT, 
                    authorized INTEGER)''')
    conn.commit()
    conn.close()
    print("[DB] Database initialized")


def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.execute("SELECT name, encoding, role, authorized FROM users")
    users = {}
    for row in cursor:
        users[row[0]] = {
            "encoding": json.loads(row[1]),
            "role": row[2],
            "authorized": bool(row[3])
        }
    conn.close()
    return users


def add_user(name, encoding, role, authorized):
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT OR REPLACE INTO users (name, encoding, role, authorized) VALUES (?, ?, ?, ?)",
        (name, json.dumps(encoding), role, int(authorized))
    )
    conn.commit()
    conn.close()


def compare_faces(known_encoding, unknown_encoding):
    known = np.array(known_encoding)
    unknown = np.array(unknown_encoding)
    distance = np.linalg.norm(known - unknown)
    return distance


@app.route('/check_face', methods=['POST'])
def check_face():
    data = request.json
    
    if 'encoding' not in data:
        return jsonify({"error": "No encoding provided"}), 400
    
    unknown_encoding = data['encoding']
    users = get_all_users()
    
    best_match = None
    best_distance = float('inf')
    
    for name, person_data in users.items():
        distance = compare_faces(person_data['encoding'], unknown_encoding)
        if distance < best_distance:
            best_distance = distance
            best_match = name
    
    if best_distance < TOLERANCE and best_match:
        person = users[best_match]
        return jsonify({
            "matched": True,
            "name": best_match,
            "role": person['role'],
            "authorized": person['authorized']
        })
    else:
        return jsonify({
            "matched": False,
            "name": "Unknown",
            "role": None,
            "authorized": False
        })


@app.route('/add_face', methods=['POST'])
def add_face():
    data = request.json
    
    name = data['name']
    encoding = data['encoding']
    role = data.get('role', 'guest')
    authorized = data.get('authorized', False)
    
    add_user(name, encoding, role, authorized)
    print(f"[DB] Added {name} (role: {role}, authorized: {authorized})")
    
    return jsonify({"success": True})


@app.route('/list_users', methods=['GET'])
def list_users():
    users = get_all_users()
    user_list = []
    for name, data in users.items():
        user_list.append({
            "name": name,
            "role": data['role'],
            "authorized": data['authorized']
        })
    return jsonify({"users": user_list})


@app.route('/delete_user/<name>', methods=['DELETE'])
def delete_user(name):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM users WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    print(f"[DB] Deleted {name}")
    return jsonify({"success": True})


if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("CLOUD SERVER - Face Database")
    print("=" * 50)
    print("Running on http://localhost:5001")
    print("Database file: faces.db")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5001, debug=False)