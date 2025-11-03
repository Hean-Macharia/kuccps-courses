from functools import wraps
import re
from flask import request, abort

def sanitize_input(data):
    """Sanitize user input to prevent injection attacks"""
    if isinstance(data, str):
        # Remove any potential script tags
        data = re.sub(r'<script.*?>.*?</script>', '', data, flags=re.IGNORECASE | re.DOTALL)
        # Remove other potentially dangerous HTML tags
        data = re.sub(r'<.*?>', '', data)
        # Escape special characters
        data = data.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        data = data.replace('"', '&quot;').replace("'", '&#x27;')
    elif isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(x) for x in data]
    return data

def validate_phone_number(phone):
    """Validate phone number format"""
    if not phone:
        return False
    # Remove any spaces or special characters
    phone = re.sub(r'[^0-9+]', '', phone)
    # Check if it matches expected formats
    valid_formats = [
        r'^\+254\d{9}$',  # +254xxxxxxxxx
        r'^254\d{9}$',    # 254xxxxxxxxx
        r'^0\d{9}$',      # 0xxxxxxxxx
        r'^\d{9}$'        # xxxxxxxxx
    ]
    return any(re.match(pattern, phone) for pattern in valid_formats)

def validate_index_number(index_number):
    """Validate index number format"""
    if not index_number:
        return False
    # Check if it matches the expected format (adjust pattern as needed)
    return bool(re.match(r'^[A-Z0-9]{8,15}$', index_number.upper()))

def secure_headers():
    """Add security headers to response"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            response = f(*args, **kwargs)
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            return response
        return decorated_function
    return decorator

def require_https():
    """Ensure request is using HTTPS in production"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_secure and not app.debug:
                url = request.url.replace('http://', 'https://', 1)
                return redirect(url, code=301)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def rate_limit(f):
    """Basic rate limiting decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get client IP
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        # Use Redis or similar for production
        if hasattr(app, '_rate_limit_data'):
            data = app._rate_limit_data
        else:
            data = app._rate_limit_data = {}
        
        now = datetime.now()
        key = f"{ip}:{request.endpoint}"
        
        # Clean old entries
        data = {k: v for k, v in data.items() if (now - v[-1]).seconds < 60}
        
        if key in data:
            # Check if limit exceeded
            if len(data[key]) >= 100:  # 100 requests per minute
                app._rate_limit_data = data
                abort(429)  # Too Many Requests
            data[key].append(now)
        else:
            data[key] = [now]
        
        app._rate_limit_data = data
        return f(*args, **kwargs)
    return decorated_function