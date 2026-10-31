"""
scripts/stress_test_camera.py
Adversarial stress harness for VisualCortex camera subsystem (Milestone 1).
"""

import os
import sys
import time
import threading
import ctypes
import numpy as np
import cv2

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config
from visual_cortex import VisualCortex, resolve_camera_backend

def get_current_process_handle_count():
    """Returns the current Windows process handle count using Windows API."""
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        handle = kernel32.GetCurrentProcess()
        count = ctypes.c_ulong()
        if kernel32.GetProcessHandleCount(handle, ctypes.byref(count)):
            return count.value
        else:
            err = kernel32.GetLastError()
            print(f"[WARN] GetProcessHandleCount returned False, last error: {err}")
    except Exception as e:
        print(f"[WARN] Failed to get handle count: {e}")
    return None

def test_frame_properties():
    print("\n" + "="*60)
    print("TEST 1: Frame Properties Verification")
    print("="*60)
    vc = VisualCortex()
    frame, err = vc._capture_frame()
    if err is not None:
        print(f"FAILED: Frame capture returned error: {err}")
        return False, f"Capture error: {err}"

    if frame is None:
        print("FAILED: Frame is None")
        return False, "Frame is None"

    print(f"Frame type: {type(frame)}")
    print(f"Frame ndim: {frame.ndim}")
    print(f"Frame shape: {frame.shape}")
    print(f"Frame dtype: {frame.dtype}")
    print(f"Frame nbytes: {frame.nbytes}")

    nonzero_count = np.count_nonzero(frame)
    mean_val = float(np.mean(frame))
    std_val = float(np.std(frame))
    print(f"Non-zero elements: {nonzero_count} / {frame.size} ({nonzero_count/frame.size*100:.2f}%)")
    print(f"Mean pixel value: {mean_val:.2f}, Std dev: {std_val:.2f}")

    assert isinstance(frame, np.ndarray), "frame must be a numpy.ndarray"
    assert frame.ndim == 3, f"Expected 3 dimensions, got {frame.ndim}"
    assert frame.shape[2] == 3, f"Expected 3 channels, got {frame.shape[2]}"
    assert frame.dtype == np.uint8, f"Expected dtype uint8, got {frame.dtype}"
    assert nonzero_count > 0, "Frame must have non-zero byte content"
    assert frame.size > 0, "Frame size must be greater than 0"

    print("PASS: Frame properties meet all requirements.")
    return True, None

def test_warmup_delays():
    print("\n" + "="*60)
    print("TEST 2: Camera Warmup Timeout / Delay Bounds")
    print("="*60)
    vc = VisualCortex()

    # Test cases: 0.0, -1.0, 0.5, and malformed types like "invalid"
    delays_to_test = [0.0, -1.0, 0.5, "invalid", None]
    for delay in delays_to_test:
        print(f"\n--- Testing CAMERA_WARMUP_DELAY = {repr(delay)} ---")
        orig_delay = getattr(config, 'CAMERA_WARMUP_DELAY', 0.75)
        try:
            config.CAMERA_WARMUP_DELAY = delay
            t0 = time.time()
            frame, err = vc._capture_frame()
            elapsed = time.time() - t0
            print(f"Elapsed time: {elapsed:.3f}s")
            print(f"Frame is None: {frame is None}, Error: {err}")
            if isinstance(delay, (int, float)) and delay >= -1.0:
                assert frame is not None, f"Frame capture failed for delay={delay}: {err}"
                assert err is None, f"Unexpected error: {err}"
                assert frame.ndim == 3 and frame.shape[2] == 3
                print(f"PASS for numeric delay={delay}")
            else:
                # For invalid types (string, None), _capture_frame must NOT raise unhandled exception
                # and must return (None, error_msg)
                assert frame is None, "Frame should be None on invalid warmup type"
                assert err is not None, "Error message must be present on invalid warmup type"
                print(f"PASS for invalid delay={repr(delay)} (safely caught and returned error)")
        finally:
            config.CAMERA_WARMUP_DELAY = orig_delay

    print("\nPASS: Warmup delay bounds and edge cases handled cleanly.")
    return True, None

