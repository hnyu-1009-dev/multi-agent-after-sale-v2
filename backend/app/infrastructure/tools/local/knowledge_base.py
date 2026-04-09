import asyncio
import time
from typing import Dict

import httpx
from agents import function_tool

from app.config.settings import settings
from app.infrastructure.logging.logger import logger


@function_tool
async def query_knowledge(question: str) -> Dict:
    """
    查询知识库中的问题并返回结果。
    """

    async with httpx.AsyncClient(trust_env=False) as client:
        try:
            started_at = time.perf_counter()
            response = await client.post(
                url=f"{settings.KNOWLEDGE_BASE_URL}/query",
                json={"question": question},
                timeout=httpx.Timeout(12.0, connect=2.0, read=10.0, write=2.0, pool=2.0),
            )
            response.raise_for_status()
            logger.info(
                "Knowledge tool query completed in %.2fs",
                time.perf_counter() - started_at,
            )
            return response.json()

        except httpx.HTTPError as e:
            logger.error("Knowledge tool HTTP error: %s", e)
            return {
                "status": "error",
                "error_msg": f"Knowledge tool HTTP error: {e}",
            }
        except Exception as e:
            logger.error("Knowledge tool unexpected error: %s", e)
            return {"status": "error", "error_msg": f"Knowledge tool unexpected error: {e}"}


async def main():
    result = await query_knowledge(question="无法上网")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
