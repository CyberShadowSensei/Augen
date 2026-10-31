# Generation 2 Orchestrator Dispatch

## Context & State Recovery
You are the Generation 2 Project Orchestrator, replacing Generation 1 (`teamwork_orchestrator_1`).
- Working directory: `d:\contextAI-main\.agents\teamwork\teamwork_orchestrator_gen2`
- Predecessor handoff: `d:\contextAI-main\.agents\teamwork\teamwork_orchestrator_1\handoff.md`
- Predecessor briefing: `d:\contextAI-main\.agents\teamwork\teamwork_orchestrator_1\BRIEFING.md`
- Predecessor progress: `d:\contextAI-main\.agents\teamwork\teamwork_orchestrator_1\progress.md`
- Scope & Contracts: `d:\contextAI-main\PROJECT.md`
- Authoritative Request: `d:\contextAI-main\.agents\teamwork\ORIGINAL_REQUEST.md`

## Parent Agent
- Parent Conversation ID: `9043545f-062a-4b89-9be3-390870fd6c4c`
- Use this ID for all escalation, status reporting, and final delivery via `send_message`.

## Current Status & Next Steps (Urgent User Request)
1. **Milestones 1 & 2 are DONE**:
   - M1: Camera index 0 with DirectShow fallback passed all reviews, stress tests, and audit.
   - M2: PyTorch sm_120 architecture compatibility, dynamic CPU fallback, offline caching, and concurrency hardening passed all 81 tests (`pytest tests/ -v`).
2. **Execute Milestone 3 Immediately**:
   - Parent priority message: *"USER URGENCY: The user explicitly requested: 'I need this ASAP'. Please expedite remaining verification and benchmark generation immediately, complete the final audit, and deliver the final report as soon as possible."*
   - Dispatch Worker to implement `scripts/benchmark_whisper.py` measuring:
     - Audio duration, transcription latency (cold-start vs warm steady-state), Real-Time Factor (RTF), memory/VRAM, and transcription accuracy.
     - Execute the benchmark script on GPU/CPU and record measured latency.
     - Execute camera verification (`python test_cam.py --headless`).
   - Dispatch Forensic Auditor for final end-to-end audit (R1 + R2).
   - Deliver comprehensive final human-facing report to Parent (`9043545f-062a-4b89-9be3-390870fd6c4c`) using `send_message`.
