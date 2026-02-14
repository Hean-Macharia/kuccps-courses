# content_generator.py

import os
from datetime import datetime

def generate_guide_content():
    """Generate comprehensive content for all guide pages"""
    
    guides = {
        'cluster_points.html': {
            'title': 'KUCCPS Cluster Points Explained 2025',
            'content': '''
            <h1>Understanding KUCCPS Cluster Points for University Admission</h1>
            
            <div class="guide-section">
                <h2>What Are Cluster Points?</h2>
                <p>Cluster Points are the scoring system used by KUCCPS to place students in university degree programs. They determine which courses you qualify for based on your KCSE performance and subject combinations.</p>
                
                <div class="info-box">
                    <h3>Key Facts About Cluster Points:</h3>
                    <ul>
                        <li>Each cluster has specific subject requirements</li>
                        <li>Points are calculated from your best 4 subjects</li>
                        <li>Different courses have different cutoff points</li>
                        <li>Points range varies by cluster (30-48 points)</li>
                    </ul>
                </div>
            </div>

            <div class="guide-section">
                <h2>How Cluster Points Are Calculated</h2>
                
                <h3>Step-by-Step Calculation:</h3>
                <ol>
                    <li><strong>Identify Required Subjects:</strong> Each cluster requires specific subjects</li>
                    <li><strong>Select Your Best Grades:</strong> Take your best performing subjects</li>
                    <li><strong>Convert Grades to Points:</strong> A=12, A-=11, B+=10, B=9, B-=8, C+=7, C=6, C-=5, D+=4, D=3, D-=2, E=1</li>
                    <li><strong>Sum Up Points:</strong> Add points from your best 4 subjects</li>
                    <li><strong>Compare with Cutoff:</strong> Check if your points meet the course requirement</li>
                </ol>

                <table class="points-table">
                    <thead>
                        <tr>
                            <th>Grade</th>
                            <th>Points</th>
                            <th>Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>A</td><td>12</td><td>Excellent</td></tr>
                        <tr><td>A-</td><td>11</td><td>Very Good</td></tr>
                        <tr><td>B+</td><td>10</td><td>Good</td></tr>
                        <tr><td>B</td><td>9</td><td>Above Average</td></tr>
                        <tr><td>B-</td><td>8</td><td>Average</td></tr>
                        <tr><td>C+</td><td>7</td><td>Minimum University Entry</td></tr>
                        <tr><td>C</td><td>6</td><td>Diploma Entry</td></tr>
                        <tr><td>C-</td><td>5</td><td>Certificate Entry</td></tr>
                        <tr><td>D+</td><td>4</td><td>Artisan Entry</td></tr>
                        <tr><td>D</td><td>3</td><td>Below Minimum</td></tr>
                        <tr><td>D-</td><td>2</td><td>Poor</td></tr>
                        <tr><td>E</td><td>1</td><td>Fail</td></tr>
                    </tbody>
                </table>
            </div>

            <div class="guide-section">
                <h2>Common Clusters and Their Requirements</h2>
                
                <div class="cluster-grid">
                    <div class="cluster-card">
                        <h3>Cluster 5: Engineering & Technology</h3>
                        <p><strong>Required:</strong> Mathematics, Physics, Chemistry</p>
                        <p><strong>Cutoff Range:</strong> 36-48 points</p>
                    </div>
                    
                    <div class="cluster-card">
                        <h3>Cluster 9: Biological Sciences</h3>
                        <p><strong>Required:</strong> Biology, Chemistry, Mathematics/Physics</p>
                        <p><strong>Cutoff Range:</strong> 32-45 points</p>
                    </div>
                    
                    <div class="cluster-card">
                        <h3>Cluster 13: Medical & Health</h3>
                        <p><strong>Required:</strong> Biology, Chemistry, Physics/Mathematics</p>
                        <p><strong>Cutoff Range:</strong> 38-48 points</p>
                    </div>
                    
                    <div class="cluster-card">
                        <h3>Cluster 2: Business & Hospitality</h3>
                        <p><strong>Required:</strong> Mathematics, English, Business Studies</p>
                        <p><strong>Cutoff Range:</strong> 30-42 points</p>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Tips for Maximizing Your Cluster Points</h2>
                <div class="tips-grid">
                    <div class="tip">
                        <h4>📊 Focus on Core Subjects</h4>
                        <p>Concentrate on the subjects required for your desired cluster</p>
                    </div>
                    <div class="tip">
                        <h4>🎯 Know Minimum Requirements</h4>
                        <p>Research the cutoff points for courses you're interested in</p>
                    </div>
                    <div class="tip">
                        <h4>📈 Improve Weak Areas</h4>
                        <p>Identify and work on subjects where you can gain more points</p>
                    </div>
                    <div class="tip">
                        <h4>🔍 Explore Alternatives</h4>
                        <p>Have backup clusters with similar subject requirements</p>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>FAQs About Cluster Points</h2>
                
                <div class="faq">
                    <h3>❓ Can I apply with less than 4 subjects?</h3>
                    <p>No, KUCCPS requires at least 4 subjects to calculate cluster points. Ensure you have grades for all required subjects.</p>
                </div>
                
                <div class="faq">
                    <h3>❓ What if I don't meet the cutoff points?</h3>
                    <p>Consider diploma or certificate courses as alternative pathways to your career goals.</p>
                </div>
                
                <div class="faq">
                    <h3>❓ Are cluster points the same every year?</h3>
                    <p>Cutoff points vary annually based on competition and available spaces. Use previous years as a guide.</p>
                </div>
                
                <div class="faq">
                    <h3>❓ Can I improve my cluster points?</h3>
                    <p>You cannot change KCSE grades, but you can improve through diploma programs or retaking specific subjects.</p>
                </div>
            </div>
            ''',
            'meta_description': 'Complete guide to KUCCPS cluster points for 2025 university admission. Learn how points are calculated, cluster requirements, and cutoff points for different courses.'
        },
        
        'kcse_admission.html': {
            'title': 'KCSE Grades and University Admission 2025',
            'content': '''
            <h1>KCSE Grades for University Admission in Kenya 2025</h1>
            
            <div class="guide-section">
                <h2>Minimum University Entry Requirements</h2>
                <p>To qualify for university admission through KUCCPS, you must meet the following minimum requirements:</p>
                
                <div class="requirements-grid">
                    <div class="requirement-card">
                        <div class="requirement-grade">C+</div>
                        <h3>Overall Grade</h3>
                        <p>Minimum mean grade for degree programs</p>
                    </div>
                    
                    <div class="requirement-card">
                        <div class="requirement-grade">C+</div>
                        <h3>Specific Subjects</h3>
                        <p>Minimum grade in cluster-specific subjects</p>
                    </div>
                    
                    <div class="requirement-card">
                        <div class="requirement-grade">4</div>
                        <h3>Subject Count</h3>
                        <p>Minimum subjects for point calculation</p>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Grade Pathways to Higher Education</h2>
                
                <div class="pathway-chart">
                    <div class="pathway">
                        <div class="grade-level">A to B</div>
                        <h3>Degree Programs</h3>
                        <p>Direct entry to Bachelor's degree courses</p>
                        <ul>
                            <li>Medicine, Engineering, Law</li>
                            <li>Most competitive courses</li>
                            <li>4-6 year programs</li>
                        </ul>
                    </div>
                    
                    <div class="pathway">
                        <div class="grade-level">C+ to C</div>
                        <h3>Diploma Programs</h3>
                        <p>Technical and professional courses</p>
                        <ul>
                            <li>2-3 year programs</li>
                            <li>Can upgrade to degree</li>
                            <li>Practical skills focus</li>
                        </ul>
                    </div>
                    
                    <div class="pathway">
                        <div class="grade-level">C- to D+</div>
                        <h3>Certificate Programs</h3>
                        <p>Vocational and skills training</p>
                        <ul>
                            <li>1-2 year programs</li>
                            <li>Entry-level skills</li>
                            <li>Can progress to diploma</li>
                        </ul>
                    </div>
                    
                    <div class="pathway">
                        <div class="grade-level">D to E</div>
                        <h3>Artisan Programs</h3>
                        <p>Technical skills training</p>
                        <ul>
                            <li>6 months - 1 year</li>
                            <li>Hands-on skills</li>
                            <li>Employment focused</li>
                        </ul>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Subject Groupings and Their Importance</h2>
                
                <table class="subject-table">
                    <thead>
                        <tr>
                            <th>Subject Group</th>
                            <th>Core Subjects</th>
                            <th>Common Courses</th>
                            <th>Minimum Grade</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>Sciences</strong></td>
                            <td>Math, Physics, Chemistry, Biology</td>
                            <td>Medicine, Engineering, Sciences</td>
                            <td>B- in core subjects</td>
                        </tr>
                        <tr>
                            <td><strong>Humanities</strong></td>
                            <td>English, Kiswahili, History, CRE</td>
                            <td>Law, Education, Arts</td>
                            <td>C+ in core subjects</td>
                        </tr>
                        <tr>
                            <td><strong>Technical</strong></td>
                            <td>Woodwork, Metalwork, Drawing</td>
                            <td>Engineering Tech, Architecture</td>
                            <td>C in core subjects</td>
                        </tr>
                        <tr>
                            <td><strong>Business</strong></td>
                            <td>Math, Business Studies, English</td>
                            <td>Commerce, Accounting, Economics</td>
                            <td>C+ in Math & English</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="guide-section">
                <h2>Improving Your Admission Chances</h2>
                
                <div class="strategy-grid">
                    <div class="strategy">
                        <h4>📚 Subject Selection Strategy</h4>
                        <ul>
                            <li>Choose subjects relevant to your career goals</li>
                            <li>Balance between sciences and humanities</li>
                            <li>Consider subject combinations for multiple clusters</li>
                        </ul>
                    </div>
                    
                    <div class="strategy">
                        <h4>🎓 Alternative Pathways</h4>
                        <ul>
                            <li>Diploma to degree bridging programs</li>
                            <li>Private university options</li>
                            <li>TVET institution pathways</li>
                        </ul>
                    </div>
                    
                    <div class="strategy">
                        <h4>🏫 Institution Choice</h4>
                        <ul>
                            <li>Apply to less competitive institutions</li>
                            <li>Consider county government scholarships</li>
                            <li>Explore emerging universities</li>
                        </ul>
                    </div>
                    
                    <div class="strategy">
                        <h4>💼 Career Alignment</h4>
                        <ul>
                            <li>Match courses with job market demand</li>
                            <li>Consider skills-based programs</li>
                            <li>Research employment rates</li>
                        </ul>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Important Dates and Deadlines</h2>
                
                <div class="timeline">
                    <div class="timeline-item">
                        <div class="timeline-date">Feb - Mar</div>
                        <h4>KUCCPS Application Period</h4>
                        <p>First revision of course choices</p>
                    </div>
                    
                    <div class="timeline-item">
                        <div class="timeline-date">April - May</div>
                        <h4>Second Revision</h4>
                        <p>Adjust choices based on cutoff points</p>
                    </div>
                    
                    <div class="timeline-item">
                        <div class="timeline-date">June - July</div>
                        <h4>Placement Results</h4>
                        <p>University placement announced</p>
                    </div>
                    
                    <div class="timeline-item">
                        <div class="timeline-date">August</div>
                        <h4>Reporting Period</h4>
                        <p>Students report to assigned institutions</p>
                    </div>
                </div>
            </div>
            ''',
            'meta_description': 'Complete guide to KCSE grades required for university admission in Kenya 2025. Learn about minimum requirements, grade pathways, and admission strategies.'
        },
        
        'diploma_courses.html': {
            'title': 'Diploma Courses in Kenya 2025 - Complete Guide',
            'content': '''
            <h1>Diploma Courses in Kenya 2025: Requirements, Colleges & Career Paths</h1>
            
            <div class="guide-section">
                <h2>What Are Diploma Courses?</h2>
                <p>Diploma courses are 2-3 year technical and professional programs offered by polytechnics, technical training institutes, and some universities. They provide practical skills and can lead directly to employment or serve as a pathway to degree programs.</p>
                
                <div class="highlight-box">
                    <h3>Benefits of Diploma Courses:</h3>
                    <ul>
                        <li><strong>Shorter Duration:</strong> 2-3 years compared to 4-6 years for degrees</li>
                        <li><strong>Practical Focus:</strong> Hands-on skills for immediate employment</li>
                        <li><strong>Lower Entry Requirements:</strong> KCSE mean grade of C plain</li>
                        <li><strong>Career Pathways:</strong> Can upgrade to degree programs</li>
                        <li><strong>Affordable:</strong> Generally lower fees than degree programs</li>
                    </ul>
                </div>
            </div>

            <div class="guide-section">
                <h2>Popular Diploma Courses in Kenya</h2>
                
                <div class="course-grid">
                    <div class="course-category">
                        <h3>🎓 Business & Management</h3>
                        <ul>
                            <li><strong>Diploma in Business Management</strong> - C plain</li>
                            <li><strong>Diploma in Human Resource Management</strong> - C plain</li>
                            <li><strong>Diploma in Supply Chain Management</strong> - C plain</li>
                            <li><strong>Diploma in Accounting</strong> - C+ with Math C+</li>
                            <li><strong>Diploma in Banking & Finance</strong> - C plain</li>
                        </ul>
                    </div>
                    
                    <div class="course-category">
                        <h3>⚕️ Medical & Health</h3>
                        <ul>
                            <li><strong>Diploma in Nursing</strong> - C+ with Biology C+</li>
                            <li><strong>Diploma in Clinical Medicine</strong> - C+ with Biology C+</li>
                            <li><strong>Diploma in Pharmacy</strong> - C+ with Chemistry C+</li>
                            <li><strong>Diploma in Medical Laboratory</strong> - C+ with Biology C+</li>
                            <li><strong>Diploma in Public Health</strong> - C plain</li>
                        </ul>
                    </div>
                    
                    <div class="course-category">
                        <h3>💻 IT & Computing</h3>
                        <ul>
                            <li><strong>Diploma in IT</strong> - C plain</li>
                            <li><strong>Diploma in Software Development</strong> - C plain</li>
                            <li><strong>Diploma in Computer Science</strong> - C plain</li>
                            <li><strong>Diploma in Cybersecurity</strong> - C plain</li>
                            <li><strong>Diploma in Data Science</strong> - C plain with Math C</li>
                        </ul>
                    </div>
                    
                    <div class="course-category">
                        <h3>🔧 Engineering & Technical</h3>
                        <ul>
                            <li><strong>Diploma in Electrical Engineering</strong> - C plain with Physics C</li>
                            <li><strong>Diploma in Mechanical Engineering</strong> - C plain with Physics C</li>
                            <li><strong>Diploma in Civil Engineering</strong> - C plain with Math C</li>
                            <li><strong>Diploma in Automotive Engineering</strong> - C plain</li>
                            <li><strong>Diploma in Building Technology</strong> - C plain</li>
                        </ul>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Top Institutions Offering Diploma Courses</h2>
                
                <div class="institution-list">
                    <div class="institution">
                        <h3>Kenya Polytechnic (TVETA Accredited)</h3>
                        <p><strong>Popular Courses:</strong> Engineering, IT, Business</p>
                        <p><strong>Location:</strong> Nairobi & branches nationwide</p>
                    </div>
                    
                    <div class="institution">
                        <h3>Kenya Medical Training College (KMTC)</h3>
                        <p><strong>Popular Courses:</strong> All medical diplomas</p>
                        <p><strong>Location:</strong> Campuses nationwide</p>
                    </div>
                    
                    <div class="institution">
                        <h3>Technical University of Kenya</h3>
                        <p><strong>Popular Courses:</strong> Technical & engineering</p>
                        <p><strong>Location:</strong> Nairobi</p>
                    </div>
                    
                    <div class="institution">
                        <h3>KASNEB Accredited Colleges</h3>
                        <p><strong>Popular Courses:</strong> Accounting, finance</p>
                        <p><strong>Location:</strong> Various private colleges</p>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Diploma to Degree Pathways</h2>
                
                <div class="pathway-info">
                    <h3>How to Upgrade from Diploma to Degree:</h3>
                    <ol>
                        <li><strong>Complete Your Diploma:</strong> Finish with good grades (Credit or Distinction)</li>
                        <li><strong>Work Experience:</strong> Some programs require 1-2 years of relevant experience</li>
                        <li><strong>Apply for Credit Transfer:</strong> Apply to universities that recognize your diploma</li>
                        <li><strong>Direct Entry to 2nd Year:</strong> Most universities allow entry to year 2 of degree</li>
                        <li><strong>Complete Degree:</strong> Finish remaining 2-3 years of degree program</li>
                    </ol>
                    
                    <div class="note-box">
                        <h4>Important Note:</h4>
                        <p>Not all diplomas guarantee degree entry. Check with specific universities about their credit transfer policies and articulation agreements.</p>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Employment Opportunities After Diploma</h2>
                
                <div class="employment-grid">
                    <div class="employment-sector">
                        <h4>🏢 Private Sector</h4>
                        <ul>
                            <li>Technicians and technologists</li>
                            <li>Supervisory roles</li>
                            <li>Middle management</li>
                            <li>Specialized technical staff</li>
                        </ul>
                    </div>
                    
                    <div class="employment-sector">
                        <h4>🏛️ Public Sector</h4>
                        <ul>
                            <li>County government jobs</li>
                            <li>National government agencies</li>
                            <li>Parastatals and regulatory bodies</li>
                            <li>Technical positions in ministries</li>
                        </ul>
                    </div>
                    
                    <div class="employment-sector">
                        <h4>👨‍💼 Self-Employment</h4>
                        <ul>
                            <li>Start your own business</li>
                            <li>Consultancy services</li>
                            <li>Contract work</li>
                            <li>Freelancing opportunities</li>
                        </ul>
                    </div>
                    
                    <div class="employment-sector">
                        <h4>🌍 International Opportunities</h4>
                        <ul>
                            <li>Work abroad programs</li>
                            <li>Regional employment (East Africa)</li>
                            <li>International companies in Kenya</li>
                            <li>Remote work possibilities</li>
                        </ul>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Application Process for Diploma Courses</h2>
                
                <div class="process-steps">
                    <div class="step">
                        <div class="step-number">1</div>
                        <h4>Check Requirements</h4>
                        <p>Verify you meet minimum KCSE requirements</p>
                    </div>
                    
                    <div class="step">
                        <div class="step-number">2</div>
                        <h4>Choose Course & College</h4>
                        <p>Select based on career goals and location</p>
                    </div>
                    
                    <div class="step">
                        <div class="step-number">3</div>
                        <h4>Apply</h4>
                        <p>Submit application through KUCCPS or direct to college</p>
                    </div>
                    
                    <div class="step">
                        <div class="step-number">4</div>
                        <h4>Submit Documents</h4>
                        <p>KCSE certificate, ID, photos, and application fee</p>
                    </div>
                    
                    <div class="step">
                        <div class="step-number">5</div>
                        <h4>Await Admission</h4>
                        <p>Check placement results and reporting dates</p>
                    </div>
                </div>
            </div>
            ''',
            'meta_description': 'Complete guide to diploma courses in Kenya 2025. Requirements, popular courses, top colleges, career paths, and diploma to degree pathways.'
        },
        
        'certificate_courses.html': {
            'title': 'Certificate Courses in Kenya 2025 - Entry Requirements',
            'content': '''
            <h1>Certificate Courses in Kenya 2025: Your Path to Skills Development</h1>
            
            <div class="guide-section">
                <h2>What Are Certificate Courses?</h2>
                <p>Certificate courses are short-term vocational training programs (6 months to 2 years) designed to provide specific skills for employment or business. They are ideal for KCSE graduates with grades D+ to C- who want to gain marketable skills quickly.</p>
                
                <div class="benefits-box">
                    <h3>Why Choose Certificate Courses?</h3>
                    <ul>
                        <li><strong>Quick Skills Acquisition:</strong> 6 months to 1 year duration</li>
                        <li><strong>Low Entry Requirements:</strong> KCSE mean grade of D+</li>
                        <li><strong>Practical Training:</strong> Hands-on skills for immediate employment</li>
                        <li><strong>Affordable:</strong> Lower fees than diploma or degree programs</li>
                        <li><strong>Flexible Learning:</strong> Part-time and evening classes available</li>
                        <li><strong>Pathway to Higher Education:</strong> Can progress to diploma programs</li>
                    </ul>
                </div>
            </div>

            <div class="guide-section">
                <h2>Certificate Courses by Category</h2>
                
                <div class="category-tabs">
                    <div class="tab-content active" id="technical">
                        <h3>🔧 Technical & Engineering</h3>
                        <ul>
                            <li><strong>Certificate in Electrical Installation</strong> - D+</li>
                            <li><strong>Certificate in Motor Vehicle Mechanics</strong> - D+</li>
                            <li><strong>Certificate in Welding & Fabrication</strong> - D plain</li>
                            <li><strong>Certificate in Plumbing</strong> - D plain</li>
                            <li><strong>Certificate in Masonry</strong> - D plain</li>
                            <li><strong>Certificate in Carpentry & Joinery</strong> - D plain</li>
                        </ul>
                    </div>
                    
                    <div class="tab-content" id="business">
                        <h3>💼 Business & Office Skills</h3>
                        <ul>
                            <li><strong>Certificate in Secretarial Studies</strong> - D+</li>
                            <li><strong>Certificate in Business Management</strong> - D+</li>
                            <li><strong>Certificate in Sales & Marketing</strong> - D plain</li>
                            <li><strong>Certificate in Customer Service</strong> - D plain</li>
                            <li><strong>Certificate in Entrepreneurship</strong> - D plain</li>
                            <li><strong>Certificate in Store Keeping</strong> - D plain</li>
                        </ul>
                    </div>
                    
                    <div class="tab-content" id="hospitality">
                        <h3>🏨 Hospitality & Tourism</h3>
                        <ul>
                            <li><strong>Certificate in Food & Beverage</strong> - D+</li>
                            <li><strong>Certificate in Housekeeping</strong> - D plain</li>
                            <li><strong>Certificate in Tour Guiding</strong> - D+</li>
                            <li><strong>Certificate in Cookery</strong> - D plain</li>
                            <li><strong>Certificate in Front Office Operations</strong> - D+</li>
                            <li><strong>Certificate in Travel Operations</strong> - D+</li>
                        </ul>
                    </div>
                    
                    <div class="tab-content" id="computing">
                        <h3>💻 Computing & IT</h3>
                        <ul>
                            <li><strong>Certificate in Computer Applications</strong> - D+</li>
                            <li><strong>Certificate in Graphic Design</strong> - D plain</li>
                            <li><strong>Certificate in Digital Marketing</strong> - D plain</li>
                            <li><strong>Certificate in Computer Repair</strong> - D+</li>
                            <li><strong>Certificate in Web Design</strong> - D+</li>
                            <li><strong>Certificate in Data Entry</strong> - D plain</li>
                        </ul>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Where to Study Certificate Courses</h2>
                
                <div class="institution-types">
                    <div class="type-card">
                        <h3>Youth Polytechnics</h3>
                        <p><strong>Focus:</strong> Technical and artisan skills</p>
                        <p><strong>Fees:</strong> Subsidized by government</p>
                        <p><strong>Duration:</strong> 6 months - 1 year</p>
                    </div>
                    
                    <div class="type-card">
                        <h3>Technical Training Institutes</h3>
                        <p><strong>Focus:</strong> Comprehensive vocational training</p>
                        <p><strong>Fees:</strong> Moderate, with HELB loans available</p>
                        <p><strong>Duration:</strong> 1-2 years</p>
                    </div>
                    
                    <div class="type-card">
                        <h3>Private Colleges</h3>
                        <p><strong>Focus:</strong> Business, IT, hospitality</p>
                        <p><strong>Fees:</strong> Varies by college</p>
                        <p><strong>Duration:</strong> 6 months - 2 years</p>
                    </div>
                    
                    <div class="type-card">
                        <h3>National Polytechnics</h3>
                        <p><strong>Focus:</strong> All certificate courses</p>
                        <p><strong>Fees:</strong> Government rates</p>
                        <p><strong>Duration:</strong> 1-2 years</p>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Certificate to Diploma Progression</h2>
                
                <div class="progression-path">
                    <div class="level">
                        <h4>Step 1: Complete Certificate</h4>
                        <p>Finish your certificate course with good grades</p>
                    </div>
                    
                    <div class="arrow">→</div>
                    
                    <div class="level">
                        <h4>Step 2: Work Experience</h4>
                        <p>Gain 1-2 years of relevant work experience</p>
                    </div>
                    
                    <div class="arrow">→</div>
                    
                    <div class="level">
                        <h4>Step 3: Apply for Diploma</h4>
                        <p>Apply for related diploma program</p>
                    </div>
                    
                    <div class="arrow">→</div>
                    
                    <div class="level">
                        <h4>Step 4: Credit Transfer</h4>
                        <p>Get exemptions for certificate modules</p>
                    </div>
                </div>
                
                <div class="note">
                    <p><strong>Note:</strong> Some institutions allow direct progression from certificate to diploma without work experience, especially for good performers.</p>
                </div>
            </div>

            <div class="guide-section">
                <h2>Job Opportunities After Certificate Courses</h2>
                
                <div class="job-opportunities">
                    <div class="job-sector">
                        <h4>🏗️ Construction Industry</h4>
                        <ul>
                            <li>Mason - Ksh 20,000 - 40,000</li>
                            <li>Electrician - Ksh 25,000 - 50,000</li>
                            <li>Plumber - Ksh 20,000 - 40,000</li>
                            <li>Welder - Ksh 25,000 - 45,000</li>
                        </ul>
                    </div>
                    
                    <div class="job-sector">
                        <h4>🏢 Office & Administration</h4>
                        <ul>
                            <li>Office Assistant - Ksh 15,000 - 30,000</li>
                            <li>Receptionist - Ksh 20,000 - 35,000</li>
                            <li>Data Entry Clerk - Ksh 18,000 - 30,000</li>
                            <li>Customer Care - Ksh 20,000 - 35,000</li>
                        </ul>
                    </div>
                    
                    <div class="job-sector">
                        <h4>🏨 Hospitality Sector</h4>
                        <ul>
                            <li>Hotel Attendant - Ksh 15,000 - 30,000</li>
                            <li>Cook/Chef - Ksh 20,000 - 40,000</li>
                            <li>Tour Guide - Ksh 25,000 - 50,000+ tips</li>
                            <li>Housekeeping - Ksh 15,000 - 30,000</li>
                        </ul>
                    </div>
                    
                    <div class="job-sector">
                        <h4>🚗 Automotive Industry</h4>
                        <ul>
                            <li>Mechanic - Ksh 25,000 - 50,000</li>
                            <li>Panel Beater - Ksh 20,000 - 40,000</li>
                            <li>Spray Painter - Ksh 20,000 - 40,000</li>
                            <li>Auto Electrician - Ksh 25,000 - 45,000</li>
                        </ul>
                    </div>
                </div>
            </div>

            <div class="guide-section">
                <h2>Government Sponsorship & Funding</h2>
                
                <div class="funding-options">
                    <div class="funding">
                        <h4>📋 TVET Scholarship</h4>
                        <p>Government scholarship for technical courses</p>
                        <p><strong>Eligibility:</strong> KCSE D+ and above</p>
                    </div>
                    
                    <div class="funding">
                        <h4>💰 HELB Loans</h4>
                        <p>Student loans for certificate courses</p>
                        <p><strong>Amount:</strong> Up to Ksh 40,000 per year</p>
                    </div>
                    
                    <div class="funding">
                        <h4>🎓 County Bursaries</h4>
                        <p>Financial support from county governments</p>
                        <p><strong>Apply:</strong> Through your local Ward office</p>
                    </div>
                    
                    <div class="funding">
                        <h4>🏢 Institutional Support</h4>
                        <p>Fee payment plans from colleges</p>
                        <p><strong>Options:</strong> Installments, work-study</p>
                    </div>
                </div>
            </div>
            ''',
            'meta_description': 'Complete guide to certificate courses in Kenya 2025. Requirements, course options, colleges, job opportunities, and progression to diploma programs.'
        }
    }
    
    # Add more guides for other pages
    guides.update({
        'kmtc_courses.html': {
            'title': 'KMTC Courses 2025 - Admission Requirements & Application',
            'content': '''
            <h1>Kenya Medical Training College (KMTC) Courses 2025</h1>
            <!-- Content for KMTC courses -->
            ''',
            'meta_description': 'Complete guide to KMTC courses for 2025 intake. Requirements, application process, campuses, and career opportunities in healthcare.'
        },
        
        'artisan_courses.html': {
            'title': 'Artisan Courses in Kenya 2025 - Skills Training',
            'content': '''
            <h1>Artisan Courses in Kenya 2025: Practical Skills Training</h1>
            <!-- Content for artisan courses -->
            ''',
            'meta_description': 'Guide to artisan courses in Kenya 2025. Learn about skills training, requirements, colleges, and employment opportunities.'
        },
        
        'ttc_courses.html': {
            'title': 'TTC Courses 2025 - Teacher Training Colleges',
            'content': '''
            <h1>Teacher Training College (TTC) Courses 2025</h1>
            <!-- Content for TTC courses -->
            ''',
            'meta_description': 'Complete guide to TTC courses in Kenya 2025. Requirements, colleges, application process, and teaching career opportunities.'
        },
        
        'kuccps_application.html': {
            'title': 'KUCCPS Application Process 2025 - Step by Step',
            'content': '''
            <h1>KUCCPS Application Process 2025: Complete Guide</h1>
            <!-- Content for KUCCPS application -->
            ''',
            'meta_description': 'Step-by-step guide to KUCCPS application process 2025. Learn how to apply for university, diploma, and certificate courses.'
        },
        
        'scholarships.html': {
            'title': 'Scholarships for Kenyan Students 2025',
            'content': '''
            <h1>Scholarships and Financial Aid for Kenyan Students 2025</h1>
            <!-- Content for scholarships -->
            ''',
            'meta_description': 'Complete guide to scholarships for Kenyan students 2025. Government, county, private, and international scholarship opportunities.'
        }
    })
    
    return guides

