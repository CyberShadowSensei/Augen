## 2026-10-31T13:25:13Z
You are teamwork_worker_m1_1, an implementation worker.
Your working directory is: d:\contextAI-main\.agents\teamwork\teamwork_worker_m1_1

MANDATORY FIRST STEP: Read d:\contextAI-main\.agents\teamwork\ORIGINAL_REQUEST.md before doing any work.
Also read d:\contextAI-main\PROJECT.md and d:\contextAI-main\.agents\teamwork\teamwork_explorer_survey_1\survey_camera.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write Ownership:
You have exclusive write ownership of:
- `config.py` (camera section)
- `visual_cortex.py`
- `test_cam.py`
Do NOT modify `audio_provider.py` or unrelated files.

Task Description (Milestone 1: Camera Access on Index 0 with Configurable Fallback):
1. In `config.py`:
   - Set `CAMERA_INDEX = 0` (integer 0, primary default webcam).
   - Set `CAMERA_BACKEND = "cv2.CAP_DSHOW"` (DirectShow backend).
   - Add `CAMERA_FALLBACK_INDICES = [1]` (fallback to AMD Privacy View camera or external cam if index 0 is locked).
   - Add `CAMERA_FALLBACK_BACKENDS = ["cv2.CAP_ANY", "cv2.CAP_MSMF"]`.
   - Add `CAMERA_AUTO_DETECT = True`.
   - Ensure `CAMERA_WARMUP_DELAY = 0.75`.
   - Keep `CAP_BACKEND = CAMERA_BACKEND` for backward compatibility.
2. In `visual_cortex.py`:
   - Add `resolve_camera_backend(backend_spec)` function supporting string representations (`"cv2.CAP_DSHOW"`, `"CAP_DSHOW"`, `"DSHOW"`, `"CAP_ANY"`, `"CAP_MSMF"`, `"AUTO"`, etc.) as well as raw integer enums.
   - Implement `_open_camera(self)`:
     - Tries primary index (`0`) with primary backend (`cv2.CAP_DSHOW`).
     - Tries primary index with fallback backends.
     - Tries fallback indices (`[1]`) with primary and fallback backends.
     - If all fail and `CAMERA_AUTO_DETECT` is True, probes indices 0..3 with `CAP_DSHOW` and `CAP_ANY`.
     - Validates that `cap.isOpened()` AND test `cap.read()` succeeds before returning `(cap, active_idx, active_backend)`.
     - Releases invalid capture handles safely.
   - Update `_capture_frame(self)`:
     - Uses `_open_camera()`.
     - Performs camera warmup loop for `CAMERA_WARMUP_DELAY` seconds, flushing frames.
     - Reads and returns final valid frame `(frame, None)`.
     - Robust error handling returning `(None, error_message)` if all attempts fail, never raising unhandled exceptions.
     - Always releases capture handle in `finally`.
3. In `test_cam.py`:
   - Update to use `config.CAMERA_INDEX`, `config.CAMERA_BACKEND`, and fallback mechanisms.
   - Support a `--headless` argument (or non-interactive test mode) so verification can run without requiring an interactive Tkinter GUI window.
4. Run verification tests:
   - Run: `python -c "from visual_cortex import VisualCortex; vc = VisualCortex(); frame, err = vc._capture_frame(); print('Capture success:', frame is not None, 'Shape:', frame.shape if frame is not None else None, 'Error:', err); assert frame is not None, f'Frame capture failed: {err}'"`
   - Run `python test_cam.py --headless` (or your headless flag).
   - Verify that camera frames are successfully captured without errors.
5. Write your handoff report to `d:\contextAI-main\.agents\teamwork\teamwork_worker_m1_1\handoff.md` with:
   - What changed
   - Exact verification commands executed and raw outputs
   - Any caveats or edge cases handled
   - Confirmation that the milestone is complete
6. Send a completion message back to the orchestrator.
