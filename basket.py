# --- Basket Management Functions ---
from flask import session
from datetime import datetime, timedelta

def clear_basket(email, index_number):
    """Clear user's basket and refresh courses from database"""
    # Clear basket-related session data
    session_keys_to_clear = []
    for key in session:
        if key.startswith('basket_') or key.endswith('_basket'):
            session_keys_to_clear.append(key)
    
    for key in session_keys_to_clear:
        session.pop(key, None)
    
    # Force reload of courses from database
    courses_keys_to_clear = []
    for key in session:
        if '_courses_' in key:
            courses_keys_to_clear.append(key)
    
    for key in courses_keys_to_clear:
        session.pop(key, None)
    
    if database_connected:
        try:
            # Update basket in database
            user_baskets_collection.update_one(
                {'email': email, 'index_number': index_number},
                {
                    '$set': {
                        'courses': [],
                        'cleared_at': datetime.now(),
                        'is_empty': True
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"❌ Error clearing basket in database: {str(e)}")

def add_to_basket(email, index_number, level, course):
    """Add course to user's basket with database sync"""
    basket_key = f'basket_{level}_{index_number}'
    
    # Get current basket
    basket = session.get(basket_key, {'courses': []})
    
    # Check if course already in basket
    course_id = str(course.get('_id', ''))
    if not any(str(c.get('_id', '')) == course_id for c in basket['courses']):
        basket['courses'].append(course)
        basket['updated_at'] = datetime.now().isoformat()
        session[basket_key] = basket
        
        # Sync with database if connected
        if database_connected:
            try:
                user_baskets_collection.update_one(
                    {'email': email, 'index_number': index_number, 'level': level},
                    {
                        '$set': {
                            'courses': basket['courses'],
                            'updated_at': datetime.now(),
                            'is_empty': False
                        }
                    },
                    upsert=True
                )
            except Exception as e:
                print(f"❌ Error syncing basket to database: {str(e)}")
                
def get_basket(email, index_number, level):
    """Get user's basket with database sync"""
    basket_key = f'basket_{level}_{index_number}'
    
    # Try database first if connected
    if database_connected:
        try:
            db_basket = user_baskets_collection.find_one({
                'email': email,
                'index_number': index_number,
                'level': level
            })
            
            if db_basket:
                # Update session with database data
                session[basket_key] = {
                    'courses': db_basket.get('courses', []),
                    'updated_at': datetime.now().isoformat(),
                    'from_db': True
                }
                return session[basket_key]
        except Exception as e:
            print(f"❌ Error getting basket from database: {str(e)}")
    
    # Fallback to session
    return session.get(basket_key, {'courses': [], 'updated_at': datetime.now().isoformat()})

def remove_from_basket(email, index_number, level, course_id):
    """Remove course from user's basket with database sync"""
    basket_key = f'basket_{level}_{index_number}'
    basket = session.get(basket_key, {'courses': []})
    
    # Remove course from basket
    basket['courses'] = [c for c in basket['courses'] if str(c.get('_id', '')) != str(course_id)]
    basket['updated_at'] = datetime.now().isoformat()
    session[basket_key] = basket
    
    # Sync with database if connected
    if database_connected:
        try:
            user_baskets_collection.update_one(
                {'email': email, 'index_number': index_number, 'level': level},
                {
                    '$set': {
                        'courses': basket['courses'],
                        'updated_at': datetime.now(),
                        'is_empty': len(basket['courses']) == 0
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"❌ Error syncing basket removal to database: {str(e)}")