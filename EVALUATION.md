# Evaluating the Personal Memory Core

This document outlines suggested methods for evaluating the performance and accuracy of the PMC system's core components.

## 1. RAG Pipeline Evaluation

The most critical component to evaluate is the Retrieval-Augmented Generation (RAG) pipeline. The goal is to ensure it is both **precise** (not retrieving irrelevant documents) and **faithful** (basing its answer on the retrieved context).

### Metrics
*   **Context Precision:** Of all the memories retrieved, what percentage are actually relevant to the query?
    *   **Test:** Run a set of queries (`test_rag_robustness.py`) and manually label each retrieved document in the logs as "relevant" or "irrelevant". Calculate `(Relevant Documents / Total Retrieved Documents)`.
*   **Answer Faithfulness:** Does the final answer stay true to the information provided in the context?
    *   **Test:** For queries where context was found, compare the LLM's final answer to the text of the retrieved documents. Manually score on a scale of 1-5 how well the answer reflects the source material without hallucinating details.
*   **Fallback Accuracy:** When no relevant context is found, does the system correctly default to `[General Knowledge]`?
    *   **Test:** Use queries that have no corresponding memories (e.g., "Who is the current president?"). Check if the `[General Knowledge]` prefix is used.

### Tools
*   `test_rag_robustness.py`: Use this script as the primary driver for generating test data.

## 2. Intent Classification (Router) Evaluation

The Command Router must accurately classify user commands.

### Metrics
*   **Classification Accuracy:** What percentage of commands are routed to the correct intent (`save`, `query`, `read_screen`, etc.)?
    *   **Test:** Run `test_command_router.py`. The output shows the spoken command and the classified intent. Manually verify each classification. Calculate `(Correct Classifications / Total Commands)`.

### Tools
*   `test_command_router.py`: Provides a standardized set of commands to test against.

## 3. End-to-End (E2E) Latency

For a real-time assistant, latency is a key user experience metric.

### Metrics
*   **"Ear-to-Mouth" Latency:** How long does it take from the moment the user stops speaking to the moment the TTS starts generating audio?
    *   **Test:** Use the timestamps in the `main.py` logs.
        1.  Find the log entry for `Transcribed: '...'`.
        2.  Find the corresponding log entry `TTS: Generating audio for '...'`.
        3.  The delta between these two timestamps is the E2E latency for that turn.

This holistic evaluation ensures the system is not only feature-rich but also robust, accurate, and responsive.
