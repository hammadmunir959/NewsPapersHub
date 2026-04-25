# NewsPapersHub — Asynchronous Newspaper Generation Pipeline

> **RSS scraping · Headless browser extraction · Programmatic PDF rendering · Real-time task tracking**

Pakistani news publishers don't expose clean APIs. Getting a structured, readable edition of **Dawn** or **The News International** requires stitching together RSS feeds, content extraction from JavaScript-rendered pages, and deterministic multi-column PDF layout — all without blocking the caller.

**NewsPapersHub** solves this as a production-grade FastAPI service: any client sends a single HTTP request, gets a `task_id` back in milliseconds, and polls for progress while the pipeline runs in the background. The output is a print-quality, A3 newspaper-layout PDF saved to disk.

```
Client  →  instant task_id  →  poll progress  →  get PDF metadata
              ↓
     Background pipeline:
     RSS feeds → Playwright scraper → ReportLab renderer → cached PDF
```

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| **API** | FastAPI + Uvicorn | Async REST + WebSocket server |
| **Task System** | asyncio + BackgroundTasks | Non-blocking background execution |
| **Scraping** | Playwright (Chromium, headless) | JavaScript-rendered page extraction |
| **Feed Parsing** | feedparser | RSS article discovery & date filtering |
| **HTML Parsing** | BeautifulSoup4 | Structured content extraction |
| **PDF Rendering** | ReportLab | Programmatic A3 newspaper layout |
| **Image Processing** | Pillow | ePaper page scan merging |
| **Validation** | Pydantic v2 | Request/response schema enforcement |

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
                    │  │ RSSService   │  │ HTTP Fetch │ │
                    │  │ (feed parse) │  │ (images)   │ │
                    │  └──────┬───────┘  └─────┬──────┘ │
                    │         │                │         │
                    │  ┌──────▼───────┐  ┌─────▼──────┐ │
                    │  │  Playwright  │  │   Pillow   │ │
                    │  │ (semaphored) │  │ (merge PDF)│ │
                    │  └──────┬───────┘  └─────┬──────┘ │
                    │         │                │         │
                    │  ┌──────▼────────────────▼──────┐ │
                    │  │      PDFService (ReportLab)   │ │
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
              │                  API Layer                      │
              │                                                 │
              │  POST /dawn/{date}  →  task_id (instant)       │
              │  GET  /tasks/progress/{id}  →  state + pct     │
              │  WS   /ws/logs  →  live log stream             │
              │                                                 │
              │  ┌─────────────────────────────┐              │
              │  │  TaskManager (in-memory)     │              │
              │  │  PENDING → DISCOVERING →     │              │
              │  │  DOWNLOADING → BUILDING_PDF  │              │
              │  │  → COMPLETED / ERROR         │              │
              │  └─────────────────────────────┘              │
              └────────────────────────────────────────────────┘
