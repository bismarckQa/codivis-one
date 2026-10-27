from fastapi import APIRouter

from app.api.routes import auth, branches, customers, license
from app.modules.inventory.routers import stock_adjustments_router
from app.modules.products.routers import products_router
from app.modules.sales.routers.sales import router as sales_router


api_router = APIRouter()
api_router.include_router(license.router)
api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(branches.router)
api_router.include_router(products_router)
api_router.include_router(stock_adjustments_router)
api_router.include_router(sales_router)
