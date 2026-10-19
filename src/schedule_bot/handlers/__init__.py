from aiogram import Router

from schedule_bot.handlers import admin, common, schedule, submissions


def setup_router() -> Router:
    router = Router()
    router.include_routers(common.router, schedule.router, submissions.router, admin.router)
    return router
