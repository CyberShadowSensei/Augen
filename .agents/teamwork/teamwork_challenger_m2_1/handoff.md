# Milestone 2 Adversarial Stress-Testing Handoff Report

**Agent**: `teamwork_challenger_m2_1`  
**Role**: critic, specialist (Empirical Challenger)  
**Date**: 2026-10-31T14:11:00Z  
**Verdict**: **`REQUEST_CHANGES`**  

---

## 1. Observation

### 1.1 Test Suite Implementation and Execution
An empirical adversarial test suite was authored in `tests/test_audio_adversarial.py` containing 25 distinct stress test cases across:
- Extreme audio buffers (0-byte, 1-byte, 399ms, exact 400ms boundary, unaligned odd-length buffers, silence, DC offsets, Nyquist noise, >30s buffers)
- Boundary configurations (indexed devices `"cuda:0"`, invalid devices `"cuda:99"`, `"tpu"`, negative silence thresholds, invalid VAD aggressiveness)
- Concurrency and thread lifecycle (None queue entry deadlock, thread leak upon early capture loop termination, start/stop idempotency)
- Offline model cache probing (`small.pt` detection and missing cache handling)

**Execution Command**:
```powershell
pytest tests/test_audio_adversarial.py -v
```
**Verbatim Output Summary**:
```text
=========================== short test summary info ===========================
FAILED tests/test_audio_adversarial.py::TestExtremeAudioBuffers::test_none_audio_buffer_resilience
FAILED tests/test_audio_adversarial.py::TestInvalidAndBoundaryConfigurations::test_cuda_indexed_device_must_check_architecture
FAILED tests/test_audio_adversarial.py::TestThreadSafetyAndDeadlockResilience::test_queue_deadlock_on_none_entry
FAILED tests/test_audio_adversarial.py::TestThreadSafetyAndDeadlockResilience::test_thread_leak_when_capture_thread_exits_early
================== 4 failed, 21 passed, 2 warnings in 16.45s ==================
```

Full regression run across the entire workspace (`pytest tests/ -v`):
```text
============ 4 failed, 68 passed, 3 warnings in 110.40s (0:01:50) =============
```

---

### 1.2 Observed Failure 1: Unchecked CUDA Indexed Devices (`cuda:0`, `cuda:1`) Bypass Architecture Guard & Hang
In `audio_provider.py` (lines 69-70):
```python
69:         target_device = str(requested_device).strip().lower()
70:         if target_device == "cuda":
```
And line 101:
```python
101:            if target_device == "cuda" and self.fallback_to_cpu:
```

**Empirical Verification**:
Command:
```powershell
python -c "from audio_provider import AudioListener; al = AudioListener(device='cuda:0')"
```
**Observation**:
Because `target_device == "cuda:0"`, the condition `if target_device == "cuda":` evaluates to `False`. The architecture check (`sm_120` detection) was completely bypassed. Whisper attempted to initialize on `cuda:0` under `torch 2.7.1+cu118`.
During `_warmup_model()`, execution entered PyTorch CUDA kernel execution and **hung indefinitely** (task-66 hung for >30 seconds without progress, requiring manual process termination).

Test case `test_cuda_indexed_device_must_check_architecture` output:
```text
AssertionError: 'cuda:0' != 'cpu' : VULNERABILITY DETECTED: device='cuda:0' bypassed sm_120 arch check and stayed 'cuda:0'!
```

---

### 1.3 Observed Failure 2: Unhandled `TypeError` in `_run_transcription` Leads to `audio_queue.join()` Deadlock
In `audio_provider.py` (lines 244-248):
```python
242:    def _run_transcription(self, audio_bytes: bytearray, callback: Callable[[str], None]):
243:        """Processes the buffered audio and transcribes it."""
244:        # Discard speech buffers shorter than 400ms (16000 samples/sec * 0.4 sec * 2 bytes/sample)
245:        min_bytes = int(self.RATE * 0.4 * 2)
246:        if len(audio_bytes) < min_bytes:
247:            logging.debug(f"Discarding audio buffer shorter than 400ms ({len(audio_bytes)} bytes < {min_bytes} bytes).")
248:            return
```
And in `_transcription_loop` (lines 231-236):
```python
231:        while not self._stop_event.is_set() or not self.audio_queue.empty():
232:            try:
233:                audio_bytes = self.audio_queue.get(timeout=1)
234:                self._run_transcription(audio_bytes, callback_function)
235:                self.audio_queue.task_done()
```

