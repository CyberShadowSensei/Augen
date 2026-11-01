"""
populate_demo_data.py

Populates the Personal Memory Core (PMC) with realistic, high-quality demo data
spanning Work/Projects, Personal/Health, People/Networking, Everyday Objects/Locations,
and Visual Cortex captures.

Usage:
    python scripts/populate_demo_data.py [--clean] [--help]
"""

import sys
import os
import time
import argparse
from datetime import datetime, timezone, timedelta

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ollama
from memory_store import MemoryStore, MemoryEntry

DEMO_MEMORIES = [
    # ─── WORK & PROJECTS ───
    {
        "text": "Project Apollo quarterly roadmap review is scheduled for Friday at 3:00 PM with Sarah Jenkins and David Chen in Conference Room B.",
        "source": "voice",
        "topic": "Project",
        "priority": "High",
        "entities": ["Project Apollo", "Sarah Jenkins", "David Chen", "Conference Room B"],
        "days_ago": 1,
        "hours_ago": 4
    },
    {
        "text": "PMC v1.5 latency milestone achieved: OpenAI Whisper is running locally on the RTX 5050 GPU with sm_120 CUDA 12.8 acceleration, achieving 11.5x real-time transcription.",
        "source": "user_input",
        "topic": "Project",
        "priority": "High",
        "entities": ["PMC v1.5", "Whisper", "RTX 5050", "CUDA 12.8"],
        "days_ago": 0,
        "hours_ago": 2
    },
    {
        "text": "ContextAI codebase repository is hosted on GitHub at CyberShadowSensei/contextAI with automated camera DirectShow fallback and multi-backend support.",
        "source": "user_input",
        "topic": "Project",
        "priority": "Medium",
        "entities": ["ContextAI", "GitHub", "DirectShow"],
        "days_ago": 2,
        "hours_ago": 5
    },
    {
        "text": "Production staging server is hosted on Ubuntu 24.04 LTS at IP 192.168.1.120, running FastAPI backend on port 8000 and ChromaDB vector store.",
        "source": "user_input",
        "topic": "Project",
        "priority": "Medium",
        "entities": ["Ubuntu", "FastAPI", "ChromaDB", "Staging Server"],
        "days_ago": 3,
        "hours_ago": 8
    },

    # ─── PEOPLE & NETWORK ───
    {
        "text": "Sarah Jenkins is the Lead ML Engineer on Project Apollo. She works remotely from Seattle and prefers asynchronous communication via Notion and Slack.",
        "source": "voice",
        "topic": "Person",
        "priority": "Medium",
        "entities": ["Sarah Jenkins", "Project Apollo", "Seattle", "Notion", "Slack"],
        "days_ago": 4,
        "hours_ago": 6
    },
    {
        "text": "Met Vikram Malhotra, partner at Nexus AI Ventures, at the Bengaluru Tech Summit. He is interested in edge AI memory systems and requested our pitch deck.",
        "source": "voice",
        "topic": "Person",
        "priority": "High",
        "entities": ["Vikram Malhotra", "Nexus AI Ventures", "Bengaluru Tech Summit"],
        "days_ago": 5,
        "hours_ago": 3
    },
    {
        "text": "David Chen's birthday is coming up on December 4th. Gift idea: Sony WH-1000XM5 noise cancelling headphones or an ergonomic mechanical keyboard.",
        "source": "user_input",
        "topic": "Person",
        "priority": "Medium",
        "entities": ["David Chen", "Sony WH-1000XM5", "Birthday"],
        "days_ago": 6,
        "hours_ago": 1
    },

    # ─── HEALTH & PERSONAL ───
    {
        "text": "Annual preventive health checkup with Dr. Mehta is confirmed for November 12th at 10:30 AM at Apollo Health Clinic, Indiranagar.",
        "source": "voice",
        "topic": "Event",
        "priority": "High",
        "entities": ["Dr. Mehta", "Apollo Health Clinic", "Indiranagar"],
        "days_ago": 2,
        "hours_ago": 1
    },
    {
        "text": "Flight to New Delhi for the developer conference: IndiGo flight 6E-204 departing November 18th at 06:45 AM from Terminal 2. PNR is KF89DL.",
        "source": "user_input",
        "topic": "Event",
        "priority": "High",
        "entities": ["IndiGo 6E-204", "Terminal 2", "New Delhi"],
        "days_ago": 3,
        "hours_ago": 2
    },
    {
        "text": "Daily fitness goal: 45 minutes of functional training at Cult Fitness, maintaining 140g daily protein intake and 3 liters of water.",
        "source": "voice",
        "topic": "Task",
        "priority": "Low",
        "entities": ["Cult Fitness", "Workout", "Nutrition"],
        "days_ago": 7,
        "hours_ago": 4
    },

    # ─── LOCATIONS & IMPORTANT OBJECTS ───
    {
        "text": "Spare apartment keys, vehicle registration documents, and physical passport are kept in the top locked drawer of the teak wood desk in the home study.",
        "source": "voice",
        "topic": "Location",
        "priority": "High",
        "entities": ["Passport", "Apartment Keys", "Home Study", "Teak Desk"],
        "days_ago": 10,
        "hours_ago": 5
    },
    {
        "text": "Office guest Wi-Fi network SSID is 'ContextAI-Guest' with password 'Synapse2026!'. Network router reset pin is in the server rack cabinet.",
        "source": "user_input",
        "topic": "Object",
        "priority": "High",
        "entities": ["Wi-Fi", "ContextAI-Guest", "Server Rack"],
        "days_ago": 8,
        "hours_ago": 9
    },
    {
        "text": "Car scheduled 20,000 km periodic service is due with Bosch Car Service center on Outer Ring Road before the end of November.",
        "source": "user_input",
        "topic": "Task",
        "priority": "Medium",
        "entities": ["Bosch Car Service", "Outer Ring Road", "Car Service"],
        "days_ago": 4,
        "hours_ago": 7
    },

    # ─── VISUAL CORTEX CAPTURES (SCREEN / CAMERA) ───
    {
        "text": "Visual Cortex scene capture: Brainstorming whiteboard titled 'PMC Architecture v1.5' showing AudioListener -> Whisper GPU -> Granite Intent Router -> ChromaDB RAGEngine.",
        "source": "visual_cortex",
        "topic": "Project",
        "priority": "High",
        "entities": ["PMC Architecture", "AudioListener", "Whisper GPU", "ChromaDB"],
        "days_ago": 1,
        "hours_ago": 1
    },
    {
        "text": "Visual Cortex OCR receipt scan: Blue Tokai Coffee Roasters on October 28. Total paid INR 640 via UPI for two Flat Whites and one Almond Croissant.",
        "source": "visual_cortex",
        "topic": "Object",
        "priority": "Low",
        "entities": ["Blue Tokai", "UPI", "Coffee Receipt"],
        "days_ago": 3,
        "hours_ago": 10
    }
]