def create_guide_templates():
    """Create guide HTML files with the generated content"""
    
    # Get the generated content
    guides = generate_guide_content()
    
    # Base template for all guides
    base_template = r'''<!DOCTYPE html>

<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}} | KUCCPS Courses Checker</title>
    <meta name="description" content="{{meta_description}}">
    <meta name="keywords" content="KUCCPS, courses, Kenya, {{keywords}}">
    <meta name="author" content="KUCCPS Courses Checker">
    
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="article">
    <meta property="og:url" content="{{current_url}}">
    <meta property="og:title" content="{{title}}">
    <meta property="og:description" content="{{meta_description}}">
    <meta property="og:image" content="/static/images/og-guide-image.jpg">
    
    <!-- Twitter -->
    <meta property="twitter:card" content="summary_large_image">
    <meta property="twitter:url" content="{{current_url}}">
    <meta property="twitter:title" content="{{title}}">
    <meta property="twitter:description" content="{{meta_description}}">
    <meta property="twitter:image" content="/static/images/twitter-guide-card.jpg">
    
    <!-- Canonical URL -->
    <link rel="canonical" href="{{current_url}}">
    
    <!-- Breadcrumb Schema -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [{
            "@type": "ListItem",
            "position": 1,
            "name": "Home",
            "item": "https://kuccpscourses.co.ke"
        },{
            "@type": "ListItem",
            "position": 2,
            "name": "Guides",
            "item": "https://kuccpscourses.co.ke/guides"
        },{
            "@type": "ListItem",
            "position": 3,
            "name": "{{title}}",
            "item": "{{current_url}}"
        }]
    }
    </script>
    
    <!-- Article Schema -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{{title}}",
        "description": "{{meta_description}}",
        "image": "https://kuccpscourses.co.ke/static/images/guide-banner.jpg",
        "author": {
            "@type": "Organization",
            "name": "KUCCPS Courses Checker"
        },
        "publisher": {
            "@type": "Organization",
            "name": "KUCCPS Courses Checker",
            "logo": {
                "@type": "ImageObject",
                "url": "https://kuccpscourses.co.ke/static/images/logo.png"
            }
        },
        "datePublished": "{{current_date}}",
        "dateModified": "{{current_date}}"
    }
    </script>
    
    <!-- CSS -->
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="stylesheet" href="/static/css/guides.css">
    
    <!-- Favicon -->
    <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
    
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        <div class="container">
            <a href="/" class="logo">KUCCPS<span>Courses</span></a>
            <ul class="nav-menu">
                <li><a href="/">Home</a></li>
                <li><a href="/degree">Degree</a></li>
                <li><a href="/diploma">Diploma</a></li>
                <li><a href="/certificate">Certificate</a></li>
                <li><a href="/artisan">Artisan</a></li>
                <li><a href="/kmtc">KMTC</a></li>
                <li><a href="/ttc">TTC</a></li>
                <li><a href="/guides" class="active">Guides</a></li>
                <li><a href="/contact">Contact</a></li>
            </ul>
            <button class="mobile-menu-btn">
                <i class="fas fa-bars"></i>
            </button>
        </div>
    </nav>

    <!-- Breadcrumb -->
    <div class="breadcrumb">
        <div class="container">
            <a href="/">Home</a> &gt;
            <a href="/guides">Guides</a> &gt;
            <span>{{title}}</span>
        </div>
    </div>

    <!-- Main Content -->
    <main class="guide-container">
        <div class="container">
            <div class="guide-header">
                <h1>{{title}}</h1>
                <div class="guide-meta">
                    <span><i class="fas fa-calendar"></i> Last Updated: {{current_date}}</span>
                    <span><i class="fas fa-clock"></i> Read time: {{read_time}} min</span>
                    <span><i class="fas fa-eye"></i> Views: {{views}}</span>
                </div>
            </div>
            
            <div class="guide-content">
                {{content}}
            </div>
            
            <!-- Related Guides -->
            <div class="related-guides">
                <h2>Related Guides</h2>
                <div class="related-grid">
                    <a href="/guides/how-to-check-kuccps-courses-2025" class="related-card">
                        <h3>How to Check KUCCPS Courses 2025</h3>
                        <p>Step-by-step guide to checking available courses</p>
                    </a>
                    <a href="/guides/kuccps-application-process" class="related-card">
                        <h3>KUCCPS Application Process</h3>
                        <p>Complete application guide for 2025 intake</p>
                    </a>
                    <a href="/guides/scholarships-opportunities" class="related-card">
                        <h3>Scholarships 2025</h3>
                        <p>Financial aid opportunities for students</p>
                    </a>
                </div>
            </div>
            
            <!-- Call to Action -->
            <div class="cta-section">
                <h2>Ready to Find Your Courses?</h2>
                <p>Use our course checker to find programs that match your KCSE grades</p>
                <div class="cta-buttons">
                    <a href="/degree" class="btn btn-primary">Check Degree Courses</a>
                    <a href="/diploma" class="btn btn-secondary">Check Diploma Courses</a>
                </div>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <div class="footer-content">
                <div class="footer-section">
                    <h3>KUCCPS Courses Checker</h3>
                    <p>Helping Kenyan students find the right courses based on their KCSE grades since 2023.</p>
                </div>
                <div class="footer-section">
                    <h3>Quick Links</h3>
                    <ul>
                        <li><a href="/">Home</a></li>
                        <li><a href="/about">About Us</a></li>
                        <li><a href="/contact">Contact</a></li>
                        <li><a href="/privacy">Privacy Policy</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h3>Contact Info</h3>
                    <p>Email: info@kuccpscourses.co.ke</p>
                    <p>Phone: +254 700 000 000</p>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2025 KUCCPS Courses Checker. All rights reserved.</p>
            </div>
        </div>
    </footer>

    <!-- JavaScript -->
    <script src="/static/js/main.js"></script>
    <script>
        // Update last updated date
        document.addEventListener('DOMContentLoaded', function() {
            // Add copy year
            const yearSpan = document.querySelector('.current-year');
            if (yearSpan) {
                yearSpan.textContent = new Date().getFullYear();
            }
            
            // Calculate read time
            const content = document.querySelector('.guide-content');
            if (content) {
                const wordCount = content.textContent.split(/\s+/).length;
                const readTime = Math.ceil(wordCount / 200); // 200 words per minute
                const readTimeElement = document.querySelector('.read-time');
                if (readTimeElement) {
                    readTimeElement.textContent = readTime;
                }
            }
        });
    </script>
</body>
</html>'''
    
    # Create templates directory if it doesn't exist
    guides_dir = 'templates/guides'
    if not os.path.exists(guides_dir):
        os.makedirs(guides_dir)
    
    # Create each guide file
    created_files = []
    for filename, guide_data in guides.items():
        filepath = os.path.join(guides_dir, filename)
        
        # Generate keywords from title
        keywords = ', '.join(guide_data['title'].split()[:10])
        
        # Prepare template variables
        template = base_template
        template = template.replace('{{title}}', guide_data['title'])
        template = template.replace('{{meta_description}}', guide_data['meta_description'])
        template = template.replace('{{keywords}}', keywords)
        template = template.replace('{{content}}', guide_data['content'])
        template = template.replace('{{current_date}}', datetime.now().strftime('%Y-%m-%d'))
        template = template.replace('{{current_url}}', f'https://kuccpscourses.co.ke/guides/{filename.replace(".html", "")}')
        template = template.replace('{{read_time}}', '10')  # Will be calculated by JS
        template = template.replace('{{views}}', '1,234')  # Placeholder
        
        # Write the file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(template)
        
        created_files.append(filename)
        print(f"✅ Created: {filename}")
    
    # Create guides index page
    create_guides_index(guides)
    
    return created_files

