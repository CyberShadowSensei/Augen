## 2026-10-31T13:41:14Z
You are teamwork_worker_m2_1, an implementation worker.
Your working directory is: d:\contextAI-main\.agents\teamwork\teamwork_worker_m2_1

MANDATORY FIRST STEP: Read d:\contextAI-main\.agents\teamwork\ORIGINAL_REQUEST.md before doing any work.
Also read:
- d:\contextAI-main\PROJECT.md
- d:\contextAI-main\.agents\teamwork\teamwork_explorer_survey_2\survey_whisper.md
- d:\contextAI-main\.agents\teamwork\teamwork_explorer_survey_3\survey_pytorch_cuda.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write Ownership:
You have exclusive write ownership of:
- Python environment package upgrades (`torch`, `torchvision`, `torchaudio`)
- `config.py` (Audio and Whisper settings section ONLY — DO NOT touch Visual Cortex settings)
- `audio_provider.py`
Do NOT modify `visual_cortex.py` or unrelated files.

Task Description (Milestone 2: PyTorch sm_120 Upgrade & Whisper Acceleration):
1. Upgrade PyTorch environment for RTX 5050 Laptop GPU (sm_120 Blackwell architecture):
   - The current `torch 2.7.1+cu118` produces `FATAL: kernel fmha_cutlassF_f16_aligned_64x64_rf_sm80 is for sm80-sm100, but was built for sm37` and hangs on sm_120.
   - Upgrade PyTorch, torchvision, and torchaudio to a CUDA 12.8 (`cu128`) build:
     `python -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128`
     (or `--index-url https://download.pytorch.org/whl/nightly/cu128`).
     Note on execution: If pip requires network access, run with BypassSandbox=true if needed or standard run_command.
   - Verify upgrade:
     `python -c "import torch; print('Torch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0)); print('Capability:', torch.cuda.get_device_capability(0))"`
2. Update `config.py`:
   - Append Whisper configuration settings:
     ```python
     # --- Audio & Whisper STT Settings ---
     WHISPER_MODEL = "base.en"       # "base.en" for lowest latency, "small.en" for highest accuracy
     WHISPER_DEVICE = "cuda"         # "cuda" or "cpu"
     WHISPER_FALLBACK_TO_CPU = True  # Automatically fallback to CPU if CUDA fails
     WHISPER_TEMPERATURE = 0.0       # Greedy single-pass decoding (eliminates hallucination loops)
     SILENCE_THRESHOLD_MS = 500      # Milliseconds of silence to trigger end-of-utterance
     VAD_AGGRESSIVENESS = 3          # 0 (least aggressive) to 3 (most aggressive)
     ```
3. Update `audio_provider.py`:
   - Import `config`.
   - In `__init__`:
     - Load settings from `config` with sensible defaults.
     - Retain the `.en` model suffix! DO NOT strip `.en` (`replace(".en", "")`). Retain `base.en` / `small.en` so Whisper loads the fast, lightweight English model instead of heavy multilingual models.
     - Dynamic device resolution: check `torch.cuda.is_available()`. If device is `"cuda"` and CUDA is unavailable, log warning and set device to `"cpu"`.
     - Device fallback: try loading `whisper.load_model(self.model_size, device=target_device)`. If CUDA loading fails and `fallback_to_cpu` is True, fall back to `"cpu"`.
     - Implement `_warmup_model(self)`: perform a 1-second dummy inference pass during initialization (`np.zeros(self.RATE, dtype=np.float32)`) so first user utterance does not suffer a 2-4s cold-start delay.
   - In `_run_transcription`:
     - Discard speech buffers shorter than 400ms (`len(audio_bytes) < int(self.RATE * 0.4 * 2)`).
     - Call `self.whisper_model.transcribe(audio_np, language="en", fp16=(self.device == "cuda"), temperature=self.temperature, condition_on_previous_text=False, without_timestamps=True)`.
     - Catch and log errors without crashing the consumer thread.
4. Run verification tests:
   - Run Python test verifying that `AudioListener` initializes on `cuda` and successfully transcribes a sample audio buffer without `sm_120` warnings, kernel crashes, or hangs.
   - Test CPU fallback path (`AudioListener(device="cpu")`).
5. Write your handoff report to `d:\contextAI-main\.agents\teamwork\teamwork_worker_m2_1\handoff.md` with:
   - What changed
   - Exact verification commands executed and raw outputs
   - Confirmation of sm_120 CUDA execution and latency observations
6. Send a completion message back to the orchestrator.
