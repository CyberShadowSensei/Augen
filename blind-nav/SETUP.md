# Setup Guide

> Environment setup, model downloads, and execution steps for Spectra / blind-nav.

---

## System Requirements

| | Minimum | Recommended |
|---|---|---|
| Python | 3.10 | 3.10 or 3.11 |
| RAM | 4 GB | 8 GB+ |
| GPU | None (CPU works) | NVIDIA CUDA (RTX 3060+) |
| VRAM | — | 4 GB+ (8 GB for Phase 2 with MiDaS + Moondream) |
| OS | Windows 10 / Ubuntu 20.04 | Windows 11 / Ubuntu 22.04 |
| Camera | Any USB or laptop webcam | 1080p 30fps |
| Ollama | Optional (Phase 1) | Required (Phase 2 — Moondream, RAG) |

---

## Option A — One-Click Launchers

These create a virtual environment, install all dependencies, download models, and start the app.

### Windows
```bat
run.bat
```

### Linux / macOS
```bash
chmod +x run.sh
./run.sh
```

---

## Option B — Manual Setup

### Step 1 — Install PyTorch

Choose the build that matches your hardware.

**NVIDIA GPU — CUDA 12.8 (RTX 40xx / 50xx, sm_120 Blackwell):**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

**NVIDIA GPU — CUDA 12.1 (RTX 30xx / 40xx):**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**CPU only (any OS):**
```bash
pip install torch torchvision torchaudio
```

### Step 2 — Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3 — Download YOLO Weights
```bash
python download_models.py
```
Downloads `yolov8n.pt` (6 MB, fast) to `models/`. Optionally also downloads `yolov8s.pt` and `yolo11n.pt`.

### Step 4 — (Optional) Install Ollama for Phase 2

Required for Moondream VLM captioning and PMC memory integration.

1. Download from [ollama.com/download](https://ollama.com/download)
2. Pull required models:
```bash
ollama pull moondream
ollama pull granite3-dense:2b
ollama pull nomic-embed-text
```

### Step 5 — Run
```bash
python run.py
```

With a specific camera index:
```bash
python run.py 1               # USB cam
python run.py http://192.168.1.50:81/stream    # IP stream (ESP32-CAM)
```

---

## Configuration

All settings are in [`config.py`](config.py). Edit before running.

```python
# Camera
CAM_INDEX    = 0          # int = USB/laptop index | str = "http://IP/stream"
FRAME_WIDTH  = 416        # reduce for better FPS on slow hardware

# Detection
YOLO_MODEL   = "models/yolov8n.pt"   # yolov8n (fast) | yolov8s (accurate)
CONFIDENCE   = 0.50                  # 0.3 = more detections | 0.7 = fewer, precise
IOU_THRESH   = 0.45                  # NMS overlap threshold

# Phase 2 — depth
USE_DEPTH        = False             # True = enable MiDaS depth estimation
MIDAS_MODEL_TYPE = "DPT_Swin2_Tiny_256"   # fastest; "DPT_Large" for best accuracy

# Navigation
DANGER_DISTANCE_FT    = 3     # distance for "Stop!" alert
WARN_DISTANCE_FT      = 6     # distance for "Caution" alert
ANNOUNCEMENT_COOLDOWN = 2.0   # seconds between non-danger announcements
TTS_RATE              = 170   # speech speed (words per minute)
```

---

## Troubleshooting

**Camera won't open**
```python
# Try index 1 or 2 in config.py
CAM_INDEX = 1
```

Or probe all camera indices:
```bash
python -c "import cv2; [print(f'Index {i}: {cv2.VideoCapture(i).isOpened()}') for i in range(4)]"
```

**No audio on Windows**
```bash
pip install pywin32
```
Or run the terminal as Administrator.

**"OpenCV was installed without GUI support"**
```bash
pip uninstall opencv-python opencv-python-headless -y
pip install "opencv-python>=4.8.0,<5.0.0"
```

**Slow FPS on CPU**
- Use `yolov8n.pt` (smallest, fastest)
- Set `FRAME_WIDTH = 320` in `config.py`
- Set `CONFIDENCE = 0.65` to skip weak detections early

**CUDA kernel crash / hang (sm_120 / Blackwell)**
- Install `torch 2.11.0+cu128` — older builds don't support sm_120:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

**MiDaS download fails (Phase 2)**
Manually download from [github.com/isl-org/MiDaS](https://github.com/isl-org/MiDaS) and place the `.pt` file in `models/`.
