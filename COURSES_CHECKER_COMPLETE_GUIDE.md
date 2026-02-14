# 🎓 KUCCPS COURSES CHECKER - COMPLETE GUIDE

**Platform:** kuccpscourses.co.ke  
**Purpose:** Help Kenyan students find KUCCPS-approved courses matching their KCSE grades  
**Last Updated:** February 2026

---

## 📋 TABLE OF CONTENTS

1. [Overview](#overview)
2. [Platform Architecture](#platform-architecture)
3. [Complete User Flow](#complete-user-flow)
4. [Course Categories](#course-categories)
5. [Pricing & Payments](#pricing--payments)
6. [Features & Functionality](#features--functionality)
7. [Data & Entry Requirements](#data--entry-requirements)
8. [Grade Requirements by Category](#grade-requirements-by-category)
9. [Cluster Points System](#cluster-points-system)
10. [Pages & Components](#pages--components)
11. [Admin Features](#admin-features)
12. [API & Integrations](#api--integrations)
13. [Technical Stack](#technical-stack)

---

## 📱 OVERVIEW

**KUCCPS Courses Checker** is a web-based platform that:

- Allows students to input their KCSE grades and KCSE index number
- Matches them with KUCCPS-approved courses across universities, colleges, and technical institutions
- Facilitates course selection through a basket system
- Processes payments via M-PESA STK Push
- Provides detailed course information including cut-off points, institutions, and cluster requirements
- Offers educational guides on cluster points, admission requirements, and course selection strategies

**Target Users:**
- Kenyan high school graduates with KCSE results
- Students seeking degree, diploma, certificate, artisan, KMTC, or TTC programs
- Students researching course requirements before KUCCPS application

**Key Value Proposition:**
- One-platform solution for course discovery and matching
- Affordable access (KES 200 first category, KES 100 per additional)
- Instant results based on verified KCSE grades
- Educational guides to understand cluster points and eligibility

---

## 🏗️ PLATFORM ARCHITECTURE

### Frontend
- **Framework:** Flask with Jinja2 templating
- **Styling:** Bootstrap 5, custom CSS with KUCCPS brand colors (red, yellow, black)
- **Frontend Libraries:** 
  - JavaScript for interactive filtering and pagination
  - Font Awesome icons
  - Chart.js (for analytics, admin dashboards)
  - PWA capabilities (service workers for offline support)

### Backend
- **Framework:** Python Flask
- **Database:** MongoDB (stores users, payments, course data, saved baskets)
- **Cache:** Redis (optional for production, in-memory fallback)
- **Authentication:** Session-based (Flask sessions)
- **API Integration:** 
  - M-PESA API for payment processing
  - Google Gemini API for AI-powered chatbot
  - OpenRouter API as backup AI provider

### API Routes
- REST API endpoints for chat (`/api/chat`), course queries, payment verification
- Test routes: `/test-gemini`, `/gemini-stats`, `/debug-openrouter`
- Admin routes for system health, payment management, user management

### AI Features
- **Gemini Integration:** Google's Gemini 1.5 Flash for instant, cached responses
- **Fallback:** OpenRouter backup and rule-based chatbot
- **Chatbot Persona:** Official KUCCPS Courses Assistant
- **Caching:** 24-hour cache for repeated queries; daily rate limiting (1500 calls for Gemini, 200 for OpenRouter)

---

## 🔄 COMPLETE USER FLOW

### **Phase 1: Home & Category Selection (Landing)**

**Page:** `index.html`  
**User Action:** Visitor lands on homepage and sees 6 course category cards:
- 🎓 Degree (Universities, 4-year programs)
- 📚 Diploma (Technical colleges, 2-year programs)
- 🏥 KMTC (Kenya Medical Training College, medical programs)
- 📖 Certificate (Vocational training, 1-2 years)
- 🔧 Artisan (Hands-on trades: plumbing, electrical, welding)
- 👨‍🏫 TTC (Teacher Training Colleges, education programs)

**User Interaction:**
- Reads category descriptions and eligibility requirements
- Selects a category by clicking the corresponding button
- Optionally views guides or about pages first

**System Output:**
- Redirects to category-specific grades entry page (e.g., `/degree`, `/diploma`)
- Session flag set: `current_flow = 'degree'` (or other category)
- Breadcrumb updated: "Home > Degree Courses"

---

### **Phase 2: Grade Entry & Data Collection**

**Pages:** 
- `degree.html`, `diploma.html`, `certificate.html`, `artisan.html`, `kmtc.html`, `ttc.html`

**User Action:** Enters KCSE grades for relevant subjects

**Degree Courses Example (degree.html):**

**Core Subjects:**
- Mathematics (select grade A to E)
- English (select grade A to E)
- Kiswahili (select grade A to E)

**Sciences:**
- Chemistry
- Biology
- Physics

**Optional Subjects:**
- Economics, Geography, History, Business Studies, Computer Studies, Agriculture, etc.

**Grade Scale:** A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E

**UI Features:**
- Clean dropdown menus for each subject
- Submit button: "Continue with Grades"
- Validation: Ensures required subjects are selected
- Responsive design (mobile, tablet, desktop)

**System Processing:**
- Stores grades in session: `session['degree_grades'] = {math: 'C+', english: 'C', ...}`
- Calculates provisional cluster points (for preview)
- Sets flag: `degree_data_submitted = True`

---

### **Phase 3: Email & Index Verification**

**Page:** `enter_details.html`

**User Input Required:**
1. **Email Address** (text input)
   - Format: valid email (user@example.com)
   - Used for session tracking and payment records

2. **KCSE Index Number** (formatted input)
   - Format: 11 digits / 4 digits (e.g., 12345678901/2024)
   - Pattern: `\d{11}/\d{4}`
   - Auto-formatting: Browser auto-inserts `/` after 11th digit
   - Used to identify student and match payment

**System Processing:**
- Validates email and index number format
- Stores in session: `session['email']`, `session['index_number']`
- Checks existing paid categories: 
  - If first category: price = KES 200
  - If additional category: price = KES 100
- Creates/updates session payment record: `session['payment_amount']`, `session['is_first_category']`
- Database: Saves initial payment record with `save_user_payment(email, index_number, flow, amount)`

**Session State After Phase 3:**
```python
{
  'email': 'student@example.com',
  'index_number': '12345678901/2024',
  'current_flow': 'degree',
  'degree_grades': {...},
  'payment_amount': 200,  # or 100 if not first category
  'is_first_category': True,  # or False
  'paid_degree': False
}
```

---

### **Phase 4: Payment Processing**

**Page:** `payment.html`

**Payment Modal:**
- **Display:** M-PESA STK Push payment dialog
- **Amount Shown:** KES 200 (first) or KES 100 (additional)
- **Phone Input:** User enters 10-digit M-PESA phone number (07xxxxxxx)

**M-PESA Integration:**
- STK Push prompt sent to user's phone
- User enters M-PESA PIN to complete payment
- Payment reference/transaction ID captured
- Webhook/callback from M-PESA confirming payment

**Payment Statuses:**
- **Processing:** Spinner shown while awaiting payment
- **Success:** Payment recorded, user redirected to results
- **Failure:** Error message displayed; user can retry or cancel

**Database Recording:**
- Transaction ID, amount, timestamp, status stored in payments collection
- User record updated: `paid_degree = True`

**System Output After Payment:**
```python
{
  'verified_payment': True,
  'payment_reference': 'MPESA_TXN_12345',
  'paid_degree': True,
  'session_remaining': 30 minutes  # Session TTL
}
```

---

### **Phase 5: Results Display & Browsing**

**Page:** `results.html` or `degree_results.html` (category-specific)

**Results Overview:**
- **Heading:** "Qualification Results"
- **Summary:** "You qualify for X courses across Y cluster(s)"
- **Filters:**
  - **Cluster Filter Buttons:** All, Engineering, Medicine, Business, Humanities, etc.
  - Each button shows count, e.g., "Engineering (45)"

**Course Card Display:**
- **Per Card:**
  - Programme Name (e.g., "Bachelor of Engineering - Mechanical")
  - Institution Name (e.g., "Kenyatta University")
  - Programme Code (7-digit: e.g., "1200101")
  - Cut-off Points (e.g., "39.25")
  - Cluster (e.g., "Engineering")
  - "Add to Basket" button

**Pagination:**
- Default: 20 courses per page
- Navigation: Previous, page numbers, Next
- Show X of Y courses

**Sorting & Filtering:**
- Filter by cluster points (ascending/descending option)
- Filter by institution
- Search by program name

**User Interactions:**
- Select cluster → Results refresh to show only that cluster
- Click "Add to Basket" → Course added to user's basket
- Pagination arrows → Load next/previous page
- View course details → Modal or expanded card with full info

**Data Source:**
- Courses loaded from MongoDB collection: `courses`
- Filter logic executed server-side or client-side (JSON embedded in page)
- Session verified to ensure payment confirmed before showing courses

---

### **Phase 6: Course Basket Management**

**Page:** `basket.html`

**Basket Overview:**
- **Header:** "My Course Basket"
- **Badge:** Shows course count (e.g., "5 courses")
- **Actions:**
  - Clear All (removes all courses)
  - Remove individual course
  - Save basket state (auto-saved to DB)

**Course Columns in Basket:**
| Column | Data |
|--------|------|
| Programme Name | e.g., "Bachelor of Engineering" |
| Institution | e.g., "University of Nairobi" |
| Cluster | e.g., "Engineering" |
| Cut-off Points | e.g., "39.5" |
| Your Points | Calculated from your grades (e.g., "42.3") |
| Qualified? | ✅ Yes / ❌ No |
| Action | Remove button |

**Features:**
- **Empty State:** If no courses in basket, shows message with links to browse categories
- **Comparison View:** Side-by-side comparison of programs (filter by cluster)
- **Export:** Option to export course list as PDF or CSV
- **Print:** Print-friendly basket view

**Database Storage:**
- Basket stored in MongoDB: `user_baskets` collection
- Key: `{email, index_number}`
- Value: Array of selected program codes

**Basket Persistence:**
- Auto-saves when course added/removed
- Persists across sessions (requires email login to retrieve)
- Can switch between categories without losing basket

---

### **Phase 7: Post-Completion Actions**

**Pages (Optional):**
- `verified_dashboard.html` – Shows saved baskets and previous selections
- `user_info.html` – User profile (email, payment history, saved categories)
- `guides_index.html` – Educational guides (cluster points, course tips, etc.)

**User Options After Results:**
1. **View Another Category:**
   - Click "Category" menu → Select Diploma, Certificate, etc.
   - Price depends on whether it's first or additional category
   - Repeat Phase 2-5

2. **Save Basket & Exit:**
   - Basket auto-saved to DB
   - User can return anytime (requires email to retrieve)

3. **Access Guides:**
   - Learn about cluster points calculation
   - Read admission requirements by course type
   - Understand KUCCPS placement process

4. **Contact Support:**
   - Email: courseschecker@gmail.com
   - Phone: +254791196121
   - Embedded chat bot (AI-powered via Gemini)

---

## 🎓 COURSE CATEGORIES

### 1. **Degree Programs**
- **Institution Type:** Universities (public and private)
- **Duration:** 4 years (typically B.Sc., B.A., B.Com, etc.)
- **Minimum Grade:** C+ mean grade
- **Cluster:** Yes, requires 4-subject cluster calculation
- **Common Clusters:**
  - **Engineering:** Math, Physics, Chemistry, + 1 elective
  - **Medicine/Surgery:** Biology, Chemistry, Physics + Math
  - **Business:** Math, English, Business Studies + 1 elective
  - **Humanities:** English, History, Geography + 1 elective
- **Typical Cut-off:** 40+ cluster points (competitive)
- **Example:** "Bachelor of Engineering (Mechanical) – Kenyatta University"

### 2. **Diploma Programs**
- **Institution Type:** Technical colleges, polytechnics
- **Duration:** 2 years
- **Minimum Grade:** C- to C plain mean grade
- **Cluster:** Varies (some require specific subjects)
- **Common Fields:**
  - Engineering (Civil, Mechanical, Electrical)
  - Business (Accounting, Marketing)
  - IT/Computing
  - Hospitality & Tourism
  - Nursing (Diploma)
  - Building Technology
- **Typical Cut-off:** 25-35 cluster points (more accessible)
- **Example:** "Diploma in Civil Engineering – Technical University of Kenya (TUK)"

### 3. **KMTC (Kenya Medical Training College)**
- **Institution Type:** Government medical training (multiple campuses)
- **Duration:** Variable (1.5 - 3 years depending on program)
- **Minimum Grade:** C- mean grade for most programs
- **Cluster:** Typically requires Biology, Chemistry, Math/Physics
- **Programmes:**
  - Nursing (Registered)
  - Clinical Medicine
  - Lab Technology
  - Pharmacy Technician
  - Dental Therapy
  - Public Health
  - Emergency & Disaster Management
  - Physiotherapy
- **Typical Cut-off:** 30-38 cluster points
- **Example:** "Diploma in Nursing – KMTC"

### 4. **Certificate Programs**
- **Institution Type:** TVET colleges
- **Duration:** 1-2 years
- **Minimum Grade:** D+ mean grade
- **Cluster:** Generally not required (skills-based)
- **Fields:**
  - Business & Entrepreneurship
  - ICT & Computing
  - Hospitality (Catering, Hotel Management)
  - Beauty & Wellness
  - Automotive
  - Hairdressing
  - Fashion Design
- **Typical Cut-off:** 15-25 cluster points
- **Example:** "Certificate in Business Studies – Jomo Kenyatta University of Agriculture"

### 5. **Artisan Programs**
- **Institution Type:** TVET & vocational training centers
- **Duration:** 1-2 years (hands-on)
- **Minimum Grade:** D plain to E (very flexible)
- **Cluster:** Not required
- **Fields:** (Hands-on technical trades)
  - Plumbing & Gas Fitting
  - Electrical Installation & Wiring
  - Welding & Fabrication
  - Carpentry & Joinery
  - Masonry & Construction
  - Automotive Mechanics
  - Hair Design & Barbering
- **Typical Cut-off:** 10-20 cluster points (most accessible)
- **Example:** "Artisan Certificate in Plumbing & Gas Fitting"

### 6. **TTC (Teacher Training Colleges)**
- **Institution Type:** Government & private teacher training institutions
- **Duration:** 2 years (Diploma) or 4 years (Degree)
- **Minimum Grade:** C mean grade (for most Diploma programs)
- **Cluster:** Subject-specific requirements (e.g., Science subjects for Science teaching)
- **Programmes:**
  - Primary Teacher Education
  - Secondary Teacher Education (by subject: Science, English, Humanities, ICT)
  - Early Childhood Development Practitioner
  - Technical Teacher Education
  - Special Needs Education
- **Typical Cut-off:** 28-38 cluster points (varies by specialization)
- **Example:** "Diploma in Primary Teacher Education – Mombasa Teachers College"

---

## 💰 PRICING & PAYMENTS

### Pricing Structure

| Category | Price | Eligibility |
|----------|-------|-------------|
| **First Category** | KES 200 | First time accessing any course category |
| **Additional Categories** | KES 100 each | After viewing/purchasing first category |

**Example Scenario:**
- Student views Degree courses → Pays KES 200
- Same student views Diploma courses → Pays KES 100
- Same student views Certificate courses → Pays KES 100
- **Total spent:** KES 400 for 3 categories

### Payment Methods

**Primary Method:** M-PESA STK Push
- **Supported:** Kenya only (Safaricom, Airtel, Equitel networks)
- **Process:**
  1. User enters 10-digit Kenyan phone number
  2. STK Push prompt appears on phone
  3. User enters M-PESA PIN
  4. Ksh 200 or 100 deducted immediately
  5. Payment reference issued
  6. Results unlocked in system

**Payment Flow:**
```
User Input Phone → STK Push Sent → User Enters PIN → Payment Processed → Webhook Received → Session Updated → Results Displayed
```

**Transaction Record Stored:**
- Transaction ID / Reference
- Amount (200 or 100)
- Timestamp
- User email & index number
- Category (degree, diploma, etc.)
- Status (completed, pending, failed)
- Phone number (masked after validation)

### Payment Verification

**Verification Process:**
1. After M-PESA confirms payment, webhook sent to `/api/payment-callback`
2. System verifies transaction ID in M-PESA API response
3. User session updated: `paid_[category] = True`
4. Database record marked: `status = 'completed'`
5. User redirected to results page

**Timeout Handling:**
- If payment not confirmed within 5 minutes, session expires
- User can retry payment from payment page
- "Payment Pending" page shown (`payment_wait.html`)

### Additional Details

**Application Fee (KUCCPS official):** KES 1,500 (NOT charged by Courses Checker)
- Paid separately to KUCCPS via eCitizen platform
- Not related to Courses Checker service

**Refund Policy:** No refunds issued (non-refundable service verification)

**Payment Security:**
- SSL/HTTPS encrypted all payment pages
- M-PESA PIN never transmitted to Courses Checker
- PCI compliance for any card data (though STK Push doesn't require card)

---

## ✨ FEATURES & FUNCTIONALITY

### 1. **Dual AI Chatbot**

**Chatbot Access:** Floating chat button on all pages (bottom-right)

**AI Providers (in order of priority):**
1. **Google Gemini (Primary):** Gemini 1.5 Flash
   - Fast, free tier available
   - Cached responses (24-hour cache)
   - Rate limit: 1,500 calls/day
   - Rich context about KUCCPS courses, eligibility, etc.

2. **OpenRouter Backup:** Aurora Alpha (free model)
   - Activated if Gemini rate limit exceeded
   - Same caching & rate limiting (200 calls/day)

3. **Rule-Based Fallback:** Hardcoded FAQ logic
   - Activated if both AI providers exhausted
   - Quick answers to common questions

**Chatbot Capabilities:**
- Answer questions about course eligibility
- Explain cluster points calculation
- Provide payment instructions
- Clarify admission requirements
- Direct to guides and resources
- Support requests escalation to email

**Chat UI:**
- Modal chat window (minimizable)
- Message history (current session)
- Typing indicator
- Response time tracked & logged
- "Report Issue" button to flag incorrect answers

**Admin Monitoring:**
- `/admin/ai-stats` – View Gemini call statistics
- `/admin/clear-ai-cache` – Manual cache clearing
- AI spending tracking (for billing)

### 2. **Educational Guides**

**Pages:**
- `guides_index.html` – Directory of all guides
- Guides under `templates/guides/` (subdirectory):
  - `cluster_points.html` – Detailed cluster points explanation
  - `kcse_admission.html` – KCSE requirements per category
  - `diploma_courses.html` – Diploma programs overview
  - `certificate_courses.html` – Certificate programs overview
  - (+ more: artisan, KMTC, TTC guides)

**Guide Content Includes:**
- Grade-to-points mapping (A=12 points, A-=11, etc.)
- Subject cluster examples (Engineering, Medicine, Business)
- Cut-off points explanation
- Entry requirements per category
- KUCCPS application timeline
- Scholarship resources
- FAQ sections

### 3. **Course Filtering & Comparison**

**Search & Filter Options:**
- **By Cluster** (Engineering, Medicine, Business, Humanities, etc.)
- **By Institution** (dropdown list of universities/colleges)
- **By Cut-off Points** (range slider: 0-50+ points)
- **By Programme Name** (search/autocomplete)
- **By Category** (degree, diploma, cert, etc. — though fixed per page)

**Sorting:**
- Sort by Cut-off Points (ascending/descending)
- Sort by Institution Name (A-Z)
- Sort by Relevance (based on user's grades)

**Comparison View:**
- Select 2-5 courses to compare side-by-side
- Columns: Program name, Institution, Cluster, Cut-off, Your Points, Eligible?

### 4. **Basket & Wishlist**

**Basket Features:**
- Add/remove individual courses
- Clear all courses at once
- Save basket to account (requires email login)
- Retrieve saved baskets from previous sessions
- Export basket as PDF or CSV
- Print basket

**Wishlist Integration:**
- Courses in basket automatically become "liked" for future reference
- Dashboard shows "Recently Liked" programs
- Comparison & export from wishlist

### 5. **User Dashboard** (verified users)

**Page:** `verified_dashboard.html`

**Dashboard Shows:**
- Payment history (all categories, amounts, dates)
- Saved baskets (retrieve and re-edit)
- View previous results
- Download receipt (PDF)
- Category history (which courses viewed, when)

**Session Management:**
- View active sessions
- Logout option (ends session)

### 6. **Payment Management** (admin)

**Admin Page:** `/admin/payment-management`

**Capabilities:**
- View all payments (filter by date, user, status)
- Payment statistics (total revenue, category breakdown)
- Refund requests (process or deny)
- Payment reconciliation
- Export payment reports

### 7. **News & Updates**

**Page:** `news.html` (public-facing)

**Admin Page:** `/admin/news` (create/edit articles)

**Content Examples:**
- "KUCCPS Placement Results Released"
- "New Scholarships Available"
- "Important Deadlines for Revision Window"
- Tips & advice on course selection

**Auto-dated & categorized** (tags: admissions, scholarships, deadlines, etc.)

### 8. **PWA / Offline Support**

**Features:**
- Service worker (`service-worker.js`) enables offline mode
- Cached static pages & assets
- Offline page (`offline.html`) when data unavailable
- Users can "install" as app on home screen (mobile)
- Notifications for payment confirmation

### 9. **Contact & Support**

**Methods:**
1. **Email:** courseschecker@gmail.com
2. **Phone:** +254791196121 (24/7 support)
3. **Chat:** AI-powered bot (integrated on all pages)
4. **Contact Form:** `contact.html` (submit inquiries)

---

## 📊 DATA & ENTRY REQUIREMENTS

### User Data Collection

| Field | Format | Required | Purpose |
|-------|--------|----------|---------|
| **Email** | user@example.com | Yes | Session tracking, payment record, contact |
| **KCSE Index** | 12345678901/2024 | Yes | Student identification, results matching |
| **Exam Year** | 2024 | Implicit | Index validation |
| **Course Category** | degree, diploma, etc. | Yes | Result filtering |
| **KCSE Grades** | A to E (per subject) | Yes | Course matching, cluster calculation |
| **Phone Number** | 07xxxxxxxxx (10 digit) | Yes (payment) | M-PESA payment |

### KCSE Subjects Collected

**Core (Required for all):**
- Mathematics
- English
- Kiswahili

**Sciences (varies by category):**
- Chemistry
- Biology
- Physics

**Optional/Electives (varies by category):**
- Economics
- Geography
- History
- Business Studies
- Computer Studies
- Agriculture
- Home Science
- Music
- Art & Design

### Data Validation

**Email Validation:**
- Must be valid email format (RFC 5322 basic)
- No duplicate check (users can use same email for multiple categories)

**Index Number Validation:**
- Format: 11 digits + "/" + 4 digits (year)
- Example: 12345678901/2024
- Auto-formatting in UI (slash inserted after 11th digit)

**Grade Validation:**
- Valid grades: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E
- Required subjects must be selected; optional can be skipped
- No grade combination validation (system accepts any combo)

**Phone Validation:**
- 10 digits only
- Must start with 07 (Kenyan network)
- No spaces or dashes allowed

---

## 🎓 GRADE REQUIREMENTS BY CATEGORY

### Degree Programs
- **Minimum Overall Grade:** C+ mean grade
- **Cluster Subjects Required:** 4 specific subjects per program
- **Common Clusters:**
  - **Engineering:** Math (min C+), Physics (min C+), Chemistry (min C+), + 1 related
  - **Medicine/Dentistry:** Biology (min B-), Chemistry (min B-), Physics/Math (min C+)
  - **Business:** Math (min C+), English (min C+), Business Studies/Economics, + 1 related
  - **Education:** Subject + Education-related (depends on specialization)
  - **Law:** English (min B-), any languages, + related subjects
- **Cluster Points Calculation:** Sum of 4 best subjects in cluster (A=12, A-=11, B+=10, ... D=3)
- **Expected Cut-off:** 35-45 cluster points (varies by institution & program popularity)

### Diploma Programs
- **Minimum Overall Grade:** C- to C plain (varies by program)
- **Cluster Subjects:** Some require specific subjects; others are flexible
- **Example Requirements:**
  - Nursing: Biology, Chemistry, Math/Physics
  - Engineering: Math, Physics, Chemistry (or related)
  - Business: Math, English (+ subjects like Accounting if available)
- **Typical Cut-off:** 25-35 cluster points

### KMTC Programs
- **Minimum Overall Grade:** C- mean grade
- **Cluster Subjects:** Typically require Biology, Chemistry, Math/Physics
- **Specific Programs:**
  - **Nursing:** Bio C, Chem C-, Math/Phys C-
  - **Clinical Medicine:** Bio B-, Chem B-, Phys/Math B-
  - **Lab Technology:** Bio C+, Chem C+, Math/Phys C
  - **Physiotherapy:** Similar to nursing (Bio, Chem, Math/Phys)
- **Typical Cut-off:** 30-38 cluster points

### Certificate Programs
- **Minimum Overall Grade:** D+ mean grade (flexible)
- **Cluster Subjects:** Generally NOT required (skills-based)
- **Subject Relevance:** 
  - Business certificates may prefer Math/English
  - ICT certificates may prefer any science subject or English
  - Hospitality: No specific subject requirements
- **Typical Cut-off:** 15-25 cluster points (if cluster required)

### Artisan Programs
- **Minimum Overall Grade:** D to E (very flexible)
- **Cluster Subjects:** NOT required (hands-on vocational focus)
- **Entry:** Based on KCSE participation & practical aptitude assessment
- **Typical Cut-off:** 10-20 cluster points (if cluster applicable)

### TTC (Teacher Training) Programs
- **Minimum Overall Grade:** C mean grade
- **Cluster Subjects:** Depends on specialization
  - **Primary Education:** Any subject cluster accepted; English & Math preferred
  - **Secondary Science:** Bio B-, Chem C+, Phys C+, Math C+
  - **Secondary English:** English B-, any other 3 subjects
  - **Early Childhood:** No specific cluster; C+ preferred
- **Subject Specialization:** 
  - Selected based on cluster subjects
  - If strong in Science cluster (Bio, Chem, Phys), placed in Science Teaching
  - If strong in Humanities (English, History, Geography), placed in Humanities Teaching
- **Typical Cut-off:** 28-38 cluster points (by specialization)

---

## 📐 CLUSTER POINTS SYSTEM

### What are Cluster Points?

**Cluster Points** represent a student's performance in 4 specific KCSE subjects that a particular degree program requires. They're calculated to standardize comparison across candidates nationwide.

### How Are Cluster Points Calculated?

**Step 1: Identify Cluster Subjects for Your Programme**
- Each degree program specifies 4 required subjects in its cluster
- Example: Engineering → [Mathematics, Physics, Chemistry, + 1 elective]
- Example: Medicine → [Biology, Chemistry, Physics/Math, + 1 related]

**Step 2: Find Your Best 4-Subject Combination**
- Look for subject cluster that INCLUDES the program's required subjects
- Select candidate's grades in those 4 subjects
- If candidate lacks one subject, may not qualify (or use substitute)

**Step 3: Convert Grades to Points**

| Grade | Points |
|-------|--------|
| A | 12 |
| A- | 11 |
| B+ | 10 |
| B | 9 |
| B- | 8 |
| C+ | 7 |
| C | 6 |
| C- | 5 |
| D+ | 4 |
| D | 3 |
| D- | 2 |
| E | 1 |

**Step 4: Sum the 4 Points**
- Total cluster points = P1 + P2 + P3 + P4
- Range: 4 (E+E+E+E) to 48 (A+A+A+A)
- Typical range for competitive programs: 36-48
- Typical range for average programs: 28-38

### Example Calculation

**Scenario:** Student with grades:
- Mathematics: B+ (10 points)
- Physics: B (9 points)
- Chemistry: C+ (7 points)
- Business Studies: C (6 points)

**For Engineering Program (requires Math, Physics, Chemistry + 1):**
- Cluster points = 10 + 9 + 7 + 6 = **32 points**

**Cut-off for Engineering at Kenyatta University:** 38 points
- Student's 32 < 38 → **Not Qualified**

**Cut-off for Engineering at a different university:** 30 points
- Student's 32 > 30 → **Qualified ✓**

### Common Clusters Used in KUCCPS

**Cluster 1 - Engineering & Physical Sciences:**
- Math, Physics, Chemistry, + 1 elective (English, Kiswahili, or ICT)
- Typical cut-off: 35-45 points

**Cluster 2 - Medicine & Health Sciences:**
- Biology, Chemistry, Physics, + Math
- Typical cut-off: 38-48 points (highest)

**Cluster 3 - Business & Economics:**
- Math, English, Economics/Business Studies, + 1 (Kiswahili, Accounting, ICT)
- Typical cut-off: 28-40 points

**Cluster 4 - Humanities & Social Sciences:**
- English, History, Geography/Economics, + Kiswahili
- Typical cut-off: 25-35 points

**Cluster 5 - Agriculture & Environmental:**
- Agriculture, Biology, Chemistry, + 1 (Geography, Math, Physics)
- Typical cut-off: 28-38 points

### Cluster Points Ranking

KUCCPS **AutoMatches** programs by rank of cluster points:
1. Candidate with highest cluster points gets first pick of programs
2. Second-highest cluster points gets second pick
3. And so on...

**Key:** Having high cluster points (38+) significantly increases **chances** of placement in competitive programs.

---

## 📄 PAGES & COMPONENTS

### Public-Facing Pages

| Page | URL | Purpose | Template File |
|------|-----|---------|---------------|
| **Home** | `/` | Landing page, category showcase | `index.html` |
| **Degree Courses** | `/degree` | Grade entry for degrees | `degree.html` |
| **Diploma Courses** | `/diploma` | Grade entry for diplomas | `diploma.html` |
| **KMTC Courses** | `/kmtc` | Grade entry for KMTC | `kmtc.html` |
| **Certificate Courses** | `/certificate` | Grade entry for certificates | `certificate.html` |
| **Artisan Courses** | `/artisan` | Grade entry for artisan | `artisan.html` |
| **TTC Courses** | `/ttc` | Grade entry for TTC | `ttc.html` |
| **Details Entry** | `/enter-details/<flow>` | Email & index entry | `enter_details.html` |
| **Payment** | `/payment/<flow>` | M-PESA payment modal | `payment.html` |
| **Payment Wait** | `/payment-wait/<flow>` | Waiting for payment confirmation | `payment_wait.html` |
| **Results** | `/show-results/<flow>` | Course matching results | `results.html` |
| **Basket** | `/basket` | Saved course basket | `basket.html` |
| **Guides Index** | `/guides` | Guide directory | `guides_index.html` |
| **Cluster Points Guide** | `/guides/cluster-points` | How cluster points work | `guides/cluster_points.html` |
| **Admission Guide** | `/guides/kcse-admission` | KCSE requirements guide | `guides/kcse_admission.html` |
| **About** | `/about` | About the platform | `about.html` |
| **Contact** | `/contact` | Contact form | `contact.html` |
| **News** | `/news` | Latest updates & news | `news.html` |
| **User Guide** | `/user-guide` | How to use Courses Checker | `user-guide.html` |
| **Offline** | (PWA cache) | Offline placeholder | `offline.html` |

### Category Result Pages (Alternative URLs)

| Category | Primary URL | Alt URL (Results) | Template |
|----------|-------------|-------------------|----------|
| Degree | `/degree` | `/degree-results` | `degree_results.html` |
| Diploma | `/diploma` | `/diploma-results` | `diploma_results.html` |
| Certificate | `/certificate` | `/certificate-results` | `certificate_results.html` |
| Artisan | `/artisan` | `/artisan-results` | `artisan_results.html` |
| KMTC | `/kmtc` | `/kmtc-results` | `kmtc_results.html` |

### API Routes & Test Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Send chat message (Gemini/AI) |
| `/test-gemini` | GET | Test Gemini integration |
| `/gemini-stats` | GET | View Gemini statistics (admin) |
| `/debug-openrouter` | GET | Debug OpenRouter (dev) |
| `/api/payment-callback` | POST | M-PESA webhook callback |
| `/submit-grades` | POST | Grade submission handler |

### Admin Pages

| Page | URL | Purpose |
|------|-----|---------|
| **Admin Login** | `/admin/login` | Admin authentication |
| **Admin Dashboard** | `/admin/dashboard` | Overview & stats |
| **User Management** | `/admin/users` | View/manage users |
| **Payment Management** | `/admin/payment-management` | Payment tracking & reconciliation |
| **Payments List** | `/admin/payments` | All payment records |
| **News Management** | `/admin/news` | Create/edit news articles |
| **System Monitoring** | `/admin/system-monitoring` | Real-time system health |
| **System Health** | `/admin/system-health` | Server & DB status |
| **Financial Reports** | `/admin/financial-reports` | Revenue & cost analysis |
| **AI Stats** | `/admin/ai-stats` | Chatbot usage & stats |
| **Clear Cache** | `/admin/clear-ai-cache` | Manual cache flush |

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Navigation Bar** | `components/navbar.html` (or in `base.html`) | Top navigation |
| **Footer** | `components/footer.html` (or in `base.html`) | Bottom links & info |
| **Chat Widget** | `chat.html` | Floating chat interface |
| **Install Prompt** | `components/install_prompt.html` | PWA install banner |
| **Breadcrumbs** | (in each template) | Navigation path |
| **Flash Messages** | (in `base.html`) | Alert notifications |

### Static Assets

| Asset | Location | Purpose |
|-------|----------|---------|
| **Main CSS** | `static/css/styles.css` | Primary styling |
| **Alt CSS** | `static/css/styles-01.css` | Theme variants |
| **Guides CSS** | `static/css/guides.css` | Guide pages styling |
| **Icons** | `static/icons/` | Brand & UI icons |
| **Images** | `static/images/` | Photos, logos, banners |
| **Videos** | `static/videos/` | Tutorial & promo videos |
| **Service Worker** | `static/js/service-worker.js` | PWA offline support |
| **PWA Config** | `static/js/pwa.js` | PWA initialization |
| **Main JS** | `static/js/script.js` | Utility functions |
| **Offline Storage** | `static/js/offline-storage.js` | Local storage manager |
| **Manifest** | `static/manifest.json` | PWA manifest |

---

## 🔐 ADMIN FEATURES

### Admin Login

**Page:** `/admin/login`  
**Credentials:** Admin username/password (set in ENV or DB)  
**Session:** Admin flagged after login; 30-minute timeout

### Dashboard

**Metrics Displayed:**
- Total users registered
- Total payments processed (KES amount)
- Total courses viewed
- Active sessions
- Payment success rate (%)
- Server uptime
- Database connection status

### User Management

**View Users:**
- Email, registration date, categories purchased
- Payment history per user
- Basket contents (courses saved)
- Last activity

**User Actions:**
- Deactivate account
- Clear user cache
- Refund (manual)
- Reset payment status

### Payment Management

**Payment Filters:**
- By date range
- By amount (200 or 100)
- By status (completed, pending, failed)
- By category

**Payment Reconciliation:**
- Manual reconcile against M-PESA statement
- Flag discrepancies
- Refund requests approval

### News Management

**Create Article:**
- Title, content, tags (admissions, scholarships, deadlines)
- Publish date
- Featured image (optional)
- Save/publish/schedule

**View/Edit Articles:**
- List all news
- Edit published articles
- Delete articles
- View publish history

### System Monitoring

**Real-Time Metrics:**
- Server CPU usage
- Memory usage
- Database connection pool status
- Active user sessions count
- Failed requests count
- API response times (avg, min, max)

**Logs:**
- Error logs (filterable by type)
- Payment logs
- API access logs
- Admin action logs

### Financial Reports

**Reports Available:**
- Revenue by category (degree, diploma, etc.)
- Revenue trend (daily, weekly, monthly)
- Cost breakdown (Gemini API calls, OpenRouter, infrastructure)
- Profit margin
- User acquisition cost (if referral tracking in place)

**Export Options:**
- PDF, CSV, Excel

### AI Statistics & Management

**Gemini Stats Displayed:**
- Calls made today vs. daily limit (1,500)
- Remaining calls today
- Cache hit rate (%)
- Average response time
- Top queries (truncated for privacy)
- Error rate

**OpenRouter Stats:**
- Calls made today (limit 200)
- Fallback activation count
- Response times compared to Gemini

**Cache Management:**
- View cache size (number of entries)
- Clear all cache (manual flush)
- Cache age distribution

---

## 🔌 API & INTEGRATIONS

### M-PESA Integration

**Provider:** Safaricom M-Pesa API  
**Integration Type:** STK Push (payment prompt)

**Flow:**
1. User enters phone number → System calls M-Pesa STK Push endpoint
2. M-Pesa sends prompt to user's phone
3. User enters PIN → M-Pesa processes payment
4. M-Pesa sends confirmation webhook to `/api/payment-callback`
5. System verifies & updates session

**Security:**
- Webhook signature verified (using M-Pesa secret/public key)
- Phone number stored temporarily (masked in DB)
- Transaction ID used as reference (not sensitive)

### Google Gemini Integration

**API:** Google Generative AI SDK (`google.generativeai`)  
**Model:** Gemini 1.5 Flash  
**Purpose:** AI chatbot responses

**Configuration:**
```python
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = "gemini-1.5-flash"
MAX_GEMINI_DAILY = 1500
```

**Features Implemented:**
- Caching (24-hour, hash-based)
- Rate limiting (daily & per-minute)
- Fallback to OpenRouter if rate limit hit
- Prompt includes KUCCPS context (courses, pricing, eligibility)
- Error logging & retry logic (3 attempts)
- Response time tracking

**Example Request:**
```json
{
  "model": "gemini-1.5-flash",
  "messages": [
    {
      "role": "user",
      "content": "What grades do I need for a degree?"
    }
  ],
  "temperature": 0.7,
  "max_output_tokens": 400
}
```

### OpenRouter Integration (Backup)

**API:** OpenRouter AI Platform  
**Primary Model:** Aurora Alpha (free)  
**Purpose:** Backup when Gemini rate limit exceeded

**Configuration:**
```python
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_DAILY_CALLS = 200
```

**Activation Trigger:**
- If Gemini returns HTTP 429 (rate limit)
- If Gemini call fails after 3 retries
- If cache miss + Gemini unavailable

### MongoDB Integration

**Collections:**
- `users` – User accounts & profile data
- `payments` – Payment records (transactions)
- `courses` – Course database (programs, institutions, cut-offs)
- `baskets` – Saved course baskets (per user)
- `news` – News articles
- `admin_users` – Admin credentials

**Connection:**
```python
MONGODB_URI = os.getenv('MONGODB_URI')  # MongoDB Atlas or local
```

### Redis Cache (Optional)

**Purpose:** Server-side caching for:
- Course queries (filtered results)
- User session data
- AI response cache (Gemini, OpenRouter)

**Fallback:** If Redis unavailable, uses in-memory dict (not suitable for production with multiple workers)

---

## 🏗️ TECHNICAL STACK

### Backend
- **Runtime:** Python 3.9+
- **Framework:** Flask 2.x
- **Templating:** Jinja2
- **ORM/DB Driver:** PyMongo (MongoDB)
- **Caching:** Flask-Caching (Redis or in-memory)
- **Environment:** python-dotenv (ENV file management)
- **Logging:** Python logging module

### Frontend
- **HTML5:** Semantic structure
- **CSS3:** Bootstrap 5, custom styles
- **JavaScript:** Vanilla JS (no major framework)
- **Icons:** Font Awesome 6
- **Charts:** Chart.js (admin dashboards)
- **Responsive:** Mobile-first design

### DevOps & Deployment
- **Docker:** Dockerfile for containerization
- **Deployment Platforms:**
  - Render.com (render.yaml config)
  - Fly.io (fly.toml config)
- **Web Server:** Gunicorn (with gunicorn_config.py)
- **Process Manager:** (handled by platform)

### External Services
- **Database:** MongoDB Atlas (cloud) or local MongoDB
- **Cache:** Redis (cloud: Redis Labs, Heroku Redis, or self-hosted)
- **Payment:** M-Pesa API (Safaricom)
- **AI:** Google Gemini + OpenRouter APIs
- **Email:** Gmail SMTP (for future notifications)

### Dependencies (requirements.txt)

```
Flask==2.3.x
pymongo==4.x
flask-caching==2.x
python-dotenv==1.x
requests==2.x
google-generativeai==0.x
```

### Project Structure

```
kuccps-courses/
├── app.py                    # Main Flask application
├── courses.py               # Course database logic
├── guide_routes.py          # Guide page routes
├── content_generator.py     # Content generation utilities
├── security.py              # Security helpers
├── basket.py                # Basket/wishlist logic
├── gunicorn_config.py       # Gunicorn configuration
├── requirements.txt         # Python dependencies
├── requirements-dev.txt     # Dev-only dependencies
├── .env.example             # Environment variables template
├── .env                     # (not in repo) Actual env vars
├── Dockerfile              # Docker build recipe
├── fly.toml                # Fly.io deployment config
├── render.yaml             # Render deployment config
├── Procfile                # Process types for platforms
├── robots.txt              # SEO robots.txt
├── static/
│   ├── css/               # Stylesheets
│   ├── js/                # JavaScript files
│   ├── images/            # Images & logos
│   ├── icons/             # Icon files
│   ├── videos/            # Video assets
│   ├── manifest.json      # PWA manifest
│   └── service-worker.js  # Offline support
├── templates/
│   ├── base.html          # Base template (nav, footer, layout)
│   ├── index.html         # Homepage
│   ├── degree.html        # Degree grades entry
│   ├── diploma.html       # ... (other categories)
│   ├── payment.html       # Payment modal
│   ├── results.html       # Course results
│   ├── basket.html        # Course basket
│   ├── admin_*.html       # Admin pages
│   ├── guides/            # Guide templates
│   ├── components/        # Reusable components
│   └── ...
├── README.md              # Project overview
├── SEO_*.md               # SEO documentation
└── [other docs]           # Guides, checklists, etc.
```

---

## 🎯 SUMMARY: COMPLETE FLOW AT A GLANCE

```
1. STUDENT LANDS ON HOMEPAGE
   ↓
2. SELECTS COURSE CATEGORY (Degree, Diploma, KMTC, Certificate, Artisan, TTC)
   ↓
3. ENTERS KCSE GRADES
   → System calculates cluster points preview
   ↓
4. PROVIDES EMAIL & KCSE INDEX NUMBER
   → System checks payment history (first vs. additional category)
   ↓
5. PROCEEDS TO PAYMENT
   → M-PESA STK Push payment initiated
   → Student enters PIN on phone
   ↓
6. PAYMENT CONFIRMED BY M-PESA WEBHOOK
   → Session marked: paid_[category] = True
   ↓
7. VIEWS PERSONALIZED COURSE RESULTS
   → System matches student's grades against database
   → Displays all qualifying courses with cut-off points
   → Clusters used for filtering & sorting
   ↓
8. FILTERS & COMPARES COURSES
   → User selects cluster (Engineering, Medicine, Business, etc.)
   → Compares programs side-by-side
   ↓
9. ADDS COURSES TO BASKET
   → Selected programs saved under student's email
   ↓
10. MANAGES BASKET
    → View all saved courses
    → Edit, remove, export list as PDF/CSV
    → Save for future reference
    ↓
11. (OPTIONAL) ACCESSES GUIDES & SUPPORT
    → Reads cluster points explanation
    → Reviews admission requirements
    → Contacts support via chat or email
    ↓
12. SESSION ENDS
    → 30-minute timeout or manual logout
    → Basket persists in DB for future login
```

---

## 🚀 KEY TAKEAWAYS

✅ **Platform Focuses On:**
- Accessibility: Affordable, easy-to-use course matching
- Accuracy: Real KUCCPS course database with current cut-offs
- Education: Guides explain cluster points and eligibility
- Support: 24/7 AI chatbot + email/phone support
- Mobile-First: Responsive design, PWA offline support

✅ **Primary Revenue Model:**
- Payment per category (KES 200 first, KES 100 additional)
- One-time no-refund model (users keep access)

✅ **Tech Stack Highlights:**
- Python/Flask backend (lightweight, scalable)
- MongoDB for flexible data storage
- Google Gemini AI for intelligent responses
- M-Pesa integration for seamless Kenyan payments
- PWA for offline capability & app-like UX

✅ **User Base:**
- High school graduates aged 17-25
- Career-focused, tech-savvy students
- Price-sensitive (prefer low-cost solutions)
- Seeking guidance on Kenyan higher education

---

**For questions or more details, contact:** courseschecker@gmail.com | +254791196121

