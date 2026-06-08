#!/usr/bin/env python3
"""Add meta keywords tags to all guide templates."""

from pathlib import Path

BASE_PATH = Path(__file__).parent / "templates" / "guides"

KEYWORDS_CONFIG = {
    "kcse_admission.html": "KUCCPS degree courses, KUCCPS cluster points calculator 2026, KUCCPS engineering requirements, KUCCPS medicine cut off, KUCCPS law entry requirements, KUCCPS business degree, KUCCPS nursing programs, KUCCPS teaching degree, KUCCPS computer science, KUCCPS degree with C+, KUCCPS cut off points trends, university admission calculator, degree program matcher, KUCCPS eligibility checker, cluster points guide, KCSE grades requirements, university entry requirements, KUCCPS admission 2026, degree placement Kenya",
    
    "diploma_courses.html": "KUCCPS diploma courses, KUCCPS diploma C-, KUCCPS technical programs, KUCCPS college placement, KUCCPS diploma nursing, KUCCPS diploma engineering, KUCCPS diploma IT, KUCCPS diploma business, KUCCPS TVET courses, KUCCPS diploma placement 2026, diploma entry requirements, technical training Kenya, KUCCPS college courses, diploma with C minus, KUCCPS diploma admission, vocational programs Kenya, technical skills training, diploma programs 2026",
    
    "certificate_courses.html": "KUCCPS certificate courses, KUCCPS certificate D+, KUCCPS short courses, KUCCPS vocational certificates, KUCCPS certificate programs, KUCCPS certificate business, certificate course checker, D plus courses KUCCPS, KUCCPS certificate admission, short term training Kenya, certificate entry requirements, KUCCPS certificate skills, professional certificates Kenya, KUCCPS certificate placement, quick training programs, KUCCPS certificate 2026, certificate with D plus",
    
    "artisan_courses.html": "KUCCPS artisan courses, KUCCPS trade programs, KUCCPS vocational training, KUCCPS plumbing course, KUCCPS electrical course, KUCCPS carpentry, KUCCPS welding, KUCCPS motor vehicle mechanics, KUCCPS hairdressing, KUCCPS catering, KUCCPS artisan requirements, artisan training Kenya, trades vocational, KUCCPS artisan admission, skilled trades training, vocational programs Kenya, artisan courses 2026, practical skills training",
    
    "ttc_courses.html": "KUCCPS TTC programs, KUCCPS teacher training, KUCCPS diploma education, KUCCPS primary teacher, KUCCPS secondary teacher, KUCCPS teaching requirements, KUCCPS education degree, KUCCPS TTC placement, KUCCPS TSC requirements, KUCCPS P1 teacher, teacher training college Kenya, KUCCPS teacher entrance, education diploma 2026, TTC admission requirements, KUCCPS teaching career, TSC job placement, teaching profession Kenya, educator training programs",
    
    "kmtc_courses.html": "KUCCPS KMTC programs, KUCCPS nursing courses, KUCCPS medical training, KUCCPS clinical medicine, KUCCPS pharmacy, KUCCPS community health, KUCCPS medical lab, KUCCPS nursing without chemistry, KUCCPS KMTC requirements, KUCCPS nursing cut off, healthcare training Kenya, nursing diploma 2026, KMTC admission requirements, medical training programs, KUCCPS health programs, clinical officer courses, healthcare education Kenya, nursing courses Kenya",
    
    "kuccps_application.html": "KUCCPS application process, KUCCPS application 2026, KUCCPS online registration, cluster points calculator, KUCCPS course selection, university admission Kenya, KUCCPS portal registration, KUCCPS eligibility check, application deadline 2026, degree placement Kenya, KUCCPS cluster selection, university course selection, admission requirements guide, application step by step, KUCCPS system explained, higher education admission",
    
    "scholarships.html": "KUCCPS scholarships, financial aid Kenya, university scholarships 2026, HELB loans, needy students fund, scholarship opportunities, education funding, tuition assistance, merit scholarships Kenya, education grants, student finance, scholarship application 2026, university fees funding, educational support programs, KUCCPS funding options, financial assistance students",
    
    "guides_index.html": "KUCCPS guides, educational guides Kenya, university guides 2026, admission guides, course selection guide, career guides Kenya, education resources, KUCCPS resources, higher education information, university admission guide, course comparison, program information, educational planning, KUCCPS education system, complete guides 2026",
}

def add_keywords(file_path, guide_name):
    """Add meta keywords tag to guide."""
    keywords = KEYWORDS_CONFIG.get(guide_name)
    if not keywords:
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if keywords already exist
    if '<meta name="keywords"' in content:
        print(f"  ✓ {guide_name} - Keywords already exist")
        return False
    
    # Find the location after {% block links %} to insert keywords
    block_start = content.find("{% block links %}")
    if block_start == -1:
        print(f"  ✗ {guide_name} - Could not find block links")
        return False
    
    # Insert after {% block links %} and newline
    insert_pos = content.find("\n", block_start) + 1
    
    keywords_tag = f'<meta name="keywords" content="{keywords}">\n'
    content = content[:insert_pos] + keywords_tag + content[insert_pos:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✓ Added keywords to {guide_name}")
    return True

def main():
    """Process all guide files."""
    guides = list(KEYWORDS_CONFIG.keys())
    
    print("Adding meta keywords tags to guides...\n")
    updated_count = 0
    
    for guide in guides:
        file_path = BASE_PATH / guide
        if file_path.exists():
            if add_keywords(file_path, guide):
                updated_count += 1
        else:
            print(f"  ✗ {guide} not found")
    
    print(f"\n✓ Completed: {updated_count} guides updated")

if __name__ == "__main__":
    main()
