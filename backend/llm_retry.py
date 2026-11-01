"""Shared Gemini call: retry transient failures, then use a backup model."""
import logging
import time

from config import get_settings

log = logging.getLogger(__name__)
BACKUP_MODEL = "gemini-3.1-flash-lite"


def generate_with_retry(client, prompt: str):
    primary = get_settings().llm_model
    last_error = None
    for model, delay in ((primary, 3), (primary, 8), (BACKUP_MODEL, 0)):
        try:
            return client.models.generate_content(model=model, contents=prompt)
        except Exception as e:
            if "503" not in str(e) and "429" not in str(e):
                raise
            last_error = e
            log.warning(f"{model} temporarily unavailable; trying next option.")
            time.sleep(delay)
    raise last_error
