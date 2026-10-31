"""
memory_store.py

A standalone Python module for the Memory Backend, handling interactions
with ChromaDB for vector storage and Ollama for embedding generation.
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta # Import timedelta
from typing import List, Dict, Optional, Any
from collections import Counter # Import Counter

import chromadb
from chromadb.config import Settings
import ollama
from pydantic import BaseModel, Field

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ENRICHMENT_PROMPT = """Analyze the following memory. Extract:
1. 'entities': A list of People, Places, Project Names, OR Key Objects (e.g., 'milk', 'keys', 'phone').
2. 'topic': MUST be one of [Person, Project, Event, Location, Object, Idea, Task, General].
3. 'priority': 'High', 'Medium', or 'Low'.
Output ONLY valid JSON format:
{"entities": ["name1", "object1"], "topic": "Event", "priority": "High"}"""

# --- Custom Exceptions ---
class OllamaConnectionError(Exception):
    """Custom exception for when Ollama is not available or the model is missing."""
    pass

# --- Data Structures ---
class MemoryEntry(BaseModel):
    """Pydantic model for a single memory entry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "user_input"
    tags: Optional[List[str]] = Field(default_factory=list)

class MemoryStore:
    """
    Handles the storage and retrieval of memories using ChromaDB and Ollama.
    """
    def __init__(self, db_path: str = "./data/chroma_db", collection_name: str = "personal_memory"):
        """Initializes the MemoryStore and its database connection."""
        logging.info("TRACE: MemoryStore.__init__ entered.")
        self.db_path = db_path
        self.collection_name = collection_name
        logging.info(f"TRACE: MemoryStore.__init__: self.collection_name set to '{self.collection_name}'.")
        try:
            self.db_client = chromadb.PersistentClient(path=self.db_path, settings=Settings(anonymized_telemetry=False))
        except Exception as e:
            logging.error(f"Failed to initialize or connect to ChromaDB: {e}", exc_info=True)
            raise

        self.ollama_client = ollama.Client()
        self.embedding_model_name: Optional[str] = None
        self._verify_ollama_connection()

    def _verify_ollama_connection(self):
        """Verifies that the Ollama service is running and the required model is available."""
        logging.info("Verifying connection to Ollama...")
        try:
            models_response = self.ollama_client.list()
            model_names = [m.get('model') for m in models_response.get('models', []) if m.get('model')]
            for model_name in model_names:
                if model_name.startswith('nomic-embed-text'):
                    self.embedding_model_name = model_name
                    break
            if not self.embedding_model_name:
                raise OllamaConnectionError("'nomic-embed-text' model not available in Ollama.")
            logging.info(f"Ollama connection verified. Using '{self.embedding_model_name}' model.")
        except Exception as e:
            raise OllamaConnectionError(f"Could not connect to Ollama. Error: {e}") from e

    def enrich_text(self, text: str) -> dict:
        """Uses an LLM to extract structured metadata from text."""
        logging.info(f"Enriching text: '{text[:50]}...'")
        default_enrichment = {"entities": [], "topic": "General", "priority": "Medium"}
        try:
            full_prompt = f"{ENRICHMENT_PROMPT}\n\nMemory Text: \"{text}\""
            response = ollama.chat(
                model="granite3-dense:2b",
                messages=[{'role': 'user', 'content': full_prompt}],
                stream=False, options={'temperature': 0.0}
            )
            json_response = response['message']['content']
            if "```json" in json_response:
                json_response = json_response.split("```json\n")[1].split("```")[0]
            enriched_data = json.loads(json_response)
            return enriched_data
        except Exception as e:
            logging.error(f"Error during text enrichment: {e}", exc_info=True)
            return default_enrichment

    def add_memory(self, text: str, source: str = "user_input") -> str:
        """Adds a new, enriched memory to the store."""
        try:
            enrichment_data = self.enrich_text(text)
            logging.info(f"[Enrichment]: {enrichment_data}")
            embedding = ollama.embeddings(model=self.embedding_model_name, prompt=text)['embedding']
            entry = MemoryEntry(text=text, source=source)
            entities_str = ",".join(enrichment_data.get('entities', []))

            # Convert ISO timestamp string to Unix timestamp (float)
            timestamp_unix = datetime.fromisoformat(entry.timestamp).timestamp()

            metadata_to_store = {
                "timestamp": timestamp_unix, # Store as Unix timestamp
                "source": source,
                "entities": entities_str,
                "topic": enrichment_data.get('topic', 'General'),
                "priority": enrichment_data.get('priority', 'Medium')
            }
            collection = self.db_client.get_or_create_collection(name=self.collection_name)
            collection.upsert(
                ids=[entry.id], embeddings=[embedding],
                documents=[entry.text], metadatas=[metadata_to_store]
            )
            logging.info(f"Successfully added enriched memory with ID: {entry.id}")
            return entry.id
        except Exception as e:
            logging.error(f"Failed to add enriched memory: {e}", exc_info=True)
            raise

    def delete_memory(self, memory_id: str) -> bool:
        """Deletes a specific memory from the collection by its ID."""
        try:
            logging.info(f"Attempting to delete memory with ID: {memory_id}")
            collection = self.db_client.get_or_create_collection(name=self.collection_name)
            collection.delete(ids=[memory_id])
            logging.info(f"Successfully deleted memory with ID: {memory_id}")
            return True
        except Exception as e:
            logging.error(f"Failed to delete memory {memory_id}: {e}", exc_info=True)
            return False

    def search_memory(self, query: str, n_results: int = 5, relevance_threshold: float = 400.0) -> List[str]:
        """
        Searches for memories, formats them into rich context strings,
        and filters by relevance.
        """
        logging.info(f"Searching for memories with query: '{query}' (top {n_results}, threshold {relevance_threshold})")
        try:
            collection = self.db_client.get_collection(name=self.collection_name)
            response = ollama.embeddings(model=self.embedding_model_name, prompt=query)
            query_embedding = response["embedding"]
            results = collection.query(
                query_embeddings=[query_embedding], n_results=n_results,
                include=["metadatas", "documents", "distances"] # Include distances
            )
            formatted_results = []
            
            # Check if results and documents are valid
            if results and results.get('documents') and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    distance = results['distances'][0][i] # Get the distance
                    
                    # Only include if relevance is above threshold (lower distance = higher relevance)
                    if distance <= relevance_threshold:
                        text = results['documents'][0][i]
                        metadata = results['metadatas'][0][i] if results.get('metadatas') and results['metadatas'][0] else {}
                        timestamp = metadata.get('timestamp', 'Unknown Time')
                        priority = metadata.get('priority', 'Normal')
                        topic = metadata.get('topic', 'General')
                        entities = metadata.get('entities', '')
                        
                        # Convert timestamp to readable string for the LLM
                        try:
                            ts_val = float(timestamp)
                            readable_ts = datetime.fromtimestamp(ts_val, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                        except (ValueError, TypeError):
                            readable_ts = str(timestamp)

                        # Use actual distance in the formatted text for debugging/info
                        enriched_text = (
                            f"[Distance: {distance:.4f}] [Time: {readable_ts}] [PRIORITY: {priority}] [TOPIC: {topic}] "
                            f"[Entities: {entities}]\nContent: {text}"
                        )
                        formatted_results.append(enriched_text)
                        logging.info(f"[RAG Retrieval]: Found -> {enriched_text[:120]}...")
                    else:
                        logging.info(f"[RAG Retrieval]: Skipping result due to low relevance (distance: {distance:.4f} > threshold: {relevance_threshold})")

            return formatted_results
        except Exception as e:
            logging.error(f"Failed to query ChromaDB: {e}", exc_info=True)
            return []

    def get_recent_memories(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves the most recent memories from the store."""
        try:
            collection = self.db_client.get_or_create_collection(name=self.collection_name)
            results = collection.get(include=["metadatas", "documents"])
            if not results or not results.get('ids'): return []
            memories = [
                {"id": results['ids'][i], "document": results['documents'][i], "metadata": results['metadatas'][i]}
                for i in range(len(results['ids']))
            ]

            def get_sortable_timestamp(mem):
                """Safely gets a timestamp value for sorting, handling mixed types."""
                ts_val = mem.get('metadata', {}).get('timestamp')
                if isinstance(ts_val, (int, float)):
                    return ts_val # Already a numeric timestamp
                if isinstance(ts_val, str):
                    try:
                        # Handle ISO format strings (with or without 'Z')
                        if ts_val.endswith('Z'):
                            ts_val = ts_val[:-1] + '+00:00'
                        return datetime.fromisoformat(ts_val).timestamp()
                    except ValueError:
                        return 0.0 # Default for unparseable strings
                return 0.0 # Default for None or other types

            sorted_memories = sorted(
                memories,
                key=get_sortable_timestamp,
                reverse=True
            )
            return sorted_memories[:limit]
        except Exception as e:
            logging.error(f"Failed to get recent memories from ChromaDB: {e}", exc_info=True)
            return []

    def get_all_memories(self) -> List[Dict[str, Any]]:
        """Retrieves all memories from the store."""
        try:
            collection = self.db_client.get_or_create_collection(name=self.collection_name)
            results = collection.get(include=["metadatas", "documents"])
            if not results or not results.get('ids'): return []

            memories = [
                {"id": results['ids'][i], "document": results['documents'][i], "metadata": results['metadatas'][i]}
                for i in range(len(results['ids']))
            ]
            logging.info(f"Retrieved {len(memories)} total memories.")
            return memories
        except Exception as e:
            logging.error(f"Failed to get all memories from ChromaDB: {e}", exc_info=True)
            return []

    def get_recent_entities(self, hours: int = 1) -> Counter:
        """
        Queries memories from the last N hours, extracts all entities from their metadata,
        and returns a frequency count.
        """
        logging.info(f"Getting entities from last {hours} hours.")
        all_entities = []
        try:
            collection = self.db_client.get_or_create_collection(name=self.collection_name)
            
            # Calculate cutoff Unix timestamp
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            cutoff_timestamp_unix = cutoff_time.timestamp()

            # Query memories newer than the cutoff using numerical comparison
            results = collection.get(
                where={"timestamp": {"$gte": cutoff_timestamp_unix}}, # Use numerical comparison
                include=["metadatas"]
            )

            if results and results.get('metadatas'):
                for metadata in results['metadatas']:
                    entities_str = metadata.get('entities')
                    if entities_str:
                        # Split by comma and strip whitespace for each entity
                        # Convert to lowercase to ensure case-insensitive matching (Project Alpha == project alpha)
                        entities_list = [entity.strip().lower() for entity in entities_str.split(',') if entity.strip()]
                        all_entities.extend(entities_list)
        except Exception as e:
            logging.error(f"Error getting recent entities: {e}", exc_info=True)
            return Counter()

        return Counter(all_entities)

    def count(self) -> int:
        """Returns the total number of memories in the collection."""
        logging.info("TRACE: MemoryStore.count: method entered.")
        try:
            collection = self.db_client.get_or_create_collection(name=self.collection_name)
            count_value = collection.count()
            logging.info(f"TRACE: MemoryStore.count: successfully retrieved count: {count_value}")
            return count_value
        except Exception as e:
            logging.error(f"Failed to get memory count: {e}", exc_info=True)
            logging.info("TRACE: MemoryStore.count: returning 0 due to error.")
            return 0


if __name__ == '__main__':
    """
    Main execution block to demonstrate and verify the MemoryStore functionality.
    
    This block requires that the Ollama service is running and has the 
    'nomic-embed-text' model available.
    """
    print("--- MemoryStore Demonstration ---")
    try:
        # 1. Instantiate the class
        print("\n1. Initializing MemoryStore...")
        memory_store = MemoryStore()
        print("   MemoryStore initialized successfully.")

        # 2. Add a sample memory
        print("\n2. Adding a sample memory...")
        sample_text = "I need to buy groceries on Saturday, specifically milk, eggs, and bread."
        memory_id = memory_store.add_memory(sample_text)
        print(f"   Memory added with ID: {memory_id}")
        
        # 3. Search for a related term
        print("\n3. Searching for a semantically related term ('food')...")
        search_results = memory_store.search_memory("food", n_results=3)

        # 4. Print the result
        print("\n4. Search Results:")
        if search_results:
            for result in search_results:
                print(f"   - Text: \"{result['text']}\"")
                print(f"     Distance: {result['distance']:.4f}")
                print(f"     Timestamp: {result['timestamp']}")
        elif search_results == []:
             print("   No results found.")
        else:
            print("   Search failed.")

    except OllamaConnectionError as e:
        print(f"\n[ERROR] A connection error with Ollama occurred: {e}")
        print("Please ensure the Ollama service is running and you have pulled the 'nomic-embed-text' model.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
    
    print("\n--- Demonstration Finished ---")

