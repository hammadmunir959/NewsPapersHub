# DAWN ePaper API

A FastAPI backend that generates downloadable PDFs of the [Dawn ePaper](https://epaper.dawn.com) for any given date. Submit a date → server scrapes page images → assembles a PDF → download it.

## Tech Stack

- **FastAPI** — async web framework with auto-docs
- **httpx** — async HTTP client for image downloading
- **img2pdf** — lossless JPEG-to-PDF assembly
- **Pillow** — image validation

## Prerequisites

- Python 3.11+
- pip

## Setup

```bash
# Clone and enter the project
cd NewsPapersHub

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Server starts at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

## API Reference

### Health Check
```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

### Generate PDF
```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-04-12"}'
# → {"job_id": "...", "status": "pending", "message": "Job queued"}
```

### Poll Status
```bash
curl http://localhost:8000/api/status/{job_id}
# → {"job_id": "...", "status": "done", "date": "2026-04-12", "pdf_url": "/api/pdf/..."}
```

### Download PDF
```bash
curl http://localhost:8000/api/pdf/{job_id} --output dawn.pdf
```

## Notes

- **Local development only** — not for production use
- Jobs are stored in-memory (lost on server restart)
- Date must be within the last 30 days
- Duplicate date requests return the existing job
