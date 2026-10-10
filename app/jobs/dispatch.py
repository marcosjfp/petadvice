"""Best-effort wakeup after the durable email transaction commits."""
import logging

import httpx

from app.settings import get_settings


def trigger_mail():
    settings = get_settings()
    if settings.deployment_mode != 'scheduled':
        return
    headers = {'Authorization': f'Bearer {settings.qstash_token}', 'Upstash-Retries': '6',
               'Upstash-Retry-Delay': 'min(600000, 60000 * pow(2, retried))'}
    if settings.vercel_automation_bypass_secret:
        headers['Upstash-Forward-x-vercel-protection-bypass'] = settings.vercel_automation_bypass_secret
        headers['Upstash-Redact-Fields'] = 'headers'
    try:
        response = httpx.post(settings.qstash_url.rstrip('/') + '/v2/publish/' + settings.job_callback_url,
            headers=headers,
            json={'kind': 'mail'}, timeout=2)
        response.raise_for_status()
    except Exception:
        # The encrypted outbox survives failures; scheduled reconciliation retries.
        # Provider exceptions can contain credentials. Never log them.
        logging.getLogger('petadvice.jobs').warning('mail_trigger_failed')
