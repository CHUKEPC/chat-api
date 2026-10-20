"""Aggregated API router assembling auth, users, chats, messages, and websockets."""

from fastapi import APIRouter

from chat_api.api.auth import router as auth_router
from chat_api.api.chats import router as chats_router
from chat_api.api.messages import router as messages_router
from chat_api.api.users import router as users_router
from chat_api.api.websocket import router as websocket_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(chats_router)
api_router.include_router(messages_router)
api_router.include_router(websocket_router)
