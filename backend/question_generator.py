"""
question_generator.py — Interview Question Generator
=====================================================
Prompt engineering core for generating interview questions from
retrieved textbook context + candidate resume.

Takes:
    - parsed_resume  : structured resume dict
    - role           : 'aiml' or 'datascience'
    - context_chunks : list of RetrievedChunk from HybridRetriever
    - prior_questions: list of question dicts already asked this session

Returns:
    Structured question dict with question_text, topic, difficulty, source_concept.

Usage:
    from question_generator import QuestionGenerator
    gen = QuestionGenerator()
    question = gen.generate(parsed_resume, role, chunks, prior_questions)
"""

import os
import re
import json
import random
import logging

from google import genai
from dataclasses import dataclass

log = logging.getLogger(__name__)

from config import get_settings

# ── Config ────────────────────────────────────────────────────────────────────

LLM_MODEL = get_settings().llm_model


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class GeneratedQuestion:
    """One interview question with metadata."""
    question_text: str
    topic: str
    difficulty: str
    source_concept: str
    source_chunks: list[str]   # chunk IDs used to generate this question

    def to_dict(self) -> dict:
        return {
            "question_text": self.question_text,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "source_concept": self.source_concept,
            "source_chunks": self.source_chunks,
        }


# ── QuestionGenerator ────────────────────────────────────────────────────────

