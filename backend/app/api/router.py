from fastapi import APIRouter

from app.api import attendance, audit, auth, cameras, departments, employees, leave, me, recognition, reports, schedules, users

api_router = APIRouter(prefix="/api/v1")
for module in (auth, users, departments, employees, cameras, schedules, recognition, attendance, leave, me, reports, audit):
    api_router.include_router(module.router)
