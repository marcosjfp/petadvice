"""Vercel entrypoint: same-origin API with a public Vite frontend."""
from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
import mimetypes
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response

from app.main import app as api
from app.settings import get_settings

PUBLIC = Path(__file__).resolve().parent / 'public'
# Files that keep their name across releases. Vercel builds give every file the same
# timestamp, and FileResponse derives its ETag from timestamp and size, so a new sw.js
# of the same length looked unchanged and browsers kept running the old app.
NEVER_STORE = {'index.html', 'sw.js'}
mimetypes.add_type('application/manifest+json', '.webmanifest')


def unhashed_file(target: Path, relative: str) -> Response:
    content = target.read_bytes()
    media_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
    headers = {'ETag': f'"{hashlib.sha256(content).hexdigest()[:32]}"'}
    headers['Cache-Control'] = 'no-store' if relative in NEVER_STORE else 'no-cache'
    return Response(content, media_type=media_type, headers=headers)


@asynccontextmanager
async def lifespan(app):
    if os.environ.get('VERCEL') == '1' and os.environ.get('VERCEL_ENV') != 'development':
        settings = get_settings()
        if not settings.production or settings.deployment_mode != 'scheduled':
            raise RuntimeError('Vercel deployments require APP_ENV=production and DEPLOYMENT_MODE=scheduled')
        if (settings.guest_only_preview or settings.accounts_without_email_preview) and os.environ.get('VERCEL_ENV') != 'preview':
            raise RuntimeError('Email-disabled modes require a protected preview deployment')
    # Mounted applications do not automatically receive parent lifespan events.
    async with api.router.lifespan_context(api):
        yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/api', api)


@app.api_route('/{path:path}', methods=['GET', 'HEAD'], include_in_schema=False)
def frontend(path: str, request: Request):
    # Include public/** in the function bundle as well as any CDN copy: Vercel's
    # Python builder otherwise excludes public files from runtime SPA fallback.
    target = (PUBLIC / path).resolve()
    if target.is_relative_to(PUBLIC.resolve()) and target.is_file():
        relative = target.relative_to(PUBLIC.resolve()).as_posix()
        # Content-hashed build assets are immutable; everything else must change when its content does.
        return FileResponse(target) if relative.startswith('assets/') else unhashed_file(target, relative)
    if path.startswith('api') or Path(path).suffix or (path and 'text/html' not in request.headers.get('accept', '')):
        raise HTTPException(404, 'Not found')
    if not (PUBLIC / 'index.html').is_file():
        raise HTTPException(503, 'Frontend has not been built')
    return unhashed_file(PUBLIC / 'index.html', 'index.html')
