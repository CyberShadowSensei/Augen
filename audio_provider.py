"""
audio_provider.py

A standalone Python module for real-time audio capture, voice activity
detection (VAD), and speech-to-text (STT) transcription.
"""

import logging
import queue
import threading
import time
from typing import Callable

import numpy as np
import pyaudio
import webrtcvad
import whisper

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AudioListener:
    """
    Listens to microphone input, detects speech, and transcribes it in real-time
    using a producer/consumer model with separate threads for audio capture and
    transcription to ensure responsiveness.
    """
    # --- Audio Configuration ---
    RATE = 16000
    CHANNELS = 1
    FRAME_DURATION_MS = 30
    FRAME_SIZE = int(RATE * FRAME_DURATION_MS / 1000)
    FORMAT = pyaudio.paInt16
    
    # --- VAD & Transcription Configuration ---
    VAD_AGGRESSIVENESS = 3
    SILENCE_THRESHOLD_MS = 500

    def __init__(self, model_size="small.en", device="cuda", tts_engine=None):
        """
        Initializes the AudioListener.
        """
        self.audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._capture_thread = None
        self._transcription_thread = None
        self.tts_engine = tts_engine # Store TTS engine reference

        try:
            logging.info("Initializing VAD...")
            self.vad = webrtcvad.Vad(self.VAD_AGGRESSIVENESS)
        except Exception as e:
            logging.error(f"Failed to initialize VAD: {e}")
            raise

        try:
            logging.info(f"Initializing Whisper model '{model_size}' on device '{device}'...")
            openai_model_size = model_size.replace(".en", "")
            self.whisper_model = whisper.load_model(openai_model_size, device=device)
            logging.info("Whisper model initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize Whisper model. CUDA available? Error: {e}")
            if "cuda" in str(e).lower():
                logging.warning("CUDA error detected. Check CUDA Toolkit/cuDNN setup or try device='cpu'.")
            raise

    def _capture_loop(self):
        """
        The audio capture loop (Producer).
        Listens to the microphone, performs VAD, and puts speech chunks onto a queue.
        """
        audio_interface = None
        audio_stream = None
        try:
            audio_interface = pyaudio.PyAudio()
            audio_stream = audio_interface.open(
                format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE,
                input=True, frames_per_buffer=self.FRAME_SIZE
            )
            logging.info("Microphone stream opened successfully.")
        except OSError as e:
            logging.error(f"Failed to open microphone stream. Is a microphone connected? Error: {e}")
            return

        speech_buffer = bytearray()
        silence_frames_threshold = int(self.SILENCE_THRESHOLD_MS / self.FRAME_DURATION_MS)
        silence_counter = 0

        while not self._stop_event.is_set():
            # --- Echo Cancellation / Deaf Period ---
            # If the AI is speaking, ignore microphone input to prevent self-transcription loop.
            if self.tts_engine and self.tts_engine.is_speaking():
                time.sleep(0.1) # Sleep to save CPU while waiting
                continue

            try:
                audio_chunk = audio_stream.read(self.FRAME_SIZE, exception_on_overflow=False)
                is_speech = self.vad.is_speech(audio_chunk, self.RATE)

                if is_speech:
                    speech_buffer.extend(audio_chunk)
                    silence_counter = 0
                elif len(speech_buffer) > 0:
                    silence_counter += 1
                    if silence_counter > silence_frames_threshold:
                        logging.info(f"Speech segment detected, adding to queue for transcription.")
                        self.audio_queue.put(speech_buffer.copy())
                        speech_buffer.clear()
                        silence_counter = 0
            except IOError as e:
                logging.warning(f"Audio stream read error: {e}")
            except Exception as e:
                logging.error(f"An unexpected error occurred in the capture loop: {e}")

        logging.info("Audio capture loop stopped.")
        if audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()
        if audio_interface:
            audio_interface.terminate()
        logging.info("Audio stream and interface closed.")

    def _transcription_loop(self, callback_function: Callable[[str], None]):
        """
        The transcription loop (Consumer).
        Pulls audio data from the queue, transcribes it, and fires the callback.
        """
        while not self._stop_event.is_set() or not self.audio_queue.empty():
            try:
                audio_bytes = self.audio_queue.get(timeout=1)
                self._run_transcription(audio_bytes, callback_function)
                self.audio_queue.task_done()
            except queue.Empty:
                continue # Allows the loop to re-check the stop event
            except Exception as e:
                logging.error(f"An unexpected error occurred in the transcription loop: {e}")
        logging.info("Transcription loop stopped.")

    def _run_transcription(self, audio_bytes: bytearray, callback: Callable[[str], None]):
        """Processes the buffered audio and transcribes it."""
        logging.info(f"Processing a speech segment of {len(audio_bytes) / (self.RATE * 2):.2f} seconds for transcription.")
        
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            result = self.whisper_model.transcribe(audio_np, language="en")
            transcribed_text = result["text"].strip()
            
            if transcribed_text:
                logging.info(f"Transcribed: '{transcribed_text}'")
                callback(transcribed_text)
        except Exception as e:
            logging.error(f"Transcription failed: {e}")

    def start_listening(self, callback_function: Callable[[str], None]):
        """
        Starts the audio capture and transcription threads.
        """
        if self._capture_thread and self._capture_thread.is_alive():
            logging.warning("Already listening.")
            return

        self._stop_event.clear()
        
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        self._transcription_thread = threading.Thread(
            target=self._transcription_loop, args=(callback_function,), daemon=True
        )
        self._transcription_thread.start()
        
        logging.info("Audio listener started with capture and transcription threads.")

    def stop_listening(self):
        """
        Stops the listening process and cleans up resources.
        """
        if not self._capture_thread or not self._capture_thread.is_alive():
            logging.warning("Not currently listening.")
            return

        logging.info("Stopping audio listener...")
        self._stop_event.set()

        self._capture_thread.join(timeout=3)
        if self._capture_thread.is_alive():
            logging.error("Audio capture thread did not terminate gracefully.")

        # Wait for the transcription queue to be fully processed
        self.audio_queue.join()
        
        self._transcription_thread.join(timeout=3)
        if self._transcription_thread.is_alive():
            logging.error("Transcription thread did not terminate gracefully.")

        logging.info("Audio listener stopped.")

