from aiogram import Router

from schedule_bot.handlers import admin, common, schedule


def setup_router() -> Router:
    router = Router()
    router.include_routers(common.router, schedule.router, admin.router)
    return router
