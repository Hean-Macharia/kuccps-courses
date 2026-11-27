

from flask import render_template, url_for, Blueprint
from datetime import datetime

# Create a Blueprint for guides with a unique name
guides_blueprint = Blueprint('kuccps_guides', __name__)

@guides_blueprint.route('/')
def guides_index():
    """Main guides index page"""
    return render_template('guides/guides_index.html',
                         title='KUCCPS Guides | KCSE Course Selection and Placement Help',
                         meta_description='Practical guides to KCSE course requirements, cluster points, course categories and the KUCCPS application process. Confirm current placement details on the official KUCCPS portal.',
                         canonical_url=url_for('kuccps_guides.guides_index', _external=True))

@guides_blueprint.route('/cluster-points-explained')
def cluster_points():
    """Guide: KUCCPS cluster points explained"""
    return render_template('guides/cluster_points.html',
                         title='KUCCPS Cluster Points Explained | Course Selection Guide',
                         meta_description='Understand how cluster points relate to course selection, why requirements differ by programme, and where to verify current KUCCPS information.',
                         canonical_url=url_for('kuccps_guides.cluster_points', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/kcse-admission-requirements')
def kcse_admission():
    """Guide: KCSE grades and university admission"""
    return render_template('guides/kcse_admission.html',
                         title='KCSE Grades and University Admission in Kenya | Guide',
                         meta_description='Learn how KCSE grades and programme-specific subject requirements affect university course options in Kenya. Check official KUCCPS guidance for the current cycle.',
                         canonical_url=url_for('kuccps_guides.kcse_admission', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/diploma-courses-kenya')
def diploma_courses():
    """Guide: Diploma courses in Kenya"""
    return render_template('guides/diploma_courses.html',
                         title='Diploma Courses in Kenya | Entry Requirements Guide',
                         meta_description='Explore diploma study pathways in Kenya and learn how to check entry requirements by programme and institution.',
                         canonical_url=url_for('kuccps_guides.diploma_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/certificate-courses-requirements')
def certificate_courses():
    """Guide: Certificate courses requirements"""
    return render_template('guides/certificate_courses.html',
                         title='Certificate Courses in Kenya | Entry Requirements Guide',
                         meta_description='Learn about certificate study pathways in Kenya and how to compare published entry requirements for individual programmes.',
                         canonical_url=url_for('kuccps_guides.certificate_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/kmtc-courses-admission')
def kmtc_courses():
    """Guide: KMTC courses admission"""
    return render_template('guides/kmtc_courses.html',
                         title='KMTC Courses | Requirements and KUCCPS Application Guide',
                         meta_description='Review KMTC course options and learn where to verify programme-specific entry requirements and current application steps.',
                         canonical_url=url_for('kuccps_guides.kmtc_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/artisan-courses-kenya')
def artisan_courses():
    """Guide: Artisan courses in Kenya"""
    return render_template('guides/artisan_courses.html',
                         title='Artisan Courses in Kenya | Training and Entry Guide',
                         meta_description='Explore artisan and vocational training pathways in Kenya and learn how to check requirements for each programme.',
                         canonical_url=url_for('kuccps_guides.artisan_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/ttc-teacher-training-courses')
def ttc_courses():
    """Guide: TTC teacher training courses"""
    return render_template('guides/ttc_courses.html',
                         title='Teacher Training College Courses in Kenya | Guide',
                         meta_description='Learn about teacher-training pathways in Kenya and verify programme requirements and current placement guidance with official sources.',
                         canonical_url=url_for('kuccps_guides.ttc_courses', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/kuccps-application-process')
def kuccps_application():
    """Guide: KUCCPS application process"""
    return render_template('guides/kuccps_application.html',
                         title='KUCCPS Application Process | Student Guide',
                         meta_description='A guide to preparing for KUCCPS course applications. Application windows and procedures can change, so confirm current instructions on the official student portal.',
                         canonical_url=url_for('kuccps_guides.kuccps_application', _external=True),
                         current_year=datetime.now().year)

@guides_blueprint.route('/scholarships-opportunities')
def scholarships():
    """Guide: Scholarships opportunities"""
    return render_template('guides/scholarships.html',
                         title='Scholarships and Student Funding in Kenya | Guide',
                         meta_description='Find starting points for checking student funding and scholarship information in Kenya, and verify current eligibility and deadlines with providers.',
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
