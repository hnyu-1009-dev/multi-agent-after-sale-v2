from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from app.api.dependencies import get_bearer_token, get_current_user
from app.infrastructure.logging.logger import logger
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    UserProfile,
)
from app.schemas.request import ChatMessageRequest, UserSessionsRequest
from app.services.agent_service import MultiAgentService
from app.services.auth_service import AuthServiceError, auth_service
from app.services.session_service import session_service

router = APIRouter()


@router.post("/api/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest):
    try:
        return auth_service.register(payload)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    try:
        return auth_service.login(payload)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/api/auth/me", response_model=UserProfile)
def get_me(current_user: UserProfile = Depends(get_current_user)):
    return current_user


@router.post("/api/auth/logout", response_model=LogoutResponse)
def logout(token: str = Depends(get_bearer_token)):
    auth_service.logout(token)
    return LogoutResponse()


@router.post("/api/query", summary="智能体对话接口")
async def query(
    request_context: ChatMessageRequest,
    current_user: UserProfile = Depends(get_current_user),
) -> StreamingResponse:
    request_context.context.user_id = current_user.user_id
    user_query = request_context.query

    logger.info("User %s query received: %s", current_user.user_id, user_query)

    async_generator_result = MultiAgentService.process_task(request_context, flag=True)
    return StreamingResponse(
        content=async_generator_result,
        status_code=200,
        media_type="text/event-stream",
    )


@router.post("/api/user_sessions")
def get_user_sessions(
    request: UserSessionsRequest,
    current_user: UserProfile = Depends(get_current_user),
):
    user_id = current_user.user_id
    logger.info("Loading sessions for user %s", user_id)

    try:
        all_sessions = session_service.get_all_sessions_memory(user_id)
        return {
            "success": True,
            "user_id": user_id,
            "total_sessions": len(all_sessions),
            "sessions": all_sessions,
        }
    except Exception as exc:
        logger.error("Failed to load sessions for user %s: %s", user_id, exc)
        return {"success": False, "user_id": user_id, "error": str(exc)}
