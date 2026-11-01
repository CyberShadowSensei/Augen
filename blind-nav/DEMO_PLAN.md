# Demo Plan — Hackathon Judging

> Spectra — Assistive Technology & Accessibility | Open Innovation Track

---

## Elevator Pitch (30 seconds)

> "Spectra is a real-time AI navigation assistant for people with visual impairments. Point any camera at a room, a corridor, or a document — and the system tells you what is there, how close it is, and what to do. No cloud, no internet, no screen required."

---

## Core Demonstration Sequence

### Step 1 — System Startup (30 seconds)
```bash
python run.py
```
> *"Navigation system ready."*

Judges see: live camera feed with bounding boxes, region dividers (LEFT / CENTER / RIGHT), FPS counter.

**Talking point:** Runs entirely offline. No API calls, no cloud dependency. Respects user privacy.

---

### Step 2 — Real-time Object Alerts (1 minute)

Walk slowly toward a chair or table.

**Expected voice output sequence:**
1. `"Chair to your left, 6 feet."` — warn
2. `"Chair ahead, 4 feet. Slow down."` — warn
3. `"Stop! Chair directly ahead, very close."` — danger (red box)

**Demonstrate:**
- Danger bounding boxes turn **red**; safe objects are **green**
- System never pauses the video to speak — fully non-blocking
- Repeat alerts every 0.6 seconds during danger vs. 2.0 seconds normally

**Talking point:** Priority system. People are announced before chairs, chairs before cups. Glass walls override everything.

---

### Step 3 — Glass Wall Detection (1 minute)

Hold a glass panel, mirror, or face the glass windows.

**Expected:**
- Cyan / gold bounding box appears around reflective surface
- `"Caution! Glass wall ahead on your centre. Stop!"`

**Talking point:** YOLOv8 cannot detect transparent surfaces — it was never trained on them. We built a separate Canny edge + specular mask detector specifically for this blind spot.

---

### Step 4 — Full Scene Description (30 seconds)

Press **D**.

**Expected:**
> *"Surroundings: To your left: 2 chairs. To your centre: 1 person, 1 laptop. To your right: 1 door."*

**Talking point:** At any moment the user can get a full mental map of the room with a single keystroke (or voice command in Phase 2).

---

### Step 5 — Live Confidence Tuning (30 seconds)

Press **−** to lower confidence to 0.30. More objects appear. Press **+** to raise to 0.70. Fewer, more certain detections.

**Talking point:** The user can tune sensitivity for their environment — a cluttered workshop needs lower confidence; a clean corridor can use higher.

---

### Step 6 — Phase 2 Teaser (1 minute)

Show the [`ARCHITECTURE.md`](ARCHITECTURE.md) diagram or a slide showing the full PMC integration stack.

**Talking point:**

> "The Phase 1 system runs today. Phase 2 integrates with our Personal Memory Core platform, adding:
> - **MiDaS depth** for calibrated distances
> - **EasyOCR** to read signs and documents aloud
> - **Moondream VLM** to describe any scene in natural language
> - **ChromaDB memory** so the system remembers previously visited spaces
> - **Whisper GPU STT** so the user issues voice commands rather than keyboard presses"

> "This is a real accessibility stack — not a prototype API wrapper."

---

## Judging Criteria Mapping

| Criterion | How Spectra Addresses It |
|-----------|--------------------------|
| **Impact** | Direct use case for 285 million visually impaired people globally (WHO). Works on commodity hardware (any laptop webcam). |
| **Innovation** | Glass wall detection is novel — no existing YOLO-based solution handles transparent barriers. PMC memory integration enables scene recall, unprecedented in edge accessibility tools. |
| **Technical Execution** | Real-time 28fps with threaded TTS, priority scoring, multi-tier urgency, configurable detection. Full GPU acceleration on RTX 5050 (sm_120 / CUDA 12.8). |
| **Feasibility** | Phase 1 is live and demonstrable today. Phase 2 built on PMC which is an operational local AI platform with 95.6% test pass rate. |
| **Completeness** | Five documentation files. One-click launchers. Config-only setup. No external API dependencies. |

---

## Hardware Setup for Demo

```
Laptop (Windows 11, RTX 5050):
├── Terminal 1: python run.py           ← main demo window
└── Optional: python run.py 1           ← USB cam if laptop cam is dim
```

Have a spare `run.bat` ready to restart in under 30 seconds if anything crashes.

---

## Backup Plan

If camera is unavailable at the venue:
1. Use a pre-recorded video feed via OBS virtual camera
2. Or: `python run.py "http://IP:81/stream"` from an ESP32-CAM phone hotspot

If GPU is unavailable:
- `config.py`: `USE_DEPTH = False` — Phase 1 runs fine on CPU at ~8fps (still fully functional for demo)

---

## Frequently Asked Questions (Judges)

**"Why not just use a phone app?"**  
Phone-based apps require internet, cloud processing, and subscription fees. Spectra runs 100% locally — critical for users in low-connectivity areas and for medical privacy compliance.

**"What is the accuracy of the distance estimation?"**  
Phase 1 uses a bounding-box heuristic — accurate to ±30% for typical indoor objects and sufficient for danger/warn/clear triage. Phase 2 replaces this with MiDaS monocular depth, calibrated to real metres.

**"Can it handle low light?"**  
YOLO degrades in very low light, like most camera-based systems. Phase 2 adds IR camera support as a future enhancement.

**"What languages does it support?"**  
TTS: any language supported by pyttsx3 (Windows SAPI voices). Moondream and Whisper support 50+ languages in Phase 2.

**"Is this open source?"**  
Yes. MIT license. All models used (YOLOv8, MiDaS, Whisper, Moondream) are open-source.

