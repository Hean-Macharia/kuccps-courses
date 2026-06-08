#!/usr/bin/env python3
"""Add FAQ schemas to guides missing them."""

from pathlib import Path

BASE_PATH = Path(__file__).parent / "templates" / "guides"

FAQ_CONFIG = {
    "kcse_admission.html": [
        ("What are KUCCPS degree entry requirements with C+ mean grade?", "With C+ mean grade on KCSE, you qualify for many KUCCPS degree programs depending on your KUCCPS cluster points. Check specific KUCCPS degree requirements - most KUCCPS programs require KUCCPS cluster points 28-35 with C+."),
        ("What KCSE grades do I need for KUCCPS engineering degree?", "KUCCPS engineering requires minimum B- mean grade with KCSE Math and Physics as mandatory. KUCCPS engineering cluster points requirement is 36-42. Verify current KUCCPS engineering cut off points as they vary annually."),
        ("What are KUCCPS medicine entry requirements?", "KUCCPS medicine requires A- or A mean grade with Biology, Chemistry, and Math subjects. KUCCPS medicine cluster points are typically 40-48. KUCCPS medicine is highly competitive with KUCCPS cut off points among the highest."),
        ("Can I do KUCCPS law with C+ grade?", "KUCCPS law requires B- mean grade minimum, so C+ does not meet KUCCPS law entry requirements. However, related KUCCPS programs may be available with C+. Check KUCCPS entry requirements for all programs matching your grades."),
        ("What is the difference between KUCCPS cluster points and KCSE mean grade?", "KCSE mean grade averages all 8 subjects. KUCCPS cluster points use your best 4 subjects in specific combinations. Both KUCCPS cluster points AND KCSE mean grade must meet program requirements - you cannot substitute one for the other."),
        ("What KUCCPS programs require Kiswahili?", "Most KUCCPS degree programs don't require Kiswahili. However, KUCCPS teaching degree for Kiswahili specialist requires strong Kiswahili grade. Check specific KUCCPS program requirements for language subject needs."),
        ("What KUCCPS programs can I access with B- mean grade?", "With B- mean grade, you qualify for many KUCCPS programs including engineering (cluster points 36+), law (cluster points 35+), business, and nursing. Check specific KUCCPS entry requirements for your chosen KUCCPS degree."),
        ("How do KUCCPS cut off points change from year to year?", "KUCCPS cut off points increase when program demand exceeds capacity. Popular KUCCPS programs like medicine and engineering typically have highest KUCCPS cut off points. Less competitive KUCCPS programs have lower KUCCPS requirements."),
        ("What KUCCPS programs don't require Physics?", "KUCCPS business, accounting, economics, and social sciences don't require Physics. However, KUCCPS engineering, medicine, nursing, and CS all require Physics. Verify subject requirements for your KUCCPS program."),
        ("What is the lowest KUCCPS entry requirement among degree programs?", "General KUCCPS programs in arts and social sciences have lower KUCCPS entry requirements - typically C+ mean grade with KUCCPS cluster points 24-28. Check specific KUCCPS entry requirements for individual degree programs."),
    ],
    "kuccps_application.html": [
        ("When does KUCCPS application open in 2026?", "KUCCPS application typically opens within 2-4 weeks after KCSE results announcement. Exact KUCCPS timeline varies annually. Monitor KUCCPS official website for 2026 KUCCPS application dates."),
        ("How do I check my KUCCPS eligibility?", "Create KUCCPS account with KCSE index number and check KUCCPS eligibility tool. KUCCPS eligibility depends on KCSE mean grade and KUCCPS cluster points from best 4 subjects. KUCCPS calculator shows programs you qualify for."),
        ("How many KUCCPS programs should I select?", "KUCCPS recommends selecting 4-6 programs within your KUCCPS cluster. KUCCPS strategy: select mix of competitive and realistic KUCCPS options. Avoid selecting programs above your KUCCPS cluster point range."),
        ("What if I don't get placed in KUCCPS?", "Unsuccessful KUCCPS applicants join KUCCPS supplementary round (if available) or private KUCCPS institutions. Some KUCCPS candidates repeat KCSE for better KUCCPS grades. KUCCPS pathways exist through diploma or certificate options."),
        ("Can I change KUCCPS programs after selection?", "Once KUCCPS placement confirmed, changes are limited. KUCCPS institution transfer may be possible in rare KUCCPS circumstances. KUCCPS policy: complete selection process carefully before KUCCPS confirmation."),
        ("How long KUCCPS selection process takes?", "KUCCPS selection typically takes 6-12 weeks after application closes. KUCCPS results announcement includes KUCCPS placement notifications. KUCCPS timeline varies depending on application volume."),
        ("What documents needed for KUCCPS admission?", "KUCCPS admission requires KCSE certificate, national ID, KUCCPS acceptance letter, medical report, and proof of fees. Check specific KUCCPS institution requirements as KUCCPS documents vary slightly."),
        ("Can I defer KUCCPS admission to next year?", "Most KUCCPS institutions allow deferment for valid KUCCPS reasons. KUCCPS deferment typically requires written request and approval. Contact KUCCPS institution directly about KUCCPS deferment process."),
        ("What are KUCCPS cluster point minimums for courses?", "Different KUCCPS programs require different minimums: KUCCPS degree 24-48, KUCCPS diploma 20-28, KUCCPS certificate 12-20, KUCCPS artisan varies. Check specific KUCCPS program cluster point requirements."),
        ("How important is course order in KUCCPS selection?", "KUCCPS selection algorithm considers preference order. Put realistic KUCCPS options first to secure placement. KUCCPS dreams (competitive programs) can be lower in KUCCPS list if realistic options prioritized first."),
    ],
    "scholarships.html": [
        ("What are main KUCCPS scholarship sources for students?", "KUCCPS funding: HELB loans (government), NSF grants (needy students), university KUCCPS scholarships, corporate KUCCPS sponsorship, international KUCCPS grants. Multiple KUCCPS sources available to qualify KUCCPS students."),
        ("How do I apply for KUCCPS HELB loan?", "KUCCPS HELB application through KUCCPS institution. KUCCPS HELB requires KCSE certificate and admission letter. KUCCPS HELB process typically opens after KUCCPS admission confirmation."),
        ("What is KUCCPS NSF needy students fund?", "KUCCPS NSF provides grants (not loans) to qualifying KUCCPS needy students. KUCCPS NSF funds approximately 15% of KUCCPS student population. KUCCPS NSF application through student portal with supporting KUCCPS documentation."),
        ("Can I get KUCCPS merit scholarship?", "KUCCPS merit scholarships available for academic excellence (top KCSE grades) or sports KUCCPS achievements. Check if your KUCCPS institution offers merit KUCCPS scholarships. KUCCPS merit criteria very specific to KUCCPS program."),
        ("What is KUCCPS scholarship repayment period?", "KUCCPS loans must begin repayment after 2-5 years post-graduation depending on KUCCPS institution. KUCCPS HELB loan repayment spans 10 years. KUCCPS grants (NSF) are non-repayable KUCCPS support."),
        ("Can international students get KUCCPS scholarships?", "Limited KUCCPS scholarships for international students through specific KUCCPS programs. Some countries sponsor KUCCPS nationals studying in Kenya. Check African KUCCPS scholarship networks for international KUCCPS support."),
        ("How much does KUCCPS HELB loan cover?", "KUCCPS HELB covers approximately 60-70% of tuition depending on KUCCPS institution. KUCCPS students pay remaining tuition from own KUCCPS resources. KUCCPS loan amount varies by KUCCPS program and institution."),
        ("What disqualifies me from KUCCPS NSF?", "KUCCPS NSF disqualifications: previously KUCCPS sponsored, family income above KUCCPS threshold, or incomplete KUCCPS documentation. KUCCPS NSF criteria strictly assessed for KUCCPS needy qualification."),
        ("Can KUCCPS scholarship be used for private institutions?", "KUCCPS government loans typically apply to recognized KUCCPS institutions only. Private KUCCPS institutions may have alternative KUCCPS funding. Check specific KUCCPS private institution scholarships."),
        ("How do I maximize KUCCPS funding?", "KUCCPS strategy: apply for HELB (all students), apply for NSF if needy (KUCCPS grants), seek university KUCCPS scholarships, explore corporate KUCCPS sponsorship programs, combine multiple KUCCPS sources for maximum KUCCPS coverage."),
    ],
    "guides_index.html": [
        ("Where do I start with KUCCPS guides?", "Start by understanding your KUCCPS eligibility using cluster points guide. Then check KUCCPS degree/diploma/certificate guides matching your interests. Review KUCCPS application process guide before registration deadline."),
        ("How accurate are KUCCPS guides for 2026?", "KUCCPS guides are updated regularly for 2026 guidelines. However, always verify details on official KUCCPS website for latest KUCCPS policy changes. KUCCPS policies may change mid-year affecting KUCCPS students."),
        ("Can KUCCPS guides help with career choice?", "Yes, KUCCPS guides detail careers for different KUCCPS program types. Guides explain KUCCPS job prospects, earning potential, and required KUCCPS skills. Use KUCCPS information for informed KUCCPS career planning."),
        ("Are KUCCPS guides free to access?", "Yes, all KUCCPS guides are completely free. KUCCPS resources aim to make KUCCPS information accessible to all students. No KUCCPS fees required for guide access."),
        ("What KUCCPS topics are covered in guides?", "KUCCPS guides cover: cluster points, degree admission, diploma courses, certificates, artisan training, teacher training, healthcare (KMTC), application process, scholarships, and general KUCCPS system overview."),
        ("How often are KUCCPS guides updated?", "KUCCPS guides are updated annually with latest KUCCPS policies and procedures. Mid-year updates occur if significant KUCCPS policy changes announced. Check publication dates on KUCCPS guides."),
        ("Can I print KUCCPS guides?", "Yes, KUCCPS guides can be downloaded and printed for personal KUCCPS use. Sharing KUCCPS guides with peers and younger students is encouraged for KUCCPS education support."),
        ("Who created these KUCCPS guides?", "KUCCPS guides created by education experts familiar with Kenya's KUCCPS system. KUCCPS information compiled from official sources and KUCCPS student experiences for accuracy."),
        ("What if I can't find KUCCPS answer?", "Check specific KUCCPS guide related to your question. Search KUCCPS FAQs in each guide. Contact KUCCPS support or your school career counselor for KUCCPS clarification."),
        ("How KUCCPS guides help KUCCPS success?", "KUCCPS guides provide knowledge for making informed KUCCPS decisions. Understanding KUCCPS system increases placement chances. KUCCPS strategic planning based on guides improves KUCCPS educational outcomes."),
    ],
}

