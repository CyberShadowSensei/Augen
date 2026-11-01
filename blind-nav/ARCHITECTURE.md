# Architecture

> System design, component responsibilities, and data flow for Spectra / blind-nav.

---

## High-Level Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Camera / Video Source                        │
│           (USB webcam | laptop cam | ESP32-CAM IP stream)           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ raw BGR frame (416 × 416 px)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        run.py — BlindNav                            │
│                                                                     │
│  ┌───────────────────────────┐  ┌──────────────────────────────┐   │
│  │  YOLOv8 Detector          │  │  Glass Wall Detector         │   │
│  │  (ultralytics, 80 COCO    │  │  (pure OpenCV heuristic)     │   │
│  │   classes, GPU/CPU)       │  │  Canny edges + specular mask  │   │
│  │                           │  │  → synthetic "glass wall"     │   │
│  │  output: [{name, bbox,    │  │    detection injected into   │   │
│  │   confidence, region,     │  │    the same detection list   │   │
│  │   distance_ft}]           │  └──────────────────────────────┘   │
│  └──────────────┬────────────┘                                     │
│                 │  merged detection list                            │
│                 ▼                                                   │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  navigation.py — Navigator                               │      │
│  │                                                          │      │
│  │  • get_region(x_center)  → "left" | "center" | "right"  │      │
│  │  • estimate_distance_bbox(bbox_height_px) → feet         │      │
│  │  • priority_score(name) → int (PRIORITY_OBJECTS list)    │      │
│  │  • generate_instruction(objects) → (message, urgency)    │      │
│  │  • describe_environment(objects) → full scene string     │      │
│  └──────────────┬───────────────────────────────────────────┘      │
│                 │  (message, urgency)                              │
│                 ▼                                                   │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  TTS Worker Thread (pyttsx3 / Kokoro)                    │      │
│  │  Non-blocking — video loop never waits for speech        │      │
│  │  Urgency cooldown: danger=0.6s | normal=2.0s             │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
│  [Phase 2]  MiDaS depth estimator runs alongside YOLO               │
│             → replaces bbox distance proxy with real depth          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### `run.py` — BlindNav (Main Orchestrator)

| Responsibility | Detail |
|----------------|--------|
| Camera management | Opens `cv2.VideoCapture`, sets resolution and buffer size |
| YOLO inference | Runs per-frame detection at `CONFIDENCE` threshold |
| Glass detection | `detect_glass_walls()` — Canny + contour solidity + specular mask |
| MiDaS depth | `estimate_depth()` — transforms frame, runs model, normalises to 0-255 |
| Frame rendering | Draws bboxes, distance labels, region dividers, FPS, depth window |
| TTS dispatch | Thread-safe queue: replaces queued messages with latest (no audio backlog) |
| Keyboard handler | `D` = describe, `+/-` = confidence, `Q` = quit |

### `navigation.py` — Navigator

| Method | Input | Output |
|--------|-------|--------|
| `get_region(x_center)` | pixel x of bbox centre | `"left"` / `"center"` / `"right"` |
| `estimate_distance_bbox(h_px)` | bbox height in pixels | estimated feet (rough proxy: `0.8 / (h/frame_h)`) |
| `estimate_distance_depth(map, bbox)` | depth map + bbox | normalised depth intensity (0–255) |
| `priority_score(name)` | object name string | int; glass > PRIORITY_OBJECTS order > unknown > IGNORE_OBJECTS |
| `generate_instruction(objects)` | full detection list | `(spoken_message, urgency)` |
| `describe_environment(objects)` | full detection list | full region-by-region description string |

### `config.py` — Centralised Settings

All tunable parameters in a single file. Designed so a non-programmer can configure the system without touching any code logic.

---

## Distance Estimation

### Phase 1 — Bounding Box Heuristic

```
distance_ft = max(1, round(0.8 / (bbox_height / frame_height), 1))
```

Approximate only. Calibrated for typical indoor object sizes (person ~6 ft tall).

### Phase 2 — MiDaS Monocular Depth

```
depth_intensity = mean(depth_map[y1:y2, x1:x2])      # 0-255 (255 = closest)
distance_ft     = max(1.0, (255 - depth_intensity) / 25.0)
```

MiDaS uses the [inverse depth convention](https://github.com/isl-org/MiDaS): higher pixel value = closer.  
`DPT_Swin2_Tiny_256` runs at ~15 fps on RTX GPU with 416×416 input.

---

## Glass Wall Detection

YOLO cannot detect transparent surfaces (glass walls, floor-to-ceiling windows).  
A custom CV pipeline runs in parallel:

1. **Greyscale + Gaussian blur** — reduce camera noise
2. **Canny edge detection** — finds strong structural edges
3. **Contour filtering** — keeps only large (`> GLASS_MIN_AREA px²`), convex, approximately-rectangular contours
4. **Solidity check** — `contour_area / hull_area > 0.35` (flat panels are convex)
5. **Specular confirmation** — at least `GLASS_REFLECT_PCT` of the ROI must be bright (`> 210` intensity), confirming a reflective surface
6. **Inject synthetic detection** — the detected region is added to the detection list with label `"glass wall"` and treated with highest navigation priority

---

## Priority & Urgency System

### Priority Order
```python
PRIORITY_OBJECTS = [
    "person", "chair", "bench",           # people and seating
    "door", "tv", "laptop", "monitor",    # venue fixtures
    "backpack", "suitcase", "handbag",    # objects on floors/tables
    "bottle", "cup",
    "bicycle", "motorcycle",              # dangerous if indoors
    "knife", "scissors",
    "cat", "dog",
]
```

Glass walls override everything — they are always highest priority.  
Objects in `IGNORE_OBJECTS` (kitchen appliances, road vehicles, food, etc.) are silently filtered.

### Urgency Triage

| Condition | Urgency | Spoken Output |
|-----------|---------|---------------|
| Object in `center`, distance ≤ 3 ft | **danger** | "Stop! {name} directly ahead, very close." |
| Object on side, distance ≤ 3 ft | **danger** | "Warning. {name} on your {side}. Move {opposite}." |
| Glass wall ≤ 3 ft | **danger** | "Caution! Glass wall ahead on your {side}. Stop!" |
| Object in center, distance 3–6 ft | **warn** | "{name} ahead, {N} feet. Slow down." |
| Object on side, distance 3–6 ft | **warn** | "{name} to your {side}, {N} feet." |
| Distance > 6 ft | **clear** | "Path clear. {name} far {side}." |
| Nothing detected | **clear** | "Path clear. Move forward." |

### Cooldown Throttling

```python
ANNOUNCEMENT_COOLDOWN = 2.0   # normal messages
DANGER_COOLDOWN       = 0.6   # danger repeats faster
```

Prevents audio flooding while ensuring urgent alerts repeat frequently.

---

## Phase 2 — PMC Integration (Planned)

When connected to the Personal Memory Core backend:

```
BlindNav (Vision)
        │
        ▼
  VisualCortex (PMC)
  ├── EasyOCR — reads text from signs, documents, labels
  └── Moondream VLM — natural-language scene description
        │
        ▼
  MemoryStore (ChromaDB)
  └── Stores scene observations as searchable memories
        │
        ▼
  RAGEngine (granite3-dense:2b)
  └── Answers questions about previously seen places/objects

  AudioListener (PMC)
  └── Whisper GPU STT — voice commands trigger scene queries
```

This enables queries like:
- *"Where was the exit door?"* — retrieves from ChromaDB scene memory
- *"What does this sign say?"* — triggers EasyOCR on current frame
- *"What is in this room?"* — triggers Moondream scene caption + TTS

