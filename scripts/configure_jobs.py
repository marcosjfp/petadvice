"""Review or apply the two QStash schedules. Never sends user data."""
import argparse
import json
import hashlib
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.settings import get_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Create/update remote QStash schedules; default is a plan')
    args = parser.parse_args()
    settings = get_settings()
    site_key = hashlib.sha256(settings.public_web_url.rstrip('/').encode()).hexdigest()[:12]
    for kind, cron in [('mail', '*/15 * * * *'), ('maintenance', '0 * * * *')]:
        schedule_id = f'petadvice-{site_key}-{kind}'
        if args.apply:
            if not settings.production or settings.deployment_mode != 'scheduled':
                raise RuntimeError('Set APP_ENV=production and DEPLOYMENT_MODE=scheduled before applying schedules')
            settings.validate_production()
            headers = {'Authorization': f'Bearer {settings.qstash_token}', 'Upstash-Cron': cron,
                       'Upstash-Schedule-Id': schedule_id, 'Upstash-Retries': '6',
                       'Upstash-Retry-Delay': 'min(600000, 60000 * pow(2, retried))'}
            if settings.vercel_automation_bypass_secret:
                headers['Upstash-Forward-x-vercel-protection-bypass'] = settings.vercel_automation_bypass_secret
                headers['Upstash-Redact-Fields'] = 'headers'
            response = httpx.post(settings.qstash_url.rstrip('/') + '/v2/schedules/' + settings.job_callback_url,
                headers=headers,
                json={'kind': kind}, timeout=15)
            response.raise_for_status()
        print(json.dumps({'schedule': schedule_id, 'cron_utc': cron, 'destination': settings.job_callback_url, 'body': {'kind': kind}, 'applied': args.apply}))
    if args.apply:
        # Seed readiness immediately rather than waiting for the first hourly run.
        initial_headers = {key: value for key, value in headers.items() if key not in ('Upstash-Cron', 'Upstash-Schedule-Id')}
        response = httpx.post(settings.qstash_url.rstrip('/') + '/v2/publish/' + settings.job_callback_url,
            headers=initial_headers, json={'kind': 'maintenance'}, timeout=15)
        response.raise_for_status()
        print(json.dumps({'initial_maintenance_requested': True}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Schedule configuration failed ({type(error).__name__}); check private configuration and provider console.', file=sys.stderr)
        sys.exit(1)
