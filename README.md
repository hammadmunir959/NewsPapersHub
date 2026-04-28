# NewsPapersHub — Asynchronous Newspaper Generation Pipeline

> **RSS scraping · Headless browser extraction · Programmatic PDF rendering · Real-time SSE task tracking**

Pakistani news publishers don't expose clean APIs. Getting a structured, readable edition of **Dawn** or **The News International** requires stitching together RSS feeds, content extraction from JavaScript-rendered pages, and deterministic multi-column PDF layout — all without blocking the caller.

**NewsPapersHub** solves this as a production-grade FastAPI service. It follows a **hybrid execution model**: leveraging asynchronous I/O for web scraping and real-time streaming, while offloading CPU-intensive parsing and PDF rendering to thread executors to maintain a responsive event loop.

```
Client  →  instant task id  →  subscribe to SSE stream  →  get real-time updates
               ↓
      Background pipeline (Async I/O + Threaded CPU):
      RSS feeds → Playwright (Async) → BeautifulSoup (Threaded) → ReportLab (Threaded)
```

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| **API** | FastAPI + Uvicorn | Async REST + SSE streaming server |
| **Task System** | SQLite + Event Bus | Persistent state management + Real-time dispatch |
| **Scraping** | Playwright (Chromium) | High-performance async headless extraction |
| **Parsing** | BeautifulSoup4 | Structured content extraction (Offloaded to Threads) |
| **PDF Rendering** | ReportLab | Programmatic A3 newspaper layout (Offloaded to Threads) |
| **Persistence** | SQLite | Reliable across-restart task tracking |
| **Feed Parsing** | feedparser | RSS article discovery & date filtering |
| **Validation** | Pydantic v2 | Strict request/response schema enforcement |

---

## System Architecture

```
                        ┌──────────────────────────────┐
                        │         External World        │
                        │  dawn.com RSS  │ e.thenews.pk │
                        └──────┬─────────────┬──────────┘
                               │             │
                    ┌──────────▼─────────────▼──────────┐
                    │         Service Layer              │
                    │                                    │
                    │  DawnService          TheNewsService│
                    │  ┌──────────────┐  ┌────────────┐ │
                    │  │ RSS (Async)  │  │ HTTP (Img) │ │
                    │  └──────┬───────┘  └─────┬──────┘ │
                    │         │                │         │
                    │  ┌──────▼───────┐  ┌─────▼──────┐ │
                    │  │  Playwright  │  │   Pillow   │ │
                    │  │ (Semaphore)  │  │ (Merge)    │ │
                    │  └──────┬───────┘  └─────┬──────┘ │
                    │         │                │         │
                    │  ┌──────▼────────────────▼──────┐ │
                    │  │      PDFService (Threaded)    │ │
                    │  │   A3 · 4-col · mastheads      │ │
                    │  └──────────────┬───────────────┘ │
                    └─────────────────│─────────────────┘
                                      │
                    ┌─────────────────▼─────────────────┐
                    │       Disk Cache (newspapers/)     │
                    │  dawn/  ·  thenews/                │
                    │  [same date = instant return]      │
                    └─────────────────┬─────────────────┘
                                      │
               ┌───────────────────────▼────────────────────────┐
               │                  API Layer                     │
               │                                                │
               │  GET /dawn/{date}  →  id (instant)             │
               │  GET /stream/{id}  →  SSE Stream (real-time)   │
               │                                                │
               │  ┌───────────────────────────────────────────┐ │
               │  │       TaskManager (SQLite Persistent)      │ │
               │  │  ┌──────────┐  ┌──────────┐  ┌─────────┐  │ │
               │  │  │ Event Bus│  │ State DB │  │ Threads │  │ │
               │  │  └──────────┘  └──────────┘  └─────────┘  │ │
               │  └───────────────────────────────────────────┘ │
               └────────────────────────────────────────────────┘
```

---

## Project Structure

```
app/
├── main.py                  # App bootstrap: CORS, routers, logging
│
├── api/v1/                  ← API Layer
│   ├── endpoints.py         # Consolidated REST & SSE endpoints
│   └── deps.py              # Bearer token auth guard
│
├── core/                    ← Infrastructure Layer
│   ├── config.py            # All constants, RSS URLs, PDF layout config
│   └── task_manager.py      # SQLite connection & Event Bus core
│
├── services/                ← Processing Layer (Hybrid Async/Threaded)
│   ├── rss_service.py       # RSS feed parser + timezone-aware logic
│   ├── dawn_service.py      # Dawn pipeline: Playwright I/O + Threaded BS4
│   ├── thenews_service.py   # TheNews pipeline: Page discovery + Merging
│   ├── pdf_service.py       # ReportLab A3 layout engine (Threaded)
│   └── task_manager_service.py # Background task lifecycle & SSE dispatch
│
└── models/schemas.py        # Pydantic schemas (id, progress, path)
```

---

## Async Design & API Architecture

### 1. The Instant Task Pattern
NewsPapersHub uses a non-blocking request pattern. When a generation endpoint (e.g., `/dawn/{date}`) is hit, the system:
1.  **Registers** the task in the **SQLite** database.
2.  **Dispatches** the processing logic to FastAPI's `BackgroundTasks`.
3.  **Returns** a unique `id` to the client instantly.

### 2. Hybrid Execution Model (I/O vs CPU)
To prevent "blocking the loop," the system separates tasks:
-   **Async I/O**: Network requests (Playwright, Feed fetching) and SSE broadcasting run on the main event loop.
-   **Threaded CPU**: Heavy computation like **BeautifulSoup parsing** and **ReportLab PDF generation** is offloaded to a `ThreadPoolExecutor` via `loop.run_in_executor`. This ensures the API remains responsive even during a 2-minute PDF build.

