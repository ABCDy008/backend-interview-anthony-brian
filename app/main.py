from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.database import engine

__all__ = ["app", "engine"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="FX Money Changer API", version="0.1.0", lifespan=lifespan)
app.include_router(router)