```

---

## Project Structure

```
app/
├── main.py                  # App bootstrap: CORS, routers, logging
│
├── api/v1/                  ← API Layer
│   ├── dawn.py              # Dawn generation endpoint
│   ├── thenews.py           # The News endpoint (multi-city support)
│   ├── tasks.py             # Progress polling endpoint
│   ├── ws.py                # WebSocket live log streaming
│   └── deps.py              # Bearer token auth guard
│
├── core/                    ← Infrastructure Layer
│   ├── config.py            # All constants, RSS URLs, PDF layout config
│   ├── task_manager.py      # In-memory task lifecycle & state store
│   └── assets/              # Static assets (newspaper portrait images)
│
├── services/                ← Processing Layer
│   ├── rss_service.py       # RSS feed parser + timezone-aware date filter
│   ├── dawn_service.py      # Dawn pipeline: RSS → Playwright → PDF
│   ├── thenews_service.py   # TheNews pipeline: ePaper images → PDF
│   └── pdf_service.py       # ReportLab A3 newspaper layout engine
│
└── models/schemas.py        # Pydantic schemas + TaskState enum
```

---

## How Each Service Works

### 🔵 RSS Service — Timezone-Safe Article Discovery

**Problem:** Dawn's RSS feeds mix 10 content channels, include duplicate cross-posted articles, and timestamp articles in PKT (UTC+5) — which `feedparser` silently converts to UTC, causing date-boundary mismatches at midnight.

**Solution:** `RSSService` fetches all 10 channels concurrently, converts timestamps back to PKT before filtering, and deduplicates by URL. When Playwright fails to fetch an article body, the RSS `<summary>` field acts as a graceful content fallback — so the PDF always has something to render.

---

### 🔵 Dawn Service — Concurrent Scraping Pipeline

**Problem:** Dawn articles are JavaScript-rendered. RSS feeds give URLs but not full article body text. Naive sequential scraping of 40–80 articles would take minutes.

**Solution:** A single Playwright Chromium instance opens a `BrowserContext`, then dispatches all article fetches concurrently behind an `asyncio.Semaphore(4)` — protecting against rate-limiting while still achieving 4× parallelism. Each page aborts all non-HTML resource types (images, stylesheets, fonts) before they are downloaded, reducing per-page network load by ~80%.

**Pipeline:**

```
RSS feeds  →  article URL list  →  Semaphored Playwright fetch (4 concurrent)
          →  BeautifulSoup extraction  →  section grouping  →  PDFService
```

**Progress emitted at every stage** (5% → 10% → 20–80% → 85% → 100%).

**Caching:** If a PDF for the requested date already exists, the pipeline is skipped entirely and the cached result returned in <1ms.

---

### 🔵 The News Service — ePaper Image Scraper

**Problem:** The News International publishes scanned page images through an ePaper viewer, not parseable HTML. Text-based scraping is not viable.

**Solution:** The service crawls the ePaper viewer page-by-page (`/pindi/14-04-2026/page1`, `/page2`, …), extracts the embedded `<img id="mainImg">` source URL using regex, downloads the full-resolution JPEG, and continues until a 404 or missing image stops the loop. All page scans are merged into a single multi-page PDF using Pillow's `save_all=True` mode, which produces a byte-exact page-order merge without re-encoding.

Cities (Islamabad, Karachi, Lahore) are downloaded **concurrently** via `asyncio.gather()`. All blocking HTTP I/O runs in a thread pool via `loop.run_in_executor()`.

---

### 🔵 PDF Service — Newspaper Layout Engine

**Problem:** ReportLab's default `SimpleDocTemplate` is single-column and has no concept of mastheads, section pages, or running headers. Building an authentic newspaper layout requires a custom document engine.

**Solution:** A custom `PersistentHeaderDocTemplate` extends `BaseDocTemplate` and overrides `afterPage()` to inject a running header (newspaper name + current section) after every page. Three `PageTemplate` types govern layout:

| Template | Structure | Used for |
|---|---|---|
| `FrontPage` | Full masthead frame + 4 content columns | First page of each edition |
| `SectionPage` | Section banner frame + 4 content columns | First page of each section |
| `NormalPage` | 4 content columns + running header | Continuation pages |

Three custom `Flowable` subclasses handle layout state:
- **`NewspaperMasthead`** — Canvas-level drawing of title, tagline, date, location, portrait
- **`SectionMasthead`** — Section name between horizontal rules
- **`SectionSwitch`** — Zero-height flowable that updates `_current_section` on the doc template at render time, enabling the correct section name in the running header

**Typography:** `Times-Roman`/`Times-Bold` for print authenticity; justified body text with first-line indent; 4-level heading hierarchy (Lead → Headline → Byline → Body).

---

### 🔵 Task Manager — Background Task Lifecycle

**Problem:** PDF generation takes 30–120 seconds. Holding an HTTP connection open that long is not viable.

**Solution:** `TaskManager` is a singleton in-memory state store. Every background task is assigned a UUID at registration. Services call `task_manager.publish(task_id, state, percentage, message)` as they progress through stages. The polling endpoint reads from this store and returns in O(1).

**State machine:**

```
PENDING → DISCOVERING → DOWNLOADING → BUILDING_PDF → COMPLETED
                                                    ↘ ERROR
