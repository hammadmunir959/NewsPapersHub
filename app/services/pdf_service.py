import os
import logging
import time
from typing import List, Dict, Any, Optional
from reportlab.platypus import (
    BaseDocTemplate, Paragraph, FrameBreak, PageBreak,
    NextPageTemplate, HRFlowable, Flowable, Frame, PageTemplate
)
from reportlab.lib.pagesizes import A3
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from bs4 import BeautifulSoup

from app.core.config import (
    PDF_MARGIN, PDF_COL_GAP, PDF_CONFIG,
    PDF_FRONT_MASTHEAD_HEIGHT, PDF_SECTION_MASTHEAD_HEIGHT,
    PDF_MASTHEAD_COL_GAP, PDF_RUNNING_HEADER_HEIGHT
)
from app.models.schemas import PaperSuccessResponse

logger = logging.getLogger(__name__)

# --------------------- Styles ---------------------
def get_newspaper_styles():
    """Return a dict of named ParagraphStyle objects used throughout."""
    styles = {
        'NewsBody': ParagraphStyle(
            name='NewsBody', fontName='Times-Roman', fontSize=10,
            leading=12, alignment=TA_JUSTIFY, firstLineIndent=15, spaceAfter=6
        ),
        'LeadHeadline': ParagraphStyle(
            name='LeadHeadline', fontName='Times-Bold', fontSize=38,
            leading=40, alignment=TA_LEFT, spaceAfter=15
        ),
        'Headline': ParagraphStyle(
            name='Headline', fontName='Times-Bold', fontSize=20,
            leading=22, alignment=TA_LEFT, spaceAfter=8, spaceBefore=12
        ),
        'Byline': ParagraphStyle(
            name='Byline', fontName='Helvetica-Bold', fontSize=8,
            leading=10, alignment=TA_LEFT, spaceAfter=10
        ),
        'BulletBody': ParagraphStyle(
            name='BulletBody', fontName='Times-Bold', fontSize=12,
            leading=15, alignment=TA_LEFT, spaceAfter=15
        ),
        'SectionTitle': ParagraphStyle(
            name='SectionTitle', fontName='Times-Roman', fontSize=28,
            leading=32, alignment=TA_CENTER, spaceAfter=20
        )
    }
    return styles

# --------------------- Section State (context) ---------------------
class SectionState:
    """Simple data holder passed through the build to track current section."""
    __slots__ = ('section_name', 'date_str', 'newspaper_display_name')
    def __init__(self):
        self.section_name = ""
        self.date_str = ""
        self.newspaper_display_name = "NEWS"

class SectionSwitch(Flowable):
    """Unrenderable flowable that signals a section change to the document."""
    def __init__(self, state: SectionState, section_name: str, display_name: str = ""):
        super().__init__()
        self.width = self.height = 0
        self._state = state
        self._section_name = section_name
        self._display_name = display_name

    def draw(self):
        self._state.section_name = self._section_name
        if self._display_name:
            self._state.newspaper_display_name = self._display_name

# --------------------- Mastheads ---------------------
class NewspaperMasthead(Flowable):
    """Front‑page masthead driven by newspaper config."""
    def __init__(self, date_str: str, config: dict, width: float = 762, height: float = 150):
        super().__init__()
        self.width = width
        self.height = height
        self.date_str = date_str
        self.config = config
        # Parse display date
        try:
            from datetime import datetime as dt
            clean_date = date_str.replace("_rss", "")
            d = dt.strptime(clean_date, "%Y-%m-%d")
            self.day = d.strftime("%A")
            self.formatted_date = d.strftime("%B %d, %Y")
        except Exception:
            logger.warning("Could not parse date '%s', using raw", date_str)
            self.day = "Monday"
            self.formatted_date = date_str

    def draw(self):
        c = self.canv
        c.saveState()
        mid_x = self.width / 2.0

        # Tagline
        tagline = self.config.get("tagline", "")
        if tagline:
            c.setFont("Helvetica", 9)
            c.drawCentredString(mid_x, self.height - 18, tagline)

        # Portrait
        portrait_path = self.config.get("portrait_path")
        if portrait_path and os.path.exists(portrait_path):
            c.drawImage(portrait_path, 10, self.height - 180, width=160, height=130,
                        mask='auto', preserveAspectRatio=True)

        # Logo text
        logo_text = self.config.get("logo_text", "NEWS")
        font_name = self.config.get("masthead_font", "Times-Bold")
        font_size = self.config.get("masthead_font_size", 80)
        c.setFont(font_name, font_size)
        c.drawCentredString(mid_x + 30, 40, logo_text)

        # Date and location
        c.setFont("Helvetica", 9)
        top_y = self.height - 20
        c.drawRightString(self.width - 15, top_y, self.day)
        c.drawRightString(self.width - 15, top_y - 12, self.formatted_date)

        location = self.config.get("location", "")
        if location:
            c.setLineWidth(1)
            c.line(self.width - 80, top_y - 25, self.width - 10, top_y - 25)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(self.width - 45, top_y - 38, location.upper())
        c.restoreState()