**Empirical Verification**:
If `None` (or any non-sized object) is queued onto `audio_queue`:
1. `len(audio_bytes)` at line 246 raises `TypeError: object of type 'NoneType' has no len()` **before** the `try...except` block in `_run_transcription`.
2. In `_transcription_loop`, line 234 raises before line 235, skipping `self.audio_queue.task_done()`.
3. In `stop_listening()`, `self.audio_queue.join()` waits for `unfinished_tasks == 0`. Because `task_done()` was skipped, `self.audio_queue.join()` **deadlocks permanently**.

Test case `test_queue_deadlock_on_none_entry` output:
```text
AssertionError: 1 != 0 : DEADLOCK VULNERABILITY DETECTED: audio_queue task_done was skipped on None entry! unfinished_tasks=1
```

---

### 1.4 Observed Failure 3: Thread Leak in `stop_listening()` when `_capture_thread` Exits Early
In `audio_provider.py` (lines 296-298):
```python
292:    def stop_listening(self):
293:        """
294:        Stops the listening process and cleans up resources.
295:        """
296:        if not self._capture_thread or not self._capture_thread.is_alive():
297:            logging.warning("Not currently listening.")
298:            return
```
And in `_capture_loop` (lines 184-186):
```python
184:        except OSError as e:
185:            logging.error(f"Failed to open microphone stream. Is a microphone connected? Error: {e}")
186:            return
```

**Empirical Verification**:
If no microphone is available (e.g., in headless CI or VM environments) or PyAudio stream open fails:
1. `_capture_loop` logs an error and returns immediately, so `self._capture_thread.is_alive()` becomes `False`.
2. Meanwhile, `self._transcription_thread` was started and is running waiting on `audio_queue`.
3. The consumer/caller attempts to stop the listener by invoking `stop_listening()`.
4. `stop_listening()` checks `if not self._capture_thread.is_alive(): return` and exits immediately with `WARNING: Not currently listening.`
5. `self._stop_event.set()` is **never called**; `self._transcription_thread` is **never joined or stopped** and leaks as a background zombie thread. Subsequent calls to `start_listening()` spawn additional duplicate transcription threads.

Test case `test_thread_leak_when_capture_thread_exits_early` output:
```text
WARNING  root:audio_provider.py:297 Not currently listening.
AssertionError: True is not false : THREAD LEAK VULNERABILITY DETECTED: stop_listening() returned early without joining _transcription_thread!
```

---

## 2. Logic Chain

1. **Indexed Device Bypasses Compatibility Guard (§1.2)**:
   - Observation §1.2 proves that `audio_provider.py` lines 70 and 101 use exact string comparison `target_device == "cuda"`.
   - When a user or system configuration specifies `WHISPER_DEVICE = "cuda:0"` (the standard PyTorch device ordinal notation for GPU 0), `target_device` is `"cuda:0"`.
   - Because `"cuda:0" != "cuda"`, the check `arch_list and cap_tag not in arch_list` does not run.
   - Consequently, Whisper initializes CUDA kernels for `sm_120` on cu118 PyTorch, which locks up the Python process in an unrecoverable driver kernel hang.
   - Furthermore, line 101 checks `if target_device == "cuda" and self.fallback_to_cpu:`, which also fails for `"cuda:0"`, disabling the CPU fallback mechanism.

2. **Uncaught Queue Exceptions Skip `task_done()` Causing Permanent Join Deadlock (§1.3)**:
   - Observation §1.3 shows that line 246 executes `if len(audio_bytes) < min_bytes:` before entering the function's internal `try...except` block.
   - Any non-sequence or `None` passed into `_run_transcription` raises `TypeError`.
   - In `_transcription_loop`, `self.audio_queue.task_done()` is located after `self._run_transcription(...)` without a `finally:` block.
   - An exception escaping `_run_transcription` skips `task_done()`, permanently desynchronizing `queue.unfinished_tasks` from 0.
   - Any subsequent call to `stop_listening()` (which executes `self.audio_queue.join()`) blocks the calling thread forever.

3. **Incomplete Liveness Guard Leaves Orphan Transcription Threads (§1.4)**:
   - Observation §1.4 shows that `stop_listening()` predicates shutdown solely on `self._capture_thread.is_alive()`.
   - The audio architecture is a dual-thread producer-consumer system (`_capture_thread` and `_transcription_thread`).
   - If the capture thread terminates early (which is guaranteed to occur in any environment without a physical microphone), `self._capture_thread.is_alive()` is `False`, but `self._transcription_thread.is_alive()` is `True`.
   - Bailing out at line 298 prevents `_stop_event.set()` from being signalled and prevents `_transcription_thread.join()` from executing, leaking threads and preventing clean resource disposal.

