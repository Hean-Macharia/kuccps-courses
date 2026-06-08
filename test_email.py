#!/usr/bin/env python3
"""
Test Brevo Email Integration
Run: python test_email.py
"""

import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Brevo Configuration
BREVO_API_KEY = os.getenv('BREVO_API_KEY')
BREVO_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL', 'support@kuccpscourses.co.ke')
BREVO_SENDER_NAME = os.getenv('BREVO_SENDER_NAME', 'KUCCPS Courses Checker')

def test_brevo_api_key():
    """Test if API key is valid"""
    print("🔍 Testing Brevo API Key...")
    
    if not BREVO_API_KEY:
        print("❌ BREVO_API_KEY not found in environment variables")
        print("💡 Please add BREVO_API_KEY to your .env file")
        return False
    
    print(f"✅ API Key found (starts with: {BREVO_API_KEY[:10]}...)")
    return True

def test_brevo_connection():
    """Test connection to Brevo API"""
    print("\n🔍 Testing Brevo API Connection...")
    
    url = "https://api.brevo.com/v3/account"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Successfully connected to Brevo API")
            print(f"📊 Account: {data.get('email', 'Unknown')}")
            print(f"📊 Credits: {data.get('plan', [{}])[0].get('credits', 'Unknown')}")
            return True
        elif response.status_code == 401:
            print("❌ Invalid API key - Unauthorized (401)")
            print("💡 Please check your BREVO_API_KEY in .env file")
            return False
        else:
            print(f"❌ API connection failed with status: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Connection timeout - Brevo API not responding")
        return False
    except Exception as e:
        print(f"❌ Connection error: {str(e)}")
        return False

def send_test_email(recipient_email):
    """Send a test email using Brevo API"""
    print(f"\n📧 Sending test email to {recipient_email}...")
    
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    
    subject = "Test Email from KUCCPS Courses Checker"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Test Email</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0;">✅ Test Email Successful!</h1>
            <p style="color: white; margin: 5px 0 0;">Brevo integration is working</p>
        </div>
        
        <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 10px 10px;">
            <p>Hello,</p>
            
            <p>This is a test email to confirm that the Brevo email integration is working correctly for the KUCCPS Courses Checker application.</p>
            
            <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <p style="margin: 0 0 10px 0;"><strong>Test Details:</strong></p>
                <p style="margin: 5px 0;">📧 Recipient: <strong>{recipient_email}</strong></p>
                <p style="margin: 5px 0;">⏰ Time: <strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</strong></p>
                <p style="margin: 5px 0;">🔧 Status: <strong>Working Perfectly</strong></p>
            </div>
            
            <p>Your email system is properly configured and ready to send:</p>
            <ul>
                <li>✅ Course results PDFs</li>
                <li>✅ Payment confirmations</li>
                <li>✅ Issue resolution notifications</li>
                <li>✅ Manual activation emails</li>
            </ul>
            
            <hr style="margin: 20px 0;">
            
            <p style="font-size: 12px; color: #666; text-align: center;">
                © 2025 KUCCPS Courses Checker. All rights reserved.
            </p>
        </div>
    </body>
    </html>
    """
    
    payload = {
        "sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
        "to": [{"email": recipient_email, "name": "Admin"}],
        "subject": subject,
        "htmlContent": html_content
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code in [200, 201, 202]:
            print(f"✅ Test email sent successfully to {recipient_email}")
            print(f"📊 Response: {response.json()}")
            return True
        else:
            print(f"❌ Failed to send email. Status: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print("📧 Brevo Email Integration Test")
    print("=" * 60)
    
    # Test 1: API Key exists
    if not test_brevo_api_key():
        sys.exit(1)
    
    # Test 2: API Connection
    if not test_brevo_connection():
        sys.exit(1)
    
    # Test 3: Send test email
    recipient = input("\n📧 Enter email address to send test email: ").strip()
    if not recipient:
        recipient = "kuccpscourses@gmail.com"
        print(f"⚠️ Using default email: {recipient}")
    
    if send_test_email(recipient):
        print("\n" + "=" * 60)
        print("✅ All tests passed! Email system is working correctly.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Email sending failed. Please check your configuration.")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()