import logging
import os.path
import shutil
import tempfile
import time

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from knowledge.config.settings import settings
from knowledge.schemas.schema import QueryRequest, QueryResponse, UploadResponse
from knowledge.services.ingestion.ingestion_processor import IngestionProcessor
from knowledge.services.query_service import QueryService
from knowledge.services.retrieval_service import RetrievalService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()
ingestion_processor = IngestionProcessor()
retrieval_service = RetrievalService()
query_service = QueryService()


@router.post("/upload", response_model=UploadResponse, summary="上传知识库文件")
async def upload_file(file: UploadFile = File(...)):
    temp_file_path = None
    try:
        temp_md_dir = settings.TMP_MD_FOLDER_PATH
        file_suffix = os.path.splitext(file.filename)[1]
        tmp_md_path = os.path.join(temp_md_dir, file.filename)
        if not os.path.exists(tmp_md_path):
            os.makedirs(temp_md_dir, exist_ok=True)

        async with aiofiles.tempfile.NamedTemporaryFile(
            delete=False, suffix=file_suffix
        ) as temp_file:
            while content := await file.read(1024 * 1024):
                await temp_file.write(content)
            temp_file_path = temp_file.name

        shutil.move(temp_file_path, tmp_md_path)
        chunks_added = await run_in_threadpool(
            ingestion_processor.ingest_file, tmp_md_path
        )

        return UploadResponse(
            status="success",
            message="文件已上传并写入知识库。",
            file_name=file.filename,
            chunks_added=chunks_added,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info("Temporary upload file removed: %s", temp_file_path)


@router.post("/query", response_model=QueryResponse, summary="查询知识库")
async def query(request: QueryRequest):
    try:
        started_at = time.perf_counter()
        user_question = request.question
        if not user_question:
            raise HTTPException(status_code=500, detail="问题不能为空")

        retrieval_context = await run_in_threadpool(
            retrieval_service.retrieval, user_question
        )
        answer = await run_in_threadpool(
            query_service.generate_answer, user_question, retrieval_context
        )

        logger.info(
            "Knowledge query completed in %.2fs with %s retrieved documents",
            time.perf_counter() - started_at,
            len(retrieval_context),
        )
        return QueryResponse(question=user_question, answer=answer)
    except Exception as e:
        logger.error("Knowledge query failed: %s", e)
        raise HTTPException(status_code=500, detail="知识库查询失败")
