"""
scripts/benchmark_whisper.py

Standalone benchmark and verification utility for Whisper STT GPU acceleration.
Measures:
  1. PyTorch & CUDA environment (GPU model, compute capability, sm_120 support).
  2. Cold-start latency (model loading time + first inference execution).
  3. Warm inference latency (mean, std, min, max over N runs).
  4. Real-Time Factor (RTF = latency / audio_duration) and speedup multiplier.
  5. System RAM RSS (via psutil) and CUDA VRAM consumption (allocated & peak).
  6. Transcription output fidelity.

Outputs a clean markdown / terminal report and optionally exports a structured JSON report.
"""

import argparse
import json
import logging
import os
import platform
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psutil
import torch
import whisper

# Ensure PMC project root is accessible
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import config
except ImportError:
    config = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def generate_synthetic_audio(duration: float = 3.0, sample_rate: int = 16000) -> np.ndarray:
    """
    Generates synthetic speech-like multi-tone harmonic PCM audio.
    Synthesizes fundamental frequency (f0=160Hz) and speech formants (f1=800Hz, f2=1200Hz, f3=2500Hz)
    with a syllabic modulation envelope (3.5 syllables/sec) to thoroughly exercise the
    Whisper acoustic encoder and autoregressive decoder without clipping.
    """
    total_samples = max(int(duration * sample_rate), int(0.4 * sample_rate))
    t = np.linspace(0, duration, total_samples, endpoint=False, dtype=np.float32)

    # Fundamental pitch and formant frequencies
    f0 = 160.0   # Vocal tract fundamental
    f1 = 800.0   # First formant (vowel resonance)
    f2 = 1200.0  # Second formant
    f3 = 2500.0  # High formant

    signal = (
        0.35 * np.sin(2.0 * np.pi * f0 * t) +
        0.25 * np.sin(2.0 * np.pi * f1 * t) +
        0.20 * np.sin(2.0 * np.pi * f2 * t) +
        0.10 * np.sin(2.0 * np.pi * f3 * t)
    )

    # 3.5 Hz syllabic amplitude modulation
    syllable_rate = 3.5
    envelope = 0.5 * (1.0 + np.sin(2.0 * np.pi * syllable_rate * t - (np.pi / 2.0)))

    # Window ramp at start and finish to prevent sudden DC step clicks
    ramp_samples = min(int(0.05 * sample_rate), total_samples // 4)
    if ramp_samples > 0:
        ramp_in = np.linspace(0.0, 1.0, ramp_samples, dtype=np.float32)
        ramp_out = np.linspace(1.0, 0.0, ramp_samples, dtype=np.float32)
        envelope[:ramp_samples] *= ramp_in
        envelope[-ramp_samples:] *= ramp_out

    modulated = (signal * envelope).astype(np.float32)
    peak = np.max(np.abs(modulated))
    if peak > 1e-6:
        modulated = (modulated / peak) * 0.75  # Normalize to -2.5 dBFS

    return modulated


def load_or_generate_audio(audio_path: Optional[str], duration: float) -> Tuple[np.ndarray, float, str]:
    """
    Loads an audio file via Whisper's audio loader, or generates synthetic speech-like PCM audio.
    Returns: (audio_np, duration_seconds, description_string)
    """
    if audio_path and os.path.isfile(audio_path):
        audio = whisper.load_audio(audio_path)
        actual_duration = float(len(audio)) / 16000.0
        return audio, actual_duration, f"File: {os.path.basename(audio_path)} ({actual_duration:.2f}s)"
    
    audio = generate_synthetic_audio(duration=duration, sample_rate=16000)
    return audio, duration, f"Synthetic Harmonic Speech-Like PCM ({duration:.2f}s)"


def get_environment_info(target_device: str) -> Dict[str, Any]:
    """Inspects and returns the PyTorch, CUDA, and hardware execution environment."""
    cuda_avail = torch.cuda.is_available()
    cuda_version = getattr(torch.version, "cuda", None)
    gpu_name = None
    gpu_capability = None
    arch_list = []

    if cuda_avail:
        try:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_capability = list(torch.cuda.get_device_capability(0))
            if hasattr(torch.cuda, "get_arch_list"):
                arch_list = torch.cuda.get_arch_list()
        except Exception as e:
            gpu_name = f"Error querying CUDA device: {e}"

    proc = psutil.Process()
    ram_rss_mb = proc.memory_info().rss / (1024.0 * 1024.0)

    return {
        "platform": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "pytorch_version": torch.__version__,
        "cuda_available": cuda_avail,
        "cuda_version": cuda_version,
        "gpu_name": gpu_name,
        "compute_capability": gpu_capability,
        "supported_architectures": arch_list,
        "active_device": target_device,
        "initial_ram_rss_mb": round(ram_rss_mb, 2)
    }


def resolve_device(requested_device: Optional[str]) -> str:
    """Resolves the active compute device with architecture check and CPU fallback."""
    if not requested_device:
        if config and hasattr(config, "WHISPER_DEVICE"):
            requested_device = config.WHISPER_DEVICE
        else:
            requested_device = "cuda" if torch.cuda.is_available() else "cpu"

    dev_str = str(requested_device).strip().lower()
    if dev_str.startswith("cuda"):
        if not torch.cuda.is_available():
            logging.warning("CUDA requested but torch.cuda.is_available() is False. Falling back to CPU.")
            return "cpu"
        
        # sm_120 architecture check
        try:
            dev_idx = 0
            if ":" in dev_str:
                dev_idx = int(dev_str.split(":")[1])
            cap = torch.cuda.get_device_capability(dev_idx)
            arch_list = torch.cuda.get_arch_list() if hasattr(torch.cuda, "get_arch_list") else []
            cap_tag = f"sm_{cap[0]}{cap[1]}"
            comp_tag = f"compute_{cap[0]}{cap[1]}"
            major_tag = f"sm_{cap[0]}0"
            if arch_list and cap_tag not in arch_list and comp_tag not in arch_list and major_tag not in arch_list:
                logging.warning(
                    f"CUDA device capability {cap} ({cap_tag}) not in PyTorch arch list {arch_list}. "
                    f"Falling back to CPU."
                )
                return "cpu"
        except Exception as ex:
            logging.debug(f"Device capability verification warning: {ex}")

    return dev_str


def find_cached_whisper_model() -> Optional[str]:
    """Finds locally cached whisper models in ~/.cache/whisper if offline."""
    cache_dir = os.path.expanduser("~/.cache/whisper")
    if os.path.isdir(cache_dir):
        for filename in os.listdir(cache_dir):
            if filename.endswith(".pt"):
                return filename[:-3]  # e.g., 'small' from 'small.pt'
    return None


def load_whisper_model(model_name: str, device: str) -> Tuple[Any, str, float]:
    """
    Loads Whisper model with offline cache fallback.
    Returns (model, resolved_model_name, load_latency_s).
    """
    t_start = time.perf_counter()
    try:
        model = whisper.load_model(model_name, device=device)
        load_time = time.perf_counter() - t_start
        return model, model_name, load_time
    except Exception as e:
        cached = find_cached_whisper_model()
        if cached and cached != model_name:
            logging.warning(
                f"Could not load requested model '{model_name}' ({e}). "
                f"Falling back to locally cached model '{cached}' on '{device}'..."
            )
            model = whisper.load_model(cached, device=device)
            load_time = time.perf_counter() - t_start
            return model, cached, load_time
        raise


def benchmark(
    model_name: str = "base.en",
    device: Optional[str] = None,
    audio_path: Optional[str] = None,
    duration: float = 3.0,
    runs: int = 5,
    temperature: float = 0.0
) -> Dict[str, Any]:
    """
    Executes the comprehensive Whisper STT benchmark measuring cold/warm latency,
    RTF, memory footprints, and transcription outputs.
    """
    active_device = resolve_device(device)
    use_fp16 = active_device.startswith("cuda")
    env_info = get_environment_info(active_device)
    proc = psutil.Process()

    logging.info(f"Preparing benchmark audio (duration: {duration:.2f}s)...")
    audio, actual_duration, audio_desc = load_or_generate_audio(audio_path, duration)

    # --- Phase 1: Cold-Start Measurement ---
    logging.info(f"Measuring Cold-Start: Loading '{model_name}' on '{active_device}'...")
    if active_device.startswith("cuda"):
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

    model, resolved_model, model_load_latency = load_whisper_model(model_name, device=active_device)
    if active_device.startswith("cuda"):
        torch.cuda.synchronize()

    # Cold inference pass (first pass initializes CUDA kernels & memory buffers)
    logging.info("Executing Cold Inference Pass...")
    if active_device.startswith("cuda"):
        torch.cuda.synchronize()
    t_first_inf_start = time.perf_counter()
    cold_result = model.transcribe(
        audio,
        language="en",
        fp16=use_fp16,
        temperature=temperature,
        condition_on_previous_text=False,
        without_timestamps=True
    )
    if active_device.startswith("cuda"):
        torch.cuda.synchronize()
    cold_inference_latency = time.perf_counter() - t_first_inf_start
    total_cold_latency = model_load_latency + cold_inference_latency

    # --- Phase 2: Warm Inference Measurement ---
    logging.info(f"Executing {runs} Warm Inference Passes...")
    warm_latencies = []
    last_transcription = cold_result.get("text", "").strip()

    for run_idx in range(1, runs + 1):
        if active_device.startswith("cuda"):
            torch.cuda.synchronize()
        t_start = time.perf_counter()
        result = model.transcribe(
            audio,
            language="en",
            fp16=use_fp16,
            temperature=temperature,
            condition_on_previous_text=False,
            without_timestamps=True
        )
        if active_device.startswith("cuda"):
            torch.cuda.synchronize()
        pass_latency = time.perf_counter() - t_start
        warm_latencies.append(pass_latency)
        last_transcription = result.get("text", "").strip()
        logging.info(f"  Warm pass {run_idx}/{runs}: {pass_latency * 1000.0:.2f} ms")

    # Metrics computation
    warm_mean = float(np.mean(warm_latencies))
    warm_std = float(np.std(warm_latencies))
    warm_min = float(np.min(warm_latencies))
    warm_max = float(np.max(warm_latencies))
    warm_median = float(np.median(warm_latencies))

    # Real-Time Factor (RTF = latency / audio_duration)
    # RTF < 1.0 means faster than real-time; speedup = 1 / RTF
    warm_rtf = warm_mean / actual_duration if actual_duration > 0 else 0.0
    warm_speedup = (1.0 / warm_rtf) if warm_rtf > 0 else 0.0
    cold_rtf = cold_inference_latency / actual_duration if actual_duration > 0 else 0.0

    # Memory profiling
    final_ram_rss_mb = proc.memory_info().rss / (1024.0 * 1024.0)
    cuda_mem_allocated_mb = None
    cuda_mem_reserved_mb = None
    cuda_mem_peak_mb = None

    if active_device.startswith("cuda"):
        cuda_mem_allocated_mb = torch.cuda.memory_allocated() / (1024.0 * 1024.0)
        cuda_mem_reserved_mb = torch.cuda.memory_reserved() / (1024.0 * 1024.0)
        cuda_mem_peak_mb = torch.cuda.max_memory_allocated() / (1024.0 * 1024.0)

    report_data = {
        "environment": env_info,
        "config": {
            "model_name": resolved_model,
            "requested_model": model_name,
            "device": active_device,
            "fp16": use_fp16,
            "temperature": temperature,
            "audio_source": audio_desc,
            "audio_duration_s": round(actual_duration, 3),
            "warm_runs": runs
        },
        "cold_start": {
            "model_load_latency_s": round(model_load_latency, 4),
            "cold_inference_latency_s": round(cold_inference_latency, 4),
            "total_cold_start_s": round(total_cold_latency, 4),
            "cold_inference_rtf": round(cold_rtf, 4)
        },
        "warm_performance": {
            "mean_latency_s": round(warm_mean, 4),
            "mean_latency_ms": round(warm_mean * 1000.0, 2),
            "std_latency_s": round(warm_std, 4),
            "std_latency_ms": round(warm_std * 1000.0, 2),
            "min_latency_s": round(warm_min, 4),
            "min_latency_ms": round(warm_min * 1000.0, 2),
            "max_latency_s": round(warm_max, 4),
            "max_latency_ms": round(warm_max * 1000.0, 2),
            "median_latency_s": round(warm_median, 4),
            "raw_latencies_s": [round(l, 4) for l in warm_latencies],
            "real_time_factor_rtf": round(warm_rtf, 5),
            "speedup_vs_realtime": round(warm_speedup, 2)
        },
        "memory": {
            "initial_ram_rss_mb": env_info["initial_ram_rss_mb"],
            "final_ram_rss_mb": round(final_ram_rss_mb, 2),
            "ram_rss_delta_mb": round(final_ram_rss_mb - env_info["initial_ram_rss_mb"], 2),
            "cuda_allocated_mb": round(cuda_mem_allocated_mb, 2) if cuda_mem_allocated_mb is not None else None,
            "cuda_reserved_mb": round(cuda_mem_reserved_mb, 2) if cuda_mem_reserved_mb is not None else None,
            "cuda_peak_mb": round(cuda_mem_peak_mb, 2) if cuda_mem_peak_mb is not None else None
        },
        "transcription": {
            "output_text": last_transcription
        }
    }

    return report_data


def print_report(data: Dict[str, Any]):
    """Renders formatted benchmark report to stdout."""
    env = data["environment"]
    cfg = data["config"]
    cold = data["cold_start"]
    warm = data["warm_performance"]
    mem = data["memory"]
    trans = data["transcription"]

    sep = "=" * 80
    print("\n" + sep)
    print("           PERSONAL MEMORY CORE (PMC) - WHISPER GPU BENCHMARK")
    print(sep)
    print("DEVICE & ENVIRONMENT:")
    print(f"  OS / Platform:          {env['platform']}")
    print(f"  PyTorch Version:        {env['pytorch_version']}")
    print(f"  CUDA Available:         {env['cuda_available']} (CUDA {env.get('cuda_version', 'N/A')})")
    print(f"  Active Device:          {cfg['device']}")
    if env.get("gpu_name"):
        cap = env.get("compute_capability")
        cap_str = f"sm_{cap[0]}{cap[1]}" if cap else "N/A"
        print(f"  GPU Hardware:           {env['gpu_name']} ({cap_str})")
        if env.get("supported_architectures"):
            print(f"  PyTorch CUDA Archs:     {', '.join(env['supported_architectures'])}")

    print("\nCONFIGURATION:")
    print(f"  Whisper Model:          {cfg['model_name']}")
    print(f"  Audio Source:           {cfg['audio_source']}")
    print(f"  Audio Duration:         {cfg['audio_duration_s']:.2f} s")
    print(f"  Inference Runs:         {cfg['warm_runs']} warm passes")
    print(f"  FP16 Accelerated:       {cfg['fp16']}")
    print(f"  Greedy Temp:            {cfg['temperature']}")

    print("\nLATENCY & REAL-TIME FACTOR:")
    print(f"  Model Load Latency:     {cold['model_load_latency_s']:.4f} s ({cold['model_load_latency_s'] * 1000.0:.1f} ms)")
    print(f"  Cold Inference Latency: {cold['cold_inference_latency_s']:.4f} s ({cold['cold_inference_latency_s'] * 1000.0:.1f} ms)")
    print(f"  Total Cold-Start Time:  {cold['total_cold_start_s']:.4f} s ({cold['total_cold_start_s'] * 1000.0:.1f} ms)")
    print(f"  Warm Latency (Mean):    {warm['mean_latency_ms']:.2f} ms +/- {warm['std_latency_ms']:.2f} ms")
    print(f"  Warm Latency (Min/Max): {warm['min_latency_ms']:.2f} ms / {warm['max_latency_ms']:.2f} ms")
    print(f"  Warm RTF:               {warm['real_time_factor_rtf']:.4f}  (<1.0 is faster than real-time)")
    print(f"  Throughput Speedup:     {warm['speedup_vs_realtime']:.1f}x real-time")

    print("\nMEMORY FOOTPRINT:")
    print(f"  RAM RSS (Process):      {mem['final_ram_rss_mb']:.2f} MB (Delta: {mem['ram_rss_delta_mb']:+.2f} MB)")
    if mem.get("cuda_allocated_mb") is not None:
        print(f"  CUDA VRAM Allocated:    {mem['cuda_allocated_mb']:.2f} MB")
        print(f"  CUDA VRAM Reserved:     {mem['cuda_reserved_mb']:.2f} MB")
        print(f"  CUDA VRAM Peak:         {mem['cuda_peak_mb']:.2f} MB")
    else:
        print("  CUDA VRAM:              N/A (running on CPU)")

    print("\nTRANSCRIPTION OUTPUT:")
    display_text = trans['output_text'] if trans['output_text'] else "[No speech transcribed / non-verbal harmonic audio]"
    print(f"  Recorded Text:          \"{display_text}\"")
    print(sep + "\n")


def main():
    parser = argparse.ArgumentParser(description="Whisper STT GPU Latency & Resource Benchmark")
    default_model = getattr(config, "WHISPER_MODEL", "base.en") if config else "base.en"
    default_device = getattr(config, "WHISPER_DEVICE", "cuda") if config else "cuda"
    default_temp = getattr(config, "WHISPER_TEMPERATURE", 0.0) if config else 0.0

    parser.add_argument("--model", type=str, default=default_model, help=f"Whisper model size (default: {default_model})")
    parser.add_argument("--device", type=str, default=default_device, help=f"Inference device (default: {default_device})")
    parser.add_argument("--audio", type=str, default=None, help="Path to input audio file (WAV/MP3). If omitted, generates synthetic audio")
    parser.add_argument("--duration", type=float, default=3.0, help="Duration in seconds for synthetic test audio (default: 3.0)")
    parser.add_argument("--runs", type=int, default=5, help="Number of warm benchmark passes (default: 5)")
    parser.add_argument("--temperature", type=float, default=default_temp, help=f"Decoding temperature (default: {default_temp})")
    parser.add_argument("--json", type=str, default=None, help="Optional output JSON path for benchmark metrics")

    args = parser.parse_args()

    results = benchmark(
        model_name=args.model,
        device=args.device,
        audio_path=args.audio,
        duration=args.duration,
        runs=args.runs,
        temperature=args.temperature
    )

    print_report(results)

    if args.json:
        out_dir = os.path.dirname(os.path.abspath(args.json))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Benchmark JSON saved to: {args.json}")


if __name__ == "__main__":
    main()
