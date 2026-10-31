"""
config.py

Central configuration file for Personal Memory Core.
"""

# --- Visual Cortex Settings ---
CAMERA_INDEX = "http://10.135.108.201:81/stream" # 0 for default webcam, 1 for external/glasses
CAMERA_WARMUP_DELAY = 0.75  # Seconds to wait for camera to stabilize (prevent black frames/logos)
CAP_BACKEND = "cv2.CAP_DSHOW" # Specific backend for Windows (e.g., for phone webcams)

# --- TTS Settings ---
TTS_VOICE = "af_sarah"
TTS_SPEED = 1.0

# --- Audio Settings ---
# VAD Aggressiveness: 0 (Least) to 3 (Most)
VAD_AGGRESSIVENESS = 3