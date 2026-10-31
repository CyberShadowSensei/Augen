"""
audio_provider.py

A standalone Python module for real-time audio capture, voice activity
detection (VAD), and speech-to-text (STT) transcription.
"""

import logging
import os
import queue
import threading
import time
from typing import Callable, Optional

import numpy as np
import pyaudio
import torch
import webrtcvad
import whisper

import config

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

    def __init__(self, model_size: Optional[str] = None, device: Optional[str] = None, tts_engine=None):
        """
        Initializes the AudioListener.
        """
        # Load settings from config with sensible defaults
        self.model_size = model_size if model_size is not None else getattr(config, "WHISPER_MODEL", "base.en")
        requested_device = device if device is not None else getattr(config, "WHISPER_DEVICE", "cuda")
        self.fallback_to_cpu = getattr(config, "WHISPER_FALLBACK_TO_CPU", True)
        self.temperature = getattr(config, "WHISPER_TEMPERATURE", 0.0)
        self.silence_threshold_ms = getattr(config, "SILENCE_THRESHOLD_MS", self.SILENCE_THRESHOLD_MS)
        self.vad_aggressiveness = getattr(config, "VAD_AGGRESSIVENESS", self.VAD_AGGRESSIVENESS)

        self.audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._transcription_lock = threading.Lock()
        self._capture_thread = None
        self._transcription_thread = None
        self.tts_engine = tts_engine  # Store TTS engine reference

        try:
            logging.info(f"Initializing VAD with aggressiveness {self.vad_aggressiveness}...")
            self.vad = webrtcvad.Vad(self.vad_aggressiveness)
        except Exception as e:
            logging.error(f"Failed to initialize VAD: {e}")
            raise

        # Dynamic device resolution
        target_device = str(requested_device).strip().lower()
        if target_device.startswith("cuda"):
            if not torch.cuda.is_available():
                logging.warning("CUDA requested for Whisper, but torch.cuda.is_available() is False. Falling back to CPU.")
                target_device = "cpu"
            else:
                dev_idx = 0
                if ":" in target_device:
                    try:
                        dev_idx = int(target_device.split(":")[1])
                    except ValueError:
                        dev_idx = 0
                # Validate architecture compatibility to prevent driver hangs on unsupported architectures (e.g. sm_120 on cu118)
                try:
                    cap = torch.cuda.get_device_capability(dev_idx)
                    arch_list = torch.cuda.get_arch_list()
                    cap_tag = f"sm_{cap[0]}{cap[1]}"
                    comp_tag = f"compute_{cap[0]}{cap[1]}"
                    major_tag = f"sm_{cap[0]}0"
                    if arch_list and cap_tag not in arch_list and comp_tag not in arch_list and major_tag not in arch_list:
                        if self.fallback_to_cpu:
                            dev_name = target_device
                            try:
                                dev_name = torch.cuda.get_device_name(dev_idx)
                            except Exception:
                                pass
                            logging.warning(
                                f"CUDA device '{dev_name}' with capability {cap} ({cap_tag}) "
                                f"is not supported by current PyTorch build (archs: {arch_list}). "
                                f"Falling back to CPU to prevent kernel hang."
                            )
                            target_device = "cpu"
                except Exception as ex:
                    logging.debug(f"Device capability check exception: {ex}")

        # Model loading with fallback
        # Retain the '.en' model suffix (DO NOT strip .en)
        try:
            logging.info(f"Initializing Whisper model '{self.model_size}' on device '{target_device}'...")
            self.whisper_model = whisper.load_model(self.model_size, device=target_device)
            self.device = target_device
            logging.info(f"Whisper model initialized successfully on '{self.device}'.")
        except Exception as e:
            if target_device.startswith("cuda") and self.fallback_to_cpu:
                logging.warning(f"Failed to initialize Whisper model on CUDA: {e}. Falling back to CPU...")
                try:
                    self.whisper_model = whisper.load_model(self.model_size, device="cpu")
                    self.device = "cpu"
                    logging.info(f"Whisper model initialized successfully on fallback device '{self.device}'.")
                except Exception as cpu_e:
                    # In offline environments, try locally cached model if model_size was not found
                    cached_model = self._find_cached_whisper_model()
                    if cached_model and cached_model != self.model_size:
                        logging.warning(
                            f"Could not load '{self.model_size}' ({cpu_e}). "
                            f"Falling back to cached model '{cached_model}' on CPU..."
                        )
                        self.whisper_model = whisper.load_model(cached_model, device="cpu")
                        self.device = "cpu"
                        self.model_size = cached_model
                        logging.info(f"Whisper model initialized successfully with cached model '{self.model_size}' on 'cpu'.")
                    else:
                        logging.error(f"Failed to initialize Whisper model on CPU: {cpu_e}")
                        raise
            else:
                cached_model = self._find_cached_whisper_model()
                if cached_model and cached_model != self.model_size:
                    logging.warning(
                        f"Could not load '{self.model_size}' ({e}). "
                        f"Falling back to cached model '{cached_model}' on '{target_device}'..."
                    )
                    self.whisper_model = whisper.load_model(cached_model, device=target_device)
                    self.device = target_device
                    self.model_size = cached_model
                    logging.info(f"Whisper model initialized successfully with cached model '{self.model_size}' on '{self.device}'.")
                else:
                    logging.error(f"Failed to initialize Whisper model: {e}")
                    raise

        # Warmup GPU / Model
        self._warmup_model()

    @staticmethod
    def _find_cached_whisper_model() -> Optional[str]:
        """Finds locally cached whisper models if network is offline."""
        cache_dir = os.path.expanduser("~/.cache/whisper")
        if os.path.isdir(cache_dir):
            for filename in os.listdir(cache_dir):
                if filename.endswith(".pt"):
                    return filename[:-3]  # e.g., "small" from "small.pt"
        return None

    def _warmup_model(self):
        """
        Performs a 1-second dummy inference pass during initialization so that
        the first user utterance does not suffer a 2-4s cold-start delay.
        """
        try:
            dummy_audio = np.zeros(self.RATE, dtype=np.float32)
            use_fp16 = self.device.startswith("cuda")
            with self._transcription_lock:
                self.whisper_model.transcribe(
                    dummy_audio,
                    language="en",
                    fp16=use_fp16,
                    temperature=self.temperature,
                    condition_on_previous_text=False,
                    without_timestamps=True
                )
            logging.info(f"Whisper model warmed up successfully on '{self.device}' (fp16={use_fp16}).")
        except Exception as e:
            logging.warning(f"Whisper warmup warning: {e}")

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
        silence_frames_threshold = max(1, int(self.silence_threshold_ms / self.FRAME_DURATION_MS))
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
                try:
                    self._run_transcription(audio_bytes, callback_function)
                finally:
                    self.audio_queue.task_done()
            except queue.Empty:
                continue # Allows the loop to re-check the stop event
            except Exception as e:
                logging.error(f"An unexpected error occurred in the transcription loop: {e}")
        logging.info("Transcription loop stopped.")

    def _run_transcription(self, audio_bytes: bytearray, callback: Callable[[str], None]):
        """Processes the buffered audio and transcribes it."""
        if not isinstance(audio_bytes, (bytes, bytearray)):
            logging.warning("Received invalid audio buffer type; discarding.")
            return

        # Discard speech buffers shorter than 400ms (16000 samples/sec * 0.4 sec * 2 bytes/sample)
        min_bytes = int(self.RATE * 0.4 * 2)
        if len(audio_bytes) < min_bytes:
            logging.debug(f"Discarding audio buffer shorter than 400ms ({len(audio_bytes)} bytes < {min_bytes} bytes).")
            return

        logging.info(f"Processing a speech segment of {len(audio_bytes) / (self.RATE * 2):.2f} seconds for transcription.")
        
        try:
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            use_fp16 = self.device.startswith("cuda")

            with self._transcription_lock:
                result = self.whisper_model.transcribe(
                    audio_np,
                    language="en",
                    fp16=use_fp16,
                    temperature=self.temperature,
                    condition_on_previous_text=False,
                    without_timestamps=True
                )
            transcribed_text = result.get("text", "").strip()
            
            if transcribed_text:
                logging.info(f"Transcribed: '{transcribed_text}'")
                callback(transcribed_text)
        except Exception as e:
            logging.error(f"Transcription failed: {e}", exc_info=True)

    def start_listening(self, callback_function: Callable[[str], None]):
        """
        Starts the audio capture and transcription threads.
        """
        is_capturing = bool(self._capture_thread and self._capture_thread.is_alive())
        is_transcribing = bool(self._transcription_thread and self._transcription_thread.is_alive())
        if is_capturing or is_transcribing:
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
        is_capturing = bool(self._capture_thread and self._capture_thread.is_alive())
        is_transcribing = bool(self._transcription_thread and self._transcription_thread.is_alive())

        if not is_capturing and not is_transcribing:
            logging.warning("Not currently listening.")
            return

        logging.info("Stopping audio listener...")
        self._stop_event.set()

        if self._capture_thread:
            self._capture_thread.join(timeout=3)
            if self._capture_thread.is_alive():
                logging.error("Audio capture thread did not terminate gracefully.")

        # Wait for the transcription queue to be fully processed
        self.audio_queue.join()
        
        if self._transcription_thread:
            self._transcription_thread.join(timeout=3)
            if self._transcription_thread.is_alive():
                logging.error("Transcription thread did not terminate gracefully.")

        logging.info("Audio listener stopped.")

