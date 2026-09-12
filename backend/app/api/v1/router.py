"""Aggregates the v1 routers."""

from fastapi import APIRouter

from app.api.v1 import auth, dashboard, interviews, profile

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(auth.users_router)
api_router.include_router(profile.router)
api_router.include_router(profile.documents_router)
api_router.include_router(profile.jobs_router)
api_router.include_router(interviews.router)
api_router.include_router(dashboard.router)
api_router.include_router(dashboard.admin_router)
