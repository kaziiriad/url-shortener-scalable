# Production SaaS Deployment Plan - URL Shortener

## Context

Transforming the existing URL shortener microservice into a production-ready public SaaS platform with:
- **OAuth authentication** (Clerk - Google/GitHub)
- **Rate limiting** (SlowAPI + Redis)
- **Security enhancements** (CORS, headers, malicious URL detection)
- **Deployment** on Vercel (frontend) + Render (backend API)

This addresses critical security gaps identified in the current codebase:
- ❌ No authentication (all endpoints public)
- ❌ No rate limiting (vulnerable to abuse/DoS)
- ❌ No CORS configuration
- ❌ Basic URL validation only
- ❌ No security headers

---

## Implementation Strategy

### Phase 1: Foundation (OAuth + Rate Limiting)

**1.1 Clerk Authentication Setup**

**Frontend (new `frontend/` directory):**
- Create Next.js 14+ app with shadcn/ui components
- Install Clerk: `npm install @clerk/nextjs`
- Configure auth provider and middleware
- Create sign-in/sign-up components

**Backend (modify existing files):**
- `/common/core/config.py` - Add Clerk env vars:
  ```python
  clerk_domain: str = os.getenv("CLERK_DOMAIN", "")
  clerk_audience: str = os.getenv("CLERK_AUDIENCE", "")
  clerk_secret_key: str = os.getenv("CLERK_SECRET_KEY", "")
  ```
- `/common/auth/jwt_handler.py` - NEW: JWT validation middleware
- `/create_service/routes/auth.py` - NEW: `/auth/me` endpoint
- `/create_service/routes/urls.py` - Add `get_current_user` dependency to `/create` endpoint
- Store `user_id` from Clerk with each URL

**1.2 Rate Limiting with SlowAPI**

**Install dependencies:**
```bash
uv add slowapi fastapi-redis
```

**New file: `/common/middleware/rate_limit.py`:**
- Redis-backed rate limiter
- Key function: authenticated users use `user_id`, anonymous use `ip`
- Rate limits: 10/minute (auth), 3/minute (anon) for URL creation
- Custom exception handler for 429 responses

**Modify `/create_service/main.py`:**
- Add rate limiter integration
- Add exception handler

**1.3 CORS Configuration**

**Modify `/create_service/main.py`:**
- Add CORSMiddleware with allowed origins (localhost:3000, Vercel domain)
- Set `allow_credentials=True`

---

### Phase 2: Security Enhancements

**2.1 Security Headers Middleware**

**New file: `/common/middleware/security.py`:**
- Custom middleware for security headers
- Headers: HSTS, X-Frame-Options, CSP, etc.

**2.2 Malicious URL Detection**

**New file: `/common/security/url_validator.py`:**
- Multi-layer validation: TLD checks, keyword detection, IP detection
- Optional VirusTotal integration
- Risk scoring system

**Modify `/common/models/schemas.py`:**
- Enhanced URL validation (max length, localhost prevention, etc.)

---

### Phase 3: Frontend Development

**3.1 Create Next.js Frontend**

**New directory structure:**
```
frontend/
├── app/
│   ├── (auth)/login/page.tsx
│   ├── dashboard/page.tsx
│   ├── create/page.tsx
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── ui/ (shadcn/ui)
│   └── url-shortener/
├── lib/
│   ├── auth.ts (Clerk config)
│   └── api.ts (API client)
└── middleware.ts
```

**3.2 Key Files:**

**`frontend/vercel.json`:** Vercel configuration
**`frontend/next.config.mjs`:** API rewrites to backend
**`frontend/lib/api.ts`:** Authenticated API client

---

### Phase 4: Production Deployment

**4.1 Render Configuration**

**New file: `/render.yaml`:** Blueprint for deployment
- Web service for FastAPI
- Worker service for Celery
- Database configurations

**4.2 Environment Variables**

Set up in Render dashboard:
- MongoDB Atlas connection string
- Redis connection
- Clerk credentials
- Sentry DSN

**4.3 Vercel Deployment**

```bash
cd frontend
vercel deploy
```

---

### Phase 5: Monitoring & Launch

**5.1 Add Sentry Error Tracking**

**New file: `/common/monitoring/sentry.py`:** Sentry integration

**5.2 Seed Production Database**

Run key pre-population script.

**5.3 Monitoring Setup**

- Configure alerts in Grafana
- Set up uptime monitoring (UptimeRobot)
- Test all endpoints

---

## Critical Files Reference

### Files to Create (new):
- `/common/auth/jwt_handler.py` - JWT validation
- `/common/middleware/rate_limit.py` - Rate limiting
- `/common/middleware/security.py` - Security headers
- `/common/security/url_validator.py` - Malicious URL detection
- `/create_service/routes/auth.py` - Auth endpoints
- `/frontend/` - Entire Next.js frontend

### Files to Modify:
- `/common/core/config.py` - Add auth/env vars
- `/create_service/main.py` - Middleware integration
- `/create_service/routes/urls.py` - Add auth dependency
- `/common/models/schemas.py` - Enhanced validation

### Files to Reuse:
- `/common/db/sql/url_repository.py` - Existing key management
- `/common/db/mongo/url_repository.py` - Existing URL storage
- `/common/utils/circuit_breaker.py` - Existing failure protection
- OpenTelemetry tracing setup - Already implemented

---

## Verification Plan

### Development Testing:
1. Start services with `docker-compose-decoupled.yml`
2. Create frontend: `cd frontend && npm install && npm run dev`
3. Test OAuth flow (sign-in/sign-up)
4. Test rate limiting (exceed limits, verify 429)
5. Test malicious URL blocking
6. Test CORS with frontend origin

### Production Testing:
1. Deploy to Render staging environment
2. Deploy to Vercel preview
3. Test auth flow end-to-end
4. Load test with k6 or locust
5. Verify monitoring/alerting
6. DNS configuration

### Success Criteria:
- ✅ OAuth authentication working (Google/GitHub)
- ✅ Rate limits enforced (per user/IP)
- ✅ Malicious URLs blocked
- ✅ Security headers present
- ✅ CORS configured for Vercel domain
- ✅ Health checks passing
- ✅ Error tracking (Sentry) configured
- ✅ Uptime monitoring active
