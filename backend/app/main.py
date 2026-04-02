from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.routers import auth, users, tasks, ref, runs, ai, stream
from app.services.kafka_service import kafka_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("TestOPS API starting — env=%s", settings.APP_ENV)
    await kafka_service.start()
    yield
    await kafka_service.stop()
    logger.info("TestOPS API shutting down")


app = FastAPI(
    title="TestOPS API",
    description="Production Readiness Portal — REST backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(tasks.router, prefix=API_PREFIX)
app.include_router(ref.router, prefix=API_PREFIX)
app.include_router(runs.router, prefix=API_PREFIX)
app.include_router(ai.router, prefix=API_PREFIX)
app.include_router(stream.router, prefix=API_PREFIX)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "version": "1.0.0"}
