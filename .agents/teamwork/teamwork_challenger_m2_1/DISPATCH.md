# Task Assignment: Milestone 2 Challenger 1

## Instructions
Empirically stress-test the Whisper audio pipeline and `audio_provider.py` implementation against extreme, invalid, and boundary inputs.

## References
- `d:\contextAI-main\config.py`
- `d:\contextAI-main\audio_provider.py`
- `d:\contextAI-main\PROJECT.md`
- `d:\contextAI-main\.agents\teamwork\ORIGINAL_REQUEST.md`

## Testing Mandate
Write a standalone stress test script (e.g. `tests/test_audio_adversarial.py` or a dedicated test harness) that aggressively exercises:
1. **Extreme Audio Inputs**: 0-byte audio, tiny audio (<400ms), huge audio chunks (>30s), all-silence buffers (`\x00` bytes), max amplitude noise, DC offset, alternating signals.
2. **Invalid & Malformed Parameters**: Invalid device strings (`"cuda:99"`, `"tpu"`, `""`), invalid model names, invalid temperature, negative silence thresholds.
3. **Transcription Resilience**: Verify `_run_transcription` never raises unhandled exceptions that could kill the worker thread or main loop, even when passed malformed audio or corrupted arrays.
4. **Offline Cache Probing**: Verify behavior when non-cached models are requested vs cached models (`small.pt`).

Run the test suite and verify all test results.

## Output
Write your handoff report to `d:\contextAI-main\.agents\teamwork\teamwork_challenger_m2_1\handoff.md` with an explicit verdict: `APPROVE` or `REQUEST_CHANGES`. Send a concise completion message back to orchestrator.

## 2026-10-31T14:00:59Z
You are Milestone 2 Challenger 1 (teamwork_challenger_m2_1).
Your working directory is: d:\contextAI-main\.agents\teamwork\teamwork_challenger_m2_1
Read your instructions in: d:\contextAI-main\.agents\teamwork\teamwork_challenger_m2_1\DISPATCH.md
Read the authoritative user request in: d:\contextAI-main\.agents\teamwork\ORIGINAL_REQUEST.md
Read project context in: d:\contextAI-main\PROJECT.md
Read worker handoff in: d:\contextAI-main\.agents\teamwork\teamwork_worker_m2_1\handoff.md

Conduct aggressive empirical adversarial stress-testing against AudioListener and the Whisper pipeline. Test extreme audio buffers (0-byte, <400ms, >30s, silence, DC offset, max noise), invalid configurations, exception guards, and offline cache probing.
Write and run your stress test script (e.g. tests/test_audio_adversarial.py).
Write your handoff report to d:\contextAI-main\.agents\teamwork\teamwork_challenger_m2_1\handoff.md with an explicit verdict: APPROVE or REQUEST_CHANGES.
Send a concise completion message to parent when done.