def create_guides_index(guides):
    """Create an index page listing all guides"""
    
    index_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KUCCPS Guides 2025 | Complete Resource Center</title>
    <meta name="description" content="Complete collection of KUCCPS guides for 2025. Learn about cluster points, admission requirements, courses, and application process.">
    <meta name="keywords" content="KUCCPS guides, university admission Kenya, course selection, KCSE grades, higher education Kenya">
    
    <!-- Schema.org markup -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "KUCCPS Guides 2025",
        "description": "Complete resource center for KUCCPS admission, courses, and placement information",
        "publisher": {
            "@type": "Organization",
            "name": "KUCCPS Courses Checker"
        }
    }
    </script>
    
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="stylesheet" href="/static/css/guides.css">
</head>
<body>
    <!-- Navigation (same as other pages) -->
    
    <main class="guides-index">
        <div class="container">
            <h1>KUCCPS Guides & Resources 2025</h1>
            <p class="intro">Everything you need to know about KUCCPS admission, course selection, and placement process.</p>
            
            <div class="guides-grid">
                {% for guide in guides %}
                <a href="/guides/{{ guide.filename.replace('.html', '') }}" class="guide-card">
                    <div class="guide-icon">
                        <i class="{{ guide.icon }}"></i>
                    </div>
                    <h3>{{ guide.title }}</h3>
                    <p>{{ guide.description }}</p>
                    <div class="guide-meta">
                        <span><i class="fas fa-clock"></i> {{ guide.read_time }} min</span>
                        <span><i class="fas fa-calendar"></i> {{ guide.date }}</span>
                    </div>
                </a>
                {% endfor %}
            </div>
            
            <!-- Categories -->
            <div class="categories">
                <h2>Browse by Category</h2>
                <div class="category-grid">
                    <a href="#admission" class="category">
                        <h3>Admission</h3>
                        <p>Requirements and process</p>
                    </a>
                    <a href="#courses" class="category">
                        <h3>Courses</h3>
                        <p>Degree, diploma, certificate</p>
                    </a>
                    <a href="#financial" class="category">
                        <h3>Financial Aid</h3>
                        <p>Scholarships and loans</p>
                    </a>
                    <a href="#career" class="category">
                        <h3>Career Guidance</h3>
                        <p>Job market and opportunities</p>
                    </a>
                </div>
            </div>
        </div>
    </main>
    
    <!-- Footer (same as other pages) -->
