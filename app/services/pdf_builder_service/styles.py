from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT

def get_newspaper_styles():
    styles = getSampleStyleSheet()
    
    # Newspaper body text
    styles.add(ParagraphStyle(name='NewsBody',
                              fontName='Times-Roman',
                              fontSize=10,
                              leading=12,
                              alignment=TA_JUSTIFY,
                              firstLineIndent=15,
                              spaceAfter=10))
                              
    styles.add(ParagraphStyle(name='DropCapBody',
                              fontName='Times-Roman',
                              fontSize=10,
                              leading=12,
                              alignment=TA_JUSTIFY,
                              firstLineIndent=0,
                              spaceAfter=10))

    styles.add(ParagraphStyle(name='LeadHeadline',
                              fontName='Times-Bold',
                              fontSize=38,
                              leading=40,
                              alignment=TA_LEFT,
                              spaceAfter=15))

    styles.add(ParagraphStyle(name='Headline',
                              fontName='Times-Bold',
                              fontSize=20,
                              leading=22,
                              alignment=TA_LEFT,
                              spaceAfter=8,
                              spaceBefore=15))

    styles.add(ParagraphStyle(name='Byline',
                              fontName='Helvetica-Bold',
                              fontSize=8,
                              leading=10,
                              alignment=TA_LEFT,
                              spaceAfter=12,
                              textColor='black'))

    styles.add(ParagraphStyle(name='BulletBody',
                              fontName='Times-Bold',
                              fontSize=12,
                              leading=15,
                              alignment=TA_LEFT,
                              spaceAfter=15))
                              
    styles.add(ParagraphStyle(name='SectionTitle',
                              fontName='Times-Roman',
                              fontSize=28,
                              leading=32,
                              alignment=TA_CENTER,
                              spaceAfter=20,
                              spaceBefore=5))

    styles.add(ParagraphStyle(name='LogoText',
                              fontName='Times-Roman',
                              fontSize=130,
                              leading=110,
                              alignment=TA_CENTER,
                              spaceAfter=5))
                              
    styles.add(ParagraphStyle(name='FounderText',
                              fontName='Helvetica',
                              fontSize=9,
                              leading=11,
                              alignment=TA_CENTER,
                              spaceAfter=15,
                              textColor='dimgrey'))

    styles.add(ParagraphStyle(name='DateBar',
                              fontName='Helvetica-Bold',
                              fontSize=10,
                              leading=12,
                              alignment=TA_CENTER,
                              spaceBefore=10,
                              spaceAfter=15))

    return styles
