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
WHISPER_MODEL = "base.en"       # "base.en" for lowest latency, "small.en" for highest accuracy
WHISPER_DEVICE = "cuda"         # "cuda" or "cpu"
WHISPER_FALLBACK_TO_CPU = True  # Automatically fallback to CPU if CUDA fails
WHISPER_TEMPERATURE = 0.0       # Greedy single-pass decoding (eliminates hallucination loops)
SILENCE_THRESHOLD_MS = 500      # Milliseconds of silence to trigger end-of-utterance
VAD_AGGRESSIVENESS = 3          # 0 (least aggressive) to 3 (most aggressive)