class SectionMasthead(Flowable):
    """Generic section divider with centered title and double rules."""
    def __init__(self, section_name: str, width: float = 762, height: float = 60):
        super().__init__()
        self.width = width
        self.height = height
        self.section_name = section_name.upper()

    def draw(self):
        c = self.canv
        c.saveState()
        c.setLineWidth(1.0)
        c.line(0, self.height - 2, self.width, self.height - 2)
        c.setFont("Times-Bold", 45)
        c.drawCentredString(self.width / 2.0, self.height / 2.0 - 15, self.section_name)
        c.line(0, 2, self.width, 2)
        c.restoreState()

# --------------------- Document Template ---------------------
class NewspaperDocTemplate(BaseDocTemplate):
    """Document template that draws a persistent header on inner pages."""
    def __init__(self, filename, state: SectionState, **kwargs):
        super().__init__(filename, **kwargs)
        self._state = state
        self._front_page_ids = {'FrontPage', 'SectionPage'}

    def afterPage(self):
        # Don't draw header on front‑page templates or when no section is set
        pt_id = getattr(self.pageTemplate, 'id', '')
        if pt_id in self._front_page_ids or not self._state.section_name:
            return
        c = self.canv
        c.saveState()
        pw, ph = self.pagesize
        top_y = ph - PDF_MARGIN + 6
        c.setFont("Times-Bold", 14)
        c.drawString(PDF_MARGIN, top_y, self._state.newspaper_display_name)
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(pw - PDF_MARGIN, top_y, self._state.section_name.upper())
        c.setLineWidth(2.5)
        c.line(PDF_MARGIN, top_y - 10, pw - PDF_MARGIN, top_y - 10)
        c.restoreState()

