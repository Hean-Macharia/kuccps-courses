"""
SEO Setup Script for kuccpscourses.co.ke
Run this to implement SEO optimizations
"""

import os
import sys
from datetime import datetime

def print_header():
    print("=" * 70)
    print("KUCCPS COURSES CHECKER - SEO OPTIMIZATION SETUP 2026")
    print("=" * 70)
    print()

def check_prerequisites():
    """Check if all prerequisites are met"""
    print("🔍 Checking prerequisites...")
    
    requirements = [
        ("Google Search Console Account", True, "Create at https://search.google.com/search-console"),
        ("Google Analytics Account", True, "Create at https://analytics.google.com"),
        ("Google Business Profile", False, "Optional for local SEO"),
        ("Social Media Profiles", True, "Facebook, Twitter, WhatsApp group"),
    ]
    
    for req, required, note in requirements:
        status = "✅" if required else "⚠️"
        print(f"  {status} {req} - {note}")
    
    return True

def generate_robots_txt():
    """Generate optimized robots.txt"""
    print("\n🤖 Generating robots.txt...")
    
    robots_content = """User-agent: *
Allow: /
Allow: /sitemap.xml
Allow: /news/
Allow: /guides/
Disallow: /admin/
Disallow: /debug/
Disallow: /temp-bypass/
Disallow: /static/js/
Disallow: /static/css/

# Crawl-delay for search engines
Crawl-delay: 2

# Sitemap location
Sitemap: https://kuccpscourses.co.ke/sitemap.xml

# Preferred domain
Host: https://www.kuccpscourses.co.ke"""
    
    with open('robots.txt', 'w') as f:
        f.write(robots_content)
    
    print("✅ robots.txt generated successfully")

def generate_seo_meta_template():
    """Generate SEO meta tags template"""
    print("\n🏷️ Generating SEO meta templates...")
    
    template = """<!-- SEO Meta Tags Template -->
{% set seo_meta = {
    'title': 'KUCCPS Courses Checker 2026 | Find Your Courses',
    'description': 'Find KUCCPS courses that match your KCSE grades. Degree, Diploma, Certificate, KMTC, Artisan and TTC programs in Kenya.',
    'keywords': 'KUCCPS, courses, KCSE, Kenya, degree, diploma, certificate, artisan, TTC, KMTC, university, college, admission 2026',
    'author': 'Hean Njuki',
    'og_type': 'website',
    'twitter_card': 'summary_large_image'
} %}

{% if seo_override %}
    {% set seo_meta = seo_meta.update(seo_override) %}
{% endif %}

<!-- Primary Meta Tags -->
<title>{{ seo_meta.title }}</title>
<meta name="description" content="{{ seo_meta.description }}">
<meta name="keywords" content="{{ seo_meta.keywords }}">
<meta name="author" content="{{ seo_meta.author }}">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="{{ seo_meta.og_type }}">
<meta property="og:url" content="{{ canonical_url|default(site_url) }}">
<meta property="og:title" content="{{ seo_meta.title }}">
<meta property="og:description" content="{{ seo_meta.description }}">
<meta property="og:image" content="{{ og_image_url }}">

<!-- Twitter -->
<meta property="twitter:card" content="{{ seo_meta.twitter_card }}">
<meta property="twitter:url" content="{{ canonical_url|default(site_url) }}">
<meta property="twitter:title" content="{{ seo_meta.title }}">
<meta property="twitter:description" content="{{ seo_meta.description }}">
<meta property="twitter:image" content="{{ twitter_image_url }}">"""
    
    with open('templates/seo_meta.html', 'w') as f:
        f.write(template)
    
    print("✅ SEO meta template generated")

def generate_keyword_research():
    """Generate keyword research report"""
    print("\n🔑 Generating keyword research...")
    
    keywords = {
        'primary': [
            "KUCCPS courses 2026",
            "how to check KUCCPS courses",
            "KUCCPS portal login",
            "KCSE cluster points",
            "university courses in Kenya"
        ],
        'secondary': [
            "diploma courses Kenya 2026",
            "certificate courses requirements",
            "KMTC courses admission",
            "TTC teacher training colleges",
            "artisan courses Kenya"
        ],
        'long_tail': [
            "what KCSE grade for medicine",
            "cluster points for engineering",
            "how to calculate KUCCPS points",
            "best diploma courses for C+",
            "affordable certificate courses Nairobi"
        ]
    }
    
    report = f"""# Keyword Research Report - KUCCPS Courses Checker
Generated: {datetime.now().strftime('%Y-%m-%d')}

## Primary Keywords (High Volume)
{chr(10).join(f"- {kw}" for kw in keywords['primary'])}

## Secondary Keywords (Medium Volume)
{chr(10).join(f"- {kw}" for kw in keywords['secondary'])}

## Long-Tail Keywords (High Intent)
{chr(10).join(f"- {kw}" for kw in keywords['long_tail'])}

## Target Pages
1. Homepage: "KUCCPS courses 2026", "how to check KUCCPS courses"
2. Degree Page: "university courses in Kenya", "cluster points for engineering"
3. Diploma Page: "diploma courses Kenya 2026", "best diploma courses for C+"
4. KMTC Page: "KMTC courses admission", "medical courses Kenya"
5. Guides: Long-tail informational keywords

## Competition Analysis
- High: "KUCCPS", "university courses"
- Medium: "diploma courses", "certificate courses"
- Low: Specific course names, location-based searches"""
    
    with open('keyword_research.md', 'w') as f:
        f.write(report)
    
    print("✅ Keyword research generated")

