import os
import shutil
import logging
from reportlab.platypus import (BaseDocTemplate, Paragraph, FrameBreak,
                                 PageBreak, NextPageTemplate, HRFlowable, Flowable, Frame, PageTemplate)
from reportlab.lib.pagesizes import A3
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from app.core.config import (
    PDF_MARGIN, PDF_COL_GAP, PDF_FRONT_MASTHEAD_HEIGHT,
    PDF_SECTION_MASTHEAD_HEIGHT, PDF_MASTHEAD_COL_GAP, PDF_RUNNING_HEADER_HEIGHT,
    PDF_CONFIG
)

logger = logging.getLogger(__name__)

def get_newspaper_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='NewsBody', fontName='Times-Roman', fontSize=10,
        leading=12, alignment=TA_JUSTIFY, firstLineIndent=15, spaceAfter=6))
    styles.add(ParagraphStyle(
        name='LeadHeadline', fontName='Times-Bold', fontSize=38,
        leading=40, alignment=TA_LEFT, spaceAfter=15))
    styles.add(ParagraphStyle(
        name='Headline', fontName='Times-Bold', fontSize=20,
        leading=22, alignment=TA_LEFT, spaceAfter=8, spaceBefore=12))
    styles.add(ParagraphStyle(
        name='Byline', fontName='Helvetica-Bold', fontSize=8,
        leading=10, alignment=TA_LEFT, spaceAfter=10))
    styles.add(ParagraphStyle(
        name='BulletBody', fontName='Times-Bold', fontSize=12,
        leading=15, alignment=TA_LEFT, spaceAfter=15))
    styles.add(ParagraphStyle(
        name='SectionTitle', fontName='Times-Roman', fontSize=28,
        leading=32, alignment=TA_CENTER, spaceAfter=20))
    return styles

class SectionSwitch(Flowable):
    def __init__(self, section_name, date_str, display_name=""):
        super().__init__()
        self.width = self.height = 0
        self.section_name = section_name
        self.date_str = date_str
        self.display_name = display_name

    def draw(self):
        self.canv._doctemplate._current_section = self.section_name
        self.canv._doctemplate._date_str = self.date_str
        if self.display_name:
            self.canv._doctemplate._newspaper_display_name = self.display_name

class NewspaperMasthead(Flowable):
    def __init__(self, date_str, news_config, width=762, height=150):
        super().__init__()
        self.width, self.height, self.date_str = width, height, date_str
        self.news_config = news_config
        try:
            from datetime import datetime as dt
            clean_date = date_str.replace("_rss", "")
            d = dt.strptime(clean_date, "%Y-%m-%d")
            self.day = d.strftime("%A")
            self.formatted_date = d.strftime("%B %d, %Y")
        except Exception as e:
            logger.warning(f"Failed to parse date string '{date_str}': {e}")
            self.day, self.formatted_date = "Monday", date_str

    def draw(self):
        c = self.canv
        c.saveState()
        mid_x = self.width / 2.0
        
        # Tagline
        tagline = self.news_config.get("tagline", "")
        if tagline:
            c.setFont("Helvetica", 9)
            c.drawCentredString(mid_x, self.height - 18, tagline)
        
        portrait_path = self.news_config.get("portrait_path")
        if portrait_path and os.path.exists(portrait_path):
            c.drawImage(portrait_path, 10, self.height - 180, width=160, height=130, mask='auto', preserveAspectRatio=True)

        # Logo text
        logo_text = self.news_config.get("logo_text", "NEWS")
        font_name = self.news_config.get("masthead_font", "Times-Bold")
        font_size = self.news_config.get("masthead_font_size", 80)
        c.setFont(font_name, font_size)
        c.drawCentredString(mid_x + 30, 40, logo_text)
        
        # Date and location info
        c.setFont("Helvetica", 9)
        info_x = self.width - 15
        top_y = self.height - 20
        c.drawRightString(info_x, top_y, self.day)
        c.drawRightString(info_x, top_y - 12, self.formatted_date)
        
        location = self.news_config.get("location", "")
        if location:
            c.setLineWidth(1)
            c.line(self.width - 80, top_y - 25, self.width - 10, top_y - 25)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(self.width - 45, top_y - 38, location.upper())
        c.restoreState()

class SectionMasthead(Flowable):
    def __init__(self, section_name, date_str, width=762, height=60):
        super().__init__()
        self.width, self.height, self.section_name, self.date_str = width, height, section_name.upper(), date_str

    def draw(self):
        c = self.canv
        c.saveState()
        c.setLineWidth(1.0)
        c.line(0, self.height - 2, self.width, self.height - 2)
        c.setFont("Times-Bold", 45)
        c.drawCentredString(self.width / 2.0, (self.height / 2.0) - 15, self.section_name)
        c.line(0, 2, self.width, 2)
        c.restoreState()

class PersistentHeaderDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self._current_section = ""
        self._date_str = ""
        self._newspaper_display_name = "NEWS"

    def afterPage(self):
        pt_id = getattr(self.pageTemplate, 'id', '')
        if pt_id in ('FrontPage', 'SectionPage') or not self._current_section:
            return
        c = self.canv
        c.saveState()
        pw, ph = self.pagesize
        top_y = ph - PDF_MARGIN + 6
        c.setFont("Times-Bold", 14)
        c.drawString(PDF_MARGIN, top_y, self._newspaper_display_name)
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(pw - PDF_MARGIN, top_y, self._current_section.upper())
        c.setLineWidth(2.5)
        c.line(PDF_MARGIN, top_y - 10, pw - PDF_MARGIN, top_y - 10)
        c.restoreState()

