# Task Assignment: Milestone 3 Benchmark & E2E Verification Worker

## Instructions
Implement `scripts/benchmark_whisper.py` and execute the end-to-end verification runs for both Camera Integration (R1) and Whisper Acceleration (R2).

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## References
- `d:\contextAI-main\config.py`
- `d:\contextAI-main\audio_provider.py`
- `d:\contextAI-main\visual_cortex.py`
- `d:\contextAI-main\test_cam.py`
- `d:\contextAI-main\PROJECT.md`
- `d:\contextAI-main\.agents\teamwork\ORIGINAL_REQUEST.md`

## Mandate

### Part 1: Implement `scripts/benchmark_whisper.py`
Create `scripts/benchmark_whisper.py` with:
- CLI argument support (`--model`, `--device`, `--audio`, `--duration`, `--runs`, `--json`).
- If no audio file is provided, generate a clean synthetic PCM speech-like chirp/sine wave or use a sample audio clip.
- Measures:
  1. **Device & Environment**: PyTorch version, CUDA availability, GPU device name, compute capability, active device.
  2. **Cold-start Latency**: Time for initial model load and first inference pass.
  3. **Warm Latency**: Average and standard deviation over N warm inference passes.
  4. **Real-Time Factor (RTF)**: `latency / audio_duration` (RTF < 1.0 indicates faster than real-time).
  5. **Memory Usage**: RAM RSS (via `psutil`) and CUDA VRAM (`torch.cuda.memory_allocated()` / `max_memory_allocated()` if CUDA is active).
  6. **Transcription Output**: Recorded text from Whisper.
- Prints a clean formatted markdown/terminal benchmark report and optionally writes JSON.

### Part 2: Execute Benchmark and Verification
1. Run `python scripts/benchmark_whisper.py --duration 3.0 --runs 5`.
2. Run camera verification: `python test_cam.py --headless` (verifies camera index 0 with DirectShow fallback).
3. Run full regression test suite: `pytest tests/ -v` (verify 81/81 pass).

## Output
Write your comprehensive handoff report to `d:\contextAI-main\.agents\teamwork\teamwork_worker_m3_1\handoff.md` detailing:
- Benchmark results (cold latency, warm latency, RTF, RAM/VRAM).
- Camera capture verification results (frame dimensions, backend, fallback behavior).
- Test suite summary.
Send a completion message back to orchestrator.


## 2026-10-31T14:33:59Z
You are Milestone 3 Worker (teamwork_worker_m3_1).
Your working directory is: d:\contextAI-main\.agents\teamwork\teamwork_worker_m3_1
Read your instructions in: d:\contextAI-main\.agents\teamwork\teamwork_worker_m3_1\DISPATCH.md
Read the authoritative user request in: d:\contextAI-main\.agents\teamwork\ORIGINAL_REQUEST.md
Read project context in: d:\contextAI-main\PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

USER URGENCY: The user explicitly requested "I need this ASAP".
Expedite your work:
1. Implement scripts/benchmark_whisper.py meeting all requirements in DISPATCH.md.
2. Execute the benchmark: python scripts/benchmark_whisper.py --duration 3.0 --runs 5.
3. Execute camera verification: python test_cam.py --headless.
4. Execute full regression test suite: pytest tests/ -v (verify 81/81 pass).
5. Write your comprehensive handoff report to d:\contextAI-main\.agents\teamwork\teamwork_worker_m3_1\handoff.md with all benchmark numbers and verification outputs.
Send a completion message when done.
