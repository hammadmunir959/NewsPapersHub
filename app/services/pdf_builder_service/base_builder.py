import os
from bs4 import BeautifulSoup
from reportlab.platypus import (BaseDocTemplate, Paragraph, Spacer, FrameBreak,
                                PageBreak, NextPageTemplate, HRFlowable, Flowable)
from reportlab.lib.pagesizes import A3
from reportlab.platypus import Frame, PageTemplate

from app.core.config import PDF_MARGIN, PDF_COL_GAP, PDF_HEADER_HEIGHT, PDF_SECTION_MASTHEAD_HEIGHT, PDF_CONFIG
from app.services.pdf_builder_service.styles import get_newspaper_styles

class PersistentHeaderDocTemplate(BaseDocTemplate):
    """Generic DocTemplate that supports persistent headers via afterPage callback."""
    
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self._current_section = ""
        self._date_str = ""
        self._builder_config = {}

    def afterPage(self):
        """Draw persistent header elements."""
        tid = getattr(self.pageTemplate, 'id', '')
        if tid in ('FrontPage', 'SectionPage'):
            return
            
        if not self._current_section:
            return

        canvas = self.canv
        canvas.saveState()
        
        page_width, page_height = self.pagesize
        margin = PDF_MARGIN
        top_y = page_height - margin + 5
        
        # Draw the header logic...
        # We can make this generic by passing a 'draw_header' callback or using config
        self._draw_persistent_header(canvas, page_width, page_height, margin, top_y)
        
        canvas.restoreState()

    def _draw_persistent_header(self, canvas, width, height, margin, top_y):
        # Default header (can be overridden by subclasses if needed)
        canvas.setFont("Times-Bold", 14)
        canvas.setFillColorRGB(0, 0, 0)
        canvas.drawString(margin, top_y, self._builder_config.get("logo_text", "NEWS"))
        
        canvas.setFont("Helvetica", 9)
        canvas.setFillColorRGB(0.35, 0.35, 0.35)
        canvas.drawString(margin + 60, top_y + 2, f"SUNDAY  {self._date_str}")
        
        page_num = str(canvas.getPageNumber())
        box_w, box_h = 28, 22
        box_x = width - margin - box_w
        canvas.setLineWidth(1.5)
        canvas.rect(box_x, top_y - 3, box_w, box_h)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawCentredString(box_x + box_w / 2, top_y + 3, page_num)
        
        canvas.setFont("Helvetica-Bold", 18) 
        canvas.drawRightString(box_x - 12, top_y, self._current_section.upper())
        
        canvas.setLineWidth(2.5)
        canvas.line(margin, top_y - 10, width - margin, top_y - 10)

