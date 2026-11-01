"""
summary_service.py — Interview Summary Generation
===================================================
Takes the full Q&A history for a session and generates a structured
assessment via LLM.
"""

import os
import re
import json
import logging
from google import genai
from config import get_settings
from llm_retry import generate_with_retry

log = logging.getLogger(__name__)
settings = get_settings()


def generate_summary(
    parsed_resume: dict,
    role: str,
    qa_pairs: list[dict],
) -> dict:
    """
    Generate a structured interview summary.

    Args:
        parsed_resume : candidate's parsed resume data
        role          : 'aiml' or 'datascience'
        qa_pairs      : list of {question_text, topic, answer_text} dicts

    Returns:
        {
            "overall_score": 7.5,
            "strengths": ["strong understanding of...", ...],
            "gaps": ["lacks depth in...", ...],
            "per_question": [
                {
                    "question_text": "...",
                    "answer_text": "...",
                    "assessment": "strong|adequate|weak",
                    "score": 8.0,
                    "feedback": "...",
                    "what_was_missed": "..."
                }, ...
            ],
            "recommendations": ["study X", "practice Y", ...]
        }
    """
    prompt = _build_summary_prompt(parsed_resume, role, qa_pairs)

    try:
        client = genai.Client(api_key=settings.google_api_key)
        
        full_prompt = _system_prompt() + "\n\n" + prompt
        response = generate_with_retry(client, full_prompt)
        raw = response.text.strip()

        # Strip markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE).strip()

        data = json.loads(raw)
        log.info(f"Summary generated: score={data.get('overall_score')}")
        return data

    except Exception as e:
        log.error(f"Summary generation failed: {e}")
        return _fallback_summary(qa_pairs)


def _system_prompt() -> str:
    return """You are a senior technical interviewer evaluating a candidate's performance.
You will receive the candidate's resume, the role they applied for, and all Q&A pairs from the interview.

Your task: generate a comprehensive, fair, and actionable assessment.

Respond with ONLY valid JSON in this exact structure:
{
  "overall_score": 7.5,
  "strengths": ["strength 1", "strength 2", ...],
  "gaps": ["gap 1", "gap 2", ...],
  "per_question": [
    {
      "question_text": "the question",
      "answer_text": "the candidate's answer",
      "assessment": "strong|adequate|weak",
      "score": 8.0,
      "feedback": "specific feedback on this answer",
      "what_was_missed": "concepts or details the candidate should have mentioned"
    }
  ],
  "recommendations": ["study recommendation 1", "practice recommendation 2", ...]
}

Scoring guide:
- 9-10: Exceptional — demonstrates deep, nuanced understanding
- 7-8: Strong — covers key concepts with good depth
- 5-6: Adequate — basic understanding but lacks depth
- 3-4: Weak — significant gaps in understanding
- 1-2: Poor — minimal relevant knowledge shown

No markdown, no explanation. ONLY the JSON."""


def _build_summary_prompt(
    parsed_resume: dict,
    role: str,
    qa_pairs: list[dict],
) -> str:
    skills = ", ".join(parsed_resume.get("skills", []))
    experience = parsed_resume.get("experience_level", "mid")

    qa_text = ""
    for i, qa in enumerate(qa_pairs, 1):
        qa_text += f"\n--- Question {i} (Topic: {qa.get('topic', 'unknown')}) ---\n"
        qa_text += f"Q: {qa['question_text']}\n"
        qa_text += f"A: {qa['answer_text']}\n"

    return f"""=== CANDIDATE PROFILE ===
Role: {role}
Experience Level: {experience}
Skills: {skills}

=== INTERVIEW Q&A ===
{qa_text}

=== TASK ===
Evaluate the candidate's performance across all questions.
Consider:
1. Technical accuracy of answers
2. Depth of understanding (surface-level vs. nuanced)
3. Ability to connect concepts to practical applications
4. Communication clarity
5. Alignment with the {experience} experience level expectations

Generate the structured assessment JSON."""


def _fallback_summary(qa_pairs: list[dict]) -> dict:
    """Minimal summary when LLM fails."""
    per_question = []
    for qa in qa_pairs:
        per_question.append({
            "question_text": qa.get("question_text", ""),
            "answer_text": qa.get("answer_text", ""),
            "assessment": "adequate",
            "score": 5.0,
            "feedback": "Assessment could not be generated automatically.",
            "what_was_missed": "N/A",
        })

    return {
        "overall_score": 5.0,
        "strengths": ["Completed the interview"],
        "gaps": ["Automated assessment unavailable"],
        "per_question": per_question,
        "recommendations": ["Review the topics covered in this interview"],
    }
