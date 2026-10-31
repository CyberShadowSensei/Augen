import streamlit as st
import time
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# Attempt to import backend modules
try:
    import ollama
    from memory_store import MemoryStore
    from rag_engine import RAGEngine
    from visual_cortex import VisualCortex
except ImportError as e:
    st.error(f"Failed to import a backend module: {e}. Please ensure all requirements are installed.")
    st.stop()

# --- Logging Configuration ---
LOG_FILE_PATH = "data/pmc.log"
os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, mode='a'),
        logging.StreamHandler()
    ]
)

# --- Helper Functions ---
def format_timestamp(ts_data: any) -> str:
    """Parses a timestamp (string or float) and converts it to formatted IST."""
    try:
        ist_tz = ZoneInfo("Asia/Kolkata")
        utc_tz = ZoneInfo("UTC")
        utc_dt = None

        if isinstance(ts_data, (int, float)):
            utc_dt = datetime.fromtimestamp(ts_data, tz=utc_tz)
        elif isinstance(ts_data, str):
            if ts_data.endswith('Z'):
                ts_data = ts_data[:-1] + '+00:00'
            utc_dt = datetime.fromisoformat(ts_data)
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=utc_tz)
        else:
            return "Invalid Timestamp Type"

        ist_dt = utc_dt.astimezone(ist_tz)
        return ist_dt.strftime("%b %d, %I:%M %p")
    except (ValueError, TypeError, KeyError):
        return "Invalid Timestamp"

def _get_log_tail(log_file_path: str, num_lines: int = 50) -> str:
    """Reads the last num_lines from the log file."""
    if not os.path.exists(log_file_path):
        return "Log file not found."
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return "".join(lines[-num_lines:])
    except Exception as e:
        return f"Error reading log file: {e}"

