"""Shared Gemini call: retry transient failures, then use a backup model."""
import logging
import ssl
import time

import httpx

from config import get_settings

log = logging.getLogger(__name__)
BACKUP_MODEL = "gemini-3.1-flash-lite"
NETWORK_ERRORS = (ssl.SSLError, ConnectionError, TimeoutError, httpx.TransportError)


def _is_transient(error: Exception) -> bool:
    return isinstance(error, NETWORK_ERRORS) or "503" in str(error) or "429" in str(error)


def generate_with_retry(client, prompt: str):
    primary = get_settings().llm_model
    last_error = None
    for model, delay in ((primary, 3), (primary, 8), (BACKUP_MODEL, 0)):
        try:
            return client.models.generate_content(model=model, contents=prompt)
        except Exception as e:
            if not _is_transient(e):
                raise
            last_error = e
            log.warning(f"{model} temporarily unavailable; trying next option.")
            time.sleep(delay)
    raise last_error