class PDFService:
    @staticmethod
    def _build_pdf(sections_data, output_path, newspaper, date_str):
        styles = get_newspaper_styles()
        page_width, page_height = A3
        doc = PersistentHeaderDocTemplate(output_path, pagesize=A3, leftMargin=PDF_MARGIN, rightMargin=PDF_MARGIN, topMargin=PDF_MARGIN, bottomMargin=PDF_MARGIN)
        
        usable_width = page_width - 2 * PDF_MARGIN
        col_count = PDF_CONFIG["global"]["col_count"]
        col_width = (usable_width - PDF_COL_GAP * (col_count - 1)) / col_count

        SHOW_DEBUG_BOUNDARIES = 0
        # Set to 1 to pinpoint layout issues if needed
        SHOW_DEBUG_BOUNDARIES = 0

        def make_col_frames(top_of_columns, frame_id_prefix):
            col_height = top_of_columns - PDF_MARGIN
            logger.info(f"Creating frames for {frame_id_prefix} from y={PDF_MARGIN} to {top_of_columns} (height={col_height})")
            return [Frame(PDF_MARGIN + i * (col_width + PDF_COL_GAP), PDF_MARGIN, col_width, col_height, id=f"{frame_id_prefix}_{i}", leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0, showBoundary=SHOW_DEBUG_BOUNDARIES) for i in range(col_count)]

        # Increased gap for safety
        GAP = 40 
        
        # Masthead frames with NO padding to prevent rejection
        masthead_y = page_height - PDF_MARGIN - PDF_FRONT_MASTHEAD_HEIGHT
        front_masthead_frame = Frame(PDF_MARGIN, masthead_y, usable_width, PDF_FRONT_MASTHEAD_HEIGHT, id='masthead', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=SHOW_DEBUG_BOUNDARIES)
        front_col_top = masthead_y - GAP
        front_col_frames = make_col_frames(front_col_top, 'front')

        sec_masthead_y = page_height - PDF_MARGIN - PDF_SECTION_MASTHEAD_HEIGHT
        sec_masthead_frame = Frame(PDF_MARGIN, sec_masthead_y, usable_width, PDF_SECTION_MASTHEAD_HEIGHT, id='section_masthead', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=SHOW_DEBUG_BOUNDARIES)
        sec_col_top = sec_masthead_y - GAP
        sec_col_frames = make_col_frames(sec_col_top, 'section')

        normal_col_top = page_height - PDF_MARGIN - PDF_RUNNING_HEADER_HEIGHT
        normal_col_frames = make_col_frames(normal_col_top, 'normal')

        doc.addPageTemplates([
            PageTemplate(id='FrontPage', frames=[front_masthead_frame] + front_col_frames),
            PageTemplate(id='SectionPage', frames=[sec_masthead_frame] + sec_col_frames),
            PageTemplate(id='NormalPage', frames=normal_col_frames),
        ])

        logger.info(f"Starting PDF build for {newspaper} - {date_str}")
        
        # Get newspaper-specific config
        news_config = PDF_CONFIG.get(newspaper, PDF_CONFIG["dawn"]) 
        display_name = news_config.get("display_name", newspaper.upper())
        
        story = []
        for idx, section in enumerate(sections_data):
            title = section.get('title', 'NEWS')
            logger.info(f"Adding section: {title} with {len(section.get('articles', []))} articles")
            
            # Robust template selection: index 0 OR title "Front Page"
            is_front = (idx == 0) or (title.upper() == "FRONT PAGE")
            
            if is_front:
                story.append(NextPageTemplate('FrontPage'))
                # No PageBreak for the very first section
                if idx > 0: story.append(PageBreak()) 
                # NewspaperMasthead is now configuration-driven
                story.append(NewspaperMasthead(date_str, news_config, width=usable_width))
                story.append(SectionSwitch(title, date_str, display_name=display_name))
                story.append(FrameBreak())
                story.append(NextPageTemplate('NormalPage'))
            else:
                story.append(NextPageTemplate('SectionPage'))
                story.append(PageBreak())
                # SectionMasthead is now generic
                story.append(SectionMasthead(title, date_str, width=usable_width))
                story.append(SectionSwitch(title, date_str, display_name=display_name))
                story.append(FrameBreak())
                story.append(NextPageTemplate('NormalPage'))

            for art_idx, art in enumerate(section.get('articles', [])):
                headline = art.get('title', '').strip()
                logger.info(f"  Processing article {art_idx+1}: {headline[:50]}...")
                if headline: story.append(Paragraph(headline, styles['Headline']))
                
                content = art.get('content', '')
                if content:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, "html.parser")
                    for p in soup.find_all("p"):
                        text = p.get_text().strip()
                        if text: story.append(Paragraph(text, styles['NewsBody']))
                
                story.append(HRFlowable(width="100%", thickness=0.75, color="black", spaceBefore=6, spaceAfter=8))

        doc.build(story)

    @staticmethod
    def _build_response(newspaper, date_str, pdf_path, cached=False):
        from app.models.schemas import PaperSuccessResponse
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        return PaperSuccessResponse(
            status="success",
            message="Returned from cache" if cached else "Successfully generated PDF",
            newspaper=newspaper,
            date=date_str,
            file_name=os.path.basename(pdf_path),
            saved_at=pdf_path,
            pages=0 if cached else 1,
            size_mb=round(size_mb, 2),
        )