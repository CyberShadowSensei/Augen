"""
config.py

Central configuration file for Personal Memory Core.
"""

# --- Visual Cortex Settings ---
CAMERA_INDEX = 0                      # Primary camera index: 0 for default webcam, 1 for external/glasses/fallback
CAMERA_BACKEND = "cv2.CAP_DSHOW"      # Primary backend for Windows: "cv2.CAP_DSHOW", "cv2.CAP_MSMF", "cv2.CAP_ANY", or int
CAMERA_FALLBACK_INDICES = [1]         # Fallback camera indices if primary index fails
CAMERA_FALLBACK_BACKENDS = ["cv2.CAP_ANY", "cv2.CAP_MSMF"]  # Fallback backends if primary backend fails
CAMERA_AUTO_DETECT = True             # Scan indices 0..3 if configured primary and fallbacks fail
CAMERA_WARMUP_DELAY = 0.75            # Seconds to wait for camera to stabilize (prevent black frames/logos)

# Backward-compatibility alias
CAP_BACKEND = CAMERA_BACKEND

# --- TTS Settings ---
TTS_VOICE = "af_sarah"
TTS_SPEED = 1.0

# --- Audio & Whisper STT Settings ---
WHISPER_MODEL = "small"          # Multilingual "small" model (robust to regional/Indian accents; runs in ~230ms on GPU)
WHISPER_DEVICE = "cuda"         # "cuda" or "cpu"
WHISPER_FALLBACK_TO_CPU = True  # Automatically fallback to CPU if CUDA fails
WHISPER_TEMPERATURE = 0.0       # Greedy single-pass decoding (eliminates hallucination loops)
WHISPER_INITIAL_PROMPT = "Personal AI assistant. Clear English commands, questions, notes, reminders, Apollo, Wi-Fi password, Dr. Mehta, David Chen, keys, meetings, appointments."
SILENCE_THRESHOLD_MS = 750      # Increased to 750ms so natural pauses between words do not clip sentences
VAD_AGGRESSIVENESS = 2          # 2 (balanced): prevents clipping of soft word beginnings and trailing consonants