</body>
</html>'''
    
    # Create guide data for index
    guide_list = []
    for filename, data in guides.items():
        guide_list.append({
            'filename': filename,
            'title': data['title'],
            'description': data['meta_description'][:100] + '...',
            'icon': get_icon_for_guide(filename),
            'read_time': '10',
            'date': datetime.now().strftime('%b %Y')
        })
    
    # Save index page
    index_path = os.path.join('templates', 'guides_index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_template.replace('{% for guide in guides %}', '').replace('{% endfor %}', ''))
    
    print("✅ Created: guides_index.html")
    return index_path

def get_icon_for_guide(filename):
    """Return appropriate Font Awesome icon for each guide"""
    icons = {
        'cluster_points.html': 'fas fa-chart-bar',
        'kcse_admission.html': 'fas fa-graduation-cap',
        'diploma_courses.html': 'fas fa-certificate',
        'certificate_courses.html': 'fas fa-file-certificate',
        'kmtc_courses.html': 'fas fa-hospital',
        'artisan_courses.html': 'fas fa-tools',
        'ttc_courses.html': 'fas fa-chalkboard-teacher',
        'kuccps_application.html': 'fas fa-edit',
        'scholarships.html': 'fas fa-hand-holding-usd'
    }
    return icons.get(filename, 'fas fa-book')

def add_guide_routes(app):
    """Add Flask routes for all guide pages"""
    
    @app.route('/guides')
    def guides_index():
        """Main guides index page"""
        return render_template('guides_index.html',
                             title='KUCCPS Guides 2025 | Complete Resource Center',
                             meta_description='Complete collection of KUCCPS guides for 2025 admission. Learn about cluster points, requirements, and application process.',
                             canonical_url=url_for('guides_index', _external=True))
    
    # Individual guide routes
    @app.route('/guides/cluster-points')
    def guide_cluster_points():
        return render_template('guides/cluster_points.html')
    
    @app.route('/guides/kcse-admission')
    def guide_kcse_admission():
        return render_template('guides/kcse_admission.html')
    
    @app.route('/guides/diploma-courses')
    def guide_diploma():
        return render_template('guides/diploma_courses.html')
    
    @app.route('/guides/certificate-courses')
    def guide_certificate():
        return render_template('guides/certificate_courses.html')
    
    @app.route('/guides/kmtc-courses')
    def guide_kmtc():
        return render_template('guides/kmtc_courses.html')
    
    @app.route('/guides/artisan-courses')
    def guide_artisan():
        return render_template('guides/artisan_courses.html')
    
    @app.route('/guides/ttc-courses')
    def guide_ttc():
        return render_template('guides/ttc_courses.html')
    
    @app.route('/guides/kuccps-application')
    def guide_application():
        return render_template('guides/kuccps_application.html')
    
    @app.route('/guides/scholarships')
    def guide_scholarships():
        return render_template('guides/scholarships.html')
    
    print("✅ Added guide routes to Flask app")

# CSS for guides (save as static/css/guides.css)
guides_css = '''
/* Guides CSS */
.guide-container {
    padding: 2rem 0;
    background: #f8f9fa;
}

