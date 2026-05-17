"""
Diagnostic script: print candidate heading lines from the first 30 pages of each PDF.
Run from backend/ directory: python debug_headings.py
"""
import pdfplumber
import os
import re

PDFS = [
    "knowledge_base/aiml/MachineLearningTomMitchell.pdf",
    "knowledge_base/aiml/2019BurkovTheHundred-pageMachineLearning.pdf",
    "knowledge_base/aiml/Bishop-Pattern-Recognition-and-Machine-Learning-2006.pdf",
    "knowledge_base/aiml/Artificial Intelligence, Machine Learning, and Deep Learning.pdf",
    "knowledge_base/datascience/Introduction to Machine Learning with Python ( PDFDrive.com )-min.pdf",
    "knowledge_base/datascience/Master Machine Learning Algorithms - Discover how they work and Implement Them From Scratch by Jason Brownlee (z-lib.org).pdf",
]

for pdf_path in PDFS:
    if not os.path.exists(pdf_path):
        print(f"\n--- SKIPPED (not found): {pdf_path}")
        continue

    print(f"\n{'='*70}")
    print(f"FILE: {os.path.basename(pdf_path)}")
    print(f"{'='*70}")

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:30], 1):
            raw = page.extract_text()
            if not raw:
                continue
            for line in raw.split("\n"):
                stripped = line.strip()
                if not stripped or len(stripped) > 80:
                    continue
                # Print lines that look like they COULD be headings:
                # - starts with uppercase
                # - or starts with a number (like "3.1 Gradient Descent")
                # - or is mostly uppercase
                is_candidate = (
                    (stripped[0].isupper() and len(stripped) < 60)
                    or re.match(r"^\d+\.?\d*\s+[A-Z]", stripped)
                    or (stripped.isupper() and len(stripped) > 3)
                )
                if is_candidate:
                    safe = stripped.encode('ascii', 'replace').decode('ascii')
                    print(f"  Page {i:3d}: {repr(safe)}")