---

## 3. Caveats

1. **Unsandboxed cu128 PyTorch Installation**:
   - Because external wheel downloads are denied by the sandbox security policy, testing was performed on host PyTorch cu118. All architecture checks and CPU fallback paths are verified against actual sm_120 hardware in this environment.
2. **Audio Hardware**:
   - Physical microphone capture was tested with mock streams and offline arrays since physical audio capture is not present in headless automated environments.

---

## 4. Conclusion

The adversarial review discovered **3 high/critical severity defects** in `audio_provider.py`. The verdict is **`REQUEST_CHANGES`**.

### Required Action Items for Milestone 2 Worker:

1. **Fix Device Resolution for Indexed CUDA Ordinals (`cuda:0`, `cuda:1`, etc.)**:
   - In `audio_provider.py` line 70, change:
     ```python
     if target_device.startswith("cuda"):
     ```
   - In line 101, change:
     ```python
     if target_device.startswith("cuda") and self.fallback_to_cpu:
     ```
   - When checking capability for an indexed device (e.g. `cuda:0`), resolve device index dynamically:
     ```python
     dev_idx = 0
     if ":" in target_device:
         try:
             dev_idx = int(target_device.split(":")[1])
         except ValueError:
             dev_idx = 0
     cap = torch.cuda.get_device_capability(dev_idx)
     ```

2. **Fix `_run_transcription` and `_transcription_loop` Queue Exception Safety**:
   - In `audio_provider.py` line 244, guard against `None` and non-bytes before `len()`:
     ```python
     if not isinstance(audio_bytes, (bytes, bytearray)):
         logging.warning("Received invalid audio buffer type; discarding.")
         return
     ```
   - In `_transcription_loop`, ensure `task_done()` is executed in a `finally` block:
     ```python
     try:
         audio_bytes = self.audio_queue.get(timeout=1)
         try:
             self._run_transcription(audio_bytes, callback_function)
         finally:
             self.audio_queue.task_done()
     except queue.Empty:
         continue
     except Exception as e:
         logging.error(f"An unexpected error occurred in the transcription loop: {e}")
     ```

3. **Fix `stop_listening()` Thread Lifecycle & Leakage**:
   - In `audio_provider.py` line 296, check if *either* thread was started or is alive, or unconditionally signal `_stop_event`:
     ```python
     is_running = (self._capture_thread and self._capture_thread.is_alive()) or \
                  (self._transcription_thread and self._transcription_thread.is_alive())
     if not is_running and not self._capture_thread:
         logging.warning("Not currently listening.")
         return

     logging.info("Stopping audio listener...")
     self._stop_event.set()

     if self._capture_thread:
         self._capture_thread.join(timeout=3)
         if self._capture_thread.is_alive():
             logging.error("Audio capture thread did not terminate gracefully.")

     # Wait for the transcription queue to be fully processed
     self.audio_queue.join()

     if self._transcription_thread:
         self._transcription_thread.join(timeout=3)
         if self._transcription_thread.is_alive():
             logging.error("Transcription thread did not terminate gracefully.")
     ```

---

## 5. Verification Method

To independently verify these findings:

1. **Run the Adversarial Test Suite**:
   ```powershell
   pytest tests/test_audio_adversarial.py -v
   ```
   *Expected outcome*: 4 failures identifying the 3 issues detailed above.

2. **Empirical Process Hang Reproducer (`cuda:0`)**:
   ```powershell
   python -c "from audio_provider import AudioListener; AudioListener(device='cuda:0')"
   ```
   *Expected outcome*: Hangs indefinitely during warmup without CPU fallback.

3. **Empirical Queue Deadlock Reproducer**:
   ```powershell
   python -c "from audio_provider import AudioListener; al = AudioListener(); al.audio_queue.put(None); al._run_transcription(al.audio_queue.get(), lambda t: None)"
   ```
   *Expected outcome*: Raises `TypeError: object of type 'NoneType' has no len()`.

4. **Invalidation Condition**:
   Once the worker applies the 3 recommended fixes, re-running `pytest tests/test_audio_adversarial.py -v` must result in **25 passed, 0 failed**.
