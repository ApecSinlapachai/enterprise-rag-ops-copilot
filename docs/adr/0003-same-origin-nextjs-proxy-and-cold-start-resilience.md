# ADR-0003: Same-Origin Next.js Proxy, Cold-Start Polling & IP-Hashed Rate Limiting

- **Status:** Accepted
- **Date:** 2026-11-26
- **Deciders:** Apec Sinlapachai

---

## 1. Context
Hosting the frontend on Vercel Hobby and the FastAPI backend on Render Free introduces two UX and security friction points: (1) direct browser requests to `*.onrender.com` can be blocked by corporate firewalls, AdBlock/Brave shields, or CORS preflights, and (2) Render Free instances sleep after inactivity (~30–50s cold start), causing naive client fetches to fail on first load. Meanwhile, a no-login public demo requires abuse protection without storing raw visitor IP addresses (PDPA).

## 2. Decision
> We will proxy all browser API traffic through **Next.js `rewrites()` (`/backend/:path*`)** in `web/next.config.mjs`, run a **bounded `/backend/health` cold-start poller** (up to 10 attempts × 5s with timer cleanup) on page mount, and enforce a **thread-safe SHA-256 IP-hashed sliding-window rate limiter** (`15 req/min`, `60 req/day`, bounded key eviction, `Retry-After` header exposed via CORS).

## 3. Alternatives Considered
| Option | Pros | Cons | Why Rejected / Chosen |
| :--- | :--- | :--- | :--- |
| **Next.js `/backend/*` Rewrites + Health Polling + In-Memory SHA-256 Limiter (Chosen)** | Zero cross-origin browser calls; zero raw IP storage; smooth Render wake-up UX; `$0` infrastructure | In-memory limiter resets on container restart (acceptable for single-instance Render Free) | Best UX, privacy, and `$0` reliability |
| **Direct Browser Calls to `*.onrender.com`** | One fewer hop | Triggers CORS preflights, AdBlock/firewall blocks, and exposes upstream host directly | Rejected after production proxy hardening |
| **Redis-Backed Distributed Rate Limiter** | Shared across multiple replicas | Adds external dependency and cost unnecessary for a single Free Tier instance | Rejected as overkill for current scale |

## 4. Consequences
- **Positive:** Verified `0` direct `*.onrender.com` calls and `0` CORS/console errors on Vercel; visitors see a clear `"Warming API..."` → `"API Ready"` transition instead of raw network errors.
- **Negative / Trade-offs:** Requires configuring `API_PROXY_TARGET` (or `NEXT_PUBLIC_API_BASE_URL`) on Vercel so `next.config.mjs` rewrites resolve to the Render backend.
- **Reversibility:** Easy — controlled solely by `web/next.config.mjs`, `web/src/lib/api.ts`, and `api/app/services/rate_limiter.py`.
