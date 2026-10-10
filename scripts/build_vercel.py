"""Build static assets without contacting a database or migrating on deploy."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=ROOT / 'web', check=True)
    subprocess.run(['npm', 'run', 'build'], cwd=ROOT / 'web', check=True)
    public = ROOT / 'public'
    if public.exists():
        shutil.rmtree(public)
    shutil.copytree(ROOT / 'web' / 'dist', public)
    print('Vercel frontend prepared; no database changes applied.')


if __name__ == '__main__':
    main()
