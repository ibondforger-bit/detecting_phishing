from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routers import deep_scan, fast_tier, whitelist


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Desktop app handles UI setup and wizard; no automatic browser popup
    yield


app = FastAPI(title="WebSense Backend", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fast_tier.router)
app.include_router(deep_scan.router)
app.include_router(whitelist.router)


@app.get("/health")
async def health() -> dict[str, str]:
    from server.routers.fast_tier import PROTECTION_ACTIVE
    status_str = "running" if PROTECTION_ACTIVE else "paused"
    return {"status": status_str}

