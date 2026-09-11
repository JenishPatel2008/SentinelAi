from pathlib import Path

from pypdf import PdfReader


pdf = Path(__file__).resolve().parents[1] / "Sentinel_AI_Border_Control_Unit_Complete_Guide.pdf"
reader = PdfReader(str(pdf))
texts = [page.extract_text() or "" for page in reader.pages]
required = [
    "SENTINEL AI",
    "1. Cover and scope",
    "2. What are we actually building?",
    "9. The AI and computer-vision pipeline",
    "29. If a judge asks how it works",
    "WebSockets",
    "SQLite",
]
print(f"exists={pdf.exists()} bytes={pdf.stat().st_size} pages={len(reader.pages)}")
print(f"blank_pages={[index + 1 for index, text in enumerate(texts) if len(text.strip()) < 40]}")
print(f"required_sections={{{', '.join(f'{item}: {any(item in text for text in texts)}' for item in required)}}}")
print(f"first_page_chars={len(texts[0])} last_page_chars={len(texts[-1])}")
print(f"page_sizes={sorted(set((float(page.mediabox.width), float(page.mediabox.height)) for page in reader.pages))}")
