# Milestone 2 Empirical Challenge Report: AudioListener Concurrency, Thread Safety, Memory & Latency

**Agent**: `teamwork_challenger_m2_2`  
**Role**: critic / specialist (Empirical Challenger)  
**Date**: 2026-10-31T14:14:00Z  
**Verdict**: **`REQUEST_CHANGES`**

---

## 1. Observation

### 1.1 Concurrency Failure: Whisper KV Cache Corruption under Concurrent `_run_transcription`
- **Location**: `d:\contextAI-main\audio_provider.py:252-271` (`_run_transcription`)
- **Observed Behavior**:
  When multiple threads invoke `AudioListener._run_transcription()` concurrently with valid PCM speech buffers, the absence of an instance-level synchronization lock around `self.whisper_model.transcribe()` causes PyTorch/Whisper internal decoding state and KV cache corruption.
- **Verbatim Error & Stack Trace**:
  ```text
  ERROR root:audio_provider.py:270 Transcription failed: Linear(in_features=768, out_features=768, bias=True)
  Traceback (most recent call last):
    File "D:\contextAI-main\audio_provider.py", line 256, in _run_transcription
      result = self.whisper_model.transcribe(
    File "C:\Users\devan\AppData\Local\Programs\Python\Python310\lib\site-packages\whisper\transcribe.py", line 295, in transcribe
      result: DecodingResult = decode_with_fallback(mel_segment)
    ...
    File "C:\Users\devan\AppData\Local\Programs\Python\Python310\lib\site-packages\whisper\model.py", line 109, in forward
      v = kv_cache[self.value]
  KeyError: Linear(in_features=768, out_features=768, bias=True)
  ```
  And second failure mode:
  ```text
  ERROR root:audio_provider.py:270 Transcription failed: cannot reshape tensor of 0 elements into shape [1, 0, 12, -1] because the unspecified dimension size -1 can be any value and is ambiguous
  Traceback (most recent call last):
    ...
    File "C:\Users\devan\AppData\Local\Programs\Python\Python310\lib\site-packages\whisper\model.py", line 119, in qkv_attention
      q = q.view(*q.shape[:2], self.n_head, -1).permute(0, 2, 1, 3)
  RuntimeError: cannot reshape tensor of 0 elements into shape [1, 0, 12, -1] because the unspecified dimension size -1 can be any value and is ambiguous
  ```
- **Empirical Test Result**:
  In `tests/test_audio_concurrency.py::TestAudioConcurrencyAndThreadSafety::test_concurrent_transcription_kv_cache_race`:
  ```text
  [STRESS] Concurrent _run_transcription: 4 threads launched, 1 succeeded, 3 dropped/failed.
  AssertionError: 1 != 4 : Thread-safety violation in _run_transcription: only 1 of 4 succeeded (3 dropped).
  ```

---

### 1.2 Lifecycle Failure: Thread Leak on Stream/Microphone Termination
- **Location**: `d:\contextAI-main\audio_provider.py:296-302` (`stop_listening`)
- **Code snippet**:
  ```python
  296:         if not self._capture_thread or not self._capture_thread.is_alive():
  297:             logging.warning("Not currently listening.")
  298:             return
  299: 
  300:         logging.info("Stopping audio listener...")
  301:         self._stop_event.set()
  ```
- **Observed Behavior**:
  When `_capture_loop` terminates early (e.g., when no physical microphone is available, when `pyaudio.PyAudio.open()` raises `OSError`, or when the audio input device disconnects), `self._capture_thread.is_alive()` becomes `False`.
  However, `self._transcription_thread` was started during `start_listening()` and remains running, waiting on `self.audio_queue.get(timeout=1)` indefinitely.
  When the application calls `stop_listening()`, line 296 evaluates `not self._capture_thread.is_alive()` as `True`, logs `Not currently listening.`, and returns **without** setting `self._stop_event` or joining `self._transcription_thread`.
- **Empirical Test Result**:
  In `tests/test_audio_concurrency.py::TestAudioConcurrencyAndThreadSafety::test_thread_leak_when_capture_loop_exits_early`:
  ```text
  WARNING root:audio_provider.py:297 Not currently listening.
  AssertionError: True is not false : DEFECT: stop_listening() failed to terminate _transcription_thread when _capture_thread had already exited!
  ```
  Cycling `start_listening()` and `stop_listening()` 5 times with a failing capture stream leaked 4 orphaned background threads:
  ```text
  Number of leaked background threads: 4
   - Leaked thread: Thread-4 (_transcription_loop) alive: True
   - Leaked thread: Thread-6 (_transcription_loop) alive: True
   - Leaked thread: Thread-8 (_transcription_loop) alive: True
   - Leaked thread: Thread-10 (_transcription_loop) alive: True
  ```

---

### 1.3 Resource & Memory Stability: 50+ Synthetic Passes Verified
- **Location**: `tests/test_audio_concurrency.py::TestResourceAndMemoryStability::test_50_synthetic_passes_resource_and_handle_stability`
- **Observed Metrics**:
  - Baseline handles: 801
  - Pass 25 handles: 801 (delta = 0)
  - Pass 50 handles: 800 (delta = -1)
  - Final handle delta: **-1 handle** (zero handle leak)
  - Baseline RSS memory: 1781.90 MB
  - Pass 25 RSS: 1785.84 MB (delta = +3.95 MB)
  - Pass 50 RSS: 1787.88 MB (delta = +5.98 MB)
  - Final RSS delta: **+5.98 MB** (bounded, stable cache allocation)
- **Status**: **PASS** (Zero handle leak, stable RAM footprint).

---