def test_handle_cleanup_and_leakage():
    print("\n" + "="*60)
    print("TEST 3: Handle Cleanup and Leakage in Windows DirectShow")
    print("="*60)
    vc = VisualCortex()

    initial_handles = get_current_process_handle_count()
    print(f"Initial process handle count: {initial_handles}")

    # Run 5 consecutive captures to see if handles steadily leak or stabilize
    for i in range(5):
        t0 = time.time()
        frame, err = vc._capture_frame()
        t1 = time.time()
        curr_handles = get_current_process_handle_count()
        print(f"Iteration {i+1}: capture={frame is not None}, elapsed={t1-t0:.3f}s, handles={curr_handles}")
        assert frame is not None, f"Capture failed at iteration {i+1}: {err}"

    # Now test candidate failure path: deliberately make primary fail and verify release
    print("\n--- Testing candidate failure path releases handles ---")
    orig_idx = config.CAMERA_INDEX
    orig_fb = config.CAMERA_FALLBACK_INDICES
    try:
        # Invalid primary (999), invalid fallback (998), auto detect False
        config.CAMERA_INDEX = 999
        config.CAMERA_FALLBACK_INDICES = [998]
        config.CAMERA_AUTO_DETECT = False

        handles_before_fail = get_current_process_handle_count()
        frame, err = vc._capture_frame()
        handles_after_fail = get_current_process_handle_count()
        print(f"Handles before fail run: {handles_before_fail}, after: {handles_after_fail}")
        print(f"Error returned as expected: {err}")
        assert frame is None, "Frame should be None on total failure"
        assert err is not None, "Error message should be present"
    finally:
        config.CAMERA_INDEX = orig_idx
        config.CAMERA_FALLBACK_INDICES = orig_fb
        config.CAMERA_AUTO_DETECT = True

    final_handles = get_current_process_handle_count()
    print(f"Final process handle count: {final_handles}")
    if initial_handles is not None and final_handles is not None:
        delta = final_handles - initial_handles
        print(f"Total handle delta across test: {delta}")
        # DirectShow / COM may allocate a fixed threadpool or COM runtime cache (~10-50 handles),
        # but should not grow uncontrollably.
        assert delta < 150, f"Handle growth too large: {delta}"

    print("PASS: Handle cleanup and leakage test passed.")
    return True, None

def test_multithreading_concurrency():
    print("\n" + "="*60)
    print("TEST 4: Multi-threading Concurrency on _capture_frame()")
    print("="*60)
    vc = VisualCortex()

    num_threads = 2
    results = [None] * num_threads
    errors = [None] * num_threads
    timings = [0.0] * num_threads
    barrier = threading.Barrier(num_threads)

    def worker(tid):
        try:
            # Wait for all threads to synchronize at start line
            barrier.wait()
            t0 = time.time()
            frame, err = vc._capture_frame()
            t1 = time.time()
            results[tid] = frame
            errors[tid] = err
            timings[tid] = t1 - t0
        except Exception as ex:
            errors[tid] = f"Exception: {ex}"

    print(f"Launching {num_threads} concurrent threads calling vc._capture_frame()...")
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)

    for i in range(num_threads):
        frame = results[i]
        err = errors[i]
        dur = timings[i]
        print(f"Thread {i}: Duration={dur:.2f}s, Success={frame is not None}, Error='{err}'")
        if frame is not None:
            print(f"  Frame shape: {frame.shape}, Mean: {np.mean(frame):.2f}")

    # Analyze outcomes:
    # Under DirectShow on Windows, a physical webcam or virtual driver (like AMD Privacy View)
    # usually grants exclusive access to the first caller.
    # What is the contract of _capture_frame()?
    # Interface Contract in PROJECT.md:
    # "Returns (frame, None) on success where frame.shape == (H, W, 3).
    #  Returns (None, error_msg) on failure; never raises unhandled exceptions."
    
    # We must verify:
    # 1. No thread raised an unhandled exception or crashed.
    # 2. At least one thread succeeded, OR both returned clean results ((frame, None) or (None, error_msg)).
    # 3. Frames returned (if any) are valid numpy arrays.
    for i in range(num_threads):
        assert errors[i] is None or isinstance(errors[i], str), f"Thread {i} returned invalid error type: {type(errors[i])}"
        if results[i] is not None:
            assert results[i].ndim == 3 and results[i].shape[2] == 3
        else:
            assert errors[i] is not None, f"Thread {i} had None frame and None error!"

    print("PASS: Concurrency test completed safely without unhandled exceptions or hangs.")
    return True, None

def main():
    print("Starting Milestone 1 Camera Subsystem Stress Test Harness...")
    all_passed = True
    tests = [
        ("Frame Properties", test_frame_properties),
        ("Warmup Delays", test_warmup_delays),
        ("Handle Cleanup & Leakage", test_handle_cleanup_and_leakage),
        ("Multi-threading Concurrency", test_multithreading_concurrency),
    ]

    summary = []
    for name, test_func in tests:
        try:
            passed, msg = test_func()
            summary.append((name, "PASS" if passed else f"FAIL ({msg})"))
            if not passed:
                all_passed = False
        except Exception as e:
            import traceback
            traceback.print_exc()
            summary.append((name, f"EXCEPTION ({e})"))
            all_passed = False

    print("\n" + "="*60)
    print("STRESS TEST SUMMARY")
    print("="*60)
    for name, res in summary:
        print(f"  {name:30}: {res}")
    print("="*60)

    if all_passed:
        print("\nALL STRESS TESTS PASSED! Verdict: APPROVE")
        sys.exit(0)
    else:
        print("\nSTRESS TESTS FAILED! Verdict: REQUEST_CHANGES")
        sys.exit(1)

if __name__ == "__main__":
    main()