.breadcrumb {
    background: #e9ecef;
    padding: 1rem 0;
    font-size: 0.9rem;
}

.breadcrumb a {
    color: #007bff;
    text-decoration: none;
}

.breadcrumb span {
    color: #6c757d;
}

.guide-header {
    background: white;
    padding: 2rem;
    border-radius: 8px;
    margin-bottom: 2rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.guide-header h1 {
    color: #2c3e50;
    margin-bottom: 1rem;
}

.guide-meta {
    display: flex;
    gap: 2rem;
    color: #6c757d;
    font-size: 0.9rem;
}

.guide-meta i {
    margin-right: 0.5rem;
}

.guide-content {
    background: white;
    padding: 2rem;
    border-radius: 8px;
    line-height: 1.8;
}

.guide-section {
    margin-bottom: 3rem;
}

.guide-section h2 {
    color: #2c3e50;
    border-bottom: 2px solid #007bff;
    padding-bottom: 0.5rem;
    margin-bottom: 1.5rem;
}

.guide-section h3 {
    color: #34495e;
    margin: 1.5rem 0 1rem;
}

.guide-section p {
    margin-bottom: 1rem;
}

/* Info boxes */
.info-box, .highlight-box, .note-box {
    background: #e8f4fc;
    border-left: 4px solid #007bff;
    padding: 1.5rem;
    margin: 1.5rem 0;
    border-radius: 4px;
}

.highlight-box {
    background: #fff3cd;
    border-left-color: #ffc107;
}

.note-box {
    background: #f8f9fa;
    border-left-color: #6c757d;
}

/* Tables */
.points-table, .subject-table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.5rem 0;
}

