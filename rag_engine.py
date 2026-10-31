"""
rag_engine.py

This module defines the RAGEngine, which uses a MemoryStore instance
to retrieve context and an Ollama client to generate responses.
"""

import logging
from typing import List, Dict, Any

import ollama
from memory_store import MemoryStore, OllamaConnectionError

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RAGEngine:
    """
    The Retrieval Augmented Generation engine. It retrieves context from
    the MemoryStore and uses it to generate a response from an LLM.
    """

    def __init__(self, memory_store: MemoryStore, llm_model: str = "granite3-dense:2b"):
        """
        Initializes the RAGEngine.
        """
        self.memory_store = memory_store
        self.llm_model = llm_model
        try:
            self.ollama_client = ollama.Client()
            logging.info(f"RAGEngine initialized, connected to Ollama and using model '{self.llm_model}'.")
        except Exception as e:
            logging.error(f"Failed to initialize Ollama client: {e}")
            raise OllamaConnectionError("Could not connect to Ollama. Ensure it is running.") from e

    def generate_response(self, query: str, chat_history: List[Dict[str, str]] = None) -> str:
        """
        Generates a response to a query using the RAG pattern, considering chat history.
        """
        logging.info(f"Generating RAG response for query: '{query}'")
        try:
            # 1. Format Chat History
            history_str = ""
            if chat_history:
                # Take the last 4 messages for context (excluding the current one if it's there)
                recent = chat_history[-4:] 
                for msg in recent:
                    role = "User" if msg['role'] == 'user' else "AI"
                    content = msg['content']
                    history_str += f"{role}: {content}\n"

            # 2. Search Memory
            results = self.memory_store.search_memory(query)
            
            # 3. Build Context String
            if results:
                context_str = "\n\n".join(results)
            else:
                context_str = "No relevant memories found."

            # 4. Construct the Prompt (Short, Concise & Direct)
            system_prompt = (
                "You are an ultra-concise, direct personal AI memory assistant.\n"
                "Your task is to answer the query using Context From Memory or General Knowledge.\n\n"
                "**STRICT INSTRUCTIONS:**\n"
                "1. Be extremely SHORT, CONCISE, and DIRECT TO THE POINT (1 to 2 sentences maximum).\n"
                "2. NO conversational filler, pleasantries, preamble, or repeating the question.\n"
                "3. If 'Context From Memory' contains the answer, start with `[From Memory]:` followed immediately by the concise answer.\n"
                "4. If the answer is not in memory, start with `[General Knowledge]:` followed immediately by the concise answer.\n"
                "5. If information is completely missing, reply: `[From Memory]: Information not found in memory.`\n\n"
                "--- RECENT CONVERSATION ---\n"
                f"{history_str}\n"
                "---------------------------\n\n"
                "--- CONTEXT FROM MEMORY ---\n"
                f"{context_str}\n"
                "---------------------------\n\n"
                "USER QUERY:\n"
                f"{query}\n"
                "---"
            )
            
            # 5. Generate Response via Ollama (capped tokens for brevity & low latency)
            response = ollama.chat(
                model=self.llm_model,
                messages=[{'role': 'user', 'content': system_prompt}],
                options={'temperature': 0.1, 'num_predict': 80}
            )
            return response['message']['content'].strip()
            
        except Exception as e:
            logging.error(f"Error generating response: {e}", exc_info=True)
            return f"Error generating response: {str(e)}" 