def add_faq_schema(file_path, guide_name):
    """Add FAQ schema to guide."""
    questions = FAQ_CONFIG.get(guide_name)
    if not questions:
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if FAQPage already exists
    if "FAQPage" in content:
        print(f"  ✓ {guide_name} - FAQPage already exists")
        return False
    
    # Build FAQ items
    faq_items = []
    for question, answer in questions:
        # Escape quotes in strings
        q = question.replace('"', '\\"')
        a = answer.replace('"', '\\"')
        faq_items.append(f'''    {{
      "@type": "Question",
      "name": "{q}",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "{a}"
      }}
    }}''')
    
    faq_schema = f'''<!-- FAQ Schema for KUCCPS -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
{",".join(faq_items)}
  ]
}}
</script>
'''
    
    # Find position to insert - before the final {% endblock %} of links block
    # Look for the last occurrence of script closing before the first content block
    content_block_start = content.find("{% block content %}")
    if content_block_start == -1:
        print(f"  ✗ {guide_name} - No content block")
        return False
    
    # Find last </script> before content block
    search_area = content[:content_block_start]
    last_script_end = search_area.rfind("</script>")
    if last_script_end == -1:
        print(f"  ✗ {guide_name} - No script found")
        return False
    
    # Insert after the last script
    insert_pos = last_script_end + len("</script>\n")
    content = content[:insert_pos] + faq_schema + content[insert_pos:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✓ Added FAQ schema to {guide_name}")
    return True

def main():
    """Process guides needing FAQ schemas."""
    guides = list(FAQ_CONFIG.keys())
    
    print("Adding FAQ schemas to guides...\n")
    updated_count = 0
    
    for guide in guides:
        file_path = BASE_PATH / guide
        if file_path.exists():
            if add_faq_schema(file_path, guide):
                updated_count += 1
        else:
            print(f"  ✗ {guide} not found")
    
    print(f"\n✓ Completed: {updated_count} guides updated")

if __name__ == "__main__":
    main()
