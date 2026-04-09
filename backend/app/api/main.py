from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import router
from app.infrastructure.database.schema_manager import ensure_database_schema
from app.infrastructure.logging.logger import logger
from app.infrastructure.tools.mcp.mcp_manager import mcp_cleanup, mcp_connect


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup: preparing database schema and MCP connections")
    try:
        ensure_database_schema()
        logger.info("Database schema initialized")
    except Exception as exc:
        logger.error("Database schema initialization failed: %s", exc)

    try:
        await mcp_connect()
        logger.info("MCP connections established")
    except Exception as exc:
        logger.error("MCP connection failed: %s", exc)

    yield

    logger.info("Application shutdown: cleaning MCP connections")
    try:
        await mcp_cleanup()
        logger.info("MCP cleanup completed")
    except Exception as exc:
        logger.error("MCP cleanup failed: %s", exc)


def create_fast_api() -> FastAPI:
    app = FastAPI(title="ITS API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router=router)
    return app


app = create_fast_api()


if __name__ == "__main__":
    uvicorn.run(app="app.api.main:app", host="127.0.0.1", port=8000)
