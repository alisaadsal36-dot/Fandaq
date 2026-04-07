"""
RAHATY — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.config import get_settings
from app.api.webhook import router as webhook_router
from app.api.v1.hotels import router as hotels_router
from app.api.v1.rooms import router as rooms_router
from app.api.v1.reservations import router as reservations_router
from app.api.v1.reports import router as reports_router
from app.api.v1.complaints import router as complaints_router
from app.api.v1.guest_requests import router as guest_requests_router
from app.api.v1.guests import router as guests_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.daily_pricing import router as daily_pricing_router
from app.api.v1.competitors import router as competitors_router
from app.api.v1.auth import router as auth_router
from app.api.v1.employee_evaluations import router as employee_evaluations_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    print(f"🏨 {settings.APP_NAME} starting up...")
    
    # Start background scheduler (scraper + reminders)
    from app.services.scheduler import init_scheduler
    init_scheduler()
    
    # Ensure default admin exists
    from app.services.auth import AuthService
    from app.database import async_session_factory
    async with async_session_factory() as db:
        await AuthService.ensure_default_admin(db)
    
    
    yield
    # Shutdown
    print(f"🏨 {settings.APP_NAME} shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-hotel management system powered by WhatsApp, Telegram and AI",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def disable_cache_for_dashboard_and_api(request: Request, call_next):
    """Prevent stale dashboard assets and API responses in browsers/proxies."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/dashboard") or path.startswith(settings.API_V1_PREFIX):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# ── CORS ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────
# WhatsApp webhook (no prefix)
app.include_router(webhook_router, tags=["WhatsApp & Telegram Webhooks"])

# Admin API v1
prefix = settings.API_V1_PREFIX
app.include_router(auth_router, prefix=prefix, tags=["Authentication"])
app.include_router(hotels_router, prefix=prefix, tags=["Hotels"])
app.include_router(rooms_router, prefix=prefix, tags=["Rooms"])
app.include_router(reservations_router, prefix=prefix, tags=["Reservations"])
app.include_router(reports_router, prefix=prefix, tags=["Reports"])
app.include_router(daily_pricing_router, prefix=prefix, tags=["Daily Pricing"])
app.include_router(competitors_router, prefix=prefix, tags=["Competitors"])
app.include_router(complaints_router, prefix=prefix, tags=["Complaints"])
app.include_router(guest_requests_router, prefix=prefix, tags=["Guest Requests"])
app.include_router(guests_router, prefix=prefix, tags=["Guests"])
app.include_router(reviews_router, prefix=prefix, tags=["Reviews"])
app.include_router(employee_evaluations_router, prefix=prefix, tags=["Employee Evaluations"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

# ── Dashboard ─────────────────────────────────────────
dashboard_dir = os.path.join(os.path.dirname(__file__), "..", "dashboard")
if os.path.isdir(dashboard_dir):
    app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
