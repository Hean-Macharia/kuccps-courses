import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url
import os
from datetime import datetime
import hashlib
import base64
import re

def init_cloudinary():
    """Initialize Cloudinary with credentials"""
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')
    
    if not all([cloud_name, api_key, api_secret]):
        print("❌ Cloudinary credentials missing in .env file")
        print("   Required: CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET")
        return False
    
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )
    print(f"✅ Cloudinary initialized with cloud: {cloud_name}")
    return True

def upload_screenshot(screenshot_base64, email, receipt, index_number):
    """
    Upload screenshot to Cloudinary using upload preset
    """
    if not screenshot_base64:
        print("⚠️ No screenshot data provided")
        return None, None, None
    
    try:
        # Preserve and validate the submitted image type instead of assuming PNG.
        mime_type = 'image/png'
        if screenshot_base64.startswith('data:'):
            header, separator, payload = screenshot_base64.partition(',')
            if not separator or ';base64' not in header:
                print("⚠️ Screenshot data URL is invalid")
                return None, None, None
            mime_type = header[5:].split(';', 1)[0].lower()
            screenshot_base64 = payload
        if mime_type not in {'image/jpeg', 'image/png', 'image/webp'}:
            print("⚠️ Unsupported screenshot type")
            return None, None, None
        
        # Validate base64 bytes and enforce the same 5 MB limit as the form.
        try:
            image_bytes = base64.b64decode(screenshot_base64, validate=True)
        except (ValueError, base64.binascii.Error):
            print("⚠️ Screenshot is not valid base64")
            return None, None, None
        if len(image_bytes) < 100 or len(image_bytes) > 5 * 1024 * 1024:
            print("⚠️ Screenshot size is invalid")
            return None, None, None
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_hash = hashlib.md5(f"{email}_{receipt}_{timestamp}".encode()).hexdigest()[:12]
        public_id = f"payment_issues/{filename_hash}"
        
        print(f"📤 Uploading to Cloudinary...")
        print(f"   Public ID: {public_id}")
        print(f"   Data size: {len(screenshot_base64)} chars")
        
        # Upload to Cloudinary using UNSIGNED upload with preset
        upload_result = cloudinary.uploader.upload(
            f"data:{mime_type};base64,{screenshot_base64}",
            public_id=public_id,
            folder="kuccps_payment_issues",
            resource_type="image",
            quality="auto:good",
            fetch_format="auto",
            tags=['payment_issue'],
            context={
                'email': email,
                'receipt': receipt,
                'index_number': index_number,
                'uploaded_at': datetime.now().isoformat()
            }
        )
        
        # Get optimized URL
        url = cloudinary.utils.cloudinary_url(
            upload_result['public_id'],
            format='auto',
            width=800,
            crop='limit',
            quality='auto'
        )[0]
        
        print(f"✅ Screenshot uploaded to Cloudinary")
        print(f"   Public ID: {upload_result['public_id']}")
        print(f"   Size: {upload_result.get('bytes', 0)} bytes")
        print(f"   Format: {upload_result.get('format')}")
        print(f"   URL: {url}")
        
        return url, upload_result['public_id'], {
            'bytes': upload_result.get('bytes', 0),
            'format': upload_result.get('format'),
            'width': upload_result.get('width'),
            'height': upload_result.get('height'),
            'created_at': upload_result.get('created_at')
        }
        
    except cloudinary.exceptions.BadRequest as e:
        error_msg = str(e)
        if "Upload preset not found" in error_msg:
            print("❌ Upload preset 'kuccps_screenshots' not found in Cloudinary")
            print("   Please create it in Cloudinary Dashboard:")
            print("   1. Go to Settings → Upload")
            print("   2. Scroll to Upload Presets")
            print("   3. Click 'Add upload preset'")
            print("   4. Name it: kuccps_screenshots")
            print("   5. Set Signing mode: Unsigned")
            print("   6. Click Save")
        else:
            print(f"❌ Cloudinary bad request: {error_msg}")
        return None, None, None
        
    except Exception as e:
        print(f"❌ Error uploading to Cloudinary: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None

def delete_screenshot(public_id):
    """Delete screenshot from Cloudinary"""
    if not public_id:
        return False
    
    try:
        result = cloudinary.uploader.destroy(public_id)
        if result.get('result') == 'ok':
            print(f"✅ Deleted screenshot: {public_id}")
            return True
        else:
            print(f"⚠️ Failed to delete screenshot: {result}")
            return False
    except Exception as e:
        print(f"❌ Error deleting screenshot: {str(e)}")
        return False

def get_screenshot_url(public_id, width=800, height=None, quality='auto'):
    """Get optimized URL for existing screenshot"""
    if not public_id:
        return None
    
    options = {
        'width': width,
        'crop': 'limit',
        'quality': quality,
        'fetch_format': 'auto'
    }
    if height:
        options['height'] = height
    
    url, _ = cloudinary_url(public_id, **options)
    return url

def test_cloudinary_connection():
    """Test signed Cloudinary upload access without exposing credentials."""
    print("\n🔧 Testing Cloudinary Connection...")
    
    # Test 1: Check credentials
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')
    
    if not all([cloud_name, api_key, api_secret]):
        print("❌ Cloudinary credentials not found in .env file")
        return False
    
    print(f"✅ Cloud name: {cloud_name}")
    
    # Test 2: Try to upload a tiny test image
    test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    try:
        public_id = f"kuccps_payment_issues/diagnostics/test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = cloudinary.uploader.upload(
            f"data:image/png;base64,{test_image}",
            public_id=public_id,
            resource_type="image",
            overwrite=True
        )
        print("✅ Signed upload test successful!")
        
        # Clean up test image
        cloudinary.uploader.destroy(public_id, resource_type="image")
        return True
        
    except cloudinary.exceptions.BadRequest as e:
        print(f"❌ Upload test failed: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def get_cloudinary_status():
    """Get Cloudinary account status"""
    try:
        # Try to get account usage
        usage = cloudinary.api.usage()
        return {
            'configured': True,
            'cloud_name': os.getenv('CLOUDINARY_CLOUD_NAME'),
            'storage_used': usage.get('storage_used', 0),
            'storage_limit': usage.get('storage_limit', 0),
            'credits_used': usage.get('credits_used', 0),
            'credits_limit': usage.get('credits_limit', 0)
        }
    except Exception as e:
        return {
            'configured': False,
            'error': str(e)
        }
