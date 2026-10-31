# Project: Personal Memory Core (PMC) - Camera & Whisper GPU sm_120 Acceleration

## Architecture
Personal Memory Core integrates multi-modal perceptual inputs:
1. **Visual Cortex (`visual_cortex.py`)**: OpenCV-based frame acquisition from local or external cameras, with OCR and scene analysis.
2. **Audio Listener (`audio_provider.py`)**: PyAudio capture, WebRTC VAD, and `openai-whisper` speech transcription.
3. **Configuration (`config.py`)**: Centralized settings for vision, audio, TTS, and device backends.
4. **Benchmarking & Testing (`scripts/benchmark_whisper.py`)**: Empirical validation of GPU acceleration, latency, and transcription fidelity.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Camera Index 0 Default | Configure `CAMERA_INDEX = 0` as primary webcam | M1 | Survey / R1 (DONE) |
| 2 | DirectShow Backend Support | Support `cv2.CAP_DSHOW` as primary backend for Windows video capture | M1 | Survey / R1 (DONE) |
| 3 | Backend String & Enum Resolution | Map string configs (`"cv2.CAP_DSHOW"`, `"CAP_ANY"`, etc.) and integers to OpenCV enums | M1 | Survey / R1 (DONE) |
| 4 | Multi-Tier Resilient Camera Fallback | Fallback across backends, fallback indices (`[1]` for AMD Privacy View / virtual cams), and auto-detect probing | M1 | Survey / R1 (DONE) |
| 5 | Non-Destructive Frame Capture Verification | Test script / verification run capturing frames without unhandled exceptions or Tkinter crash | M1 | Survey / R1 (DONE) |
| 6 | PyTorch sm_120 cu128 Environment Upgrade | Upgrade `torch`, `torchvision`, `torchaudio` to CUDA 12.8 wheels natively supporting sm_120 Blackwell | M2 | Survey / R2 |
| 7 | Fix Whisper Model Suffix Stripping | Retain `.en` suffix (`base.en`, `small.en`) to avoid loading heavy multilingual models | M2 | Survey / R2 |
| 8 | Dynamic Whisper Device & CPU Fallback | Check `torch.cuda.is_available()`, attempt `device="cuda"`, gracefully fall back to CPU on error | M2 | Survey / R2 |
| 9 | Whisper Latency & Hallucination Optimization | Set `fp16=(device=="cuda")`, `temperature=0.0`, `condition_on_previous_text=False`, `without_timestamps=True` | M2 | Survey / R2 |
| 10 | Whisper GPU Startup Warmup | 1-second dummy inference during initialization to eliminate 2-4s cold-start latency | M2 | Survey / R2 |
| 11 | Whisper Configuration Centralization | Expose `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_FALLBACK_TO_CPU`, `WHISPER_TEMPERATURE` in `config.py` | M2 | Survey / R2 |
| 12 | Standalone Whisper GPU Benchmark Script | Create `scripts/benchmark_whisper.py` measuring cold-start, warm latency, RTF, VRAM, and accuracy | M3 | Survey / R2 |
| 13 | End-to-End Acceptance Verification | Verify camera frame capture and Whisper GPU execution against all acceptance criteria | M3 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Camera Access & Configurable Fallback | `config.py`, `visual_cortex.py`, `test_cam.py` | none | DONE |
| 2 | PyTorch sm_120 Upgrade & Whisper Acceleration | Python packages (`torch`, `torchvision`, `torchaudio`), `config.py`, `audio_provider.py` | none | DONE |
| 3 | Whisper GPU Benchmark & E2E Acceptance Verification | `scripts/benchmark_whisper.py`, benchmark run, acceptance validation | M1, M2 | DONE |

## Milestone 1 Outputs
- `config.py`: `CAMERA_INDEX = 0`, `CAMERA_BACKEND = "cv2.CAP_DSHOW"`, `CAMERA_FALLBACK_INDICES = [1]`, `CAMERA_FALLBACK_BACKENDS = ["cv2.CAP_ANY", "cv2.CAP_MSMF"]`, `CAMERA_AUTO_DETECT = True`, `CAMERA_WARMUP_DELAY = 0.75`, `CAP_BACKEND = CAMERA_BACKEND`.
- `visual_cortex.py`: Added `resolve_camera_backend()`, multi-tier `_open_camera()`, robust `_capture_frame()`.
- `test_cam.py`: Added `--headless` CLI flag, config integration, fallback awareness.
- Verification: Captured valid frames `(480, 640, 3)`. Passed 35 adversarial tests, passed multi-threading/concurrency and zero-handle-leak tests, passed Forensic Integrity Audit (CLEAN).

## Interface Contracts
### `config.py` ↔ `visual_cortex.py`
- `CAMERA_INDEX`: `int` (e.g. `0`) or `str` (e.g. streaming URL)
- `CAMERA_BACKEND`: `str` (e.g. `"cv2.CAP_DSHOW"`) or `int`
- `CAMERA_FALLBACK_INDICES`: `list[int]` (e.g. `[1]`)
- `CAMERA_FALLBACK_BACKENDS`: `list[str | int]` (e.g. `["cv2.CAP_ANY", "cv2.CAP_MSMF"]`)
- `CAMERA_AUTO_DETECT`: `bool` (default `True`)
- `CAMERA_WARMUP_DELAY`: `float` (seconds, default `0.75`)
- Backward compatibility: `CAP_BACKEND = CAMERA_BACKEND`

### `config.py` ↔ `audio_provider.py`
- `WHISPER_MODEL`: `str` (default `"base.en"`)
- `WHISPER_DEVICE`: `str` (default `"cuda"`)
- `WHISPER_FALLBACK_TO_CPU`: `bool` (default `True`)
- `WHISPER_TEMPERATURE`: `float` (default `0.0`)
- `SILENCE_THRESHOLD_MS`: `int` (default `500`)
- `VAD_AGGRESSIVENESS`: `int` (default `3`)

### `visual_cortex.py` Public API
- `VisualCortex._capture_frame()` -> `tuple[np.ndarray | None, str | None]`
  - Returns `(frame, None)` on success where `frame.shape == (H, W, 3)`.
  - Returns `(None, error_msg)` on failure; never raises unhandled exceptions.

### `audio_provider.py` Public API
- `AudioListener(model_size=None, device=None, tts_engine=None)`
- `AudioListener.whisper_model`: loaded `whisper` model instance on active device
- `AudioListener.device`: `"cuda"` or `"cpu"`

## Code Layout
- `config.py`: Global configuration parameters
- `visual_cortex.py`: Camera acquisition, backend resolution, and fallback logic
- `audio_provider.py`: Audio capture, VAD, Whisper transcription, device fallback
- `test_cam.py`: Camera diagnostic utility
- `scripts/benchmark_whisper.py`: Standalone benchmark for Whisper GPU latency and accuracy
