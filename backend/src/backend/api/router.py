from fastapi import APIRouter

from backend.api.routes_auth import router as auth_router
from backend.api.routes_categories import router as categories_router
from backend.api.routes_classification import router as classification_router
from backend.api.routes_dashboard import router as dashboard_router
from backend.api.routes_imports import router as imports_router
from backend.api.routes_reports import router as reports_router
from backend.api.routes_transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(categories_router, prefix="/categories", tags=["categories"])
api_router.include_router(imports_router, prefix="/imports", tags=["imports"])
api_router.include_router(transactions_router, prefix="/transactions", tags=["transactions"])
api_router.include_router(classification_router, prefix="/classification", tags=["classification"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
