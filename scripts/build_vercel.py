"""Build static assets without contacting a database or migrating on deploy."""
from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=ROOT / 'web', check=True)
    build_env = dict(os.environ)
    build_env['VITE_GUEST_ONLY_PREVIEW'] = 'true' if os.getenv('GUEST_ONLY_PREVIEW', '').lower() in ('true', '1', 'yes') else 'false'
    build_env['VITE_ACCOUNTS_WITHOUT_EMAIL_PREVIEW'] = 'true' if os.getenv('ACCOUNTS_WITHOUT_EMAIL_PREVIEW', '').lower() in ('true', '1', 'yes') else 'false'
    subprocess.run(['npm', 'run', 'build'], cwd=ROOT / 'web', env=build_env, check=True)
    public = ROOT / 'public'
    if public.exists():
        shutil.rmtree(public)
    shutil.copytree(ROOT / 'web' / 'dist', public)
    print('Vercel frontend prepared; no database changes applied.')


if __name__ == '__main__':
    main()
