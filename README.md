# NewsPapersHub API (v2.0.0)

A high-fidelity FastAPI backend for generating print-quality newspaper PDFs. Reconstructs clean, searchable, and professional broadsheet-style PDFs from article text and metadata using ReportLab.

## Features

- **Consolidated Architecture**: Streamlined to use only two core services—one for scraping and one for PDF generation.
- **Dynamic broadsheet Generation**: Scrapes article text and metadata to reconstruct a professional newspaper layout.
- **Disk Caching**: Automatically saves generated PDFs to local storage to serve subsequent requests instantly.
- **Lightweight Scraping**: Uses `httpx` and `BeautifulSoup4` for efficient, JS-free text extraction (no Playwright required).

## 🛠 Tech Stack

- **FastAPI**: Modern, high-performance web framework.
- **ReportLab**: Professional PDF generation library for vector-text layouts.
- **BeautifulSoup4**: For parsing and extracting article content from HTML.
- **httpx**: Lightweight, async HTTP client for scraping.

##  Project Structure

```text
NewsPapersHub/
├── app/
│   ├── api/            # Route handlers (v1)
│   ├── core/           # Config (shared constants)
│   ├── models/         # Pydantic schemas
│   ├── services/       # Core business logic
│   │   ├── scraper_service.py     # httpx-based text scraping
│   │   └── pdf_service.py         # ReportLab generation & orchestration
│   └── utils/          # Shared utility functions (dates, paths)
├── tests/              # Manual and automated tests
└── newspapers/         # Local PDF cache
```

## Setup

```bash
# Clone the repository
git clone https://github.com/your-repo/NewsPapersHub.git
cd NewsPapersHub

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## API Usage

### Health Check
`GET /health`

### Get / Generate Newspaper
`GET /api/v1/get-paper/{newspaper}/{date_str}`

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `newspaper` | Path | Yes | Name of the newspaper (e.g., `dawn`) |
| `date_str` | Path | Yes | Date in `YYYY-MM-DD` format |

**Example Request**:
```bash
curl "http://localhost:8000/api/v1/get-paper/dawn/2026-04-12"
```