.points-table th, .subject-table th {
    background: #007bff;
    color: white;
    padding: 1rem;
    text-align: left;
}

.points-table td, .subject-table td {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #dee2e6;
}

.points-table tr:nth-child(even), .subject-table tr:nth-child(even) {
    background: #f8f9fa;
}

/* Grid layouts */
.cluster-grid, .tips-grid, .pathway-chart, .course-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin: 1.5rem 0;
}

.cluster-card, .tip, .pathway, .course-category {
    background: white;
    padding: 1.5rem;
    border-radius: 8px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    border: 1px solid #e9ecef;
}

.tip h4, .pathway h3, .course-category h3 {
    color: #2c3e50;
    margin-top: 0;
}

.requirement-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

.requirement-card {
    text-align: center;
    padding: 1.5rem;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.requirement-grade {
    font-size: 2.5rem;
    font-weight: bold;
    color: #007bff;
    margin-bottom: 0.5rem;
}

/* FAQ */
.faq {
    margin-bottom: 1.5rem;
    padding: 1rem;
    background: #f8f9fa;
    border-radius: 6px;
}

.faq h3 {
    margin-top: 0;
    color: #2c3e50;
}

/* Process steps */
.process-steps {
    display: flex;
    justify-content: space-between;
    margin: 2rem 0;
    flex-wrap: wrap;
}

.step {
    flex: 1;
    min-width: 150px;
    text-align: center;
    padding: 1rem;
    position: relative;
}

.step-number {
    width: 40px;
    height: 40px;
    background: #007bff;
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1rem;
    font-weight: bold;
}

/* Related guides */
.related-guides {
    margin-top: 3rem;
    padding-top: 2rem;
    border-top: 2px solid #e9ecef;
}

.related-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
    margin-top: 1.5rem;
}