# --- Configuration & Page Setup ---
st.set_page_config(
    layout="wide",
    page_title="Personal Memory Core v1.5",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Sci-Fi Terminal Aesthetic ---
CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
html, body, [class*="st-"], .st-emotion-cache-16txtl3 {font-family: 'JetBrains Mono', 'Courier New', monospace; color: #c0c0c0;}
.stApp {background-color: #0e1117;}
header, footer {visibility: hidden;}
h1, h2, h3 {color: #00ff41; text-transform: uppercase;}
h1 {font-size: 2.5em; letter-spacing: 2px;}
h2 {font-size: 1.8em; letter-spacing: 1px;}
.st-emotion-cache-16txtl3 div[data-testid="stMetric"] {background-color: rgba(0, 255, 65, 0.05); border-left: 2px solid #00ff41; padding: 10px; border-radius: 0px;}
.st-emotion-cache-16txtl3 div[data-testid="stMetric"] label {color: #00ff41;}
.st-emotion-cache-16txtl3 div[data-testid="stMetric"] div {color: #c0c0c0;}
.stButton > button {border: 1px solid #00ff41; background-color: transparent; color: #00ff41; border-radius: 0px; padding: 10px 20px; width: 100%;}
.stButton > button:hover {border-color: #c0c0c0; color: #c0c0c0; background-color: rgba(0, 255, 65, 0.1);}
div[data-testid="stChatMessage"] {background-color: transparent !important;}
.stChatInput {background-color: #0e1117;}

/* Memory Card Styling */
.mem-card {
    border-left: 2px solid #00ff41;
    background: #1c1c1c;
    padding: 10px;
    margin-bottom: 8px;
    font-family: 'JetBrains Mono';
    border-radius: 0px;
}
.mem-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: #00ff41;
    font-size: 0.8em;
    text-transform: uppercase;
    margin-bottom: 5px;
}
.mem-body {
    color: #e0e0e0;
    font-size: 0.95em;
}
.mem-delete {
    color: #ff4b4b;
    text-decoration: none;
    font-weight: bold;
    font-size: 1.2em;
    cursor: pointer;
}
.mem-delete:hover {
    color: #ff0000;
}
"""
st.markdown(f'<style>{CSS}</style>', unsafe_allow_html=True)


# --- Initialization using Session State ---
if 'memory_store' not in st.session_state:
    try:
        st.session_state.memory_store = MemoryStore()
    except Exception as e:
        st.error(f"Failed to initialize MemoryStore: {e}")
        st.stop()

if 'rag_engine' not in st.session_state:
    try:
        st.session_state.rag_engine = RAGEngine(st.session_state.memory_store)
    except Exception as e:
        st.error(f"Failed to initialize RAGEngine: {e}")
        st.stop()

if 'visual_cortex' not in st.session_state:
    with st.spinner("Initializing Visual Cortex... This may take a moment on first run."):
        try:
            st.session_state.visual_cortex = VisualCortex()
        except Exception as e:
            st.error(f"Failed to initialize VisualCortex: {e}")
            st.stop()

# --- Helper functions that still use Streamlit's data caching ---
@st.cache_data(ttl=10)
def get_memory_count():
    return st.session_state.memory_store.count()

@st.cache_data(ttl=10)
def fetch_recent_memories(limit=15):
    return st.session_state.memory_store.get_recent_memories(limit=limit)

# Stop if core components failed to initialize
if 'memory_store' not in st.session_state or 'rag_engine' not in st.session_state:
    st.error("[FATAL] Core components could not be initialized. Application halted.")
    st.stop()


# --- Handle Delete Action from Query Parameter ---
if "delete_id" in st.query_params:
    mem_id_to_delete = st.query_params["delete_id"]
    if st.session_state.memory_store.delete_memory(mem_id_to_delete):
        st.toast(f"Memory {mem_id_to_delete[:8]}... deleted.")
        st.query_params.clear() # Clear param to prevent re-deletion
        st.cache_data.clear() # Clear data cache
        st.rerun()
    else:
        st.toast(f"Error: Could not delete memory {mem_id_to_delete[:8]}...")
        st.query_params.clear()


# --- Sidebar: System Telemetry & Actions ---
with st.sidebar:
    st.header("Telemetry")
    st.markdown("---")
    st.text("Active Models:")
    
    try:
        # Corrected attribute access
        rag_model_name = st.session_state.rag_engine.llm_model
        embed_model_name = st.session_state.memory_store.embedding_model_name
        st.success(f"LLM: {rag_model_name}")
        st.success(f"Embed: {embed_model_name}")
    except Exception as e:
        st.error("Could not load model info")

    st.metric(label="Memories Stored", value=get_memory_count())
    st.metric(label="VRAM Usage (Mock)", value="2.4 / 6.0 GB")
    st.markdown("---")

    st.header("Actions")
    if st.button("Force Refresh Log"):
        st.cache_data.clear()
        st.rerun()

    # --- NEW: Analyze Screen Button & Logic ---
    if st.button("👁️ Analyze Screen"):
        with st.spinner("Activating Visual Cortex (Full Analysis)..."):
            # Use the combined method for both Description + OCR
            full_analysis = st.session_state.visual_cortex.analyze_full_scene()

            if "Error:" not in full_analysis:
                st.session_state.memory_store.add_memory(full_analysis, source='visual_combined')
                st.success("Visual Memory Saved!")
                st.info(f"Analysis: {full_analysis[:200]}...") # Show preview
                # Log refresh
                st.session_state.log_content = _get_log_tail(LOG_FILE_PATH)
                time.sleep(3)
                st.rerun()
            else:
                st.error(f"Visual Cortex Error: {full_analysis}")
                time.sleep(3)

    st.markdown("---")
    with st.expander("ℹ️ About Personal Memory Core"):
        st.markdown("""
        **Personal Memory Core (PMC)** is a local-first, privacy-focused AI assistant
        designed to function as a "Second Brain."
        """)

        st.markdown("""
        ```mermaid
        graph TD
            main[main.py] --> audio[audio_provider.py]
            main --> visual[visual_cortex.py]
            main --> rag[rag_engine.py]
            rag --> memory[memory_store.py]
            memory --> db[(ChromaDB)]
            main --> ui[app.py]
        ```
        """)
    
    st.markdown("---")
    with st.expander("📄 System Logs"):
        if st.button("🔄 Refresh Logs"):
            st.rerun()
        log_content = _get_log_tail(LOG_FILE_PATH)
        st.code(log_content, language='log')


# --- Main Layout ---
st.title("Personal Memory Core v1.5")
col_chat, col_memory = st.columns([3, 2])


# --- COLUMN 1: The "Command Line" (Chat) ---
with col_chat:
    st.header("Command Line")
    
    # Define chat container here to be used for both display and updates
    chat_container = st.container(height=550)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Render existing messages
    for message in st.session_state.messages:
        with chat_container.chat_message(message["role"]):
            st.markdown(message["content"])
            
    if prompt := st.chat_input(">> Command / Query..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container.chat_message("user"):
            st.markdown(prompt)
            
        # Generate and display assistant response
        with chat_container.chat_message("assistant"):
            with st.spinner("[SYSTEM] Processing..."):
                # Pass chat history for context
                response = st.session_state.rag_engine.generate_response(prompt, chat_history=st.session_state.messages)
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.cache_data.clear()
        # Removed st.rerun() to avoid full page reload flicker


# --- COLUMN 2: The "Live Memory Log" (Timeline) ---
with col_memory:
    st.header("Live Memory Log")
    memories = fetch_recent_memories()
    if not memories:
        st.info("No memories found in log.")
    else:
        for mem in memories:
            text = mem.get('document', 'N/A')
            raw_ts = mem.get('metadata', {}).get('timestamp', str(datetime.now()))
            display_ts = format_timestamp(raw_ts)
            mem_id = mem.get('id', '')

            # Using a cleaner HTML structure with flexbox for alignment
            card_html = f"""
            <div class="mem-card">
                <div class="mem-header">
                    <span>[{display_ts}]</span>
                    <a href="?delete_id={mem_id}" target="_self" class="mem-delete" title="Delete this memory">🗑️</a>
                </div>
                <div class="mem-body">{text}</div>
            </div>
            """
            
            # Using st.container for the inspector context
            with st.container():
                st.markdown(card_html, unsafe_allow_html=True)

                # NEW: Inspector (Correctly placed below the card)
                with st.expander("🔍 Inspect Metadata", expanded=False):
                    meta_to_show = {
                        "Topic": mem['metadata'].get('topic', 'N/A'),
                        "Priority": mem['metadata'].get('priority', 'N/A'),
                        "Entities": mem['metadata'].get('entities', 'None'),
                        "Source": mem['metadata'].get('source', 'unknown'),
                        "ID": mem['id']
                    }
                    st.json(meta_to_show)