```

`run_and_track_task()` wraps every service call: if the function is a coroutine it is `await`ed; if synchronous (e.g., a blocking ReportLab render call) it is dispatched to a thread pool via `run_in_executor`, so the async event loop is never stalled.

> ⚠️ **Known limitation:** The task store is process-local in-memory. It does not survive restarts and does not scale across multiple workers. A production upgrade would replace it with Redis or a message queue (Celery/ARQ). This was a conscious design choice for the single-process deployment target.

---

## API Reference

### Quick mental model
> Call a generation endpoint → get `task_id` → poll `/tasks/progress/{id}` until `state = "completed"` → find PDF at `saved_at`

---

### Generation Endpoints

#### `GET /api/v1/dawn/{date_str}`
Start Dawn PDF generation. Returns immediately.

| | |
|---|---|
| Auth | `Authorization: Bearer <key>` |
| Path param | `date_str` — `YYYY-MM-DD` |
| Response | `{ "task_id": "...", "status": "started", "message": "..." }` |
| Errors | `400` invalid date · `403` bad key · `500` server error |

#### `GET /api/v1/thenews/{date_str}?city=islamabad&city=karachi`
Start The News PDF download. Supports concurrent multi-city generation.

| | |
|---|---|
| Auth | `Authorization: Bearer <key>` |
| Path param | `date_str` — `YYYY-MM-DD` |
| Query param (`city`, repeatable) | `islamabad` · `karachi` · `lahore` — defaults to all three |
| Response | Same `task_id` shape as Dawn |

---

### Monitoring Endpoints

#### `GET /api/v1/tasks/progress/{task_id}`
Poll task status. Always responds instantly — no long-poll.

**Response:**
```json
{
  "task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "state": "downloading",
  "percentage": 54,
  "message": "Scraped 24/44 articles...",
  "result": null
}
```

**`state` values:**

| State | Meaning |
|---|---|
| `pending` | Queued, not yet started |
| `discovering` | Reading RSS / detecting ePaper pages |
| `downloading` | Scraping article content / downloading images |
| `building_pdf` | ReportLab / Pillow rendering |
| `completed` | Done — `result` holds PDF metadata array |
| `error` | Failed — `message` holds error detail |

**Completed `result` shape:**
```json
[{
  "newspaper": "dawn",
  "date": "2026-04-25",
  "file_name": "dawn_25_04_2026.pdf",
  "saved_at": "/path/to/newspapers/dawn/dawn_25_04_2026.pdf",
  "size_mb": 1.84
}]
```

---

### Streaming Endpoint

#### `WS /api/v1/ws/logs`
Real-time log streaming. Useful for UI dashboards displaying live scraping progress.

Auth: `Authorization: Bearer <key>` header in the WebSocket handshake. Unauthorized connections are closed with `1008 Policy Violation`.

**Design:** A custom `logging.Handler` subclass is registered globally at startup. Every `logger.*()` call in the codebase broadcasts to all active WebSocket connections via `asyncio.create_task()` (fire-and-forget — broadcast never blocks the event loop). Multiple clients are supported simultaneously via an `active_connections` list. There is no backpressure mechanism — this is appropriate for internal/dev UI use, not public-facing consumers.

---

#### `GET /health`
No auth. Returns `{ "status": "ok" }`.

---

## Engineering Challenges & Tradeoffs

These are the non-obvious problems that shaped the architecture.

### 1. RSS Timezone Drift
`feedparser` normalizes all timestamps to UTC and discards timezone info. Dawn timestamps are PKT (UTC+5). Naive date comparison caused articles published between 00:00–05:00 PKT to be filtered into the wrong day. **Fix:** explicitly convert UTC back to PKT before date comparison.

### 2. JavaScript-Rendered Content
Dawn's article pages require JavaScript execution to render content. Static HTTP fetching (`requests`) returns skeletal HTML with no body text. **Fix:** Playwright's Chromium engine renders each page fully before extraction. Resource interception (`route.abort()` for images/CSS/fonts) reduces per-page latency significantly since non-text assets are never downloaded.

### 3. Blocking PDF Render in an Async Service
ReportLab's `doc.build()` is fully synchronous and CPU-bound. Calling it directly inside an `async def` would block the entire event loop for the duration of the render. **Fix:** `loop.run_in_executor(None, ...)` offloads it to the default thread pool, keeping the event loop free.

### 4. ReportLab Multi-Column Layout
ReportLab's standard templates have no concept of newspapers. Mastheads, section pages, and running headers all require custom `Flowable` subclasses and a patched `BaseDocTemplate.afterPage()` hook. The core challenge was maintaining `_current_section` state across a page boundary — solved with a zero-height `SectionSwitch` flowable that writes to the doc template's state at render time.

### 5. ePaper Page Boundary Detection
The News ePaper has no metadata endpoint for page count. **Fix:** the scraper iterates page numbers until `_fetch_page_image_url()` returns `None` (404 or no `mainImg` element), signaling end-of-edition. This is resilient to variable page counts across dates.

### 6. In-Memory Task Store Limitation
The current `TaskManager` stores task state in a Python dict. This is not durable (lost on restart), not shared across processes, and unbounded in memory if cleanup is never triggered. **Known.** For the single-process, local deployment target this is an acceptable tradeoff. A Redis-backed store or a queue system (Celery, ARQ) would be the natural scaling path.

---

## PDF Output

Generated PDFs are saved to `newspapers/` and cached permanently:

```
newspapers/
├── dawn/
│   └── dawn_25_04_2026.pdf                  # ~1.5–3 MB, A3, 4-column
└── thenews/
    ├── TheNews_Islamabad_25_04_2026.pdf      # ~8–15 MB (scanned images)
    ├── TheNews_Karachi_25_04_2026.pdf
    └── TheNews_Lahore_25_04_2026.pdf
