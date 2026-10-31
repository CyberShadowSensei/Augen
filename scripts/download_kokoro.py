import os
import requests
import logging

# --- Configuration ---
KOKORO_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
VOICES_BIN_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin"
MODEL_DIR = "kokoro_models"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def download_file(url, dest_path):
    if os.path.exists(dest_path):
        logging.info(f"File already exists: {dest_path}")
        return

    logging.info(f"Downloading {url} to {dest_path}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info("Download complete.")
    except Exception as e:
        logging.error(f"Failed to download {url}: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path) # Clean up partial file

def main():
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        logging.info(f"Created directory: {MODEL_DIR}")

    model_path = os.path.join(MODEL_DIR, "kokoro-v0_19.onnx")
    voices_path = os.path.join(MODEL_DIR, "voices.bin")

    download_file(KOKORO_MODEL_URL, model_path)
    download_file(VOICES_BIN_URL, voices_path)

    logging.info("Kokoro model setup complete.")

if __name__ == "__main__":
    main()