### 3. Real-time Event Bus & SSE
The `TaskManagerService` implements a lightweight **Event Bus** subscription model:
-   Services `publish` updates (progress, state, messages) as they work.
-   The Bus broadcasts these updates to an `asyncio.Queue` for each subscriber.
-   The `/stream/{id}` endpoint consumes from this queue and yields **Server-Sent Events (SSE)**, allowing frontend clients to show frame-by-frame progress smoothly.

---

## Playwright Deep Dive: High-Efficiency Extraction

The `DawnService` utilizes Playwright (Chromium) for complex JavaScript-heavy extraction. It is optimized for speed and reliability:

### Concurrency & Throttling
-   **Semaphore Control**: Articles are scraped concurrently behind an `asyncio.Semaphore(4)`, preventing memory spikes while maintaining high throughput.
-   **Throttling**: A configurable delay is applied between requests within the semaphore to avoid IP rate-limiting from publishers.

### Aggressive Resource Interception
To reduce latency by up to 80%, Playwright is configured to **abort** all non-essential resource types before they are even downloaded:
-   **Blocked**: Images, Stylesheets, Fonts, Media, Tracking Scripts, Analytics.
-   **Allowed**: Only the primary HTML document for parsing.

### Pipelined Progress
The scraper uses `asyncio.as_completed` wrapped with indices. This allows the system to:
1.  Fire all scraping tasks at once.
2.  Emit an SSE update the *moment* any single article finishes.
3.  Collect results in original order for the final PDF layout.

### 🔵 The News Service — ePaper Image Scraper

**Problem:** The News International publishes scanned page images through an ePaper viewer, not parseable HTML. Text-based scraping is not viable.

**Solution:** The service crawls the ePaper viewer page-by-page, extracts the embedded `<img id="mainImg">` source URL, and downloads the full-resolution JPEG. These images are then merged into a single multi-page PDF using Pillow. To maintain responsiveness, the BeautifulSoup parsing of the viewer HTML is offloaded to a thread executor.

---

### 🔵 PDF Service — Newspaper Layout Engine

**Problem:** ReportLab's default templates are single-column. A newspaper layout requires A3 multi-column frames.

**Solution:** A custom `PersistentHeaderDocTemplate` implements a 4-column layout with mastheads and running headers. Since ReportLab's `doc.build()` is fully synchronous and CPU-bound, it is executed via `run_in_executor` to prevent the async event loop from stalling.

---

## API Reference

### Quick mental model
> Call a generation endpoint → get `id` → subscribe to `/api/v1/stream/{id}` for real-time progress → find PDF at `path` in the `result` array

---

### Generation Endpoints

#### `GET /api/v1/dawn/{date}`
Start Dawn PDF generation. Returns immediately.

| | |
|---|---|
| Response | `{ "id": "...", "state": "pending", "progress": 0, "message": "...", "result": null }` |

#### `GET /api/v1/thenews/{date}?city=islamabad`
Start The News PDF download. Supports concurrent multi-city generation.

| | |
|---|---|
| Query param | `city` (repeatable) — `islamabad` · `karachi` · `lahore` |
| Response | Same `TaskProgressResponse` shape as Dawn |

---

### Real-time Monitoring

#### `GET /api/v1/stream/{id}`
**Server-Sent Events (SSE)** endpoint. Recommended for UI integration.

- **Data format**: JSON string following the `TaskProgressResponse` schema.
- **Behavior**: Streams updates as they happen and closes automatically when the task reaches a terminal state (`completed` or `error`).

#### `GET /api/v1/tasks/progress/{id}` (Legacy Polling)
Standard REST polling. Returns the current state of the task in the SQLite database.

---

### Schema Definitions

#### `TaskProgressResponse`
| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | The unique task identifier |
| `state` | `enum` | `pending` · `discovering` · `downloading` · `building_pdf` · `completed` · `error` |
| `progress` | `int` | Completion percentage (0–100) |
| `message` | `string` | Human-readable current status |
| `result` | `list` | Metadata of generated PDFs (populated on `completed`) |

#### `PaperSuccessResponse`
| Field | Type | Description |
|---|---|---|
| `newspaper` | `string` | `dawn` or `thenews` |
| `date` | `string` | `YYYY-MM-DD` |
| `file_name` | `string` | Name of the generated file |
| `path` | `string` | Absolute path to the file on disk |
| `pages` | `int` | Number of pages in the PDF |
| `size_mb` | `float` | File size in megabytes |

---

## Engineering Challenges & Tradeoffs

### 1. Blocking the Async Loop
One of the primary challenges was integrating ReportLab (pure CPU/Sync) with Playwright (Async I/O). The solution involved a **Hybrid Execution Model** where all high-CPU calls (Parsing, PDF generation) are offloaded to dedicated worker threads, preserving the main loop for SSE streaming and network I/O.

### 2. Task Durability
Previous versions used in-memory dictionaries for task tracking, which were lost on server restarts. The current architecture migrates this to a **SQLite** backend, ensuring task states and results persist across reloads.

### 3. Real-time Progress Granularity
Transitioning from polling to **SSE** required an internal Event Bus. The `DawnService` now uses a wrapped `as_completed` pattern to emit progress updates the millisecond any single article is scraped, providing a much higher resolution of progress to the user.

---

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt
playwright install chromium

# 2. Run
uvicorn app.main:app --reload

# 3. Generate & Stream (Client side)
# GET /api/v1/dawn/2026-04-25 -> returns {"id": "UUID"}
# Subscribe to /api/v1/stream/UUID
```

---

**Author:** Hammad Munir · [github.com/hammadmunir959](https://github.com/hammadmunir959)