class QuestionGenerator:
    """
    Generates interview questions by combining retrieved textbook context
    with candidate resume data.

    Stateless aside from the LLM client — safe to reuse across sessions.
    """

    def __init__(self):
        self.llm = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))
        log.info("QuestionGenerator initialised.")

    # ── Batch Generation (preferred — 1 LLM call for all questions) ──────

    def generate_batch(
        self,
        parsed_resume: dict,
        role: str,
        context_chunks: list,
        num_questions: int = 5,
    ) -> list[dict]:
        """
        Generate ALL questions in a SINGLE LLM call.

        This drops API usage from 10+ calls to 1.
        Raises rag_service.RateLimitHit on 429/402 errors.
        """
        from services.rag_service import RateLimitHit

        prompt = self._build_batch_prompt(parsed_resume, role, context_chunks, num_questions)

        try:
            full_prompt = self._batch_system_prompt(num_questions) + "\n\n" + prompt
            response = self.llm.models.generate_content(
                model=LLM_MODEL,
                contents=full_prompt,
            )
            raw = response.text.strip()
            return self._parse_batch_response(raw, context_chunks)

        except Exception as e:
            error_str = str(e)
            # Detect rate limit / quota errors — DON'T retry, surface immediately
            if "429" in error_str or "402" in error_str or "rate limit" in error_str.lower():
                log.error(f"Rate limit hit during batch generation: {e}")
                raise RateLimitHit(str(e))
            log.error(f"Batch question generation failed: {e}")
            raise

    def _batch_system_prompt(self, num_questions: int) -> str:
        return f"""You are a senior technical interviewer for AI/ML and Data Science roles.
Generate exactly {num_questions} targeted interview questions based on:
1. The candidate's resume (skills, projects, experience level)
2. Retrieved textbook content (ground questions in this content)

Rules:
- Generate exactly {num_questions} questions
- Each question MUST cover a DIFFERENT topic — no repeats
- Questions MUST be answerable using concepts from the provided textbook context
- Do NOT ask yes/no questions — ask questions requiring explanation or analysis
- Calibrate difficulty to the candidate's experience level
- Reference the candidate's specific skills or projects where relevant

Respond with ONLY a valid JSON array of {num_questions} objects:
[
  {{
    "question_text": "Your interview question here",
    "topic": "short topic label (e.g. backpropagation, regularization)",
    "difficulty": "junior|mid|senior",
    "source_concept": "section/concept from the textbook"
  }},
  ...
]

No explanation, no markdown fences, ONLY the JSON array."""

    def _build_batch_prompt(
        self,
        parsed_resume: dict,
        role: str,
        context_chunks: list,
        num_questions: int,
    ) -> str:
        """Build prompt for batch question generation."""
        skills     = ", ".join(parsed_resume.get("skills", []))
        domains    = ", ".join(parsed_resume.get("domains", []))
        experience = parsed_resume.get("experience_level", "mid")
        projects   = "\n".join(
            f"  - {p}" for p in parsed_resume.get("notable_projects", [])
        )

        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            source = os.path.basename(chunk.source) if hasattr(chunk, 'source') else "unknown"
            section = chunk.section_title if hasattr(chunk, 'section_title') else "unknown"
            context_parts.append(
                f"[Chunk {i}] (Section: {section} | Source: {source})\n{chunk.text}"
            )
        context_str = "\n\n---\n\n".join(context_parts) if context_parts else "No context available."

        return f"""=== CANDIDATE PROFILE ===
Role: {role}
Experience Level: {experience}
Skills: {skills}
Domains: {domains}
Notable Projects:
{projects}

=== RETRIEVED TEXTBOOK CONTEXT ===
(You MUST ground your questions in this content.)

{context_str}

=== TASK ===
Generate exactly {num_questions} interview questions for this candidate.
Each question should:
1. Be grounded in the textbook context above
2. Relate to the candidate's skills or projects
3. Cover a UNIQUE topic (all {num_questions} questions must be on different topics)
4. Match the {experience} experience level
5. Require explanation or analysis (not yes/no)
"""

    def _parse_batch_response(self, raw: str, context_chunks: list) -> list[dict]:
        """Parse the LLM's batch JSON response into a list of question dicts."""
        # Strip markdown fences if present
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE).strip()

        chunk_ids = [c.id for c in context_chunks] if context_chunks else []

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            log.warning(f"Failed to parse batch JSON. Raw: {raw[:300]}")
            # Try extracting JSON array
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    log.error("Could not extract JSON array from batch response.")
                    return []
            else:
                return []

        if not isinstance(data, list):
            log.error(f"Batch response is not a list: {type(data)}")
            return []

        questions = []
        for item in data:
            if isinstance(item, dict) and "question_text" in item:
                questions.append({
                    "question_text": item.get("question_text", ""),
                    "topic": item.get("topic", "general"),
                    "difficulty": item.get("difficulty", "mid"),
                    "source_concept": item.get("source_concept", "textbook"),
                    "source_chunks": chunk_ids,
                })

        return questions

    # ── Single Generation (kept for backwards compatibility) ─────────────

    def generate(
        self,
        parsed_resume: dict,
        role: str,
        context_chunks: list,
        prior_questions: list[dict],
    ) -> GeneratedQuestion:
        """
        Generate one interview question.

        Args:
            parsed_resume   : {skills, domains, experience_level, notable_projects}
            role            : 'aiml' or 'datascience'
            context_chunks  : list of RetrievedChunk from retriever
            prior_questions : list of question dicts already generated this session

        Returns:
            GeneratedQuestion with structured data
        """
        prompt = self._build_prompt(parsed_resume, role, context_chunks, prior_questions)

        try:
            full_prompt = self._system_prompt() + "\n\n" + prompt
            response = self.llm.models.generate_content(
                model=LLM_MODEL,
                contents=full_prompt,
            )
            raw = response.text.strip()
            return self._parse_response(raw, context_chunks)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "402" in error_str:
                log.error(f"Rate limit hit: {e}")
                # Don't retry — fall through to fallback immediately
            else:
                log.error(f"Question generation LLM call failed: {e}")
            return self._fallback_question(parsed_resume, context_chunks)

    # ── Prompt Construction ──────────────────────────────────────────────────

    def _system_prompt(self) -> str:
        return """You are a senior technical interviewer for AI/ML and Data Science roles.
Your job is to generate ONE targeted interview question based on:
1. The candidate's resume (skills, projects, experience level)
2. Retrieved textbook content (your primary source — you MUST ground your question in this content)
3. Topics already covered (you MUST NOT repeat these)

Rules:
- Ask exactly ONE question
- The question MUST be answerable using concepts from the provided textbook context
- Do NOT ask yes/no questions — ask questions that require explanation or analysis
- Calibrate difficulty to the candidate's experience level
- Reference the candidate's specific skills or projects where relevant
- Do NOT ask generic questions like "What is machine learning?"

Respond with ONLY valid JSON in this exact format:
{
  "question_text": "Your interview question here",
  "topic": "short topic label (e.g. backpropagation, regularization, CNN architecture)",
  "difficulty": "junior|mid|senior",
  "source_concept": "section/concept from the textbook that grounds this question"
}

No explanation, no markdown fences, ONLY the JSON object."""

    def _build_prompt(
        self,
        parsed_resume: dict,
        role: str,
        context_chunks: list,
        prior_questions: list[dict],
    ) -> str:
        """Build the full prompt with all context."""

        # Resume section
        skills     = ", ".join(parsed_resume.get("skills", []))
        domains    = ", ".join(parsed_resume.get("domains", []))
        experience = parsed_resume.get("experience_level", "mid")
        projects   = "\n".join(
            f"  - {p}" for p in parsed_resume.get("notable_projects", [])
        )

        # Context section (from retrieved chunks)
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            source = os.path.basename(chunk.source) if hasattr(chunk, 'source') else "unknown"
            section = chunk.section_title if hasattr(chunk, 'section_title') else "unknown"
            context_parts.append(
                f"[Chunk {i}] (Section: {section} | Source: {source})\n{chunk.text}"
            )
        context_str = "\n\n---\n\n".join(context_parts) if context_parts else "No context available."

        # Prior questions section
        if prior_questions:
            prior_str = "\n".join(
                f"  - Topic: {q.get('topic', 'unknown')} — {q.get('question_text', '')[:80]}..."
                for q in prior_questions
            )
        else:
            prior_str = "  None yet (this is the first question)"

        return f"""=== CANDIDATE PROFILE ===
Role: {role}
Experience Level: {experience}
Skills: {skills}
Domains: {domains}
Notable Projects:
{projects}

=== RETRIEVED TEXTBOOK CONTEXT ===
(You MUST ground your question in this content. Do not use general knowledge.)

{context_str}

=== TOPICS ALREADY COVERED ===
(Do NOT repeat these topics. Ask about something DIFFERENT.)

{prior_str}

=== TASK ===
Generate exactly ONE interview question for this candidate.
The question should:
1. Be grounded in the textbook context above
2. Relate to the candidate's skills or projects
3. Cover a topic NOT already asked about
4. Match the {experience} experience level
5. Require explanation or analysis (not yes/no)
"""

    # ── Response Parsing ─────────────────────────────────────────────────────

    def _parse_response(self, raw: str, context_chunks: list) -> GeneratedQuestion:
        """Parse the LLM JSON response into a GeneratedQuestion."""
        # Strip markdown fences if present
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            log.warning(f"Failed to parse question JSON, attempting extraction. Raw: {raw[:200]}")
            data = self._extract_json_fallback(raw)

        chunk_ids = [c.id for c in context_chunks] if context_chunks else []

        return GeneratedQuestion(
            question_text=data.get("question_text", "Explain a core concept from your area of expertise."),
            topic=data.get("topic", "general"),
            difficulty=data.get("difficulty", "mid"),
            source_concept=data.get("source_concept", "general knowledge"),
            source_chunks=chunk_ids,
        )

    def _extract_json_fallback(self, raw: str) -> dict:
        """Last-resort: try to find a JSON object anywhere in the response."""
        match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        log.error("Could not extract JSON from LLM response. Using defaults.")
        return {}

    def _fallback_question(self, parsed_resume: dict, context_chunks: list) -> GeneratedQuestion:
        """Generate a safe fallback question when LLM fails entirely."""
        skills = parsed_resume.get("skills", ["machine learning"])
        skill = random.choice(skills) if skills else "machine learning"
        chunk_ids = [c.id for c in context_chunks] if context_chunks else []

        return GeneratedQuestion(
            question_text=f"Can you explain how {skill} works and describe a scenario where you applied it in practice?",
            topic=skill,
            difficulty=parsed_resume.get("experience_level", "mid"),
            source_concept="general knowledge (LLM fallback)",
            source_chunks=chunk_ids,
        )
