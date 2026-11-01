FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed \
    ANONYMIZED_TELEMETRY=False

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the models in so a restart never depends on downloading them.
RUN python -c "from fastembed import TextEmbedding as E; from fastembed.rerank.cross_encoder import TextCrossEncoder as C; E('sentence-transformers/all-MiniLM-L6-v2'); C('Xenova/ms-marco-MiniLM-L-6-v2')"

COPY . .

# Run unprivileged; Chroma needs write access to its folder.
RUN useradd -u 1000 -m app && chown -R app:app /app
USER app

EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
