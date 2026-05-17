"""
Quick test script for the HybridRetriever.
Run from the backend/ directory:
    python test_retriever.py
"""

from dotenv import load_dotenv
load_dotenv()  # loads backend/.env into environment variables

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

from retriever import HybridRetriever

# 1. Initialize retriever (loads models — takes a few seconds)
retriever = HybridRetriever()

# 2. Fake resume to simulate a candidate
sample_resume = {
    "skills": ["PyTorch", "neural networks", "gradient descent"],
    "domains": ["deep learning", "computer vision"],
    "experience_level": "mid",
    "notable_projects": ["built image classifier", "fine-tuned BERT"],
}

# 3. Run the full hybrid retrieval pipeline
result = retriever.retrieve(sample_resume, role="aiml", prior_topics=[])

# 4. Print diagnostics
print(f"\nQueries used: {result.queries_used}")
print(f"CRAG triggered: {result.crag_triggered}")
if result.crag_triggered:
    print(f"CRAG reformulated query: {result.crag_reformulated_query}")
print(f"Chunks returned: {len(result.chunks)}")
print()

# 5. Print each chunk's details
for c in result.chunks:
    print(f"Score: {c.score} | Method: {c.retrieval_method} | Section: {c.section_title}")
    print(c.text[:200])
    print("---")

# 6. Print the formatted context string (what the LLM would see)
print("\n========== CONTEXT STRING ==========\n")
print(retriever.build_context_string(result.chunks))