```

| Metric | Dawn (text PDF) | The News (image PDF) |
|---|---|---|
| First generation | ~60–120 sec | ~30–60 sec per city |
| Cached repeat | < 1 ms | < 1 ms |
| Typical size | 1.5–3 MB | 8–20 MB |
| Format | A3, 4-column, text-selectable | Multi-page scanned image |

---

## Quick Start

```bash
# 1. Install
git clone https://github.com/hammadmunir959/NewsPapersHub.git
cd NewsPapersHub
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure
echo "APP_API_KEY=your-secret-key" > .env

# 3. Run
uvicorn app.main:app --reload --port 8000
```

```bash
# 4. Generate a Dawn edition
curl "http://localhost:8000/api/v1/dawn/2026-04-25" \
  -H "Authorization: Bearer your-secret-key"
# → {"task_id": "abc-123", "status": "started", ...}

# 5. Poll until done
curl "http://localhost:8000/api/v1/tasks/progress/abc-123" \
  -H "Authorization: Bearer your-secret-key"
# → {"state": "completed", "percentage": 100, "result": [...]}
```

Interactive docs: **`http://localhost:8000/docs`**

---

## Security

- All generation and polling routes are protected by a global `Depends(get_api_key)` guard injected at router registration — not per-endpoint.
- The WebSocket endpoint uses manual header authentication (FastAPI's `Depends` cannot intercept a WS handshake before connection acceptance).
- API key is environment-variable only — never hardcoded.

---

## Dependencies

```
fastapi>=0.111.0    uvicorn[standard]>=0.29.0    python-dotenv>=1.0.1
pydantic>=2.7.0     playwright                    beautifulsoup4
reportlab>=4.2.0    feedparser>=6.0.11            Pillow>=10.3.0
```

---

**Author:** Hammad Munir · [github.com/hammadmunir959](https://github.com/hammadmunir959)
