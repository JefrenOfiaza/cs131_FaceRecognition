# Face Recognition Security System

Edge computing security system using face recognition.

## Setup

Install dependencies:
```bash
sudo apt-get install cmake python3-pip libopenblas-dev liblapack-dev
pip3 install opencv-python face_recognition flask requests numpy --break-system-packages
```

## How to Run

Open 3 terminals and run in order:
```bash
# Terminal 1
python3 cloud_server.py

# Terminal 2
python3 fog_server.py

# Terminal 3
python3 edge_device.py
```

## Controls

Click on the camera window first, then:

| Key | Action |
|-----|--------|
| r | Register a face |
| l | List registered users |
| q | Quit |

## Registering a Face

1. Look at camera
2. Press `r`
3. Enter name
4. Enter role (admin/user/guest)
5. Enter authorized (y/n)

## Running on Jetson (Second Edge Device)

Edit `edge_device.py` on Jetson:
```python
FOG_URL = "http://YOUR_PC_IP:5000"
CLOUD_URL = "http://YOUR_PC_IP:5001"
DEVICE_ID = "edge_jetson"
```

Then run:
```bash
python3 edge_device.py
```