# Development Status

> What is implemented, tested, and verified — and what is on the roadmap.

---

## Phase 1 — Implemented & Working

### Core Pipeline

| Feature | File | Status | Notes |
|---------|------|--------|-------|
| YOLOv8n real-time detection | `run.py` | Complete | 80 COCO classes, ~30fps on GPU |
| YOLOv8s (accurate) support | `run.py` | Complete | Swappable via `config.py` |
| Left / centre / right spatial mapping | `navigation.py` | Complete | Frame-width trisection |
| Bounding box distance estimation | `navigation.py` | Complete | Rough proxy, calibrated for indoor |
| Priority object list | `config.py`, `navigation.py` | Complete | 20+ priority classes, tuned for indoor venues |
| Ignore list filtering | `config.py`, `navigation.py` | Complete | Kitchen, road, outdoor objects suppressed |
| Danger / warn / clear urgency triage | `navigation.py` | Complete | 3-tier with configurable distance thresholds |
| Threaded TTS — non-blocking | `run.py` | Complete | Video loop never freezes during speech |
| TTS cooldown throttling | `run.py` | Complete | Separate danger (0.6s) and normal (2.0s) cooldowns |
| Heuristic glass wall detection | `run.py` | Complete | Canny + solidity + specular mask — YOLO-invisible barriers |
| On-demand scene description (D key) | `run.py`, `navigation.py` | Complete | Full L/C/R object census, spoken |
| Runtime confidence adjustment (+/−) | `run.py` | Complete | 0.10 – 0.95 range, live |
| FPS display overlay | `run.py` | Complete | Top-right corner |
| Region divider overlay | `run.py` | Complete | LEFT / CENTER / RIGHT lines on frame |
| CLI camera argument | `run.py` | Complete | `python run.py 1` or `python run.py http://...` |
| One-click launchers | `run.bat`, `run.sh` | Complete | Creates venv, installs deps, runs |
| OpenCV GUI pre-check | `run.py` | Complete | Clear error message if headless OpenCV installed |

### Hardware Verified

| Hardware | Status |
|----------|--------|
| Windows 11 + RTX 5050 (CUDA 12.8, sm_120) | Verified |
| Laptop webcam (DirectShow, index 0) | Verified |
| USB Logitech C920 (index 1) | Verified |
| ESP32-CAM HTTP stream | Verified |
| CPU-only (Intel Core i7, no GPU) | Verified |

---

## Phase 2 — In Development

### Depth & Navigation

| Feature | Status | Notes |
|---------|--------|-------|
| MiDaS monocular depth (`USE_DEPTH=True`) | Planned | Model loader in place, not yet tested end-to-end |
| Real distance from depth map per bbox | Planned | Formula implemented, needs calibration run |
| Floor / navigable path segmentation | Planned | Requires semantic segmentation model |
| Object tracking across frames | Planned | SORT or ByteTrack |
| Stair / step detection | Planned | Depth gradient analysis |

### PMC Integration

| Feature | Status | Notes |
|---------|--------|-------|
| EasyOCR document & sign reading | Planned | EasyOCR working in PMC, not yet wired to blind-nav |
| Moondream VLM scene captioning | Planned | Working in PMC via Ollama |
| ChromaDB scene memory | Planned | PMC MemoryStore ready to receive visual memories |
| Whisper voice command trigger | Planned | PMC AudioListener functional on GPU |
| RAG query over historical scenes | Planned | PMC RAGEngine operational |

### Audio / UX

| Feature | Status | Notes |
|---------|--------|-------|
| Spatial audio (left/right ear pan) | Planned | Stereo panning to reinforce L/C/R region announcements |
| Kokoro neural TTS (replaces pyttsx3) | Planned | Kokoro-ONNX running in PMC, integration pending |

---

## Known Limitations

| Issue | Impact | Workaround |
|-------|--------|------------|
| Phase 1 distance is a rough proxy | ±50% accuracy | Fine for danger alerting; Phase 2 depth will improve |
| Glass detection has false positives in bright light | Occasional spurious glass alerts | Increase `GLASS_REFLECT_PCT` and `GLASS_EDGE_THRESH` in `config.py` |
| No GPU support for RTX 50xx on PyTorch < 2.11 | Falls back to CPU (still works, lower FPS) | Install `torch 2.11.0+cu128` |
| TTS queue replaces all pending messages | Fast-changing scenes may drop intermediate alerts | Acceptable — ensures freshest information is always spoken |
| No object tracking | Same object may be re-announced | Will be resolved with SORT in Phase 2 |

---

## Performance (Verified on RTX 5050 GPU)

| Component | Metric |
|-----------|--------|
| YOLOv8n at 416×416 | ~28 fps |
| TTS latency (pyttsx3) | ~50ms to queue, non-blocking |
| Whisper base.en GPU (PMC) | ~260ms warm RTF=0.087 |
| MiDaS DPT_Swin2_Tiny_256 (Phase 2) | ~15fps at 416×416 (estimated) |

