"""
blind-nav  |  download_models.py
Downloads all required model weights into the models/ folder.
Run once before first launch.
"""

import os
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


YOLO_MODELS = {
    "yolov8n.pt": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt",
    "yolov8s.pt": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt",
    "yolo11n.pt": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt",
}


def progress_bar(block_num, block_size, total_size):
    downloaded = block_num * block_size
    pct = min(downloaded / total_size * 100, 100) if total_size > 0 else 0
    bar = "#" * int(pct / 2)
    sys.stdout.write(f"\r  [{bar:<50}] {pct:.1f}%")
    sys.stdout.flush()


def download(name, url):
    dest = MODELS_DIR / name
    if dest.exists():
        print(f"  [OK] {name} already exists, skipping.")
        return
    print(f"\n  Downloading {name} ...")
    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress_bar)
        print(f"\n  [OK] Saved -> {dest}")
    except Exception as e:
        print(f"\n  [FAIL] Failed to download {name}: {e}")


def download_midas():
    """MiDaS is fetched via torch.hub at runtime — just validate torch is available."""
    try:
        import torch
        print(f"\n  [OK] PyTorch {torch.__version__} found. MiDaS will auto-download on first run with USE_DEPTH=True.")
        if torch.cuda.is_available():
            print(f"  [OK] CUDA detected: {torch.cuda.get_device_name(0)}")
        else:
            print("  [INFO] No CUDA GPU found - will run on CPU (slower for depth model).")
    except ImportError:
        print("  [FAIL] PyTorch not installed. Run: pip install -r requirements.txt")


if __name__ == "__main__":
    print("=" * 55)
    print("  blind-nav  |  Model Downloader")
    print("=" * 55)

    print("\n[1/2] YOLO detection models:")
    for name, url in YOLO_MODELS.items():
        download(name, url)

    print("\n[2/2] MiDaS depth model (Phase 2):")
    download_midas()

    print("\n" + "=" * 55)
    print("  Done! You can now run:  python run.py")
    print("=" * 55)