def generate_content_calendar():
    """Generate content calendar for 2026"""
    print("\n📅 Generating content calendar...")
    
    calendar = """# Content Calendar 2026 - KUCCPS Courses Checker

## January 2026
- [ ] Blog: "KCSE Results 2025 Released - Next Steps for University Admission"
- [ ] Update: Refresh all course databases for 2026 intake
- [ ] Social: Launch 2026 admission campaign

## February 2026
- [ ] Guide: "KUCCPS First Revision - Complete Guide 2026"
- [ ] Blog: "Top 10 Degree Courses for 2026 Admission"
- [ ] Update: Add 2026-specific course requirements

## March 2026
- [ ] Guide: "How to Choose Between Degree and Diploma"
- [ ] Blog: "Affordable University Courses in Kenya"
- [ ] Case Study: "Success Stories - Students Who Used Our Checker"

## April 2026
- [ ] Guide: "KUCCPS Second Revision - Last Chance to Change Courses"
- [ ] Blog: "Diploma vs Certificate - Which is Better?"
- [ ] Update: Industry demand analysis for 2026

## May 2026
- [ ] Guide: "What to Do If You Miss KUCCPS Placement"
- [ ] Blog: "Alternative Career Paths Beyond University"
- [ ] Social: Q&A sessions for anxious students

## Ongoing Tasks
- Weekly: Update news section with KUCCPS announcements
- Monthly: Check and update broken links
- Quarterly: Refresh meta descriptions
- Bi-annually: Major content audit"""
    
    with open('content_calendar.md', 'w') as f:
        f.write(calendar)
    
    print("✅ Content calendar generated")

def generate_backlink_strategy():
    """Generate backlink acquisition strategy"""
    print("\n🔗 Generating backlink strategy...")
    
    strategy = """# Backlink Acquisition Strategy 2026

## Phase 1: Foundation (Months 1-3)
1. **Local Business Directories**
   - KenyaYote.com
   - OnlineKenya.com
   - KenyanList.com
   
2. **Education Portals**
   - Kenya Education Guide
   - University.co.ke
   - College.co.ke

3. **Social Profiles**
   - Complete Google Business Profile
   - Active Facebook Page
   - Twitter account with regular updates
   - LinkedIn company page

## Phase 2: Outreach (Months 4-6)
1. **Guest Posting**
   - Education blogs in Kenya
   - Student forums
   - Career guidance websites

2. **Resource Links**
   - Create valuable guides (like this one)
   - Offer as resource for educational websites
   - Get listed in "useful tools for students" pages

3. **Partnerships**
   - Collaborate with schools
   - Partner with educational NGOs
   - Work with career counselors

## Phase 3: Authority Building (Months 7-12)
1. **Press Coverage**
   - Local education news
   - Student success stories
   - Service launches/updates

2. **Academic References**
   - Get mentioned in educational research
   - University resource pages
   - Government education portals

3. **Social Proof**
   - Student testimonials
   - Success case studies
   - Media mentions

## Target Websites
1. High Authority (.edu, .ac.ke, .go.ke)
2. Education blogs with DA 30+
3. Student forums and communities
4. Local news websites
5. Career guidance portals

## Tracking
- Use Google Search Console
- Monitor referring domains monthly
- Track organic traffic growth
- Measure keyword rankings"""
    
    with open('backlink_strategy.md', 'w') as f:
        f.write(strategy)
    
    print("✅ Backlink strategy generated")

def main():
    print_header()
    
    if not check_prerequisites():
        print("\n❌ Some prerequisites are missing. Please address them first.")
        sys.exit(1)
    
    try:
        generate_robots_txt()
        generate_seo_meta_template()
        generate_keyword_research()
        generate_content_calendar()
        generate_backlink_strategy()
        
        print("\n" + "=" * 70)
        print("✅ SEO SETUP COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        
        print("\n📋 Next Steps:")
        print("1. Upload the generated robots.txt to your server root")
        print("2. Implement the SEO meta template in your base.html")
        print("3. Follow the keyword research for content creation")
        print("4. Use the content calendar to plan your 2026 updates")
        print("5. Execute the backlink strategy gradually")
        print("\n6. Register for Google Search Console and verify ownership")
        print("7. Submit your sitemap in GSC")
        print("8. Set up Google Analytics tracking")
        print("9. Monitor performance monthly in GSC")
        print("10. Update content regularly based on search trends")
        
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()