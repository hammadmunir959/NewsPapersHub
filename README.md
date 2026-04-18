# NewsPapersHub API

**NewsPapersHub** is a high-performance, asynchronous REST API powered by **FastAPI** that automates the extraction, formatting, and generation of print-ready newspaper PDFs. It is designed with a scalable, configuration-driven architecture to easily support multiple publications.

Currently supported newspapers:
- **Dawn** (Text-based, high-fidelity broadsheet layout)
- **The News International** (Image-based e-paper merging)

---

## Features & Capabilities

### Dawn Newspaper (Text & Layout Extraction)
- **RSS-Driven Discovery:** Uses live RSS feeds (Home, Pakistan, World, Business, Latest News, Magazines, etc.) to discover all critical articles of the day, ensuring 100% coverage.
- **Playwright Full-Text Extraction:** Connects to discovered article URLs using Headless Chromium to extract the full story securely and reliably.
- **Resilient Fallback Mechanism:** If an article's full-text extraction fails (e.g., due to a timeout or network error), the system gracefully falls back to the RSS summary, ensuring that no news is lost in the final PDF.
- **Automated Broadsheet PDF Layout:** Uses `ReportLab` to dynamically generate a multi-column, print-ready newspaper PDF, complete with authentic mastheads, section headers, and article separation lines.

### The News International (E-Paper Image Merging)
- **Multi-City Support:** Download the daily e-paper for specific cities including **Islamabad, Karachi, Lahore, Peshawar**, and **Rawalpindi**.
- **Page Assembly:** Seamlessly downloads high-resolution page scans and intelligently merges them into a single, cohesive PDF document using `Pillow`.
- **Descriptive Naming Convention:** Automatically saves files using clear formatting: `TheNews_Islamabad_18_04_2026.pdf`.

### Core Infrastructure & Security
- **API Key Authentication:** All endpoints are protected via a robust API key system requiring an `Authorization` header, preventing unauthorized access.
- **Smart Caching:** Avoids redundant processing and network calls; if a PDF for a specific date and publication already exists on disk, the API instantly returns the cached file.
- **Configuration-Driven Design:** New newspapers, layouts, fonts, masthead logos, and taglines can be universally adjusted in `app/core/config.py` without modifying the core generation logic.

---

## Getting Started

### 1. Prerequisites
- Python `3.10+`
- Node.js (for Playwright dependencies, though Playwright handles chromium installation internally)

### 2. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/your-username/NewsPapersHub.git
cd NewsPapersHub

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python requirements
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 3. Configuration
Set up your environment variables. Create a `.env` file in the root directory:
```env
APP_API_KEY=your_super_secret_api_key_here
```

### 4. Running the API
Start the FastAPI server via Uvicorn:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
*The API will be available at `http://localhost:8000`*

---

## API Usage

All API requests must include the `Authorization` header using either the raw key or the Bearer format:
```http
Authorization: Bearer your_super_secret_api_key_here
```

### Endpoints

#### `GET /api/v1/dawn/{date_str}`
Generates or retrieves the **Dawn** newspaper PDF for a specific date.
- **Params:** `date_str` (Format: `YYYY-MM-DD`, e.g., `2026-04-18`)
- **Response:**
```json
[
  {
    "status": "success",
    "message": "Successfully generated PDF",
    "newspaper": "dawn",
    "date": "2026-04-18",
    "file_name": "dawn_18_04_2026.pdf",
    "saved_at": "/path/to/newspapers/dawn/dawn_18_04_2026.pdf",
    "pages": 1,
    "size_mb": 0.24
  }
]
```

#### `GET /api/v1/thenews/{date_str}`
Generates or retrieves **The News** PDFs for the specified cities.
- **Params:** `date_str` (Format: `YYYY-MM-DD`)
- **Query Params:** `city` (List of cities. Allowed values: `islamabad`, `karachi`, `lahore`, `peshawar`, `rawalpindi`. If omitted, generates for all configured cities).
- **Example Request:** `/api/v1/thenews/2026-04-18?city=islamabad&city=karachi`
- **Response:**
```json
[
  {
    "status": "success",
    "message": "Successfully downloaded PDF for islamabad",
    "newspaper": "thenews",
    "date": "2026-04-18",
    "file_name": "TheNews_Islamabad_18_04_2026.pdf",
    "saved_at": "/path/to/newspapers/thenews/TheNews_Islamabad_18_04_2026.pdf",
    "pages": 0,
    "size_mb": 10.11
  }
]
```

---

## System Architecture

- **`app/main.py`**: The FastAPI application initialization and routing.
- **`app/api/`**: API endpoints (`dawn.py`, `thenews.py`) and dependencies (`deps.py` for API Key auth).
- **`app/services/`**: The core logic:
  - `rss_service.py`: Discovers and parses articles from Dawn's RSS feeds.
  - `dawn_service.py`: Orchestrates Dawn scraping (using Playwright) and prepares content blocks.
  - `thenews_service.py`: Scrapes e-paper image URLs and merges them via Pillow.
  - `pdf_service.py`: A highly configurable PDF layout engine built on ReportLab.
- **`app/core/config.py`**: The single source of truth for all layout variables, paths, constants, and API configuration.
- **`newspapers/`**: The local storage directory where generated PDFs are cached.
