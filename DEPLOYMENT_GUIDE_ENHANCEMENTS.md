# Deployment & Testing Guide - Enhanced Course Templates

## Pre-Deployment Testing Checklist

### Local Testing (Development Environment)
- [ ] Start Flask app locally: `python app.py`
- [ ] Visit each URL in browser:
  - http://localhost:5000/degree
  - http://localhost:5000/diploma
  - http://localhost:5000/certificate
  - http://localhost:5000/kmtc
  - http://localhost:5000/artisan
  - http://localhost:5000/ttc

### Visual Verification Per Page
- [ ] New "Why Choose" section displays with 4 benefit cards
- [ ] "Frequently Asked Questions" accordion opens/closes correctly
- [ ] Success Stories display in 3-column layout on desktop
- [ ] Prerequisites section shows 2-column layout with requirements
- [ ] All headings render properly
- [ ] No layout breaking or overlapping text
- [ ] Buttons and interactive elements function

### Responsive Design Testing
- [ ] Mobile (320px): Sections stack properly
- [ ] Tablet (768px): 2-column layouts adjust correctly
- [ ] Desktop (1200px): Full width layout displays properly
- [ ] Test in Chrome DevTools device emulation for each breakpoint

### Content Quality Checks
- [ ] No spelling or grammar errors visible
- [ ] All testimonial names and details are appropriate
- [ ] FAQ answers are clear and relevant to the program
- [ ] Prerequisites accurately reflect actual program entry requirements
- [ ] Success stories are realistic and inspiring

## Deployment Steps

### Step 1: Prepare for Deployment
```bash
# Navigate to project directory
cd /path/to/kuccps-courses

# Verify all files are valid HTML (optional)
find templates/ -name "*.html" -type f -exec grep -l "Why Choose" {} \;

# Expected output should show all 6 templates updated
```

### Step 2: Deploy to Production

**If using Git/GitHub:**
```bash
git status  # Verify 6 files modified
git add templates/*.html
git commit -m "Add future enhancements: Why Choose, FAQs, Success Stories, Prerequisites to all course templates"
git push origin main
```

**If using direct deployment:**
- Upload all 6 modified template files to production server
- Verify file permissions: chmod 644 *.html
- Clear any template caches if applicable

### Step 3: Post-Deployment Verification

1. **Verify Live Sites Load:**
   - https://yourdomain.com/degree
   - https://yourdomain.com/diploma
   - https://yourdomain.com/certificate
   - https://yourdomain.com/kmtc
   - https://yourdomain.com/artisan
   - https://yourdomain.com/ttc

2. **Check Page Source for New Content:**
   ```bash
   curl https://yourdomain.com/degree | grep "Why Choose"
   curl https://yourdomain.com/diploma | grep "Success Stories"
   ```

3. **Verify Caching:** 
   - Clear any CDN cache if configured
   - Clear Redis cache if Redis caching is enabled:
   ```python
   # In app.py or via Redis CLI
   REDIS_CLIENT.flushall()
   # or
   cache.clear()
   ```

4. **Check Error Logs:**
   - Monitor application logs for any template rendering errors
   - Check for 500 errors on these pages

## Google Search Console Integration

### Step 4: Request URL Re-indexing

1. **Open Google Search Console**
   - Go to https://search.google.com/search-console
   - Select your property

2. **For Each URL, Request Inspection:**
   - Click "URL Inspection" tool (top search bar)
   - Enter: `https://yourdomain.com/degree`
   - Click "Request indexing" button
   - Repeat for: diploma, certificate, kmtc, artisan, ttc

3. **Monitor Coverage Tab:**
   - Go to Coverage section
   - Look for your 6 URLs
   - Verify no errors or excluded pages
   - Note: May take 1-2 weeks for full re-indexing

### Step 5: Canonical URL Monitoring (2-Week Protocol)

**Week 1: Initial Observation**
- Baseline canonical selections (note which URLs Google assigns to each)
- Check GSC Performance tab for search impressions per URL
- Monitor for 404s or crawl errors

