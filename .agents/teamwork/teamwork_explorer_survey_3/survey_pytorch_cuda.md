# Survey Report: PyTorch & CUDA sm_120 Environment Investigation

**Date**: 2026-10-31  
**Investigator**: teamwork_explorer_survey_3  
**Target Hardware**: NVIDIA GeForce RTX 5050 Laptop GPU (Blackwell Architecture, Compute Capability 12.0 / `sm_120`)  
**Target Requirement**: Requirement R2 (openai-whisper GPU Acceleration on RTX 5050)

---

## 1. Executive Summary

The project's speech-to-text pipeline (`audio_provider.py`) fails when running `openai-whisper` on GPU (`device="cuda"`). While basic CUDA context initialization and simple 2x2 tensor allocations succeed, Transformer multi-head attention execution crashes with an unhandled fatal kernel mismatch:
```text
FATAL: kernel `fmha_cutlassF_f16_aligned_64x64_rf_sm80` is for sm80-sm100, but was built for sm37
```
This error is output in an infinite loop (>138,000 lines within seconds) causing the process to hang indefinitely.

The root cause is that the current environment runs **PyTorch 2.7.1+cu118** (compiled against CUDA 11.8). CUDA 11.8 has no knowledge of NVIDIA's Blackwell architecture (`sm_120` / compute capability 12.0), lacking both native `sm_120` SASS machine code and the PTX ISA compiler version needed to target compute capability 12.0.

The host system's GPU driver is **NVIDIA 616.56** with CUDA UMD **13.4**, which is fully capable of running **CUDA 12.8 (`cu128`)** builds. Upgrading `torch`, `torchvision`, and `torchaudio` to the official `cu128` wheels resolves the architecture mismatch completely and enables Whisper to execute directly on the RTX 5050 with hardware acceleration.

---

## 2. Environment Diagnostics

### 2.1 Python Runtime
- **Executable**: `C:\Users\devan\AppData\Local\Programs\Python\Python310\python.exe`
- **Python Version**: `3.10.11 (tags/v3.10.11:7d4cc5a, Apr 5 2023, 00:38:17) [MSC v.1929 64 bit (AMD64)]`
- **Pip Version**: `pip 26.2.1`
- **Environment Type**: Global user Python installation (no active `.venv` or conda environment).
- **Package Manager Available**: Standard `pip` in PATH (conda, mamba, and uv are not present in PATH).

### 2.2 Host GPU and Driver
Output from `nvidia-smi`:
- **GPU Model**: `NVIDIA GeForce RTX 5050 Laptop GPU`
- **Driver Version**: `616.56` (WDDM Model)
- **CUDA UMD Version**: `13.4`
- **Total VRAM**: `8151 MiB` (~8 GB)
- **Current VRAM Usage**: ~1396 MiB (Display / System usage, >6.5 GB free)

### 2.3 Current PyTorch & CUDA State
Diagnostic script execution revealed:
- **`torch.__version__`**: `2.7.1+cu118`
- **`torch.version.cuda`**: `11.8`
- **`torch.cuda.is_available()`**: `True`
- **`torch.cuda.device_count()`**: `1`
- **`torch.cuda.get_device_name(0)`**: `NVIDIA GeForce RTX 5050 Laptop GPU`
- **`torch.cuda.get_device_capability(0)`**: `(12, 0)` -> `sm_120`
- **`torch.cuda.get_arch_list()`**:
  ```python
  ['sm_37', 'sm_50', 'sm_60', 'sm_61', 'sm_70', 'sm_75', 'sm_80', 'sm_86', 'sm_90', 'compute_37']
  ```
- **Associated Packages**:
  - `torchaudio`: `2.7.1+cu118`
  - `torchvision`: `0.22.1+cu118`
  - `openai-whisper`: `20250625`
  - `tiktoken`: `0.14.0`
  - `triton`: `NOT INSTALLED`

---

## 3. Reproduction of Failure Mechanism

### 3.1 Initial PyTorch Import Warning
When initializing any CUDA tensor on `cuda:0`, PyTorch emits:
```text
C:\Users\devan\AppData\Local\Programs\Python\Python310\lib\site-packages\torch\cuda\__init__.py:287: UserWarning: 
NVIDIA GeForce RTX 5050 Laptop GPU with CUDA capability sm_120 is not compatible with the current PyTorch installation.
The current PyTorch install supports CUDA capabilities sm_37 sm_50 sm_60 sm_61 sm_70 sm_75 sm_80 sm_86 sm_90 compute_37.
If you want to use the NVIDIA GeForce RTX 5050 Laptop GPU GPU with PyTorch, please check the instructions at https://pytorch.org/get-started/locally/
```

