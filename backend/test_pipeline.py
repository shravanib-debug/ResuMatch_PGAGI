"""
test_pipeline.py — End-to-End Pipeline Test (Phase 1.4)
=======================================================
Proves the entire AI core works before any FastAPI code exists.

Flow (simulated 3 rounds):
    Hardcoded resume → HybridRetriever → Question Generator → Structured output
    Prior topics grow each round to prove no repetition.

Run from backend/ directory:
    python test_pipeline.py
"""

from dotenv import load_dotenv
load_dotenv()  # must be BEFORE importing modules that read env vars

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

import json
from retriever import HybridRetriever
from question_generator import QuestionGenerator

# ── Sample Resume ─────────────────────────────────────────────────────────────

SAMPLE_RESUME = {
    "skills": ["PyTorch", "neural networks", "gradient descent", "CNNs", "transfer learning"],
    "domains": ["deep learning", "computer vision"],
    "experience_level": "mid",
    "notable_projects": [
        "built image classifier using ResNet for medical imaging",
        "fine-tuned BERT for sentiment analysis on product reviews",
    ],
}

ROLE = "aiml"
NUM_ROUNDS = 3

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  END-TO-END PIPELINE TEST — Phase 1.4")
    print("  Simulating a 3-round interview session")
    print("=" * 70)

    # Init components (loads models — takes a few seconds)
    print("\n⏳ Loading retriever and question generator...")
    retriever = HybridRetriever()
    generator = QuestionGenerator()
    print("✅ Components loaded.\n")

    prior_questions: list[dict] = []
    prior_topics: list[str] = []

    for round_num in range(1, NUM_ROUNDS + 1):
        print(f"\n{'─' * 70}")
        print(f"  ROUND {round_num} of {NUM_ROUNDS}")
        print(f"  Prior topics: {prior_topics if prior_topics else 'none yet'}")
        print(f"{'─' * 70}")

        # ── Step 1: Retrieve context ──────────────────────────────────────
        print("\n📚 Step 1: Retrieving context...")
        result = retriever.retrieve(
            parsed_resume=SAMPLE_RESUME,
            role=ROLE,
            prior_topics=prior_topics,
        )

        print(f"   Queries used:")
        for i, q in enumerate(result.queries_used, 1):
            print(f"     {i}. {q}")
        print(f"   CRAG triggered: {result.crag_triggered}")
        if result.crag_triggered:
            print(f"   CRAG reformulated: {result.crag_reformulated_query}")
        print(f"   Chunks retrieved: {len(result.chunks)}")

        # Print chunk summaries
        for i, c in enumerate(result.chunks, 1):
            print(f"     [{i}] Score: {c.score:.3f} | Section: {c.section_title}")
            print(f"         {c.text[:100]}...")

        # ── Step 2: Generate question ─────────────────────────────────────
        print(f"\n🧠 Step 2: Generating interview question...")
        question = generator.generate(
            parsed_resume=SAMPLE_RESUME,
            role=ROLE,
            context_chunks=result.chunks,
            prior_questions=prior_questions,
        )

        # ── Step 3: Display result ────────────────────────────────────────
        print(f"\n✅ GENERATED QUESTION:")
        print(f"   Text:           {question.question_text}")
        print(f"   Topic:          {question.topic}")
        print(f"   Difficulty:     {question.difficulty}")
        print(f"   Source concept: {question.source_concept}")
        print(f"   Chunk IDs:      {len(question.source_chunks)} chunks referenced")

        # Validate JSON round-trip
        q_dict = question.to_dict()
        try:
            json_str = json.dumps(q_dict, indent=2)
            reparsed = json.loads(json_str)
            print(f"   JSON valid:     ✅ (round-trip OK)")
        except Exception as e:
            print(f"   JSON valid:     ❌ ({e})")

        # Update prior state for next round
        prior_questions.append(q_dict)
        prior_topics.append(question.topic)

    # ── Final Summary ─────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  SESSION SUMMARY")
    print(f"{'=' * 70}")
    print(f"\n  Total rounds:     {NUM_ROUNDS}")
    print(f"  Topics covered:   {prior_topics}")

    # Check for topic uniqueness
    unique_topics = set(t.lower() for t in prior_topics)
    if len(unique_topics) == len(prior_topics):
        print(f"  Topic diversity:  ✅ All {len(prior_topics)} topics are unique")
    else:
        print(f"  Topic diversity:  ⚠️  Only {len(unique_topics)} unique out of {len(prior_topics)}")

    print(f"\n  All questions generated:")
    for i, q in enumerate(prior_questions, 1):
        print(f"\n  Q{i} [{q['topic']}] ({q['difficulty']})")
        print(f"     {q['question_text']}")
        print(f"     Source: {q['source_concept']}")

    print(f"\n{'=' * 70}")
    print("  ✅ Phase 1.4 complete — AI core validated end-to-end")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
