import os
import random
from reportlab.platypus import Flowable
from app.services.pdf_builder_service.base_builder import BaseNewspaperBuilder

class SectionSwitch(Flowable):
    """Invisible flowable that updates the doc's current section name."""
    def __init__(self, section_name, date_str):
        super().__init__()
        self.width = 0 
        self.height = 0
        self._section_name = section_name
        self._date_str = date_str

    def draw(self):
        self.canv._doctemplate._current_section = self._section_name
        self.canv._doctemplate._date_str = self._date_str

class DawnMasthead(Flowable):
    """Draws the iconic Dawn masthead with Quaid portrait, DAWN logo, and metadata."""
    def __init__(self, date_str, width=762, height=140):
        super().__init__()
        self.width = width
        self.height = height
        self.date_str = date_str

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFont("Helvetica", 6)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(self.width / 2.0, self.height - 10, "F O U N D E D   B Y   Q U A I D - I - A Z A M   M O H A M M A D   A L I   J I N N A H")

        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "core", "assets")
        portrait_path = os.path.join(assets_dir, "quaid.jpg")
        if os.path.exists(portrait_path):
            c.drawImage(portrait_path, 40, 20, width=80, height=90)

        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.6, 0.6, 0.6)
        for i in range(11):
            y = 30 + i * 6
            c.line(130, y, self.width - 130, y)

        c.setFillColorRGB(1, 1, 1)
        c.rect(self.width / 2 - 130, 20, 260, 90, stroke=0, fill=1)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Times-Roman", 120)
        c.drawCentredString(self.width / 2.0, 30, "DAWN")

        rx = self.width - 10
        c.setFont("Helvetica", 8)
        c.drawRightString(rx, self.height - 35, "SUNDAY")
        c.drawRightString(rx, self.height - 45, self.date_str)
        c.drawRightString(rx, self.height - 55, "Shawwal 23, 1447")
        c.setLineWidth(0.5)
        c.line(self.width - 110, self.height - 60, rx, self.height - 60)
        c.restoreState()

class DawnSectionMasthead(Flowable):
    """Large header banner used at the start of Dawn sections."""
    def __init__(self, section_name, date_str, width=762, height=120):
        super().__init__()
        self.width = width
        self.height = height
        self.section_name = section_name.upper()
        self.date_str = date_str

    def draw(self):
        c = self.canv
        c.saveState()
        c.setLineWidth(2.0)
        c.line(0, self.height - 2, self.width, self.height - 2)
        c.setLineWidth(0.3)
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.line(0, self.height - 5, self.width, self.height - 5)
        
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 7)
        c.drawString(0, self.height - 15, f"DAWN SUNDAY {self.date_str}")
        
        max_width = self.width - 40
        font_size = 80
        c.setFont("Times-Bold", font_size)
        text_width = c.stringWidth(self.section_name, "Times-Bold", font_size)
        
        while text_width > max_width and font_size > 20:
            font_size -= 4
            c.setFont("Times-Bold", font_size)
            text_width = c.stringWidth(self.section_name, "Times-Bold", font_size)
            
        c.drawCentredString(self.width / 2.0, 35, self.section_name)
        
        c.setLineWidth(2.0)
        c.line(0, 15, self.width, 15)
        c.restoreState()

class DawnBuilder(BaseNewspaperBuilder):
    def __init__(self, date_str):
        super().__init__("dawn", date_str)
    
    def get_masthead(self) -> Flowable:
        return DawnMasthead(self.date_str)
    
    def get_section_masthead(self, section_name: str) -> Flowable:
        return DawnSectionMasthead(section_name, self.date_str)
