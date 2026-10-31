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

    def _capture_frame(self):
        """Helper to capture a single frame from the webcam, with warm-up and flushing."""
        cap = None
        try:
            logging.info(f"Opening Camera Index: {config.CAMERA_INDEX}...")
            # Removed CAP_DSHOW to prevent index reordering
            cap = cv2.VideoCapture(config.CAMERA_INDEX)
            if not cap.isOpened():
                return None, f"Error: Camera {config.CAMERA_INDEX} unavailable."
            
            # --- Camera Warmup and Buffer Flushing ---
            logging.info(f"Warming up camera for {config.CAMERA_WARMUP_DELAY} seconds (flushing frames)...")
            start_time = time.time()
            frames_flushed = 0
            while (time.time() - start_time) < config.CAMERA_WARMUP_DELAY:
                ret, _ = cap.read() # Read and discard frame
                if ret:
                    frames_flushed += 1
                time.sleep(0.01) # Small sleep to prevent 100% CPU on flushing loop

            logging.info(f"Warmup complete. Flushed {frames_flushed} frames.")

            # Capture the actual frame
            ret, frame = cap.read()
            if not ret:
                logging.error("Failed to capture final frame from camera.")
                return None, "Error: Failed to capture final frame."
            
            return frame, None
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