

from flask import render_template, url_for, Blueprint
from datetime import datetime

# Create a Blueprint for guides with a unique name
guides_blueprint = Blueprint('kuccps_guides', __name__)

@guides_blueprint.route('/')
def guides_index():
    """Main guides index page"""
    return render_template('guides/guides_index.html',
                         title='KUCCPS Guides 2025 | Complete Resource Center',
                         meta_description='Complete collection of KUCCPS guides for 2025 admission. Learn about cluster points, requirements, and application process.',
                         canonical_url=url_for('kuccps_guides.guides_index', _external=True))

@guides_blueprint.route('/cluster-points-explained')
def cluster_points():
    """Guide: KUCCPS cluster points explained"""
    return render_template('guides/cluster_points.html',
                         title='KUCCPS Cluster Points Explained 2025 | How to Calculate',
                         meta_description='Complete guide to KUCCPS cluster points for 2025 university admission. Learn how points are calculated and what you need.',
                         canonical_url=url_for('kuccps_guides.cluster_points', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/kcse-admission-requirements')
def kcse_admission():
    """Guide: KCSE grades and university admission"""
    return render_template('guides/kcse_admission.html',
                         title='KCSE Grades and University Admission 2025 | Minimum Requirements',
                         meta_description='Learn about KCSE grades required for university admission in Kenya 2025. Complete guide to admission requirements.',
                         canonical_url=url_for('kuccps_guides.kcse_admission', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/diploma-courses-kenya')
def diploma_courses():
    """Guide: Diploma courses in Kenya"""
    return render_template('guides/diploma_courses.html',
                         title='Diploma Courses in Kenya 2025 - Complete Guide',
                         meta_description='Complete guide to diploma courses in Kenya 2025. Requirements, popular courses, colleges, and career paths.',
                         canonical_url=url_for('kuccps_guides.diploma_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/certificate-courses-requirements')
def certificate_courses():
    """Guide: Certificate courses requirements"""
    return render_template('guides/certificate_courses.html',
                         title='Certificate Courses in Kenya 2025 - Entry Requirements',
                         meta_description='Complete guide to certificate courses in Kenya 2025. Requirements, course options, and job opportunities.',
                         canonical_url=url_for('kuccps_guides.certificate_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/kmtc-courses-admission')
def kmtc_courses():
    """Guide: KMTC courses admission"""
    return render_template('guides/kmtc_courses.html',
                         title='KMTC Courses 2025 - Admission Requirements & Application',
                         meta_description='Complete guide to KMTC courses for 2025 intake. Requirements, application process, campuses, and career opportunities.',
                         canonical_url=url_for('kuccps_guides.kmtc_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/artisan-courses-kenya')
def artisan_courses():
    """Guide: Artisan courses in Kenya"""
    return render_template('guides/artisan_courses.html',
                         title='Artisan Courses in Kenya 2025 - Skills Training',
                         meta_description='Guide to artisan courses in Kenya 2025. Learn about skills training, requirements, colleges, and employment opportunities.',
                         canonical_url=url_for('kuccps_guides.artisan_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/ttc-teacher-training-courses')
def ttc_courses():
    """Guide: TTC teacher training courses"""
    return render_template('guides/ttc_courses.html',
                         title='TTC Courses 2025 - Teacher Training Colleges',
                         meta_description='Complete guide to TTC courses in Kenya 2025. Requirements, colleges, application process, and teaching career opportunities.',
                         canonical_url=url_for('kuccps_guides.ttc_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/kuccps-application-process')
def kuccps_application():
    """Guide: KUCCPS application process"""
    return render_template('guides/kuccps_application.html',
                         title='KUCCPS Application Process 2025 - Step by Step',
                         meta_description='Step-by-step guide to KUCCPS application process 2025. Learn how to apply for university, diploma, and certificate courses.',
                         canonical_url=url_for('kuccps_guides.kuccps_application', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/scholarships-opportunities')
def scholarships():
    """Guide: Scholarships opportunities"""
    return render_template('guides/scholarships.html',
                         title='Scholarships for Kenyan Students 2025',
                         meta_description='Complete guide to scholarships for Kenyan students 2025. Government, county, private, and international scholarship opportunities.',
                         canonical_url=url_for('kuccps_guides.scholarships', _external=True),
                         current_year=datetime.now().year)

def register_guides(app):
    """Register the guides blueprint with the Flask app"""
    # Check if blueprint is already registered
    if 'kuccps_guides' not in app.blueprints:
        app.register_blueprint(guides_blueprint, url_prefix='/guides')
        print("✅ Guides blueprint registered successfully")
    else:
        print("⚠️ Guides blueprint already registered")