.related-card {
    background: white;
    padding: 1.5rem;
    border-radius: 8px;
    text-decoration: none;
    color: inherit;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    transition: transform 0.3s;
}

.related-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
}

/* CTA Section */
.cta-section {
    text-align: center;
    padding: 3rem;
    background: linear-gradient(135deg, #007bff, #0056b3);
    color: white;
    border-radius: 8px;
    margin: 3rem 0;
}

.cta-section h2 {
    color: white;
    margin-bottom: 1rem;
}

.cta-buttons {
    margin-top: 2rem;
}

.cta-buttons .btn {
    margin: 0 0.5rem;
    padding: 0.75rem 2rem;
}

/* Mobile responsiveness */
@media (max-width: 768px) {
    .guide-meta {
        flex-direction: column;
        gap: 0.5rem;
    }
    
    .process-steps {
        flex-direction: column;
    }
    
    .step {
        margin-bottom: 1.5rem;
    }
    
    .cluster-grid, .course-grid {
        grid-template-columns: 1fr;
    }
}
'''

# Run the content generator
if __name__ == "__main__":
    print("📝 Generating guide content...")
    created = create_guide_templates()
    
    # Save CSS
    css_dir = 'static/css'
    if not os.path.exists(css_dir):
        os.makedirs(css_dir)
    
    with open(os.path.join(css_dir, 'guides.css'), 'w', encoding='utf-8') as f:
        f.write(guides_css)
    
    print(f"✅ Created {len(created)} guide templates")
    print("✅ Created guides.css")
    print("🎉 Guide content generation complete!")