"""
Email Service for KUCCPS Courses Checker
Uses Brevo API for sending course reports with PDF attachments
"""

import os
import logging
from datetime import datetime
import base64
import threading
from queue import Queue
import io
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import Brevo SDK
BREVO_AVAILABLE = False
brevo_python = None

try:
    import brevo_python
    from brevo_python.rest import ApiException
    BREVO_AVAILABLE = True
    logger.info("✅ Brevo SDK loaded successfully")
except ImportError:
    try:
        import sib_api_v3_sdk as brevo_python
        from sib_api_v3_sdk.rest import ApiException
        BREVO_AVAILABLE = True
        logger.info("✅ Brevo SDK (sib_api_v3_sdk) loaded successfully")
    except ImportError:
        logger.warning("⚠️ Brevo Python SDK not installed. Run: pip install brevo-python")

# Email queue for background processing
email_queue = Queue()
email_queue_thread_started = False
_email_worker_lock = threading.Lock()


class EmailService:
    """Email service using Brevo API only"""
    
    def __init__(self):
        """Initialize email service with configuration from environment"""
        # Load from environment variables
        self.api_key = os.getenv('BREVO_API_KEY')
        self.sender_email = os.getenv('BREVO_SENDER_EMAIL', 'info@kuccpscourses.co.ke')
        self.sender_name = os.getenv('BREVO_SENDER_NAME', 'KUCCPS Courses Checker')
        self.cc_email = os.getenv('BREVO_CC_EMAIL', 'kuccpscourses@gmail.com')
        
        # Initialize Brevo API client
        self.api_instance = None
        self.enabled = False
        
        if BREVO_AVAILABLE and self.api_key and self.api_key != 'your_brevo_api_key_here':
            try:
                configuration = brevo_python.Configuration()
                configuration.api_key['api-key'] = self.api_key
                self.api_instance = brevo_python.TransactionalEmailsApi(brevo_python.ApiClient(configuration))
                self.enabled = True
                logger.info("✅ Brevo email service initialized successfully")
                logger.info(f"📧 Sender: {self.sender_name} <{self.sender_email}>")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Brevo: {e}")
                self.enabled = False
        elif not BREVO_AVAILABLE:
            logger.warning("⚠️ Brevo SDK not available. Install with: pip install brevo-python")
        elif not self.api_key:
            logger.warning("⚠️ BREVO_API_KEY not found in environment variables")
            logger.info("💡 Add BREVO_API_KEY to your .env file")
    
    def send_courses_report(self, email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer, is_manual_activation=False):
        """Send courses report email with PDF attachment"""
        
        # Validate inputs
        if not email:
            logger.error("❌ No email address provided")
            return False
        
        if not self.enabled:
            logger.warning(f"⚠️ Email service disabled. Would have sent report to {email}")
            logger.info(f"📧 Report would contain {total_courses} courses for index {index_number}")
            return True  # Return True to not break the flow
        
        try:
            # Generate email content
            subject = self._generate_subject(index_number, is_manual_activation)
            html_content = self._generate_html_content(email, index_number, mpesa_receipt, total_courses, courses_by_level, is_manual_activation)
            text_content = self._generate_text_content(email, index_number, mpesa_receipt, total_courses, courses_by_level, is_manual_activation)
            
            # Prepare attachment
            attachments = []
            if pdf_buffer:
                try:
                    # Reset buffer position to beginning
                    if hasattr(pdf_buffer, 'seek'):
                        pdf_buffer.seek(0)
                    
                    # Read PDF content
                    pdf_content = pdf_buffer.read()
                    
                    # Encode to base64
                    encoded_pdf = base64.b64encode(pdf_content).decode('utf-8')
                    
                    attachments = [{
                        'name': f"courses_report_{index_number.replace('/', '_')}.pdf",
                        'content': encoded_pdf
                    }]
                    logger.info(f"📎 PDF attachment prepared: {len(pdf_content)} bytes")
                except Exception as e:
                    logger.error(f"❌ PDF attachment error: {e}")
            
            # Create email object
            send_smtp_email = brevo_python.SendSmtpEmail(
                to=[{'email': email, 'name': email.split('@')[0]}],
                bcc=[{'email': self.cc_email, 'name': 'Admin'}],
                sender={'email': self.sender_email, 'name': self.sender_name},
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                attachment=attachments if attachments else None
            )
            
            # Send email via Brevo
            response = self.api_instance.send_transac_email(send_smtp_email)
            
            logger.info(f"✅ Email sent successfully to {email}")
            logger.info(f"📧 Message ID: {response}")
            logger.info(f"📊 Courses: {total_courses} across {len(courses_by_level)} levels")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send email to {email}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _generate_subject(self, index_number, is_manual_activation=False):
        """Generate email subject line"""
        if is_manual_activation:
            return f"🎓 Your KUCCPS Course Results (Manual Activation) - {index_number}"
        return f"🎓 Your KUCCPS Courses Report - {index_number}"
    
    def _generate_html_content(self, email, index_number, mpesa_receipt, total_courses, courses_by_level, is_manual_activation=False):
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
        
        # Manual activation banner
        manual_banner = ''
        if is_manual_activation:
            manual_banner = '''
            <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #28a745;">
                <p style="margin: 0; color: #155724;">
                    <strong>✨ MANUAL ACTIVATION</strong><br>
                    Your account was manually activated by our support team. Access granted at no cost.
                </p>
            </div>
            '''
        
        receipt_display = mpesa_receipt if mpesa_receipt else "your receipt number"
        current_year = datetime.now().year
        current_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your KUCCPS Courses Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
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
            border-radius: 12px 12px 0 0;
        }}
        .content {{
            background: #ffffff;
            padding: 30px;
            border-left: 1px solid #e2e8f0;
            border-right: 1px solid #e2e8f0;
        }}
        .footer {{
            background: #f7fafc;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #718096;
            border-radius: 0 0 12px 12px;
            border: 1px solid #e2e8f0;
            border-top: none;
        }}
        .info-box {{
            background: #f7fafc;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #1e3c72;
        }}
        .button {{
            display: inline-block;
            background: #1e3c72;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 6px;
            margin: 20px 0;
        }}
        .button:hover {{
            background: #2c5282;
        }}
        h1 {{ margin: 0; font-size: 24px; }}
        h2 {{ color: #1e3c72; margin-top: 0; font-size: 18px; }}
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
        {manual_banner}
        
        <p>Dear Student,</p>
        
        <p>Thank you for using <strong>KUCCPS Courses Checker</strong>. Based on your KCSE results, we've identified <strong class="highlight">{total_courses}</strong> courses that match your qualifications!</p>
        
        <div class="info-box">
            <h2>📋 Your Information</h2>
            <p><strong>Email:</strong> {email}<br>
            <strong>KCSE Index:</strong> {index_number}<br>
            <strong>M-Pesa Receipt:</strong> {receipt_display}<br>
            <strong>Report Generated:</strong> {current_date}</p>
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
                <li>Cluster points and cut-off information</li>
            </ul>
        </div>
        
        <h2>🔑 Important Information</h2>
        <ul>
            <li><strong>Keep this email safe!</strong> Use receipt <strong>{receipt_display}</strong> to access results anytime</li>
            <li>For official placement, apply through <a href="https://students.kuccps.net">students.kuccps.net</a></li>
            <li>Official KUCCPS application fee: <strong>KES 1,500</strong></li>
        </ul>
        
        <div style="text-align: center;">
            <a href="https://www.kuccpscourses.co.ke/verify-payment" class="button">🔍 Verify Your Results Online</a>
        </div>
        
        <hr>
        
        <p><strong>Need help?</strong> Contact us:</p>
        <ul>
            <li>📧 Email: kuccpscourses@gmail.com</li>
            <li>📞 Phone: +254750732841</li>
            <li>💬 Live chat: Available on our website</li>
        </ul>
    </div>
    
    <div class="footer">
        <p>© {current_year} KUCCPS Courses Checker. All rights reserved.<br>
        This is an automated email. Please do not reply directly.<br>
        Visit: <a href="https://www.kuccpscourses.co.ke">www.kuccpscourses.co.ke</a></p>
    </div>
</body>
</html>'''
        
        return html
    
    def _generate_text_content(self, email, index_number, mpesa_receipt, total_courses, courses_by_level, is_manual_activation=False):
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
        
        # Manual activation note
        manual_note = ""
        if is_manual_activation:
            manual_note = """
✨ MANUAL ACTIVATION
Your account was manually activated by our support team. Access granted at no cost.

"""
        
        receipt_display = mpesa_receipt if mpesa_receipt else "your receipt number"
        current_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        
        text = f"""
{manual_note}KUCCPS Courses Report
=====================

Dear Student,

Thank you for using KUCCPS Courses Checker. Based on your KCSE results, we've identified {total_courses} courses that match your qualifications!

Your Information:
-----------------
Email: {email}
KCSE Index: {index_number}
M-Pesa Receipt: {receipt_display}
Report Generated: {current_date}

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
- Cluster points and cut-off information

Important Information:
---------------------
- Keep this email safe! Use receipt {receipt_display} to access results anytime
- For official placement, apply through: https://students.kuccps.net
- Official KUCCPS application fee: KES 1,500

Need help? Contact us:
- Email: kuccpscourses@gmail.com
- Phone: +254750732841
- Live chat: Available on our website

---
© {datetime.now().year} KUCCPS Courses Checker. All rights reserved.
Visit: https://www.kuccpscourses.co.ke
"""
        
        return text

def send_manual_activation_email(email, index_number, flow, mpesa_receipt):
    """
    Send manual activation email notification to user
    This is a simplified version without PDF attachment
    """
    try:
        if not email:
            logger.error("❌ No email address provided for manual activation")
            return False
        
        service = EmailService()
        
        if not service.enabled:
            logger.warning(f"⚠️ Email service disabled. Would have sent manual activation to {email}")
            return True
        
        # Generate subject
        subject = f"✅ Account Activated - Complete Your {flow.upper()} Course Selection"
        
        # Generate HTML content
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Account Activated - KUCCPS Courses Checker</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Account Activated! 🎉</h1>
                <p style="color: white; margin: 5px 0 0;">Your access has been restored</p>
            </div>
            
            <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 10px 10px;">
                <p>Dear Student,</p>
                
                <p>Good news! Your account has been <strong>manually activated</strong> by our support team. You can now access your {flow.upper()} course results at no additional cost.</p>
                
                <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0 0 10px 0;"><strong>✅ Your Activation Details:</strong></p>
                    <p style="margin: 5px 0;">📧 Email: {email}</p>
                    <p style="margin: 5px 0;">📝 Index Number: {index_number}</p>
                    <p style="margin: 5px 0;">💰 M-Pesa Receipt: <strong>{mpesa_receipt}</strong></p>
                    <p style="margin: 5px 0;">📚 Course Level: {flow.upper()}</p>
                </div>
                
                <p><strong>To get your course results now:</strong></p>
                <ol>
                    <li>Visit <a href="https://www.kuccpscourses.co.ke">www.kuccpscourses.co.ke</a></li>
                    <li>Click on the <strong>{flow.upper()}</strong> course category</li>
                    <li>Re-enter your KCSE grades for that category</li>
                    <li>When prompted for payment, use the <strong>"Already Made Payment"</strong> option</li>
                    <li>Enter your M-Pesa receipt number: <strong>{mpesa_receipt}</strong></li>
                    <li>Enter your KCSE index number: <strong>{index_number}</strong></li>
                    <li>Your course results will be generated instantly!</li>
                </ol>
                
                <div style="background: #e8f4fd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0; color: #0056b3;">
                        <strong>🎉 You will NOT be charged again.</strong> The manual activation gives you free access to complete your course qualification process.
                    </p>
                </div>
                
                <p>If you need any assistance, please contact our support team at kuccpscourses@gmail.com or +254750732841.</p>
                
                <hr style="margin: 20px 0;">
                
                <p style="font-size: 12px; color: #666; text-align: center;">
                    © 2025 KUCCPS Courses Checker. All rights reserved.<br>
                    This is an automated message, please do not reply directly to this email.
                </p>
            </div>
        </body>
        </html>
        '''
        
        # Generate text content
        text_content = f'''
Account Activated! 🎉
===================

Dear Student,

Good news! Your account has been manually activated by our support team. You can now access your {flow.upper()} course results at no additional cost.

Your Activation Details:
- Email: {email}
- Index Number: {index_number}
- M-Pesa Receipt: {mpesa_receipt}
- Course Level: {flow.upper()}

To get your course results now:
1. Visit www.kuccpscourses.co.ke
2. Click on the {flow.upper()} course category
3. Re-enter your KCSE grades for that category
4. When prompted for payment, use the "Already Made Payment" option
5. Enter your M-Pesa receipt number: {mpesa_receipt}
6. Enter your KCSE index number: {index_number}
7. Your course results will be generated instantly!

🎉 You will NOT be charged again.

Need help? Contact: kuccpscourses@gmail.com or +254750732841

---
© 2025 KUCCPS Courses Checker. All rights reserved.
        '''
        
        # Create email object
        send_smtp_email = brevo_python.SendSmtpEmail(
            to=[{'email': email, 'name': email.split('@')[0]}],
            sender={'email': service.sender_email, 'name': service.sender_name},
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
        
        # Send email via Brevo
        response = service.api_instance.send_transac_email(send_smtp_email)
        
        logger.info(f"✅ Manual activation email sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send manual activation email to {email}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def email_worker():
    """Background worker to process email queue"""
    logger.info("🚀 Email worker thread started")
    
    while True:
        try:
            # Get job from queue with timeout
            try:
                job = email_queue.get(timeout=2)
            except Exception:
                # Queue.get timeout is normal, just continue
                continue
            
            # Skip if job is None
            if job is None:
                email_queue.task_done()
                continue
            
            # Extract job data
            email = job.get('email')
            index_number = job.get('index_number')
            courses_by_level = job.get('courses_by_level', {})
            total_courses = job.get('total_courses', 0)
            mpesa_receipt = job.get('mpesa_receipt')
            pdf_buffer = job.get('pdf_buffer')
            is_manual_activation = job.get('is_manual_activation', False)
            
            # Validate required fields
            if not email or not index_number:
                logger.warning(f"⚠️ Invalid job data: missing email or index_number")
                email_queue.task_done()
                continue
            
            logger.info(f"📧 Processing email for {email} - {total_courses} courses")
            
            # Create service and send email
            service = EmailService()
            success = service.send_courses_report(
                email=email,
                index_number=index_number,
                courses_by_level=courses_by_level,
                total_courses=total_courses,
                mpesa_receipt=mpesa_receipt,
                pdf_buffer=pdf_buffer,
                is_manual_activation=is_manual_activation
            )
            
            if success:
                logger.info(f"✅ Email sent successfully to {email}")
            else:
                logger.error(f"❌ Failed to send email to {email}")
            
            # Mark task as done
            email_queue.task_done()
            
        except Exception as e:
            logger.error(f"❌ Email worker error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # Still mark as done to prevent queue blockage
            try:
                email_queue.task_done()
            except Exception:
                pass
            # Small delay before continuing
            time.sleep(1)


def start_email_worker():
    """Start the background email worker thread"""
    global email_queue_thread_started
    
    with _email_worker_lock:
        if not email_queue_thread_started:
            try:
                thread = threading.Thread(target=email_worker, daemon=True)
                thread.start()
                email_queue_thread_started = True
                logger.info("✅ Email worker thread started successfully")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to start email worker: {e}")
                return False
        else:
            logger.info("ℹ️ Email worker already running")
            return True


def queue_courses_report(email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer, is_manual_activation=False):
    """Queue email for background sending"""
    try:
        # Validate inputs
        if not email or not index_number:
            logger.warning(f"⚠️ Cannot queue email: missing email or index_number")
            return False
        
        # Ensure PDF buffer is in bytes format
        if pdf_buffer:
            try:
                if hasattr(pdf_buffer, 'seek'):
                    pdf_buffer.seek(0)
            except Exception as e:
                logger.warning(f"⚠️ PDF buffer seek error: {e}")
        
        # Create job
        job = {
            'email': email,
            'index_number': index_number,
            'courses_by_level': courses_by_level,
            'total_courses': total_courses,
            'mpesa_receipt': mpesa_receipt,
            'pdf_buffer': pdf_buffer,
            'is_manual_activation': is_manual_activation
        }
        
        # Add to queue
        email_queue.put(job)
        
        logger.info(f"📧 Email queued for {email} - {total_courses} courses")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to queue email: {e}")
        return False


def send_courses_report(email, index_number, courses_by_level, total_courses, mpesa_receipt, pdf_buffer, is_manual_activation=False):
    """Synchronous wrapper to send email directly"""
    service = EmailService()
    return service.send_courses_report(
        email=email,
        index_number=index_number,
        courses_by_level=courses_by_level,
        total_courses=total_courses,
        mpesa_receipt=mpesa_receipt,
        pdf_buffer=pdf_buffer,
        is_manual_activation=is_manual_activation
    )




# Start email worker automatically when module loads
_email_worker_started = False

if not _email_worker_started:
    # Small delay to ensure logger is configured
    time.sleep(0.5)
    start_email_worker()
    _email_worker_started = True