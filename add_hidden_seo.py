#!/usr/bin/env python3
"""Add hidden SEO divs to guides that have FAQ but no hidden content."""

from pathlib import Path

BASE_PATH = Path(__file__).parent / "templates" / "guides"

HIDDEN_SEO_CONTENT = {
    "diploma_courses.html": """<h2>KUCCPS Diploma Courses & Technical Programs 2026</h2>
<p>KUCCPS diploma courses provide excellent career pathways for students not pursuing university degrees. KUCCPS diploma programs require C- mean grade combined with appropriate KUCCPS cluster points (typically 20-28). KUCCPS diploma offers specialized training in KUCCPS nursing diploma, KUCCPS engineering diploma, KUCCPS IT diploma, KUCCPS business diploma, and KUCCPS TVET programs.</p>
<p>KUCCPS diploma entry requirements are more accessible than KUCCPS degree programs. Students with C- or D+ may qualify for KUCCPS diploma depending on subject combination and KUCCPS cluster points. KUCCPS diploma placement offers practical skills training for careers in various KUCCPS technical fields.</p>
<p>Popular KUCCPS diploma options include KUCCPS nursing diploma (2-3 years), KUCCPS engineering diploma in various specializations, KUCCPS IT diploma for technology careers, and KUCCPS hospitality diploma. Each KUCCPS diploma program has specific KUCCPS entry requirements regarding subject prerequisites and KUCCPS cluster points needed.</p>""",
    
    "certificate_courses.html": """<h2>KUCCPS Certificate Courses & Short Training Programs 2026</h2>
<p>KUCCPS certificate courses provide shorter training pathways for quick skill acquisition and employment. KUCCPS certificate programs require D+ mean grade, making them accessible to more students. KUCCPS certificate courses range from 6 months to 1 year, offering specialized KUCCPS training in business, technology, hospitality, and vocational fields.</p>
<p>KUCCPS certificate entry requirements are lower than KUCCPS diploma or degree. Students with D+ can qualify for KUCCPS certificate programs through KUCCPS application process. KUCCPS certificate programs are ideal for rapid career transition and immediate employment prospects in KUCCPS fields.</p>
<p>Popular KUCCPS certificate options include KUCCPS business certificate, KUCCPS IT certificate, KUCCPS hospitality certificate, and KUCCPS vocational certificates. Each KUCCPS certificate program offers practical skills and industry-recognized qualifications valuable in job market within KUCCPS sectors.</p>""",
    
    "artisan_courses.html": """<h2>KUCCPS Artisan Courses & Vocational Training 2026</h2>
<p>KUCCPS artisan programs provide hands-on vocational training for skilled trades and immediate employment. KUCCPS artisan courses are accessible with lower KCSE requirements (D-), making KUCCPS artisan training available to most secondary school leavers. KUCCPS artisan specializations include plumbing, electrical, carpentry, welding, motor vehicle mechanics, and hairdressing offered through KUCCPS training centers.</p>
<p>KUCCPS artisan training emphasizes practical skills over theory. KUCCPS artisan programs typically run 1-2 years with substantial hands-on components. KUCCPS artisan graduates acquire marketable skills for self-employment or immediate KUCCPS employment in construction, automotive, and service industries.</p>
<p>KUCCPS artisan entry requirements are among lowest in Kenyan KUCCPS education system. KUCCPS artisan programs accept D- mean grade and sometimes don't require specific subject combinations. KUCCPS artisan training provides pathway for students not pursuing traditional KUCCPS degree or diploma.</p>""",
    
    "ttc_courses.html": """<h2>KUCCPS Teacher Training & TTC Programs 2026</h2>
<p>KUCCPS Teacher Training Colleges (TTC) prepare educators for Kenya's schools through comprehensive KUCCPS teacher training programs. KUCCPS TTC entry requires specific qualifications and KCSE grades (typically B- for KUCCPS teacher training). KUCCPS TTC programs including KUCCPS primary teacher education and KUCCPS secondary teacher training offer 2-year and 3-year KUCCPS certification paths respectively.</p>
<p>KUCCPS teacher training emphasizes pedagogy, subject expertise, and practical classroom experience. KUCCPS TTC includes teaching practice in real schools, combining KUCCPS theoretical knowledge with hands-on KUCCPS teaching experience. KUCCPS graduates qualify for TSC (Teachers Service Commission) employment as KUCCPS teachers.</p>
<p>KUCCPS TTC pathway options: KUCCPS primary teacher training (P1 certificate - 2 years), KUCCPS secondary teacher training (diploma - 3 years), KUCCPS early childhood education. Each KUCCPS TTC program has distinct KUCCPS entry requirements and subject specializations available through KUCCPS colleges.</p>""",
    
    "kmtc_courses.html": """<h2>KUCCPS KMTC Healthcare & Nursing Courses 2026</h2>
<p>KMTC (Kenya Medical Training College) under KUCCPS offers comprehensive healthcare and nursing education programs. KUCCPS KMTC nursing courses include KUCCPS nursing diploma and KUCCPS clinical officer training with strong hands-on medical experience. KUCCPS KMTC entry requires B- mean grade combined with KUCCPS cluster points, mandatory Biology and Chemistry subjects for KUCCPS healthcare programs.</p>
<p>KUCCPS nursing programs through KMTC prepare registered nurses for healthcare delivery across Kenya. KUCCPS KMTC nursing diploma takes 3 years with clinical rotations in KUCCPS hospitals. KUCCPS nursing without chemistry entry requirements vary - verify specific KUCCPS KMTC program prerequisites for KUCCPS course access.</p>
<p>KUCCPS KMTC specializations include KUCCPS nursing (registered nurse), KUCCPS clinical officer, KUCCPS community health, KUCCPS pharmacy assistant, KUCCPS laboratory technician. Each KUCCPS KMTC program has distinct KUCCPS entry requirements and specialization focus within healthcare.</p>""",
}

def add_hidden_seo(file_path, guide_name):
    """Add hidden SEO div to guide."""
    content = HIDDEN_SEO_CONTENT.get(guide_name)
    if not content:
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    # Check if already has hidden SEO
    if "Hidden SEO" in file_content:
        print(f"  ✓ {guide_name} - Hidden SEO already exists")
        return False
    
    # Find the final {% endblock %} and insert before it
    last_endblock = file_content.rfind("{% endblock %}")
    if last_endblock == -1:
        print(f"  ✗ {guide_name} - Could not find endblock")
        return False
    
    hidden_div = f'''
<!-- Hidden SEO Content -->
<div style="position: absolute; clip: rect(1px, 1px, 1px, 1px); width: 1px; height: 1px; overflow: hidden;">
{content}
</div>
'''
    
    file_content = file_content[:last_endblock] + hidden_div + "\n" + file_content[last_endblock:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(file_content)
    
    print(f"  ✓ Added hidden SEO to {guide_name}")
    return True

def main():
    """Process guides needing hidden SEO."""
    guides = list(HIDDEN_SEO_CONTENT.keys())
    
    print("Adding hidden SEO content to guides...\n")
    updated_count = 0
    
    for guide in guides:
        file_path = BASE_PATH / guide
        if file_path.exists():
            if add_hidden_seo(file_path, guide):
                updated_count += 1
        else:
            print(f"  ✗ {guide} not found")
    
    print(f"\n✓ Completed: {updated_count} guides updated")

if __name__ == "__main__":
    main()
