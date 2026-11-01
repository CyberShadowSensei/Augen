# GitHub Repository Metadata — Spectra / blind-nav

Use these in GitHub's **About** section (gear icon on repo page).

---

## Short Description (one-liner for GitHub About)

```
Real-time AI navigation assistant for the visually impaired — YOLOv8 object detection, glass wall detection, and spoken guidance. No cloud. No screen required.
```

---

## Extended Description (for README header / GitHub About "description" field)

```
Spectra is a multimodal AI accessibility assistant that interprets visual surroundings and delivers contextual information through speech. Built for the visually impaired: real-time object detection, spatial awareness (left / centre / right), heuristic glass wall detection, and threaded non-blocking TTS. Phase 2 adds MiDaS depth, EasyOCR document reading, Moondream scene captioning, and PMC long-term memory.
```

---

## GitHub Topics (repository tags)

```
accessibility  assistive-technology  computer-vision  yolov8  object-detection
depth-estimation  text-to-speech  blind  navigation  midas  easyocr  python
pytorch  opencv  real-time  open-innovation  hackathon  offline-ai  edge-ai
```

---

## Website Field

```
https://github.com/CyberShadowSensei/contextAI
```

---

## Social Preview Alt Text

```
Spectra — AI vision assistant for the visually impaired. Annotated camera frame showing detected person (green box, "person 0.87 | 4.2ft | center") and glass wall (cyan box, "GLASS 3ft | centre"), with LEFT / CENTER / RIGHT region dividers overlaid.
```

---

## Release Tag Description (v0.1.0 — Phase 1)

```
## Spectra v0.1.0 — Phase 1: Real-time Navigation

First stable release of the blind-nav navigation assistant.

### What's included
- YOLOv8n/s real-time object detection (80 COCO classes)
- Left / centre / right spatial mapping
- Bounding box distance estimation
- Danger / warn / clear urgency triage with spoken output
- Heuristic glass wall detector (Canny + specular mask)
- Threaded non-blocking TTS (pyttsx3)
- On-demand full scene description (D key)
- Runtime confidence adjustment (+/−)
- One-click launchers: run.bat (Windows) / run.sh (Linux/macOS)
- Priority object whitelist tuned for indoor / venue environments

### Requirements
- Python 3.10+
- PyTorch 2.2+ (CPU) or 2.11+cu128 (NVIDIA GPU)
- Any USB or laptop webcam

### Phase 2 Preview
MiDaS depth, EasyOCR, Moondream VLM, Whisper voice commands, and PMC memory integration coming next.
```
