# test_email_simple.py
#!/usr/bin/env python3
"""Test email functionality with working PDF generation"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try different import options
try:
    from email_sender import EmailSender
    print("✅ Using Brevo email sender")
except ImportError:
    try:
        from email_sender_simple import EmailSender
        print("⚠️ Using simple email sender (simulation mode)")
    except ImportError:
        print("❌ No email sender found")
        sys.exit(1)

from pdf_generator import generate_course_pdf

print("=" * 60)
print("TESTING EMAIL WITH PDF")
print("=" * 60)

# Test data
test_user_data = {
    'email': 'test@example.com',
    'name': 'Test User',
    'grades': {
        'Mathematics': 'B',
        'English': 'C+',
        'Kiswahili': 'C',
        'Chemistry': 'B-',
        'Physics': 'C'
    },
    'mean_grade': 'C plain',
    'cluster_points': {'Engineering': 35.2, 'Medicine': 32.0}
}

test_courses = [
    {
        'programme_name': 'Bachelor of Civil Engineering',
        'institution_name': 'University of Nairobi',
        'programme_code': '1005002',
        'cut_off_points': '38.5',
        'minimum_subject_requirements': {'Mathematics': 'B+', 'Physics': 'B', 'Chemistry': 'B-'}
    },
    {
        'programme_name': 'Diploma in Nursing',
        'institution_name': 'KMTC Nairobi',
        'programme_code': '2001003',
        'minimum_grade': 'C plain',
        'duration': '3 years'
    },
    {
        'programme_name': 'Diploma in Information Technology',
        'institution_name': 'Strathmore University',
        'programme_code': '2004567',
        'cut_off_points': '30.0'
    }
]

print("\n1. Generating PDF...")
pdf_content = generate_course_pdf(
    user_data=test_user_data,
    courses=test_courses,
    flow='test',
    mpesa_receipt='TEST123456',
    index_number='12345678901/2024'
)

if pdf_content:
    print(f"✅ PDF generated: {len(pdf_content)} bytes")
    
    # Check if PDF is valid (starts with PDF header)
    if pdf_content[:4] == b'%PDF':
        print("✅ PDF appears valid (has PDF header)")
    else:
        print(f"⚠️ PDF header: {pdf_content[:20]}")
    
    print("\n2. Sending email...")
    email_sender = EmailSender()
    
    # Get test email from environment or use default
    test_email = os.getenv('TEST_EMAIL', 'parmarshaifaly@gmail.com')
    
    success = email_sender.send_course_results_email(
        recipient_email=test_email,
        user_name='Test User',
        courses_count=len(test_courses),
        flow='diploma',
        mpesa_receipt='TEST123456',
        index_number='12345678901/2024',
        pdf_content=pdf_content
    )
    
    if success:
        print(f"✅ Email sent successfully to {test_email}")
    else:
        print("❌ Failed to send email")
        
else:
    print("❌ PDF generation failed")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)