"""Vercel entrypoint: same-origin API with a public Vite frontend."""
from contextlib import asynccontextmanager
from pathlib import Path
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from app.main import app as api
from app.settings import get_settings

PUBLIC = Path(__file__).resolve().parent / 'public'


@asynccontextmanager
async def lifespan(app):
    if os.environ.get('VERCEL') == '1' and os.environ.get('VERCEL_ENV') != 'development':
        settings = get_settings()
        if not settings.production or settings.deployment_mode != 'scheduled':
            raise RuntimeError('Vercel deployments require APP_ENV=production and DEPLOYMENT_MODE=scheduled')
    # Mounted applications do not automatically receive parent lifespan events.
    async with api.router.lifespan_context(api):
        yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/api', api)


@app.api_route('/{path:path}', methods=['GET', 'HEAD'], include_in_schema=False)
def frontend(path: str, request: Request):
    # Vercel serves existing public files from the CDN. This also permits local
    # smoke testing of the release entrypoint and navigation fallback.
    target = (PUBLIC / path).resolve()
    if target.is_relative_to(PUBLIC.resolve()) and target.is_file():
        return FileResponse(target)
    if path.startswith('api') or Path(path).suffix or 'text/html' not in request.headers.get('accept', ''):
        raise HTTPException(404, 'Not found')
    if not (PUBLIC / 'index.html').is_file():
        raise HTTPException(503, 'Frontend has not been built')
    return FileResponse(PUBLIC / 'index.html', headers={'Cache-Control': 'no-cache'})