### 3.2 Basic Tensor vs. Attention Kernel Divergence
- **Basic Tensor Operation**: `x = torch.ones((2, 2), device="cuda"); y = x + x` succeeds. Simple point-wise arithmetic uses generic CUDA kernels that do not strictly check CUTLASS architecture dispatch.
- **Whisper Inference**:
  When executing `whisper.load_model("small", device="cuda").transcribe(audio, fp16=True)`, the forward pass enters the Transformer encoder/decoder attention layers.
  PyTorch selects the Fused Multi-Head Attention (FMHA) CUTLASS kernel. Because the GPU reports `sm_120` (outside `sm_80` to `sm_100` ranges supported by CUDA 11.8 binaries), the CUTLASS dispatcher erroneously falls back to an `sm37` build target.
  This triggers an assertion failure in stderr:
  ```text
  FATAL: kernel `fmha_cutlassF_f16_aligned_64x64_rf_sm80` is for sm80-sm100, but was built for sm37
  ```
  During diagnostic execution (Task-56), this error printed over **138,666 times** in seconds (producing a 13.7 MB log), completely deadlocking the worker process and hanging transcription indefinitely.

---

## 4. Solution Space Analysis

### 4.1 Root Cause
NVIDIA's Blackwell generation (GeForce RTX 50-series: 5090, 5080, 5070, 5050) introduces CUDA Compute Capability 12.0 (`sm_120`). Support for `sm_120` and its PTX architecture was added in **CUDA Toolkit 12.8**. Older CUDA toolkits (CUDA 11.8, 12.1, 12.4) cannot compile or forward-JIT kernels for sm_120.

### 4.2 Hardware & Driver Compatibility
The host driver is `616.56` with CUDA UMD `13.4`. Under NVIDIA's CUDA Forward Compatibility Model, any display driver version ≥ `581.xx` fully supports CUDA 12.8 binaries and runtimes without requiring a driver update.

### 4.3 Target PyTorch Distribution
PyTorch provides official Windows wheels compiled with CUDA 12.8 (`cu128`):
- Wheel Index: `https://download.pytorch.org/whl/cu128`
- Preview / Nightly Index: `https://download.pytorch.org/whl/nightly/cu128`
These wheels include:
1. Native `sm_120` Cutlass and FlashAttention kernels.
2. Architecture support up to compute capability 12.0 (`sm_120`, `compute_120`).
3. Pre-compiled binaries for Python 3.10 on Windows x86_64 (`win_amd64`).

### 4.4 Dependency Impact Assessment
- **`openai-whisper` (`20250625`)**: Fully compatible. It is pure Python calling PyTorch operations (`torch.nn`, `torch.matmul`, `torch.nn.functional.scaled_dot_product_attention`). No reinstallation needed.
- **`torchvision`**: Must be upgraded alongside PyTorch to match the `cu128` ABI.
- **`torchaudio`**: Must be upgraded alongside PyTorch to match the `cu128` ABI.
- **`easyocr`**: Uses `gpu=False` in `visual_cortex.py` line 18, so it runs on CPU without VRAM contention or CUDA issues.
- **`transformers` & `timm`**: Pure Python / PyTorch libraries; will seamlessly use the upgraded PyTorch CUDA runtime.

---

## 5. Precise Upgrade & Implementation Plan

### Step 1: Upgrading PyTorch Stack to cu128
Execute pip upgrade for `torch`, `torchvision`, and `torchaudio`:
```powershell
python -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```
*Note on fallback*: If the stable index repository is temporarily unreachable or delayed for a specific minor sub-wheel, use the official nightly cu128 index:
```powershell
python -m pip install --upgrade --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
```

### Step 2: Verification of CUDA Device & Architecture
Run verification script to ensure:
1. No `UserWarning` about sm_120 incompatibility.
2. `torch.version.cuda` reflects `12.8`.
3. `torch.cuda.get_arch_list()` includes `sm_120` or `compute_120`.

```powershell
python -c "import torch; print('Torch:', torch.__version__); print('CUDA build:', torch.version.cuda); print('Arch list:', torch.cuda.get_arch_list()); print('Device:', torch.cuda.get_device_name(0)); x = torch.randn(10, 10, device='cuda'); print('CUDA tensor:', x.sum().item())"
```

### Step 3: Verification of Whisper Transcription on GPU
Test Whisper transcription using the cached model (`small.pt`):
```powershell
python -c "import whisper, torch, time; m = whisper.load_model('small', device='cuda'); a = torch.zeros(16000*2, dtype=torch.float32).numpy(); t0 = time.time(); res = m.transcribe(a, fp16=True); print('Transcription successful in', f'{time.time()-t0:.2f}s, text:', res['text'])"
```

Expected result:
- Model loads onto GPU VRAM (~1.5 GB VRAM allocated).
- FP16 transcription executes without `FATAL: kernel fmha_cutlassF_f16_aligned_64x64_rf_sm80` errors.
- Transcription completes in < 0.5s for 2 seconds of audio with zero errors or warnings.
