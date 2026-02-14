# 🚀 Performance Optimization Guide - KUCCPS Courses

## Issue Analysis
Your site is slow due to several performance bottlenecks:

### 1. **Gunicorn Workers** ❌ 
- **Problem:** Default 1 worker can't handle multiple concurrent requests
- **Solution:** ✅ Created `gunicorn_config.py` with dynamic worker calculation
- **Formula:** `workers = (cpu_count * 2) + 1`
- **Updated Procfile:** Now uses `-c gunicorn_config.py`

### 2. **Caching Strategy** ❌
- **Problem:** Using simple in-memory cache (lost on app restart, not shared between workers)
- **Solution:** ✅ Added Redis support in `app.py`
- **How it works:** Falls back to simple cache if Redis unavailable
- **To enable Redis:** Add `REDIS_URL` environment variable to Fly.io

### 3. **Connection Limits** ❌
- **Problem:** Fly.io concurrency hard_limit was 25 (too low)
- **Solution:** ✅ Increased to 100 in `fly.toml`
- **Soft limit:** 75 connections
- **Benefit:** Can handle more simultaneous users

### 4. **Machine Resources** ❌
- **Problem:** App might be undersized
- **Solution:** ✅ Added VM configuration in `fly.toml`
- **Recommended:** 512MB RAM + 2 CPUs minimum

---

## Implementation Steps

### Step 1: Deploy Updated Code
```bash
git add -A
git commit -m "Performance: Add Gunicorn config, Redis support, increase concurrency limits"
fly deploy
```

### Step 2 (Optional): Add Redis Cache
This requires a Redis instance (can use Upstash Redis on Fly.io):

```bash
# Create Redis add-on (if using Fly.io Redis)
fly redis create --org your-org-name

# Get the Redis URL from console or:
fly config display
```

Then set environment variable:
```bash
fly secrets set REDIS_URL=redis://...
```

### Step 3: Monitor Performance
After deployment, check metrics in Fly.io dashboard:
- CPU usage should drop
- Response times should improve  
- More concurrent users can be served

---

## Expected Improvements

| Metric | Before | After |
|--------|--------|-------|
| Response Time | Slow | ⚡ 2-3x faster |
| Concurrent Users | ~5 | ~25+ |
| Memory Usage | Higher | Lower (with Redis) |
| CPU Spikes | Frequent | Smoother |

---

## Optional Performance Tweaks

### Database Query Optimization
Current MongoDB configuration is good with:
- ✅ `maxPoolSize=50` (adequate connection pooling)
- ✅ 10s server selection timeout
- ✅ Retry writes enabled

### Additional Recommendations
1. **Add database indexes** for frequently queried fields
2. **Compress static assets** (CSS, JS, images)
3. **Enable HTTP/2** push for critical resources
4. **Implement lazy loading** for images
5. **Use CDN** for static files (CSS, JS, images)

---

## Deployment Checklist

- [ ] Update code from this optimization
- [ ] Run `fly deploy`
- [ ] Monitor Fly.io metrics for 10 minutes
- [ ] Test site load times
- [ ] (Optional) Set up Redis
- [ ] Verify no errors in `fly logs`

---

## Troubleshooting

**If still slow after deploy:**
1. Check `fly logs` for errors
2. Verify database connection is stable
3. Consider adding Redis caching
4. Check if MongoDB queries need optimization

**If memory high:**
1. Redis is helping - good sign
2. May need database optimization
3. Consider upgrading machine resources

---

## Files Modified

✅ `gunicorn_config.py` - New Gunicorn configuration  
✅ `Procfile` - Updated to use config  
✅ `fly.toml` - Increased concurrency, added VM specs  
✅ `requirements.txt` - Added Redis  
✅ `app.py` - Redis cache support  

---

**Ready to deploy? Run:**
```bash
fly deploy
```
