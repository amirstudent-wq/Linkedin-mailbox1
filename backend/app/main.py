import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import auth, messages, ai, use_cases, scheduler as scheduler_router
from .services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initialising database…")
    await init_db()
    logger.info("Starting scheduler…")
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()
    logger.info("Application shut down.")


app = FastAPI(
    title="LinkedIn Mailbox Manager",
    description="AI-powered LinkedIn inbox management with daily reply scanning.",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(messages.router)
app.include_router(ai.router)
app.include_router(use_cases.router)
app.include_router(scheduler_router.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "LinkedIn Mailbox Manager API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