### 1.4 Queue Saturation & Edge Case Ingestion
- **Location**: `tests/test_audio_concurrency.py::TestAudioQueueFloodingAndRobustness`
- **Observed Metrics**:
  - 20-30 buffers flooded into `audio_queue`.
  - Queue drained completely to size 0 without deadlocking or dropping valid items.
  - Feeding odd-length buffers (`len=16001`) and noise buffers (`0xFF`) was handled gracefully inside `try...except` without crashing consumer thread.
- **Status**: **PASS** (Queue draining and error containment verified).

---

### 1.5 Latency & Startup Warmup Verification
- **Location**: `tests/test_audio_concurrency.py::TestWhisperLatencyAndWarmup`
- **Observed Metrics**:
  - Cold model load time (`whisper.load_model('small', device='cpu')`): **2.975s**
  - First inference latency without prior warmup (cold start): **1.674s**
  - Warm inference latency (1.0s audio): **1.116s - 1.213s**
  - Inference latency by duration (on CPU, `small` model):
    - 0.5s audio: latency = 1.094s, RTF = **2.19** (slower than real-time on CPU)
    - 1.0s audio: latency = 1.116s, RTF = **1.12**
    - 2.0s audio: latency = 1.123s, RTF = **0.56** (faster than real-time)
  - Model startup warmup eliminates lazy execution penalty on subsequent passes.

---

## 2. Logic Chain

1. **Unsynchronized Inference Corrupts Shared Model State**:
   - `whisper.model.Whisper` is a stateful PyTorch module containing mutable Key-Value caches (`kv_cache`) in attention blocks (`cross_attn`, `attn`) during greedy decoding.
   - Observation §1.1 proves that concurrent invocations of `_run_transcription` mutate the same `self.whisper_model` instance simultaneously, producing `KeyError: Linear(...)` and `RuntimeError: cannot reshape tensor of 0 elements`.
   - In a production environment where audio chunks arrive concurrently or multiple components access transcription, this causes dropped voice commands.

2. **Early Capture Exit Bypasses Transcription Thread Shutdown**:
   - In `AudioListener.start_listening()`, two threads are started: `_capture_thread` and `_transcription_thread`.
   - Observation §1.2 proves that if `_capture_thread` terminates (due to microphone disconnect, OS permission error, or stream open failure), `self._capture_thread.is_alive()` returns `False`.
   - `stop_listening()` immediately returns on line 298 without signaling `_stop_event` or joining `_transcription_thread`.
   - The orphaned `_transcription_thread` loops indefinitely on `audio_queue.get(timeout=1)`.
   - Subsequent `start_listening()` calls spawn additional transcription threads, leaking OS threads and competing for queue items, which in turn triggers Observation §1.1.

3. **System Integrity Depends on Thread and Concurrency Safeguards**:
   - While sequential processing and queue flooding are stable (§1.3, §1.4), the lifecycle and thread safety defects (§1.1, §1.2) prevent reliable long-running operation in headless, intermittent-mic, or multi-threaded scenarios.

---

## 3. Caveats

1. **GPU sm_120 Execution**:
   - PyTorch cu128 wheels could not be fetched due to sandbox network restrictions; all benchmarks were executed on CPU using the local cached `small` model.
   - On CUDA with Tensor Cores, inference latency will be significantly lower (~50-150ms vs ~1100ms), but the underlying thread-safety and KV cache race conditions in PyTorch/Whisper remain identical.
2. **Review-Only Constraint**:
   - Per role constraints, `audio_provider.py` was not modified by the Challenger. Fixes must be applied by the implementer.

---

## 4. Conclusion & Required Changes

**Verdict**: **`REQUEST_CHANGES`**

The following fixes must be implemented in `audio_provider.py`:

### Required Fix 1: Add Synchronization Lock to `_run_transcription`
In `audio_provider.py`:
1. In `AudioListener.__init__`:
   ```python
   self._transcription_lock = threading.Lock()
   ```
2. In `AudioListener._run_transcription`:
   Acquire `with self._transcription_lock:` around `self.whisper_model.transcribe(...)`.

### Required Fix 2: Clean Shutdown in `stop_listening()`
In `audio_provider.py:stop_listening`:
Replace:
```python
if not self._capture_thread or not self._capture_thread.is_alive():
    logging.warning("Not currently listening.")
    return
```
With a check that inspects **both** threads:
```python
is_capturing = bool(self._capture_thread and self._capture_thread.is_alive())
is_transcribing = bool(self._transcription_thread and self._transcription_thread.is_alive())

if not is_capturing and not is_transcribing:
    logging.warning("Not currently listening.")
    return

logging.info("Stopping audio listener...")
self._stop_event.set()

if self._capture_thread:
    self._capture_thread.join(timeout=3)
    if self._capture_thread.is_alive():
        logging.error("Audio capture thread did not terminate gracefully.")

# Wait for queue to be fully processed
self.audio_queue.join()

if self._transcription_thread:
    self._transcription_thread.join(timeout=3)
    if self._transcription_thread.is_alive():
        logging.error("Transcription thread did not terminate gracefully.")

logging.info("Audio listener stopped.")
```

---

## 5. Verification Method

To independently reproduce and verify these findings:

1. **Run the Stress Test Suite**:
   ```powershell
   pytest tests/test_audio_concurrency.py -v
   ```
   *Expected outcome*: 7 passed, 2 failed exposing the KV cache race and thread leak.

2. **Verify Memory and Handle Stability (50 Passes)**:
   ```powershell
   pytest tests/test_audio_concurrency.py -v -k "test_50_synthetic_passes"
   ```
   *Expected outcome*: PASSED with handle delta <= 5 and RSS growth < 100MB.

3. **Verify Queue Saturation & Malformed Buffer Containment**:
   ```powershell
   pytest tests/test_audio_concurrency.py -v -k "test_queue_saturation or test_malformed"
   ```
   *Expected outcome*: PASSED.
