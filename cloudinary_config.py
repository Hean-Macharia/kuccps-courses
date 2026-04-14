import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url
import os
from datetime import datetime
import hashlib
import base64

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
        # Extract base64 data if it has prefix
        if ',' in screenshot_base64:
            screenshot_base64 = screenshot_base64.split(',')[1]
        
        # Validate base64 data
        if len(screenshot_base64) < 100:
            print("⚠️ Screenshot data too small, may be invalid")
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
            f"data:image/png;base64,{screenshot_base64}",
            public_id=public_id,
            folder="kuccps_payment_issues",
            upload_preset="kuccps_screenshots",  # You must create this in Cloudinary dashboard
            resource_type="image",
            quality="auto:good",
            fetch_format="auto",
            tags=['payment_issue', email, receipt],
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
    """Test Cloudinary connection and upload preset"""
    print("\n🔧 Testing Cloudinary Connection...")
    
    # Test 1: Check credentials
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    
    if not cloud_name or not api_key:
        print("❌ Cloudinary credentials not found in .env file")
        return False
    
    print(f"✅ Cloud name: {cloud_name}")
    print(f"✅ API key: {api_key[:10]}...")
    
    # Test 2: Try to upload a tiny test image
    test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    try:
        result = cloudinary.uploader.upload(
            f"data:image/png;base64,{test_image}",
            public_id="test_upload_preset",
            upload_preset="kuccps_screenshots"
        )
        print("✅ Upload preset test successful!")
        print(f"   Test URL: {result['secure_url']}")
        
        # Clean up test image
        cloudinary.uploader.destroy("test_upload_preset")
        return True
        
    except cloudinary.exceptions.BadRequest as e:
        if "Upload preset not found" in str(e):
            print("❌ Upload preset 'kuccps_screenshots' not found")
            print("\n📝 Please create the upload preset:")
            print("   1. Go to https://cloudinary.com/console")
            print("   2. Click Settings (gear icon)")
            print("   3. Go to Upload tab")
            print("   4. Scroll to 'Upload presets'")
            print("   5. Click 'Add upload preset'")
            print("   6. Name: kuccps_screenshots")
            print("   7. Signing mode: Unsigned")
            print("   8. Allowed formats: PNG, JPG, JPEG")
            print("   9. Click Save")
        else:
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