**Week 2: Post-Indexing Observation**
- Compare canonical selections to earlier note
- Google should now select correct canonicals based on unique content
- Check if traffic patterns change (improved impressions for specific program pages)

**Expected Outcome:**
- Google respects your declared canonical URLs
- Each program page ranks independently
- Search queries like "KMTC programs" go to /kmtc
- Search queries like "artisan trades" go to /artisan

## Monitoring & Analytics

### Key Metrics to Track (First Month)

1. **Google Search Console:**
   - Canonical URL selections per page
   - Click-through rate by URL
   - Impressions for program-specific keywords

2. **Google Analytics:**
   - Traffic to each program page
   - Bounce rate (should be lower with more content)
   - Scroll depth (should increase with new sections)
   - Conversion rate by program page

3. **Ranking Keywords:**
   - Monitor rank for queries like:
     - "degree programs Kenya"
     - "KMTC courses"
     - "certificate programs"
     - "teacher training colleges"
     - "artisan training"

### Dashboard Setup (Recommended):
Create a spreadsheet to track weekly:
- Date
- URL
- Current Canonical Selection (GSC)
- Search Impressions (GSC)
- Page Clicks (GSC)
- Organic Traffic (GA4)
- Bounce Rate (GA4)

## Troubleshooting

### Issue: Page renders with style issues

**Solution:**
- Check for CSS class name typos (common: my-5, mb-5, shadow-sm)
- Verify Bootstrap version in base.html matches new classes
- Check browser console for JavaScript errors

### Issue: Accordion not opening/closing

**Solution:**
- Verify Bootstrap JavaScript is loaded
- Check for data-bs-toggle and data-bs-target attributes
- Ensure unique IDs for each accordion (no duplicates)

### Issue: Success Stories display off-center

**Solution:**
- Check col-md-6 or col-md-4 classes applied correctly
- Verify row div wraps all columns
- Check for conflicting CSS rules

### Issue: Content doesn't appear after deployment

**Solution:**
- Clear browser cache (Ctrl+Shift+Delete)
- Clear server-side cache if applicable (Redis, CDN)
- Verify file upload was successful
- Check file permissions: `ls -la templates/degree.html`

## Rollback Plan (If Needed)

If deployed content causes issues:

```bash
# Revert to previous version via Git
git revert HEAD
git push origin main

# OR manually restore from backup
cp backups/certificate.html templates/certificate.html
# Repeat for all 6 templates

# Clear caches
# Redis: redis-cli FLUSHALL
# CDN: Manual purge in CDN control panel
```

## Content Updates (Future Maintenance)

### Updating Success Stories
- Edit success story card HTML in template
- Update graduate names, achievements, earnings
- Keep format consistent (3 cards per template)

### Adding More FAQs
- Accordion structure allows unlimited items
- Copy accordion-item div and increment IDs
- Update questions, answers, and target IDs

### Adjusting Prerequisites
- Edit the two-column section
- Update list items with current requirements
- Keep content current as program requirements change

## Performance Impact

### Expected Page Size Changes
- Degree: +150-200 lines (new sections)
- Diploma: +200+ lines (multiple sections)
- Certificate: +180-220 lines
- KMTC: +140-180 lines
- Artisan: +160-200 lines
- TTC: +200+ lines

**Page Load Time Impact:** Minimal (HTML only, no JS overhead)

### Optimization Recommendations
- Keep images optimized (FAQs/stories sections are text-only)
- Consider lazy-loading if page becomes too long
- Monitor Core Web Vitals in GSC

---

## Success Criteria

✅ Deployment successful when:
1. All 6 pages load without errors
2. New sections visible on each page
3. Accordions and interactive elements work
4. Google Search Console shows URLs being indexed
5. No 404 or server errors in logs
6. Page performance acceptable (< 3s load time)
7. Canonical URLs being respected by Google within 2 weeks

---

**Last Updated:** February 5, 2026
**All Enhancements:** COMPLETE & READY FOR DEPLOYMENT
