FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    ANONYMIZED_TELEMETRY=False

WORKDIR /app

# CPU-only torch keeps the image gigabytes smaller than the default GPU build.
COPY requirements.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Bake the models in so a restart never depends on downloading them.
RUN python -c "from sentence_transformers import SentenceTransformer as S, CrossEncoder as C; S('all-MiniLM-L6-v2'); C('cross-encoder/ms-marco-MiniLM-L-6-v2')"

COPY . .

# Hugging Face Spaces runs containers as UID 1000; Chroma needs write access.
RUN useradd -u 1000 -m app && chown -R app:app /app
USER app

EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
