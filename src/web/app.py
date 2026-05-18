"""FastAPI 应用入口 —— 启动 Web 服务和调度器。"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from src.web.routes import router
from src.scheduler.jobs import start_scheduler
from src.db.models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield

app = FastAPI(title="Evomentor", lifespan=lifespan)
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("src/web/templates/index.html", "r", encoding="utf-8") as f:
        return f.read()
