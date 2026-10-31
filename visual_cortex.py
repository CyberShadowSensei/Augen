import logging
import time
import io
import cv2
import easyocr
import ollama
import streamlit as st
import config # Import configuration

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@st.cache_resource
def get_easyocr_reader():
    """Initializes and caches the EasyOCR Reader."""
    logging.info("Initializing EasyOCR Reader (cached)... This may take a moment.")
    # GPU=False to save VRAM for the LLMs
    reader = easyocr.Reader(['en'], gpu=False)
    logging.info("EasyOCR Reader initialized successfully.")
    return reader

def resolve_camera_backend(backend_spec):
    """
    Resolves backend configuration (string or integer) to a valid OpenCV backend enum.
    Supports strings like 'cv2.CAP_DSHOW', 'CAP_DSHOW', 'DSHOW', 'CAP_ANY', 'CAP_MSMF',
    as well as raw integer flags (e.g., cv2.CAP_DSHOW = 700).
    """
    if isinstance(backend_spec, int):
        return backend_spec
    if not isinstance(backend_spec, str):
        return getattr(cv2, 'CAP_ANY', 0)

    cleaned = backend_spec.strip().replace("cv2.", "").upper()
    mapping = {
        "CAP_DSHOW": getattr(cv2, 'CAP_DSHOW', 700),
        "DSHOW": getattr(cv2, 'CAP_DSHOW', 700),
        "CAP_MSMF": getattr(cv2, 'CAP_MSMF', 1400),
        "MSMF": getattr(cv2, 'CAP_MSMF', 1400),
        "CAP_ANY": getattr(cv2, 'CAP_ANY', 0),
        "ANY": getattr(cv2, 'CAP_ANY', 0),
        "AUTO": getattr(cv2, 'CAP_ANY', 0),
        "DEFAULT": getattr(cv2, 'CAP_ANY', 0),
        "CAP_FFMPEG": getattr(cv2, 'CAP_FFMPEG', 1900),
        "FFMPEG": getattr(cv2, 'CAP_FFMPEG', 1900),
        "CAP_GSTREAMER": getattr(cv2, 'CAP_GSTREAMER', 1800),
        "GSTREAMER": getattr(cv2, 'CAP_GSTREAMER', 1800),
        "CAP_V4L": getattr(cv2, 'CAP_V4L', 200),
        "CAP_V4L2": getattr(cv2, 'CAP_V4L2', 200),
        "V4L": getattr(cv2, 'CAP_V4L', 200),
        "V4L2": getattr(cv2, 'CAP_V4L2', 200),
    }
    return mapping.get(cleaned, getattr(cv2, 'CAP_ANY', 0))

