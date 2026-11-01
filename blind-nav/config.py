# =============================================================
#  blind-nav  |  config.py  — all tunable settings in one place
# =============================================================

# ── Camera ────────────────────────────────────────────────────
CAM_INDEX = 0          # int: laptop/USB cam index  OR  str: "http://IP:PORT/video_feed"
FRAME_WIDTH  = 416     # ↓ reduced from 640 for lower inference latency (nano model handles 416 well)
FRAME_HEIGHT = 416

# ── Model ─────────────────────────────────────────────────────
# Phase 1 (detection only, no depth)
YOLO_MODEL   = "models/yolov8n.pt"   # yolov8n / yolov8s / yolov8m / yolo11n
CONFIDENCE   = 0.50                  # ↑ raised from 0.45 to prune weak detections early
IOU_THRESH   = 0.45                  # ↓ slightly tighter NMS — fewer redundant boxes

# Phase 2 (add depth — set USE_DEPTH=True after testing Phase 1)
USE_DEPTH        = False
MIDAS_MODEL_TYPE = "DPT_Swin2_Tiny_256"   # fastest; "DPT_Large" for better accuracy
DEPTH_DANGER_THRESHOLD = 200              # 0-255 intensity; higher = closer

# ── Navigation ────────────────────────────────────────────────
ANNOUNCEMENT_COOLDOWN = 2.0   # ↓ from 2.5s — slightly more responsive for demo
DANGER_COOLDOWN       = 0.6   # ↓ from 0.8s — faster danger re-alerts
DANGER_DISTANCE_FT    = 3     # estimated feet threshold for "danger" alert
WARN_DISTANCE_FT      = 6     # estimated feet threshold for "caution" alert
TTS_RATE              = 170   # ↑ from 155 wpm — snappier speech = less audio lag

# ── Display ───────────────────────────────────────────────────
SHOW_DEPTH_WINDOW = True      # show separate depth-map window (Phase 2 only)
SHOW_FPS          = True
SHOW_REGIONS      = True      # draw LEFT / CENTER / RIGHT dividers

# ── Glass wall detection ──────────────────────────────────────
DETECT_GLASS      = True      # enable heuristic glass/transparent barrier detector
GLASS_EDGE_THRESH = 120       # Canny high threshold (↑ = fewer false positives)
GLASS_MIN_AREA    = 8000      # minimum contour area (px²) to consider as glass panel
GLASS_REFLECT_PCT = 0.08      # fraction of ROI that must be specular (bright) to confirm glass

# ── Hackathon / Indoor object priority whitelist ──────────────
# Tuned for typical indoor hackathon / conference venue layout.
# Lower index = higher priority for voice announcement.
PRIORITY_OBJECTS = [
    # People & furniture most likely to be in a hackathon hall
    "person", "chair", "bench",
    # Common venue fixtures
    "door", "tv", "laptop", "monitor",
    # Things left on tables / floors
    "backpack", "suitcase", "handbag",
    "bottle", "cup",
    # Rare but dangerous
    "bicycle", "motorcycle",
    "knife", "scissors",
    "cat", "dog",
]

# Objects to ignore entirely (reduce noise in hackathon context).
# Removed: objects that only appear in kitchens, bedrooms, etc.
IGNORE_OBJECTS = [
    # Structural (YOLO sometimes tags these for outdoor/COCO scenes)
    "sky", "ceiling", "floor", "wall", "background",
    # Kitchen / home appliances — irrelevant at a hackathon
    "refrigerator", "oven", "microwave",
    "toaster", "blender", "dishwasher",
    "washing machine", "dryer",
    # Bedroom / living room items
    "bed", "couch", "dining table",
    "toilet", "sink", "bathtub",
    # Outdoor / road objects
    "car", "truck", "bus", "train",
    "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench",          # bench re-added to priority above
    "airplane", "boat",
    # Food items — not navigation-relevant
    "banana", "apple", "sandwich", "orange", "broccoli",
    "carrot", "hot dog", "pizza", "donut", "cake",
    "bowl", "spoon", "fork",
    # Misc household
    "vase", "clock", "scissors",       # scissors re-added to priority above
    "teddy bear", "hair drier", "toothbrush",
    "potted plant",
]

