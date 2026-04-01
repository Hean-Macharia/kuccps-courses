import io
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import logging

logger = logging.getLogger(__name__)

class CoursePDFGenerator:
    """Generate PDF reports for qualified courses"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1e3c72'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Heading style
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2c5282'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        ))
        
        # Subheading style
        self.styles.add(ParagraphStyle(
            name='CustomSubheading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#4a5568'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        ))
        
        # Info style
        self.styles.add(ParagraphStyle(
            name='InfoStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#718096'),
            spaceAfter=6
        ))
        
        # Course name style
        self.styles.add(ParagraphStyle(
            name='CourseName',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=3,
            fontName='Helvetica-Bold'
        ))
        
        # Normal text style
        self.styles.add(ParagraphStyle(
            name='CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=6
        ))
    
    def generate_courses_pdf(self, email, index_number, courses_by_level, total_courses, mpesa_receipt=None):
        """Generate PDF with all qualified courses
        
        Args:
            email: User's email address
            index_number: User's KCSE index number
            courses_by_level: Dict with levels as keys and list of courses as values
            total_courses: Total number of courses across all levels
            mpesa_receipt: M-Pesa receipt number (optional)
        
        Returns:
            BytesIO object containing the PDF
        """
        buffer = io.BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Story (content) list
        story = []
        
        # Add header section
        story.extend(self._create_header_section(email, index_number, mpesa_receipt, total_courses))
        
        # Add summary section
        story.extend(self._create_summary_section(courses_by_level))
        
        # Add courses by level
        for level, courses in courses_by_level.items():
            if courses:
                story.extend(self._create_level_section(level, courses))
                # Add page break after each level except the last
                if level != list(courses_by_level.keys())[-1]:
                    story.append(PageBreak())
        
        # Add footer with generation timestamp
        story.extend(self._create_footer(mpesa_receipt))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer
    
    def _create_header_section(self, email, index_number, mpesa_receipt, total_courses):
        """Create header section with user info"""
        elements = []
        
        # Title
        elements.append(Paragraph("KUCCPS Courses Checker", self.styles['CustomTitle']))
        
        # User Information Table
        info_data = [
            ["Email:", email],
            ["KCSE Index Number:", index_number],
            ["M-Pesa Receipt:", mpesa_receipt or "N/A"],
            ["Total Qualified Courses:", str(total_courses)],
            ["Generated On:", datetime.now().strftime("%B %d, %Y at %I:%M %p")]
        ]
        
        info_table = Table(info_data, colWidths=[1.5*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e3c72')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2d3748')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 20))
        
        # Important note
        note_text = """
        <font color="#e53e3e"><b>IMPORTANT:</b></font> 
        This is a list of courses you qualify for based on your KCSE grades. 
        For official placement, please apply through the KUCCPS portal (students.kuccps.net).
        """
        elements.append(Paragraph(note_text, self.styles['InfoStyle']))
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_summary_section(self, courses_by_level):
        """Create summary section with course counts by level"""
        elements = []
        
        elements.append(Paragraph("Course Summary", self.styles['CustomHeading']))
        
        # Summary table
        summary_data = [["Course Level", "Number of Courses"]]
        total = 0
        
        level_display = {
            'degree': 'Degree Programs (C+ and above)',
            'diploma': 'Diploma Programs (C- and above)',
            'certificate': 'Certificate Programs (D+ and above)',
            'artisan': 'Artisan Programs (D and above)',
            'kmtc': 'KMTC Medical Programs',
            'ttc': 'Teacher Training Programs'
        }
        
        for level, courses in courses_by_level.items():
            count = len(courses)
            if count > 0:
                display_name = level_display.get(level, level.title())
                summary_data.append([display_name, str(count)])
                total += count
        
        summary_data.append(["<b>TOTAL</b>", f"<b>{total}</b>"])
        
        summary_table = Table(summary_data, colWidths=[3.5*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3c72')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _format_requirements(self, course):
        """Format course requirements properly, returning 'None' if empty"""
        try:
            # Check if minimum_subject_requirements exists
            if 'minimum_subject_requirements' not in course:
                return "None"
            
            reqs = course['minimum_subject_requirements']
            
            # Check if reqs is None or empty
            if reqs is None:
                return "None"
            
            # Check if it's a dictionary and not empty
            if isinstance(reqs, dict):
                if len(reqs) == 0:
                    return "None"
                
                # Format requirements
                requirements = []
                for subj, grade in reqs.items():
                    if subj and grade:
                        # Clean up subject names
                        subj_clean = subj.replace('_', ' ').title()
                        requirements.append(f"{subj_clean}: {grade}")
                
                if requirements:
                    return ', '.join(requirements[:3])  # Limit to 3 requirements
                else:
                    return "None"
            
            # If reqs is a list or other type
            if isinstance(reqs, list) and len(reqs) > 0:
                return ', '.join(str(r) for r in reqs[:3])
            
            # Default fallback
            return "None"
            
        except Exception as e:
            logger.error(f"Error formatting requirements: {e}")
            return "None"
    
    def _create_level_section(self, level, courses):
        """Create section for a specific course level"""
        elements = []
        
        level_titles = {
            'degree': '🎓 DEGREE PROGRAMS',
            'diploma': '📚 DIPLOMA PROGRAMS',
            'certificate': '📜 CERTIFICATE PROGRAMS',
            'artisan': '🔧 ARTISAN PROGRAMS',
            'kmtc': '🏥 KMTC PROGRAMS',
            'ttc': '👨‍🏫 TEACHER TRAINING PROGRAMS'
        }
        
        title = level_titles.get(level, f"{level.upper()} PROGRAMS")
        elements.append(Paragraph(title, self.styles['CustomHeading']))
        elements.append(Spacer(1, 10))
        
        # Calculate how many courses per page to avoid overflow
        courses_per_page = 25
        
        for i in range(0, len(courses), courses_per_page):
            chunk = courses[i:i + courses_per_page]
            
            # Create table for this chunk
            table_data = [["#", "Programme Name", "Institution", "Code", "Requirements"]]
            
            for idx, course in enumerate(chunk, start=i+1):
                # Get course details with safe defaults
                course_name = course.get('programme_name') or course.get('course_name', 'N/A')
                institution = course.get('institution_name', 'N/A')
                code = course.get('programme_code') or course.get('course_code', 'N/A')
                
                # Format requirements using the new method
                req_text = self._format_requirements(course)
                
                # Truncate long text for table display
                if len(course_name) > 50:
                    course_name = course_name[:47] + "..."
                if len(institution) > 40:
                    institution = institution[:37] + "..."
                if len(req_text) > 60:
                    req_text = req_text[:57] + "..."
                
                table_data.append([
                    str(idx),
                    Paragraph(course_name, self.styles['CustomNormal']),
                    Paragraph(institution, self.styles['CustomNormal']),
                    code,
                    Paragraph(req_text, self.styles['CustomNormal'])
                ])
            
            # Create table with appropriate column widths
            col_widths = [0.5*inch, 2*inch, 1.8*inch, 0.8*inch, 2.2*inch]
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (3, 0), (3, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 15))
            
            # Add page break if more chunks remain
            if i + courses_per_page < len(courses):
                elements.append(PageBreak())
        
        # Add spacing after level section
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_footer(self, mpesa_receipt=None):
        """Create footer with disclaimer"""
        elements = []
        
        # Format the receipt number for display
        receipt_display = mpesa_receipt if mpesa_receipt else "XXXXXX"
        
        disclaimer_text = f"""
        <font color="#718096" size="8">
        <hr/>
        <b>Disclaimer:</b> This document is generated by KUCCPS Courses Checker (kuccpscourses.co.ke), an independent platform.
        This is not an official KUCCPS document. All information is based on available data and may be subject to change.
        For official placement, always refer to the KUCCPS portal (students.kuccps.net).<br/><br/>
        <b>How to access this report again:</b> Visit kuccpscourses.co.ke/verify-payment and enter your M-Pesa receipt number ({receipt_display}) and KCSE index number.
        <br/><br/>
        Generated on {datetime.now().strftime("%B %d, %Y at %I:%M %p")}
        </font>
        """
        
        elements.append(Paragraph(disclaimer_text, self.styles['Normal']))
        
        return elements


def generate_courses_pdf(email, index_number, courses_by_level, total_courses, mpesa_receipt=None):
    """Wrapper function to generate PDF"""
    generator = CoursePDFGenerator()
    return generator.generate_courses_pdf(email, index_number, courses_by_level, total_courses, mpesa_receipt)