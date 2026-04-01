import os
import logging
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64

logger = logging.getLogger(__name__)

# Try to import Brevo, but don't fail if not available
try:
    import brevo_python
    from brevo_python.rest import ApiException
    BREVO_AVAILABLE = True
except ImportError:
    try:
        import sib_api_v3_sdk as brevo_python
        from sib_api_v3_sdk.rest import ApiException
        BREVO_AVAILABLE = True
    except ImportError:
        BREVO_AVAILABLE = False
        logger.warning("Brevo Python SDK not installed. Email sending will use SMTP fallback.")

class EmailService:
    """Email service with multiple providers support"""
    
    def __init__(self):
        self.sender_email = os.getenv('BREVO_SENDER_EMAIL', 'info@kuccpscourses.co.ke')
        self.sender_name = os.getenv('BREVO_SENDER_NAME', 'KUCCPS Courses Checker')
        self.cc_email = os.getenv('BREVO_CC_EMAIL', 'courseschecker@gmail.com')
        
        # SMTP fallback settings
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        
        # Initialize Brevo if available
        self.api_key = os.getenv('BREVO_API_KEY')
        self.api_instance = None
        
        if BREVO_AVAILABLE and self.api_key:
            try:
                configuration = brevo_python.Configuration()
                configuration.api_key['api-key'] = self.api_key
                self.api_instance = brevo_python.TransactionalEmailsApi(brevo_python.ApiClient(configuration))
                logger.info("✅ Brevo API configured successfully")
            except Exception as e:
                logger.error(f"❌ Failed to configure Brevo: {e}")
                self.api_instance = None
        else:
            logger.info("ℹ️ Brevo not configured, will use SMTP fallback if available")
    
    def send_courses_report(self, email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer):
        """Send courses report email with PDF attachment"""
        
        # Try Brevo first if available
        if self.api_instance:
            try:
                return self._send_via_brevo(email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer)
            except Exception as e:
                logger.error(f"❌ Brevo failed, trying SMTP fallback: {e}")
        
        # Fallback to SMTP
        if self.smtp_user and self.smtp_password:
            try:
                return self._send_via_smtp(email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer)
            except Exception as e:
                logger.error(f"❌ SMTP also failed: {e}")
                return False
        
        # Log that email wasn't sent (for development)
        logger.warning(f"⚠️ No email provider configured. Would have sent email to {email} with {total_courses} courses.")
        logger.info(f"📧 Email content would have been: {self._generate_email_subject(index_number)}")
        return False
    
    def _send_via_brevo(self, email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer):
        """Send email using Brevo API"""
        
        # Prepare email subject and body
        subject = self._generate_email_subject(index_number)
        html_body = self._generate_email_html(email, index_number, mpesa_receipt, total_courses, courses_by_level)
        text_body = self._generate_email_text(email, index_number, mpesa_receipt, total_courses, courses_by_level)
        
        # Prepare attachment
        pdf_attachment = self._prepare_brevo_attachment(pdf_buffer, f"courses_report_{index_number}.pdf")
        
        # Create email object
        send_smtp_email = brevo_python.SendSmtpEmail(
            to=[{'email': email, 'name': email.split('@')[0]}],
            bcc=[{'email': self.cc_email, 'name': 'Admin'}],
            sender={'email': self.sender_email, 'name': self.sender_name},
            subject=subject,
            html_content=html_body,
            text_content=text_body,
            attachment=[pdf_attachment]
        )
        
        # Send email
        response = self.api_instance.send_transac_email(send_smtp_email)
        
        logger.info(f"✅ Email sent via Brevo to {email}. Message ID: {response}")
        return True
    
    def _send_via_smtp(self, email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer):
        """Send email using SMTP (fallback)"""
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{self.sender_name} <{self.sender_email}>"
        msg['To'] = email
        msg['Cc'] = self.cc_email
        msg['Subject'] = self._generate_email_subject(index_number)
        
        # Add body
        html_body = self._generate_email_html(email, index_number, mpesa_receipt, total_courses, courses_by_level)
        text_body = self._generate_email_text(email, index_number, mpesa_receipt, total_courses, courses_by_level)
        
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Add attachment
        attachment = self._prepare_smtp_attachment(pdf_buffer, f"courses_report_{index_number}.pdf")
        msg.attach(attachment)
        
        # Send email
        recipients = [email, self.cc_email]
        
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg, from_addr=self.sender_email, to_addrs=recipients)
        
        logger.info(f"✅ Email sent via SMTP to {email}")
        return True
    
    def _prepare_brevo_attachment(self, pdf_buffer, filename):
        """Prepare PDF attachment for Brevo"""
        pdf_buffer.seek(0)
        pdf_content = pdf_buffer.read()
        
        # Encode PDF content in base64 for Brevo
        encoded_pdf = base64.b64encode(pdf_content).decode('utf-8')
        
        return {
            'name': filename,
            'content': encoded_pdf
        }
    
    def _prepare_smtp_attachment(self, pdf_buffer, filename):
        """Prepare PDF attachment for SMTP"""
        pdf_buffer.seek(0)
        pdf_content = pdf_buffer.read()
        
        attachment = MIMEBase('application', 'pdf')
        attachment.set_payload(pdf_content)
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        
        return attachment
    
    def _generate_email_subject(self, index_number):
        """Generate email subject"""
        return f"Your KUCCPS Courses Report - {index_number}"
    
    def _generate_email_html(self, email, index_number, mpesa_receipt, total_courses, courses_by_level):
        """Generate HTML email content"""
        
        # Build level summaries
        level_summaries = []
        level_display = {
            'degree': '🎓 Degree Programs',
            'diploma': '📚 Diploma Programs',
            'certificate': '📜 Certificate Programs',
            'artisan': '🔧 Artisan Programs',
            'kmtc': '🏥 KMTC Medical Programs',
            'ttc': '👨‍🏫 Teacher Training Programs'
        }
        
        for level, courses in courses_by_level.items():
            if courses:
                count = len(courses)
                display = level_display.get(level, level.title())
                level_summaries.append(f"<li><strong>{display}:</strong> {count} courses</li>")
        
        level_summary_html = '\n'.join(level_summaries) if level_summaries else '<li>No courses found</li>'
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Your KUCCPS Courses Report</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #1e3c72 0%, #2c5282 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .content {{
                    background: #f7fafc;
                    padding: 30px;
                    border-left: 1px solid #e2e8f0;
                    border-right: 1px solid #e2e8f0;
                }}
                .footer {{
                    background: #edf2f7;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #718096;
                    border-radius: 0 0 10px 10px;
                    border: 1px solid #e2e8f0;
                }}
                .info-box {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    border-left: 4px solid #1e3c72;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}
                .button {{
                    display: inline-block;
                    background: #1e3c72;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 20px;
                }}
                .button:hover {{
                    background: #2c5282;
                }}
                h1 {{ margin: 0; font-size: 24px; }}
                h2 {{ color: #1e3c72; margin-top: 0; }}
                ul {{ padding-left: 20px; }}
                li {{ margin: 8px 0; }}
                .highlight {{ color: #1e3c72; font-weight: bold; }}
                hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎓 KUCCPS Courses Report</h1>
                <p>Your personalized course recommendations</p>
            </div>
            
            <div class="content">
                <p>Dear Student,</p>
                
                <p>Thank you for using <strong>KUCCPS Courses Checker</strong>. Based on your KCSE results, we've identified <strong class="highlight">{total_courses}</strong> courses that match your qualifications!</p>
                
                <div class="info-box">
                    <h2>📋 Your Information</h2>
                    <p><strong>Email:</strong> {email}<br>
                    <strong>KCSE Index:</strong> {index_number}<br>
                    <strong>M-Pesa Receipt:</strong> {mpesa_receipt}<br>
                    <strong>Report Generated:</strong> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</p>
                </div>
                
                <h2>📊 Course Summary</h2>
                <ul>
                    {level_summary_html}
                </ul>
                
                <div class="info-box">
                    <h2>📎 What's in the PDF?</h2>
                    <p>The attached PDF contains a complete list of all {total_courses} courses you qualify for, including:</p>
                    <ul>
                        <li>Programme names and codes</li>
                        <li>Institution names</li>
                        <li>Subject requirements</li>
                        <li>Course duration and level details</li>
                    </ul>
                </div>
                
                <h2>🔑 Important Information</h2>
                <ul>
                    <li><strong>Keep this email safe!</strong> You can use the M-Pesa receipt number <strong>{mpesa_receipt}</strong> to access your results anytime at <a href="https://www.kuccpscourses.co.ke">kuccpscourses.co.ke</a></li>
                    <li>This is an <strong>unofficial guidance tool</strong>. For official placement, apply through the KUCCPS portal at <a href="https://students.kuccps.net">students.kuccps.net</a></li>
                    <li>The official KUCCPS application fee is <strong>KES 1,500</strong> (separate from our course checking fee)</li>
                    <li>Application deadlines: Usually opens in April, closes July 15th</li>
                </ul>
                
                <div style="text-align: center;">
                    <a href="https://www.kuccpscourses.co.ke/verify-payment" class="button">🔍 Verify Your Results Online</a>
                </div>
                
                <hr>
                
                <p><strong>Need help?</strong> Contact us:</p>
                <ul>
                    <li>📧 Email: courseschecker@gmail.com</li>
                    <li>📞 Phone: +254791196121</li>
                    <li>💬 Live chat: Available on our website</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>© {datetime.now().year} KUCCPS Courses Checker. All rights reserved.<br>
                This is an automated email. Please do not reply directly to this message.<br>
                Visit us at <a href="https://www.kuccpscourses.co.ke">www.kuccpscourses.co.ke</a></p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _generate_email_text(self, email, index_number, mpesa_receipt, total_courses, courses_by_level):
        """Generate plain text email content"""
        
        # Build level summaries
        level_summaries = []
        level_display = {
            'degree': 'Degree Programs',
            'diploma': 'Diploma Programs',
            'certificate': 'Certificate Programs',
            'artisan': 'Artisan Programs',
            'kmtc': 'KMTC Medical Programs',
            'ttc': 'Teacher Training Programs'
        }
        
        for level, courses in courses_by_level.items():
            if courses:
                count = len(courses)
                display = level_display.get(level, level.title())
                level_summaries.append(f"- {display}: {count} courses")
        
        level_summary_text = '\n'.join(level_summaries) if level_summaries else "- No courses found"
        
        text = f"""
KUCCPS Courses Report
=====================

Dear Student,

Thank you for using KUCCPS Courses Checker. Based on your KCSE results, we've identified {total_courses} courses that match your qualifications!

Your Information:
-----------------
Email: {email}
KCSE Index: {index_number}
M-Pesa Receipt: {mpesa_receipt}
Report Generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}

Course Summary:
--------------
{level_summary_text}

What's in the PDF?
------------------
The attached PDF contains a complete list of all {total_courses} courses you qualify for, including:
- Programme names and codes
- Institution names
- Subject requirements
- Course duration and level details

Important Information:
---------------------
- Keep this email safe! You can use the M-Pesa receipt number {mpesa_receipt} to access your results anytime at: https://www.kuccpscourses.co.ke/verify-payment
- This is an unofficial guidance tool. For official placement, apply through the KUCCPS portal: https://students.kuccps.net
- The official KUCCPS application fee is KES 1,500 (separate from our course checking fee)
- Application deadlines: Usually opens in April, closes July 15th

Need help? Contact us:
- Email: courseschecker@gmail.com
- Phone: +254791196121
- Live chat: Available on our website

---
© {datetime.now().year} KUCCPS Courses Checker. All rights reserved.
Visit us at: https://www.kuccpscourses.co.ke
"""
        
        return text


def send_courses_report(email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer):
    """Wrapper function to send email"""
    service = EmailService()
    return service.send_courses_report(email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer)