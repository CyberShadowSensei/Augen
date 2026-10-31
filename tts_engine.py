import logging
import threading
import os
import re
import time
import sounddevice as sd
import numpy as np
from kokoro_onnx import Kokoro

# --- Configuration ---
MODEL_DIR = "kokoro_models"
MODEL_PATH = os.path.join(MODEL_DIR, "kokoro-v0_19.onnx")
VOICES_PATH = os.path.join(MODEL_DIR, "voices.bin")
DEFAULT_VOICE = "af_sarah" # A clear, natural female voice

class TTSEngine:
    """
    Manages text-to-speech functionality using Kokoro (High Quality).
    Speech synthesis runs in a separate thread to prevent blocking.
    """
    def __init__(self):
        logging.info("Initializing Kokoro TTS Engine...")
        self.kokoro = None
        try:
            if not os.path.exists(MODEL_PATH) or not os.path.exists(VOICES_PATH):
                logging.error(f"Kokoro model files not found in {MODEL_DIR}. Please run download_kokoro.py")
            else:
                self.kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
                logging.info("Kokoro TTS Engine initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize Kokoro: {e}", exc_info=True)

        self._speaker_thread = None
        self._speak_queue = [] # Queue for speech tasks
        self._speak_lock = threading.Lock() # Lock for queue access
        self._speaking_event = threading.Event() # Event to signal when speaking is active
        self._stop_signal = False # Flag to interrupt speech

    def _split_sentences(self, text):
        """Splits text into sentences for fluid streaming playback."""
        # Split by punctuation followed by a space or end of line
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _speak_worker(self):
        """Worker thread that processes speech requests from the queue."""
        while True:
            with self._speak_lock:
                if not self._speak_queue:
                    if self._stop_signal:
                        break # Exit if stop signal is set and queue is empty
                    time.sleep(0.1) # Wait for new tasks
                    continue

                text_to_speak = self._speak_queue.pop(0) # Get next text from queue
            
            if text_to_speak is None: # Special signal to stop the worker thread
                break

            if not self.kokoro:
                logging.warning("Kokoro not initialized, skipping speech.")
                continue

            self._speaking_event.set() # Signal that speaking is active
            self._stop_signal = False # Reset stop signal for new utterance

            # Split into sentences for lower latency perception
            sentences = self._split_sentences(text_to_speak)
            # sentences = [text_to_speak] # Speak the whole text at once for better prosody test
            
            for sentence in sentences:
                # Sanitize: Remove markdown/formatting artifacts like "---", "**"
                clean_sentence = re.sub(r'[-*_#]+', '', sentence).strip()
                
                if not clean_sentence or not re.search(r'[a-zA-Z0-9]', clean_sentence):
                    logging.info(f"TTS: Skipping unspeakable text: '{sentence}'")
                    continue

                if self._stop_signal:
                    logging.info("TTS interrupted.")
                    break

                logging.info(f"TTS: Generating audio for '{clean_sentence[:30]}...'")
                try:
                    # Generate audio (returns samples, sample_rate)
                    samples, sample_rate = self.kokoro.create(
                        text=clean_sentence,
                        voice=DEFAULT_VOICE,
                        speed=1.0,
                        lang="en-us"
                    )
                    
                    # Add 0.5s of silence to the end to prevent cutoff
                    # sample_rate is typically 24000
                    silence_duration = 0.5
                    silence_samples = int(sample_rate * silence_duration)
                    silence = np.zeros(silence_samples, dtype=np.float32)
                    samples = np.concatenate((samples, silence))

                    # Play audio
                    if self._stop_signal: break
                    sd.play(samples, sample_rate)
                    sd.wait() # Wait until playback is finished
                    
                except Exception as e:
                    logging.error(f"TTS failed to speak: {e}", exc_info=True)
            
            self._speaking_event.clear() # Signal that speaking is done

        logging.info("TTS worker thread stopped.")

    def speak(self, text: str):
        """Adds text to the speech queue. Starts worker thread if not running."""
        if not self.kokoro:
            logging.warning("Kokoro TTS Engine not initialized. Cannot speak.")
            return

        with self._speak_lock:
            self._speak_queue.append(text)
        
        if not self._speaker_thread or not self._speaker_thread.is_alive():
            logging.info("Starting TTS speaker thread...")
            self._speaker_thread = threading.Thread(target=self._speak_worker, daemon=True)
            self._speaker_thread.start()

    def stop_speaking(self):
        """Stops current speech and clears the queue."""
        self._stop_signal = True
        sd.stop() # Stop any currently playing audio
        with self._speak_lock:
            self._speak_queue.clear()

    def is_speaking(self) -> bool:
        """Checks if the TTS engine is currently speaking."""
        return self._speaking_event.is_set()


if __name__ == "__main__":
    # Simple test for TTSEngine
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    tts = TTSEngine()
    if tts.kokoro:
        print("Speaking...")
        tts.speak("Hello! I am your personal memory core. This voice is generated by Kokoro, a high quality local model.")
        tts.speak("Notice how I pause between sentences? That makes me sound more natural.")
        
        import time
        while tts.is_speaking() or len(tts._speak_queue) > 0:
            time.sleep(0.1)
        print("Test finished.")
    else:
        print("TTS failed to initialize.")