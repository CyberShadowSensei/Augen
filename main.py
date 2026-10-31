"""
main.py

The \"Hardened\" Orchestrator for Personal Memory Core.
Implements a strict State Machine and Concurrency Control to prevent race conditions.
"""

import json
import logging
import os
import threading
import time
import re
from datetime import datetime
from enum import Enum

import ollama
from audio_provider import AudioListener
from memory_store import MemoryStore
from rag_engine import RAGEngine
from visual_cortex import VisualCortex
from tts_engine import TTSEngine
from typing import Optional

# --- Configuration ---
LOG_FILE_PATH = "data/pmc.log"
os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

# Setup Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers(): logger.handlers.clear()
file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s'))
logger.addHandler(file_handler)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(stream_handler)

logging.info("--- PMC Kernel Starting (Hardened Mode) ---")

# --- State Definitions ---
class SystemState(Enum):
    DEFAULT = "DEFAULT"   # Listening for commands
    CHAT = "CHAT"         # Conversational mode
    BUSY = "BUSY"         # Processing (Vision/RAG) - Input Blocked
    MUTED = "MUTED"       # TTS Speaking - Input Blocked (Echo Cancel)

class AssistantController:
    def __init__(self):
        logging.info("Initializing System Kernel...")
        
        # 1. State & Concurrency
        self.state = SystemState.DEFAULT
        self.llm_lock = threading.Lock() # Global LLM Lock
        self.state_lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # 2. Components
        try:
            self.memory_store = MemoryStore()
            self.rag_engine = RAGEngine(self.memory_store)
            self.vision = VisualCortex()
            self.tts = TTSEngine()
            self.audio_listener = AudioListener(tts_engine=self.tts)
        except Exception as e:
            logging.error(f"Kernel Panic: Failed to init components: {e}", exc_info=True)
            raise

        # 3. Data
        self.last_saved_id: Optional[str] = None
        self.last_nudge_topic: Optional[str] = None
        self.chat_history = []

    # --- State Management ---
    def set_state(self, new_state: SystemState):
        with self.state_lock:
            logging.info(f"State Transition: {self.state.name} -> {new_state.name}")
            self.state = new_state

    # --- Core Logic ---
    def determine_intent(self, text: str) -> dict:
        """Strict Router with LLM Lock and Regex JSON extraction."""
        logging.info(f"Router: Analyzing '{text}'...")
        
        intent_system_prompt = """You are an expert, JSON-only router. Classify the input.
- **save**: User wants to SAVE/LOG information (e.g., 'Remember...', 'Note:', 'I met with...', or simple facts like 'Flight is at 5pm').
  Input: "Remember that I need to pick up dry cleaning." -> Output: {"intent": "save", "content": "I need to pick up dry cleaning.", "confidence": 0.9}
  Input: "From Delhi." -> Output: {"intent": "save", "content": "From Delhi.", "confidence": 0.9}
  Input: "19th December." -> Output: {"intent": "save", "content": "19th December.", "confidence": 0.9}

- **query**: User asks a QUESTION (e.g., 'When...?', 'What...?', 'Who...?').
  Input: "Who is the CEO of Apple?"
  Output: {"intent": "query", "content": "Who is the CEO of Apple?", "confidence": 0.9}
  *IMPORTANT: 'content' MUST be the actual question text.*

- **chat**: User EXPLICITLY commands to switch mode.
  Input: "Let's chat", "Switch to chat mode", "Start conversation".
  Output: {"intent": "chat", "content": null, "confidence": 0.9}
  *NOTE: Greetings like "Hello" or "Hi" are NOT chat triggers. They are queries or ignore.*

- **stop_chat**: User wants to stop chatting. ("Stop chat", "Go back to normal")

- **pause**: User wants to pause listening.
  Input: "Stop listening.", "Pause.", "Hold on."
  Output: {"intent": "pause", "content": null, "confidence": 0.9}

- **read_screen**: User wants to PERFORM VISUAL ANALYSIS using the camera/screen.
  Input: "Read this screen", "Scan this document", "What does this say?", "Open the camera", "Tell me what you see".
  Output: {"intent": "read_screen", "content": null, "confidence": 0.95}

- **ignore**: Noise, fillers, or simple greetings.
  Input: "Uhh...", "Hmm", "Thank you", "Hello", "Hi".
  Output: {"intent": "ignore", "content": null, "confidence": 0.0}

Output JSON: {"intent": "save", "content": "..."}"""

        with self.llm_lock:
            try:
                response = ollama.chat(
                    model="granite3-dense:2b",
                    messages=[{'role': 'user', 'content': f"{intent_system_prompt}\nInput: \"{text}\""}],
                    stream=False,
                    options={'temperature': 0.0}
                )
                content = response['message']['content']
                
                # Robust Regex Extraction for JSON
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    intent_data = json.loads(json_str)
                    
                    # --- HARD KERNEL GUARDRAIL ---
                    # Prevent accidental Chat Mode triggers
                    if intent_data.get('intent') == 'chat':
                        triggers = ["chat", "mode", "conversation"]
                        if not any(t in text.lower() for t in triggers):
                            logging.warning(f"Kernel blocked accidental Chat switch: '{text}'")
                            return {"intent": "ignore"}

                    logging.info(f"Intent classified: {intent_data}")
                    return intent_data
                else:
                    logging.warning(f"Router failed to generate JSON: {content}")
                    return {"intent": "ignore"}
            except Exception as e:
                logging.error(f"Router Error: {e}")
                return {"intent": "ignore"}

    def extract_query_target(self, text: str) -> str:
        """Helper to extract the exact search query from input."""
        try:
            with self.llm_lock:
                response = ollama.chat(
                    model="granite3-dense:2b",
                    messages=[{'role': 'user', 'content': f"Extract the core question/search term from this text. Output ONLY the question. Input: \"{text}\""}],
                    options={'temperature': 0.0}
                )
            return response['message']['content'].strip()
        except:
            return text # Fallback to original text

    # --- Main Loop ---
    def process_audio_callback(self, text: str):
        # 1. State Check (Hard Lock)
        if self.state in [SystemState.BUSY, SystemState.MUTED]:
            logging.info(f"Input dropped (State: {self.state.name}): '{text}'")
            return

        # 2. Noise Filter (Global)
        if len(text) < 2:
            return
            
        # Patch Fix: Ignore common Whisper hallucinations
        if text.strip().lower() in ["thank you.", "thanks.", "thank you very much.", "bye.", "you", "you.", "you?", "okay", "okay."]:
            logging.info(f"Ignored Whisper hallucination: '{text}'")
            return

        # 3. Barge-In (Safety Net)
        if self.tts.is_speaking():
            self.tts.stop_speaking()

        # 4. CHAT MODE LOOP
        if self.state == SystemState.CHAT:
            if ("stop" in text.lower() and "chat" in text.lower()) or \
               ("exit" in text.lower() and "mode" in text.lower()):
                self.set_state(SystemState.DEFAULT)
                self.tts.speak("Chat mode deactivated.")
                return
            
            # Chat Logic
            self.chat_history.append({"role": "user", "content": text})
            with self.llm_lock:
                # Chat Prompt
                response = self.rag_engine.generate_response(text, self.chat_history)
            
            self.chat_history.append({"role": "assistant", "content": response})
            self.tts.speak(response)
            return

        # 5. COMMAND LOOP (DEFAULT)
        try:
            # Safe print for Windows consoles that might choke on utf-8 chars
            try:
                print(f"\n[User]: {text}")
            except UnicodeEncodeError:
                print(f"\n[User]: {text.encode('ascii', 'replace').decode('ascii')}")
            
            intent_data = self.determine_intent(text)
            intent = intent_data.get("intent", "ignore")
            content = intent_data.get("content", "")

            if intent == "save":
                if content:
                    memory_id = self.memory_store.add_memory(content, source="voice")
                    self.last_saved_id = memory_id
                    print(f"[System]: Memory Saved (ID: {memory_id[:8]}...).\n")
                else:
                    # Fallback: Save the whole text if content extraction failed
                    memory_id = self.memory_store.add_memory(text, source="voice")
                    print(f"[System]: Memory Saved (Fallback).\n")
            
            elif intent == "query":
                # Double-check content extraction
                if not content or len(content) < 3:
                    content = self.extract_query_target(text)
                
                if content:
                    with self.llm_lock:
                        answer = self.rag_engine.generate_response(content, self.chat_history)
                    print(f"[System]: {answer}\n")
                    self.tts.speak(answer)
                else:
                    print(f"[System]: (Could not determine what to query)\n")

            elif intent == "chat":
                self.set_state(SystemState.CHAT)
                self.tts.speak("Chat mode activated. I'm listening.")

            elif intent == "read_screen":
                self.set_state(SystemState.BUSY) # Lock system
                self.tts.speak("Scanning...")
                
                # Vision Pipeline
                try:
                    with self.llm_lock:
                        analysis = self.vision.analyze_full_scene()
                    
                    time.sleep(1) # VRAM cooldown

                    if "Error" not in analysis:
                        # Synthesis
                        prompt = f"Summarize this visual analysis for the user as a helpful observation: {analysis}"
                        with self.llm_lock:
                            response = ollama.chat(model="granite3-dense:2b", messages=[{'role':'user', 'content': prompt}])
                        
                        summary = response['message']['content']
                        
                        # Store Unified Memory
                        self.memory_store.add_memory(summary, source="visual")
                        print(f"[System]: {summary}\n")
                        self.tts.speak(summary)
                    else:
                        self.tts.speak("I couldn't see anything.")
                finally:
                    self.set_state(SystemState.DEFAULT) # Unlock

            elif intent == "delete_last":
                if self.last_saved_id:
                    self.memory_store.delete_memory(self.last_saved_id)
                    print("[System]: Deleted.\n")
                    self.tts.speak("Deleted last memory.")
            
            elif intent == "pause":
                self.tts.speak("Pausing. Say resume to activate.")
                # We don't have a specific 'pause' loop here, but the intent is caught.
                # Actually, the original 'pause' logic was 'is_paused' flag.
                # Let's reinstate it simply:
                self.is_paused = True

        except Exception as e:
            logging.error(f"Loop Error: {e}")

    def _proactive_loop(self):
        """Proactive Nudge Loop (Gated)."""
        while not self._stop_event.wait(30):
            # 1. Gate: Only run in DEFAULT state
            if self.state != SystemState.DEFAULT:
                continue
            
            # 2. Gate: Don't run if TTS is speaking
            if self.tts.is_speaking():
                continue

            # 3. Logic
            try:
                recent_entities = self.memory_store.get_recent_entities(hours=1)
                # print(f"[Debug Proactive]: Entities found: {recent_entities}") 
                
                for entity, count in recent_entities.items():
                    if count >= 2:
                        if self.last_nudge_topic != entity:
                            nudge_message = f"\n[Proactive Nudge]: You've mentioned '{entity}' {count} times. Want a summary?"
                            print(nudge_message)
                            
                            # Only speak if not busy/muted (Double check)
                            if self.state == SystemState.DEFAULT:
                                self.tts.speak(nudge_message)
                                self.last_nudge_topic = entity 
                        break 
            except Exception as e:
                logging.error(f"Proactive Error: {e}")
                
    def _warmup(self):
        logging.info("Warming up...")
        with self.llm_lock:
            try: ollama.chat(model="granite3-dense:2b", messages=[{'role':'user', 'content':'hi'}])
            except: pass
        self.tts.speak("System online.")

    def run(self):
        self._warmup()
        self.audio_listener.start_listening(self.process_audio_callback)
        try:
            while not self._stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.audio_listener.stop_listening()

if __name__ == "__main__":
    AssistantController().run()