class VisualCortex:
    """
    The Eyes of the system. Handles camera capture and visual processing.
    """
    def __init__(self):
        try:
            self.reader = get_easyocr_reader()
        except Exception as e:
            logging.error(f"Failed to initialize EasyOCR: {e}", exc_info=True)
            self.reader = None

    def _open_camera(self):
        """
        Attempts to open VideoCapture using primary configuration,
        falling back through configured backends and indices if needed.
        Returns: (cap, active_index, active_backend) or (None, None, None)
        """
        primary_idx = getattr(config, 'CAMERA_INDEX', 0)
        primary_backend_raw = getattr(config, 'CAMERA_BACKEND', getattr(config, 'CAP_BACKEND', 'cv2.CAP_DSHOW'))
        primary_backend = resolve_camera_backend(primary_backend_raw)

        fallback_indices = getattr(config, 'CAMERA_FALLBACK_INDICES', [1])
        if not isinstance(fallback_indices, (list, tuple)):
            fallback_indices = [fallback_indices]

        fallback_backends_raw = getattr(config, 'CAMERA_FALLBACK_BACKENDS', ['cv2.CAP_ANY', 'cv2.CAP_MSMF'])
        if not isinstance(fallback_backends_raw, (list, tuple)):
            fallback_backends_raw = [fallback_backends_raw]
        fallback_backends = [resolve_camera_backend(b) for b in fallback_backends_raw]

        # Assemble candidate pairs: (index, backend) preserving priority order
        candidates = []
        def add_candidate(idx, backend):
            cand = (idx, backend)
            if cand not in candidates:
                candidates.append(cand)

        # 1. Primary index with primary backend
        add_candidate(primary_idx, primary_backend)
        # 2. Primary index with fallback backends
        for fb_backend in fallback_backends:
            add_candidate(primary_idx, fb_backend)
        # 3. Fallback indices with primary backend, then fallback backends
        for fb_idx in fallback_indices:
            add_candidate(fb_idx, primary_backend)
            for fb_backend in fallback_backends:
                add_candidate(fb_idx, fb_backend)

        # Attempt candidate configurations
        for idx, backend in candidates:
            cap = None
            try:
                logging.info(f"Attempting to open camera: index={idx}, backend={backend}...")
                if isinstance(idx, str):
                    cap = cv2.VideoCapture(idx)
                else:
                    cap = cv2.VideoCapture(idx, backend)

                if cap and cap.isOpened():
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None:
                        logging.info(f"Camera opened successfully on index {idx} with backend {backend}.")
                        return cap, idx, backend
                    else:
                        logging.warning(f"Camera index {idx} opened but failed initial read test.")
                        cap.release()
                        cap = None
                else:
                    if cap:
                        cap.release()
                        cap = None
                    logging.warning(f"Camera index {idx} failed to open with backend {backend}.")
            except Exception as e:
                if cap:
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                logging.warning(f"Exception opening camera index {idx} with backend {backend}: {e}")

        # Tier 4: Auto-detection across indices 0..3 if enabled
        if getattr(config, 'CAMERA_AUTO_DETECT', True):
            logging.info("Initiating auto-detection across indices 0..3...")
            probe_backends = [getattr(cv2, 'CAP_DSHOW', 700), getattr(cv2, 'CAP_ANY', 0)]
            for probe_idx in range(4):
                for probe_backend in probe_backends:
                    if (probe_idx, probe_backend) in candidates:
                        continue
                    cap = None
                    try:
                        cap = cv2.VideoCapture(probe_idx, probe_backend)
                        if cap and cap.isOpened():
                            ret, test_frame = cap.read()
                            if ret and test_frame is not None:
                                logging.info(f"Auto-detection found functional camera at index {probe_idx} (backend {probe_backend}).")
                                return cap, probe_idx, probe_backend
                            cap.release()
                            cap = None
                        else:
                            if cap:
                                cap.release()
                                cap = None
                    except Exception:
                        if cap:
                            try:
                                cap.release()
                            except Exception:
                                pass
                            cap = None

        logging.error("All camera candidates failed.")
        return None, None, None

    def _capture_frame(self):
        """Helper to capture a single frame from the webcam, with warm-up and flushing."""
        cap = None
        try:
            cap, active_idx, active_backend = self._open_camera()
            if not cap:
                return None, f"Error: Unable to access camera (Index {config.CAMERA_INDEX} and all fallbacks failed)."

            # --- Camera Warmup and Buffer Flushing ---
            warmup_delay = getattr(config, 'CAMERA_WARMUP_DELAY', 0.75)
            logging.info(f"Warming up camera on index {active_idx} for {warmup_delay} seconds (flushing frames)...")
            start_time = time.time()
            frames_flushed = 0
            while (time.time() - start_time) < warmup_delay:
                ret, _ = cap.read() # Read and discard frame
                if ret:
                    frames_flushed += 1
                time.sleep(0.01) # Small sleep to prevent 100% CPU on flushing loop

            logging.info(f"Warmup complete. Flushed {frames_flushed} frames.")

            # Capture the actual frame
            ret, frame = cap.read()
            if not ret or frame is None:
                logging.error("Failed to capture final frame from camera.")
                return None, "Error: Failed to capture final frame."

            return frame, None
        except Exception as e:
            logging.error(f"Unexpected error in _capture_frame: {e}", exc_info=True)
            return None, f"Error: Camera capture failed ({e})."
        finally:
            if cap and cap.isOpened():
                cap.release()

    def capture_and_read(self) -> str:
        """
        Captures an image and extracts TEXT (OCR).
        Useful for documents, signs, and screens.
        """
        if not self.reader: return "Error: OCR engine not initialized."
        frame, error = self._capture_frame()
        if error: return error
        return self._run_ocr(frame)

    def capture_and_describe(self) -> str:
        """
        Captures an image and DESCRIBES it using Moondream.
        Useful for objects, scenes, and context.
        """
        frame, error = self._capture_frame()
        if error: return error
        return self._run_moondream(frame)

    def analyze_full_scene(self) -> str:
        """
        Captures ONE frame and runs BOTH Moondream (Description) and OCR (Text).
        Displays a HUD window with the results for the demo.
        """
        frame, error = self._capture_frame()
        if error: return error

        try:
            # Show "Scanning" state if GUI is available
            preview = frame.copy()
            cv2.putText(preview, "SCANNING...", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("PMC Vision", preview)
            cv2.waitKey(100) # Force UI update
        except Exception:
            pass # Ignore if headless

        # Run both (Sequential to manage load)
        description = self._run_moondream(frame)
        text_content = self._run_ocr(frame)

        try:
            # Draw HUD overlays
            # 1. Background box for text
            h, w, _ = frame.shape
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, h-100), (w, h), (0, 0, 0), -1) # Bottom bar
            cv2.rectangle(overlay, (0, 0), (w, 60), (0, 0, 0), -1)    # Top bar
            alpha = 0.6
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

            # 2. Text
            cv2.putText(frame, f"OCR: {text_content[:50]}...", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame, f"AI: {description[:60]}...", (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Show final result
            cv2.imshow("PMC Vision", frame)
            cv2.waitKey(5000) # Show for 5 seconds
            cv2.destroyAllWindows()
        except Exception:
            pass # Ignore if headless

        combined_result = f"Visual Description: {description}\n\nExtracted Text: {text_content}"
        logging.info(f"Full Scene Analysis Complete. Length: {len(combined_result)}")
        return combined_result

    def _run_ocr(self, frame) -> str:
        """Internal helper for OCR."""
        logging.info("Performing OCR...")
        try:
            if not self.reader: return "OCR Unavailable."
            text_list = self.reader.readtext(frame, detail=0, paragraph=True)
            full_text = "\n".join(text_list)
            return full_text if full_text else "No text detected."
        except Exception as e:
            return f"Error during OCR: {e}"

    def _run_moondream(self, frame) -> str:
        """Internal helper for Moondream."""
        logging.info("Sending image to Moondream...")
        try:
            success, buffer = cv2.imencode(".jpg", frame)
            if not success: return "Error: Failed to encode image."
            
            # Use keep_alive=0 to unload immediately and save VRAM
            response = ollama.chat(
                model='moondream:1.8b',
                messages=[{
                    'role': 'user',
                    'content': 'Describe this image.',
                    'images': [buffer.tobytes()]
                }],
                keep_alive=0 # Force unload immediately to save VRAM
            )
            
            return response['message']['content']
        except Exception as e:
            return f"Error running Moondream: {e}"