# --------------------- PDF Builder ---------------------
class PDFBuilder:
    """Assembles the full PDF from section data using a NewspaperDocTemplate."""
    def __init__(self, newspaper: str, date_str: str, config: Optional[dict] = None):
        self.newspaper = newspaper
        self.date_str = date_str
        # Merge with global config if not provided
        self.config = config or PDF_CONFIG.get(newspaper, PDF_CONFIG["dawn"])
        self.styles = get_newspaper_styles()
        self.state = SectionState()
        self.state.date_str = date_str
        self.state.newspaper_display_name = self.config.get("display_name", newspaper.upper())

    def _create_frames(self, top_of_columns: float, prefix: str) -> List[Frame]:
        col_count = PDF_CONFIG["global"]["col_count"]
        usable_width = A3[0] - 2 * PDF_MARGIN
        col_width = (usable_width - PDF_COL_GAP * (col_count - 1)) / col_count
        col_height = top_of_columns - PDF_MARGIN
        gap = self.config.get("masthead_gap", 40)  # configurable gap
        return [
            Frame(
                PDF_MARGIN + i * (col_width + PDF_COL_GAP),
                PDF_MARGIN,
                col_width,
                col_height,
                id=f"{prefix}_{i}",
                leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0,
                showBoundary=self.config.get("debug_frames", False)
            )
            for i in range(col_count)
        ]

    def _make_templates(self) -> List[PageTemplate]:
        page_width, page_height = A3
        usable_width = page_width - 2 * PDF_MARGIN
        gap = self.config.get("masthead_gap", 40)

        # Front page: masthead + columns
        masthead_y = page_height - PDF_MARGIN - PDF_FRONT_MASTHEAD_HEIGHT
        front_masthead_frame = Frame(
            PDF_MARGIN, masthead_y, usable_width, PDF_FRONT_MASTHEAD_HEIGHT,
            id='masthead', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
            showBoundary=self.config.get("debug_frames", False)
        )
        front_col_frames = self._create_frames(masthead_y - gap, 'front')

        # Section page: section masthead + columns
        sec_masthead_y = page_height - PDF_MARGIN - PDF_SECTION_MASTHEAD_HEIGHT
        sec_masthead_frame = Frame(
            PDF_MARGIN, sec_masthead_y, usable_width, PDF_SECTION_MASTHEAD_HEIGHT,
            id='section_masthead', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
            showBoundary=self.config.get("debug_frames", False)
        )
        sec_col_frames = self._create_frames(sec_masthead_y - gap, 'section')

        # Normal page: just columns (header drawn by afterPage)
        normal_col_frames = self._create_frames(
            page_height - PDF_MARGIN - PDF_RUNNING_HEADER_HEIGHT, 'normal'
        )

        return [
            PageTemplate(id='FrontPage', frames=[front_masthead_frame] + front_col_frames),
            PageTemplate(id='SectionPage', frames=[sec_masthead_frame] + sec_col_frames),
            PageTemplate(id='NormalPage', frames=normal_col_frames),
        ]

    def _build_story(self, sections_data: List[Dict[str, Any]]) -> list:
        story = []
        usable_width = A3[0] - 2 * PDF_MARGIN

        for idx, section in enumerate(sections_data):
            title = section.get('title', 'NEWS')
            logger.info("Adding section: %s (%d articles)", title, len(section.get('articles', [])))

            is_front = (idx == 0) or (title.upper() == "FRONT PAGE")

            if is_front:
                story.append(NextPageTemplate('FrontPage'))
                if idx > 0:
                    story.append(PageBreak())
                story.append(NewspaperMasthead(self.date_str, self.config, width=usable_width))
                story.append(SectionSwitch(self.state, title, self.state.newspaper_display_name))
                story.append(FrameBreak())
                story.append(NextPageTemplate('NormalPage'))
            else:
                story.append(NextPageTemplate('SectionPage'))
                story.append(PageBreak())
                story.append(SectionMasthead(title, width=usable_width))
                story.append(SectionSwitch(self.state, title, self.state.newspaper_display_name))
                story.append(FrameBreak())
                story.append(NextPageTemplate('NormalPage'))

            # Articles
            for art_idx, art in enumerate(section.get('articles', [])):
                headline = art.get('title', '').strip()
                if headline:
                    story.append(Paragraph(headline, self.styles['Headline']))
                content = art.get('content', '')
                if content:
                    soup = BeautifulSoup(content, "html.parser")
                    for p in soup.find_all("p"):
                        text = p.get_text().strip()
                        if text:
                            story.append(Paragraph(text, self.styles['NewsBody']))
                story.append(HRFlowable(width="100%", thickness=0.75, color="black",
                                        spaceBefore=6, spaceAfter=8))
        return story

    def build(self, output_path: str, sections_data: List[Dict[str, Any]]):
        """Create the PDF file at output_path."""
        doc = NewspaperDocTemplate(
            output_path,
            self.state,
            pagesize=A3,
            leftMargin=PDF_MARGIN,
            rightMargin=PDF_MARGIN,
            topMargin=PDF_MARGIN,
            bottomMargin=PDF_MARGIN
        )
        doc.addPageTemplates(self._make_templates())
        story = self._build_story(sections_data)
        logger.info("Starting PDF build for %s - %s", self.newspaper, self.date_str)
        try:
            doc.build(story)
            logger.info("PDF successfully saved to %s", output_path)
        except Exception as exc:
            logger.exception("PDF build failed")
            raise RuntimeError(f"Failed to build PDF: {exc}") from exc

# --------------------- PDF Service ---------------------
class PDFService:
    """Thin orchestration service that uses PDFBuilder."""

    @staticmethod
    def _build_pdf(sections_data: List[Dict[str, Any]], output_path: str,
                   newspaper: str, date_str: str):
        """Build the PDF (blocking) – intended to run in a thread executor."""
        builder = PDFBuilder(newspaper, date_str)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        builder.build(output_path, sections_data)

    @staticmethod
    def _build_response(newspaper: str, date_str: str, pdf_path: str) -> PaperSuccessResponse:
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        return PaperSuccessResponse(
            newspaper=newspaper,
            date=date_str,
            file_name=os.path.basename(pdf_path),
            path=pdf_path,
            pages=0,
            size_mb=round(size_mb, 2),
        )