class BaseNewspaperBuilder:
    """Abstract base class for building newspaper PDFs."""
    
    def __init__(self, newspaper_name: str, date_str: str):
        self.newspaper = newspaper_name.lower()
        self.date_str = date_str
        self.styles = get_newspaper_styles()
        self.config = {**PDF_CONFIG["global"], **PDF_CONFIG.get(self.newspaper, {})}
        
    def get_masthead(self) -> Flowable:
        """Override to return the front-page masthead flowable."""
        raise NotImplementedError

    def get_section_masthead(self, section_name: str) -> Flowable:
        """Override to return a section start masthead flowable."""
        raise NotImplementedError

    def extract_html_elements(self, html_str: str) -> list[dict]:
        soup = BeautifulSoup(html_str, 'html.parser')
        elements = []
        for element in soup.find_all(['p', 'li']):
            text = element.get_text(strip=True)
            if text:
                elements.append({'type': element.name, 'text': text})
        return elements

    def create_layout_templates(self, doc, dynamic_masthead_height=250):
        col_count = self.config["col_count"]
        col_gap = PDF_COL_GAP
        margin = PDF_MARGIN
        page_width, page_height = A3
        usable_width = page_width - 2 * margin
        usable_height = page_height - 2 * margin
        col_width = (usable_width - (col_gap * (col_count - 1))) / col_count

        # 1. Normal Page
        inner_top = page_height - margin - PDF_HEADER_HEIGHT
        frames_normal = []
        for i in range(col_count):
            x = margin + i * (col_width + col_gap)
            frames_normal.append(Frame(x, margin, col_width, inner_top - margin, id=f'col_{i}', leftPadding=2, rightPadding=2, topPadding=0, bottomPadding=0))
        normal_page = PageTemplate(id='NormalPage', frames=frames_normal)

        # 2. Front Page
        col_height_front = usable_height - dynamic_masthead_height - 20
        frames_front = [Frame(margin, page_height - margin - dynamic_masthead_height, usable_width, dynamic_masthead_height, id='masthead', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
        for i in range(col_count):
            x = margin + i * (col_width + col_gap)
            frames_front.append(Frame(x, margin, col_width, col_height_front, id=f'front_col_{i}', leftPadding=2, rightPadding=2, topPadding=10, bottomPadding=0))
        front_page = PageTemplate(id='FrontPage', frames=frames_front)

        # 3. Section Start Page
        header_frame_height = PDF_SECTION_MASTHEAD_HEIGHT + 10
        col_height_section = usable_height - header_frame_height - 20
        frames_section = [Frame(margin, page_height - margin - header_frame_height, usable_width, header_frame_height, id='section_masthead', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
        for i in range(col_count):
            x = margin + i * (col_width + col_gap)
            frames_section.append(Frame(x, margin, col_width, col_height_section, id=f'section_col_{i}', leftPadding=2, rightPadding=2, topPadding=10, bottomPadding=0))
        section_page = PageTemplate(id='SectionPage', frames=frames_section)

        return [front_page, section_page, normal_page]

    def build(self, sections_data: list[dict], output_path: str):
        # Dynamic height calc logic...
        dyn_height = 190  # Extra safety buffer for SectionSwitch, spacers, and float precision
        lead_bullets = ""
        if sections_data and sections_data[0].get('articles'):
            lead = sections_data[0]['articles'][0]
            p = Paragraph(lead['title'], self.styles['LeadHeadline'])
            _, h = p.wrap(A3[0] - 2*PDF_MARGIN, 1000)
            dyn_height += h
            elems = self.extract_html_elements(lead['content'])
            bullets = [e['text'] for e in elems if e['type'] == 'li']
            if bullets:
                lead_bullets = "    &bull;    ".join(bullets)
                p2 = Paragraph(lead_bullets, self.styles['BulletBody'])
                _, h2 = p2.wrap(A3[0] - 2*PDF_MARGIN, 1000)
                dyn_height += h2 + 40
            else:
                dyn_height += 30 # Space buffer if no bullets
                
        doc = PersistentHeaderDocTemplate(output_path, pagesize=A3)
        doc._date_str = self.date_str
        doc._builder_config = self.config
        doc.addPageTemplates(self.create_layout_templates(doc, dyn_height))

        story = []
        is_front = True
        for idx, section in enumerate(sections_data):
            title = section.get('title', f'Section {idx + 1}')
            
            if is_front:
                story.append(NextPageTemplate('FrontPage'))
                from app.services.pdf_builder_service.dawn_builder import SectionSwitch # Temporary for compatibility
                story.append(SectionSwitch(title, self.date_str))
                story.append(self.get_masthead())
                story.append(Spacer(1, 15))
                if section.get('articles'):
                    a = section['articles'][0]
                    story.append(Paragraph(a['title'], self.styles['LeadHeadline']))
                    if lead_bullets: story.append(Paragraph(lead_bullets, self.styles['BulletBody']))
                    story.append(HRFlowable(width="100%", thickness=2, color="black", spaceAfter=8))
                    story.append(FrameBreak())
                    if a.get('author'): story.append(Paragraph(f"BY {a['author'].upper()}", self.styles['Byline']))
                    for pt in [e['text'] for e in self.extract_html_elements(a['content']) if e['type'] == 'p']:
                        story.append(Paragraph(pt, self.styles['NewsBody']))
                    story.append(Spacer(1, 10))
                    story.append(HRFlowable(width="100%", thickness=1, color="gray", spaceAfter=10))
                    rest = section['articles'][1:]
                else: 
                    error_msg = section.get('error', "Front page articles could not be fetched.")
                    story.append(Spacer(1, 30))
                    story.append(Paragraph(f"<b>Notice:</b> {error_msg}", self.styles['NewsBody']))
                    story.append(FrameBreak())
                    rest = []
                story.append(NextPageTemplate('NormalPage'))
                is_front = False
            else:
                story.append(NextPageTemplate('SectionPage'))
                story.append(PageBreak())
                from app.services.pdf_builder_service.dawn_builder import SectionSwitch
                story.append(SectionSwitch(title, self.date_str))
                story.append(self.get_section_masthead(title))
                story.append(FrameBreak())
                story.append(NextPageTemplate('NormalPage'))
                rest = section.get('articles', [])
                
            # ── Render Section Content or Error ──
            if not section.get('articles'):
                error_msg = section.get('error', f"No articles found for the {title} section on this date.")
                from app.services.pdf_builder_service.styles import get_newspaper_styles
                st = get_newspaper_styles()
                story.append(Spacer(1, 40))
                story.append(Paragraph(f"<b>Notice:</b> {error_msg}", st['NewsBody']))
                story.append(Spacer(1, 20))
                story.append(HRFlowable(width="100%", thickness=1, color="gray"))
                continue

            for a in rest:
                story.append(Paragraph(a['title'], self.styles['Headline']))
                if a.get('author'): story.append(Paragraph(f"BY {a['author'].upper()}", self.styles['Byline']))
                for pt in [e['text'] for e in self.extract_html_elements(a['content']) if e['type'] == 'p']:
                    story.append(Paragraph(pt, self.styles['NewsBody']))
                story.append(Spacer(1, 8))
                story.append(HRFlowable(width="100%", thickness=1.5, color="black", spaceBefore=8, spaceAfter=8))

        doc.build(story)
        return output_path
