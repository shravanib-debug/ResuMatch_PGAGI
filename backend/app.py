"""Hugging Face Gradio Space entry point: serves the FastAPI app on the Space's port."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
