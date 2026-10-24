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
    public_beta = os.getenv('ACCOUNTS_WITHOUT_EMAIL_BETA', '').lower() in ('true', '1', 'yes')
    without_email = public_beta or os.getenv('ACCOUNTS_WITHOUT_EMAIL_PREVIEW', '').lower() in ('true', '1', 'yes')
    build_env['VITE_ACCOUNTS_WITHOUT_EMAIL_PREVIEW'] = 'true' if without_email else 'false'
    build_env['VITE_PUBLIC_TEST_BETA'] = 'true' if public_beta else 'false'
    subprocess.run(['npm', 'run', 'build'], cwd=ROOT / 'web', env=build_env, check=True)
    public = ROOT / 'public'
    if public.exists():
        shutil.rmtree(public)
    shutil.copytree(ROOT / 'web' / 'dist', public)
    if public_beta:
        index = public / 'index.html'
        index.write_text(index.read_text().replace('</head>', '<meta name="robots" content="noindex,nofollow" /></head>'))
    print('Vercel frontend prepared; no database changes applied.')


if __name__ == '__main__':
    main()
