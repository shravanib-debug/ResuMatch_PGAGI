"""
rag_service.py — RAG Orchestration Service
============================================
Wraps HybridRetriever + QuestionGenerator into a service layer
that the API routers call. Manages the full flow:
    resume → retrieval → question generation → storage

Optimised for free-tier OpenRouter:
- Generates ALL questions in ONE LLM call (2 API calls total, not 10+)
- Stops hammering API after rate limit hit
- Dynamic fallback using resume skills
"""

import logging
import random
from retriever import HybridRetriever
from question_generator import QuestionGenerator, GeneratedQuestion

log = logging.getLogger(__name__)

# ── Singleton instances (loaded once, reused across requests) ─────────────────

_retriever: HybridRetriever | None = None
_generator: QuestionGenerator | None = None


def get_retriever() -> HybridRetriever:
    """Lazy-init singleton retriever."""
    global _retriever
    if _retriever is None:
        log.info("Initializing HybridRetriever (first request)...")
        _retriever = HybridRetriever()
    return _retriever


def get_generator() -> QuestionGenerator:
    """Lazy-init singleton question generator."""
    global _generator
    if _generator is None:
        log.info("Initializing QuestionGenerator (first request)...")
        _generator = QuestionGenerator()
    return _generator


def generate_questions_for_session(
    parsed_resume: dict,
    role: str,
    num_questions: int = 5,
) -> list[dict]:
    """
    Generate a batch of interview questions for a session.

    Strategy:
    1. ONE retrieval pass → gather context chunks
    2. ONE LLM call → generate ALL questions at once (batch prompt)
    3. If rate-limited → use smart fallback from resume skills

    Returns a list of question dicts ready for DB storage.
    """
    retriever = get_retriever()
    generator = get_generator()

    # ── Step 1: Single retrieval pass ──────────────────────────────────────
    log.info(f"Retrieving context for {num_questions} questions...")

    try:
        result = retriever.retrieve(
            parsed_resume=parsed_resume,
            role=role,
            prior_topics=[],
        )
        log.info(f"  Retrieved {len(result.chunks)} chunks, CRAG: False")
    except Exception as e:
        log.warning(f"Retrieval failed: {e}. Using empty context.")
        result = None

    chunks = result.chunks if result else []

    # ── Step 3: Generate ALL questions in ONE LLM call ────────────────────
    log.info(f"Generating {num_questions} questions in a single LLM call...")

    try:
        questions = generator.generate_batch(
            parsed_resume=parsed_resume,
            role=role,
            context_chunks=chunks,
            num_questions=num_questions,
        )

        if questions and len(questions) >= num_questions:
            log.info(f"  Batch generation successful: {len(questions)} questions")
            for i, q in enumerate(questions):
                log.info(f"  Q{i + 1}: [{q['topic']}] {q['question_text'][:80]}...")
            return questions[:num_questions]
        else:
            log.warning(f"  Batch returned only {len(questions) if questions else 0} questions, padding with fallback")
            questions = questions or []
            # Pad with fallback
            existing_topics = [q["topic"] for q in questions]
            while len(questions) < num_questions:
                fb = _single_fallback(parsed_resume, role, chunks, existing_topics)
                questions.append(fb)
                existing_topics.append(fb["topic"])
            return questions[:num_questions]

    except RateLimitHit:
        log.error("Rate limit hit during batch generation. Falling back for this request only.")
        return _generate_all_fallback(parsed_resume, role, chunks, num_questions)

    except Exception as e:
        log.error(f"Batch generation failed: {e}. Using fallback.")
        return _generate_all_fallback(parsed_resume, role, chunks, num_questions)


class RateLimitHit(Exception):
    """Raised when OpenRouter returns 429 or daily limit error."""
    pass


def _generate_all_fallback(
    parsed_resume: dict,
    role: str,
    chunks: list,
    num_questions: int,
) -> list[dict]:
    """Generate all questions from resume skills without LLM."""
    log.info(f"Generating {num_questions} fallback questions from resume skills...")

    questions = []
    existing_topics = []

    for _ in range(num_questions):
        q = _single_fallback(parsed_resume, role, chunks, existing_topics)
        questions.append(q)
        existing_topics.append(q["topic"])

    return questions


def _single_fallback(
    parsed_resume: dict,
    role: str,
    chunks: list,
    existing_topics: list[str],
) -> dict:
    """Generate one smart fallback question using resume data."""
    skills = parsed_resume.get("skills", [])
    projects = parsed_resume.get("notable_projects", [])
    experience = parsed_resume.get("experience_level", "mid")

    # Filter out already-used skills
    used_lower = {t.lower() for t in existing_topics}
    available_skills = [s for s in skills if s.lower() not in used_lower]

    if not available_skills:
        available_skills = skills if skills else ["machine learning"]

    skill = random.choice(available_skills)
    chunk_ids = [c.id for c in chunks] if chunks else []

    # Generate contextual question templates based on experience
    templates = {
        "junior": [
            f"Can you explain the fundamental concepts behind {skill} and describe how you've used it in a project?",
            f"What are the key advantages and limitations of {skill}? Give a concrete example from your experience.",
            f"Walk me through how you would approach a problem using {skill}. What steps would you take?",
        ],
        "mid": [
            f"Describe a challenging problem you solved using {skill}. What trade-offs did you consider?",
            f"How does {skill} compare to alternative approaches? When would you choose one over the other?",
            f"Explain the internal workings of {skill} and how understanding them helped you debug or optimise a real project.",
        ],
        "senior": [
            f"How would you architect a production system that leverages {skill} at scale? What pitfalls would you anticipate?",
            f"Describe a situation where {skill} was the wrong choice. What did you learn, and what would you use instead?",
            f"If you were mentoring a junior developer on {skill}, what are the most common misconceptions you'd address?",
        ],
    }

    level_templates = templates.get(experience, templates["mid"])
    question_text = random.choice(level_templates)

    return {
        "question_text": question_text,
        "topic": skill,
        "difficulty": experience,
        "source_concept": "resume-based fallback (LLM unavailable)",
        "source_chunks": chunk_ids,
    }