# Patterns of mic noise fragments from early hardware testing to purge if --clean is specified
JUNK_PHRASES = [
    "bathroom",
    "tiny one",
    "it's kind of the screen",
    "i'm going to go ahead",
    "then.",
    "this is what they call it",
    "i'm going to eat this",
    "i'm not going to do it again",
    "we were thinking this may speak",
    "i'm not sure if i can get it"
]

def clean_noisy_memories(ms: MemoryStore):
    """Purges mic capture noise from early device testing."""
    print("Scanning for early testing noise/garbage entries...")
    all_mems = ms.get_all_memories()
    deleted = 0
    for m in all_mems:
        doc = m.get('document', '').lower().strip()
        is_junk = any(junk in doc for junk in JUNK_PHRASES) or (len(doc.split()) <= 2 and doc in ["then.", "hello", "test"])
        if is_junk:
            mid = m['id']
            if ms.delete_memory(mid):
                deleted += 1
                print(f"  [Purged] {mid[:8]}... : '{m.get('document', '')[:50]}'")
    print(f"Purged {deleted} noisy test entries.\n")

def populate_memories(ms: MemoryStore):
    """Inserts the high quality demo dataset into ChromaDB with embeddings."""
    print(f"Connecting to Ollama embedding model: '{ms.embedding_model_name}'...")
    collection = ms.db_client.get_or_create_collection(name=ms.collection_name)
    now = datetime.now(timezone.utc)
    
    total = len(DEMO_MEMORIES)
    print(f"\nAdding {total} realistic demo memories across Work, Health, People, and Visual Cortex...\n")
    
    for idx, item in enumerate(DEMO_MEMORIES, start=1):
        text = item["text"]
        source = item.get("source", "user_input")
        topic = item.get("topic", "General")
        priority = item.get("priority", "Medium")
        entities = item.get("entities", [])
        entities_str = ",".join(entities)
        
        # Calculate realistic timestamps spread over the last few days
        delta = timedelta(days=item.get("days_ago", 0), hours=item.get("hours_ago", 0))
        entry_time = now - delta
        timestamp_unix = entry_time.timestamp()
        
        # Generate embedding via Ollama
        emb_response = ollama.embeddings(model=ms.embedding_model_name, prompt=text)
        embedding = emb_response["embedding"]
        
        entry = MemoryEntry(text=text, source=source)
        metadata_to_store = {
            "timestamp": timestamp_unix,
            "source": source,
            "entities": entities_str,
            "topic": topic,
            "priority": priority
        }
        
        collection.upsert(
            ids=[entry.id],
            embeddings=[embedding],
            documents=[entry.text],
            metadatas=[metadata_to_store]
        )
        print(f"  [{idx}/{total}] [{topic.upper()}] [{priority}] {text[:65]}...")
        print(f"         Entities: {entities_str}")

    print(f"\nSuccessfully populated {total} demo memories!")
    print(f"Total memories in database: {ms.count()}")

def main():
    parser = argparse.ArgumentParser(description="Populate Personal Memory Core with rich demo data.")
    parser.add_argument("--clean", action="store_true", help="Clean up noise/junk mic fragments from early hardware testing.")
    parser.add_argument("--purge-all", action="store_true", help="Delete ALL existing memories before populating.")
    args = parser.parse_args()

    print("=" * 60)
    print("  Personal Memory Core (PMC) - Demo Data Seeder")
    print("=" * 60)

    try:
        ms = MemoryStore()
    except Exception as e:
        print(f"ERROR: Could not connect to MemoryStore or Ollama: {e}")
        print("Ensure 'ollama serve' is running!")
        sys.exit(1)

    if args.purge_all:
        print("Purging ALL existing memories...")
        all_mems = ms.get_all_memories()
        for m in all_mems:
            ms.delete_memory(m['id'])
        print(f"Purged {len(all_mems)} memories.\n")
    elif args.clean:
        clean_noisy_memories(ms)

    populate_memories(ms)

    print("\n" + "=" * 60)
    print("Demo Data Population Complete!")
    print("Sample queries you can now test in CLI or Web UI:")
    print("  1. 'What is the status of Project Apollo?'")
    print("  2. 'When is my appointment with Dr. Mehta?'")
    print("  3. 'What are gift ideas for David Chen?'")
    print("  4. 'Where did I keep my passport and spare keys?'")
    print("  5. 'What is the guest Wi-Fi password?'")
    print("  6. 'What did the whiteboard scan say?'")
    print("=" * 60)

if __name__ == "__main__":
    main()

