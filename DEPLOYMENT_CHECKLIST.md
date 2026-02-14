# Canonical URL Fix - Deployment Checklist

## ✅ Fixes Applied

### Code Changes
- [x] Added SERVER_NAME configuration to Flask app
- [x] Enhanced `get_canonical_url()` function with fallback mechanism
- [x] Added explicit canonical tag to `/diploma` page
- [x] Added explicit canonical tag to `/kmtc` page
- [x] Added explicit canonical tag to `/certificate` page
- [x] Added explicit canonical tag to `/artisan` page
- [x] Added explicit canonical tag to `/ttc` page
- [x] Added explicit canonical tag to `/degree` page

### Documentation
- [x] Created CANONICAL_FIX_JAN_31_2026.md with technical details
- [x] Created CANONICAL_FIX_CHANGES.md with summary
- [x] Created this deployment checklist

## 📋 Pre-Deployment Checklist

### Code Review
- [ ] Review changes in `app.py`
- [ ] Review canonical tags in all template files
- [ ] Verify no syntax errors
- [ ] Test locally if possible

### Testing
- [ ] Test canonical URL generation for all routes
- [ ] Verify URLs include `https://www.` prefix
- [ ] Check for proper trailing slash handling
- [ ] Verify no broken links

## 🚀 Deployment Steps

### Step 1: Push Code
```bash
cd c:\Users\ADMIN\Documents\Documents\kuccps-courses
git status
git add -A
git commit -m "Fix: Add explicit self-referential canonical tags and SERVER_NAME configuration

- Add SERVER_NAME configuration for proper URL generation
- Enhance get_canonical_url() with robust fallback mechanism  
- Add explicit self-referential canonical tags to all course pages
- Resolves Google Search Console duplicate canonical issue"
git push origin main  # or your deployment branch
```

### Step 2: Verify Deployment
- [ ] Confirm code deployed to production
- [ ] Check `/diploma` page loads correctly
- [ ] Verify canonical tag in page source

### Step 3: Resubmit to Google
1. Go to Google Search Console
2. For each affected page:
   - Click "URL Inspection"
   - Enter: `https://www.kuccpscourses.co.ke/[page]`
   - Click "Request Indexing"

**Pages to Resubmit**:
- [ ] https://www.kuccpscourses.co.ke/diploma ← **PRIMARY FIX**
- [ ] https://www.kuccpscourses.co.ke/kmtc
- [ ] https://www.kuccpscourses.co.ke/certificate
- [ ] https://www.kuccpscourses.co.ke/artisan
- [ ] https://www.kuccpscourses.co.ke/ttc
- [ ] https://www.kuccpscourses.co.ke/degree

## ⏱️ Timeline

- **Immediately After Deployment**: 
  - Resubmit all pages to Google
  - Monitor for errors

- **24-48 Hours**: 
  - Check Google Search Console
  - Verify pages are being indexed
  - Confirm no duplicate warnings

- **1-2 Weeks**: 
  - Verify all pages fully indexed
  - Monitor ranking changes
  - Check for any indexation issues

## 🔍 Verification Steps

### After Deployment
1. **Check Page Source**
   ```
   View the source of https://www.kuccpscourses.co.ke/diploma
   Should see: <link rel="canonical" href="https://www.kuccpscourses.co.ke/diploma" />
   ```

2. **Test All Pages**
   - `/degree` → should have canonical to `/degree`
   - `/diploma` → should have canonical to `/diploma`
   - `/kmtc` → should have canonical to `/kmtc`
   - `/certificate` → should have canonical to `/certificate`
   - `/artisan` → should have canonical to `/artisan`
   - `/ttc` → should have canonical to `/ttc`

3. **Check Headers** (optional)
   ```
   curl -I https://www.kuccpscourses.co.ke/diploma
   Should return 200 OK with proper headers
   ```

## 📊 Success Criteria

Your fix is successful when:
1. ✅ `/diploma` page is indexed in Google
2. ✅ Canonical URL shows `https://www.kuccpscourses.co.ke/diploma` (not `/kmtc`)
3. ✅ No "duplicate" warnings in Google Search Console
4. ✅ All 6 course pages are properly indexed
5. ✅ Pages appear in search results

## 🚨 Rollback Plan

If issues occur:
```bash
git revert HEAD
git push origin main
```

The previous working version will be restored.

## 📞 Support Information

If you encounter issues:
1. Check the logs in CANONICAL_FIX_JAN_31_2026.md
2. Review the technical details in CANONICAL_FIX_CHANGES.md
3. Verify SERVER_NAME is set for production environment
4. Check Flask app logs for canonical URL generation messages

---

**Created**: January 31, 2026  
**Status**: Ready for Deployment
