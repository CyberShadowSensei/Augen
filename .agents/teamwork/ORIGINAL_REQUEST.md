# Original User Request

## Approved Task Prompt — 2026-10-31T13:01:20Z

Configure camera access using index 0 with DirectShow fallback support and update the PyTorch environment so openai-whisper runs on the RTX 5050 GPU with minimal latency.

Working directory: d:\contextAI-main
Integrity mode: development

## Requirements

### R1. Camera Access on Index 0 with Configurable Fallback
Update `config.py` and `visual_cortex.py` to support camera index 0 with the DirectShow backend (`cv2.CAP_DSHOW`, as demonstrated in `test_cam.py`), while keeping camera index and backend settings configurable with graceful fallback behavior if opening the camera fails.

### R2. openai-whisper GPU Acceleration on RTX 5050 (sm_120)
Retain `openai-whisper` and resolve the CUDA/PyTorch incompatibility on the NVIDIA GeForce RTX 5050 Laptop GPU (sm_120 Blackwell architecture) by updating the PyTorch/CUDA environment to an sm_120-compatible build so that Whisper transcription executes directly on the GPU without kernel errors or hangs.

## Acceptance Criteria

### Camera Integration
- [ ] `config.py` and `visual_cortex.py` support camera index 0 with `cv2.CAP_DSHOW` and provide configurable fallback handling.
- [ ] A verification run captures frames from camera index 0 successfully without errors.

### Whisper GPU Acceleration & Latency
- [ ] PyTorch detects the RTX 5050 GPU and executes `openai-whisper` on `device="cuda"` without sm_120 incompatibility warnings or kernel crashes.
- [ ] A benchmark script executes Whisper transcription on GPU with a sample audio clip, verifying correct transcription and reporting the measured latency.
