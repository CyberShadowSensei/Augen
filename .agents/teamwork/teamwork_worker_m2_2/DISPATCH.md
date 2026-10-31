# Task Assignment: Milestone 2 Implementation Remediation Worker (Iteration 2)

## Instructions
Remediate the 4 concrete defects identified by Challenger 1 and Challenger 2 in `audio_provider.py`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## References
- `d:\contextAI-main\config.py`
- `d:\contextAI-main\audio_provider.py`
- `d:\contextAI-main\tests\test_audio_whisper.py`
- `d:\contextAI-main\tests\test_audio_adversarial.py`
- `d:\contextAI-main\tests\test_audio_concurrency.py`
- `d:\contextAI-main\.agents\teamwork\teamwork_challenger_m2_1\handoff.md`
- `d:\contextAI-main\.agents\teamwork\teamwork_challenger_m2_2\handoff.md`
- `d:\contextAI-main\PROJECT.md`
- `d:\contextAI-main\.agents\teamwork\ORIGINAL_REQUEST.md`

## Defects to Fix in `audio_provider.py`:

1. **Indexed CUDA Device Support (`cuda:0`, `cuda:1`, etc.)**:
   - Lines 70 & 101: use `target_device.startswith("cuda")` instead of exact equality `== "cuda"`.
   - Parse device ordinal if present (`dev_idx = int(target_device.split(":")[1]) if ":" in target_device else 0`) when querying `torch.cuda.get_device_capability(dev_idx)`.
   - Ensure `sm_120` compatibility check runs on indexed devices and falls back to CPU if architecture is missing from `torch.cuda.get_arch_list()`.

2. **Exception Safety & Deadlock Prevention in Transcription Queue**:
   - In `_run_transcription`, guard against non-buffer or `None` inputs (`if not isinstance(audio_bytes, (bytes, bytearray)): return`) before querying `len(audio_bytes)`.
   - In `_transcription_loop`, ensure `self.audio_queue.task_done()` is executed inside a `finally` block:
     ```python
     try:
         audio_bytes = self.audio_queue.get(timeout=1)
         try:
             self._run_transcription(audio_bytes, callback_function)
         finally:
             self.audio_queue.task_done()
     except queue.Empty:
         continue
     ```

3. **Thread Lifecycle and Zombie Leak Prevention in `stop_listening()`**:
   - In `stop_listening()`, check if *either* thread is running or was started. Do NOT return early if `_capture_thread` exited early (e.g. no microphone / headless CI).
   - Unconditionally set `self._stop_event.set()`.
   - Join `_capture_thread` if initialized (with timeout).
   - Join `self.audio_queue.join()`.
   - Join `_transcription_thread` if initialized (with timeout).

4. **Thread-Safe Whisper Transcription & KV Cache Protection**:
   - Add `self._transcription_lock = threading.Lock()` in `AudioListener.__init__`.
   - In `_run_transcription`, acquire `with self._transcription_lock:` around `self.whisper_model.transcribe(...)`.

## Verification Mandate
After applying fixes, run all test suites:
- `pytest tests/test_audio_whisper.py -v` (expect 12 passed)
- `pytest tests/test_audio_adversarial.py -v` (expect 25 passed, 0 failed)
- `pytest tests/test_audio_concurrency.py -v` (expect 9 passed, 0 failed)
- Full regression: `pytest tests/ -v` (expect 81 passed, 0 failed)

## Output
Write your handoff report to `d:\contextAI-main\.agents\teamwork\teamwork_worker_m2_2\handoff.md`.
Send a completion message back to orchestrator.
