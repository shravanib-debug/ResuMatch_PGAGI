"""
resume_service.py — Resume Parsing Service
===========================================
Extracts text from uploaded PDF resumes and uses LLM to parse
structured data (skills, domains, experience, projects).
"""

import os
import re
import json
import logging
import pdfplumber
from google import genai
from config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract raw text from PDF bytes using pdfplumber."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        text_parts = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    finally:
        os.unlink(tmp_path)


def parse_resume_with_llm(raw_text: str) -> dict:
    """
    Use LLM to extract structured data from resume text.

    Returns:
        {
            "skills": ["Python", "PyTorch", ...],
            "domains": ["deep learning", "NLP", ...],
            "experience_level": "junior" | "mid" | "senior",
            "notable_projects": ["built X", "designed Y", ...],
            "experience_years": 3
        }
    """
    # Truncate to avoid token limits (resumes are usually short)
    truncated = raw_text[:4000]

    prompt = f"""Extract structured data from this resume text. Return ONLY valid JSON.

Resume text:
---
{truncated}
---

Extract and return this exact JSON structure:
{{
  "skills": ["list of technical skills mentioned"],
  "domains": ["list of domain areas like 'deep learning', 'NLP', 'computer vision'"],
  "experience_level": "junior or mid or senior (based on years of experience and role seniority)",
  "notable_projects": ["brief descriptions of notable projects mentioned"],
  "experience_years": 0
}}

Rules:
- skills: extract specific technologies, frameworks, languages, and techniques
- domains: extract broad areas of expertise
- experience_level: "junior" (<2 years), "mid" (2-5 years), "senior" (5+ years)
- notable_projects: summarize each project in one sentence
- experience_years: estimate total years of relevant experience

Return ONLY the JSON. No explanation."""

    try:
        client = genai.Client(api_key=settings.google_api_key)
        
        response = client.models.generate_content(
            model=settings.llm_model,
            contents=prompt,
        )
        raw = response.text.strip()

        # Strip markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE).strip()

        data = json.loads(raw)
        log.info(f"Resume parsed: {len(data.get('skills', []))} skills, {data.get('experience_level', 'unknown')} level")
        return data

    except Exception as e:
        log.error(f"Resume parsing LLM call failed: {e}")
        return _fallback_parse(raw_text)


def _fallback_parse(raw_text: str) -> dict:
    """Simple heuristic extraction when LLM fails."""
    text_lower = raw_text.lower()

    # Extract common ML/DS skills by keyword matching
    known_skills = [
        "python", "pytorch", "tensorflow", "keras", "scikit-learn", "pandas",
        "numpy", "sql", "java", "c++", "r", "spark", "docker", "kubernetes",
        "aws", "gcp", "azure", "git", "linux", "matlab",
    ]
    skills = [s for s in known_skills if s in text_lower]

    known_domains = [
        "machine learning", "deep learning", "natural language processing",
        "computer vision", "data science", "artificial intelligence",
        "reinforcement learning", "nlp",
    ]
    domains = [d for d in known_domains if d in text_lower]

    return {
        "skills": skills or ["python", "machine learning"],
        "domains": domains or ["machine learning"],
        "experience_level": "mid",
        "notable_projects": [],
        "experience_years": 2,
    }
