import base64
import hashlib
import json
from datetime import timedelta
from unittest.mock import Mock

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.schema import EmailDelivery, GuestAccess, MaintenanceStatus, TriageSession
from app.services.auth import utcnow
from app.settings import get_settings
from tests.test_auth import client, reset_db, signup, test_engine  # noqa: F401
from tests.test_hardening import production_settings


@pytest.fixture
def scheduled(monkeypatch):
    settings = get_settings()
    for field, value in {'deployment_mode': 'scheduled', 'qstash_current_signing_key': 'current-' + 'x'*40, 'qstash_next_signing_key': 'next-' + 'x'*40, 'qstash_token': 'test-only', 'public_web_url': 'https://petadvice.example'}.items():
        monkeypatch.setattr(settings, field, value)
    monkeypatch.setattr('app.services.account_actions.trigger_mail', lambda: None)
    monkeypatch.setattr('app.api.auth.trigger_mail', lambda: None)
    return settings


def signature(raw_body, settings, key=None, **claims):
    digest = base64.urlsafe_b64encode(hashlib.sha256(raw_body).digest()).decode().rstrip('=')
    return jwt.encode({'iss': 'Upstash', 'sub': settings.job_callback_url, 'nbf': utcnow()-timedelta(seconds=1), 'exp': utcnow()+timedelta(minutes=5), 'body': digest, **claims}, key or settings.qstash_current_signing_key, algorithm='HS256')


def post_job(client, scheduled, kind='maintenance', **claims):
    body = json.dumps({'kind': kind}).encode()
    return client.post('/jobs/run', content=body, headers={'Content-Type': 'application/json', 'Upstash-Signature': signature(body, scheduled, **claims)})


@pytest.mark.parametrize('claims', [{'iss': 'attacker'}, {'sub': 'https://other.example/api/jobs/run'}, {'body': 'wrong'}, {'exp': 1}, {'nbf': 9999999999}])
def test_bad_signatures_cannot_run_jobs(client, scheduled, claims):
    assert post_job(client, scheduled, **claims).status_code == 401
    with Session(test_engine) as db:
        assert db.get(MaintenanceStatus, 'maintenance') is None


def test_key_rotation_raw_body_and_duplicate_callbacks(client, scheduled):
    body = b'{ "kind" : "maintenance" }'
    headers = {'Content-Type': 'application/json', 'Upstash-Signature': signature(body, scheduled, key=scheduled.qstash_next_signing_key)}
    assert client.post('/jobs/run', content=body, headers=headers).status_code == 200
    assert client.post('/jobs/run', content=body, headers=headers).status_code == 200
    assert client.post('/jobs/run', content=b'{"kind":"maintenance"}', headers=headers).status_code == 401
    assert client.post('/jobs/run', json={'kind': 'maintenance'}).status_code == 401
    assert client.get('/ready').status_code == 200
    with Session(test_engine) as db:
        status = db.get(MaintenanceStatus, 'maintenance'); status.last_success_at = utcnow()-timedelta(minutes=60); db.add(status); db.commit()
    assert client.get('/ready').status_code == 200
    with Session(test_engine) as db:
        status = db.get(MaintenanceStatus, 'maintenance'); status.last_success_at = utcnow()-timedelta(minutes=91); db.add(status); db.commit()
    assert client.get('/ready').status_code == 503


def test_resend_failure_is_durable_then_retries_with_same_idempotency_key(client, scheduled, monkeypatch):
    signup(client, 'scheduled@example.com')
    monkeypatch.setattr(get_settings(), 'mail_backend', 'resend')
    monkeypatch.setattr(get_settings(), 'resend_api_key', 'test-only-resend')
    request = httpx.Request('POST', 'https://api.resend.com/emails')
    sender = Mock(return_value=httpx.Response(503, request=request))
    monkeypatch.setattr('app.services.mail.httpx.post', sender)
    assert post_job(client, scheduled, 'mail').status_code == 503
    initial_key = sender.call_args.kwargs['headers']['Idempotency-Key']
    assert sender.call_args.kwargs['json']['to'] == ['scheduled@example.com']
    with Session(test_engine) as db:
        mail = db.exec(select(EmailDelivery)).one(); assert mail.attempts == 1
        mail.next_attempt_at = utcnow()-timedelta(seconds=1); db.add(mail); db.commit()
    sender.return_value = httpx.Response(200, json={'id': 'test-id'}, request=request)
    assert post_job(client, scheduled, 'mail').status_code == 200
    assert sender.call_args.kwargs['headers']['Idempotency-Key'] == initial_key
    with Session(test_engine) as db:
        assert db.exec(select(EmailDelivery)).all() == []
        assert db.get(MaintenanceStatus, 'maintenance') is None


def test_trigger_failure_keeps_committed_outbox_and_hides_provider_errors(client, monkeypatch, caplog):
    monkeypatch.setattr(get_settings(), 'deployment_mode', 'scheduled')
    monkeypatch.setattr('app.jobs.dispatch.httpx.post', Mock(side_effect=RuntimeError('secret-provider-token')))
    signup(client, 'trigger@example.com')
    with Session(test_engine) as db:
        assert len(db.exec(select(EmailDelivery)).all()) == 1
    assert 'mail_trigger_failed' in caplog.text and 'secret-provider-token' not in caplog.text


def test_maintenance_deletes_only_expired_guest_data(client, scheduled):
    checks = [client.post('/triage/start', json={'symptom_tag': 'vomiting'}).json() for _ in range(2)]
    with Session(test_engine) as db:
        access = db.get(GuestAccess, checks[0]['session_id']); access.expires_at = utcnow()-timedelta(seconds=1); db.add(access); db.commit()
    assert post_job(client, scheduled).json()['guest_checks'] == 1
    with Session(test_engine) as db:
        assert db.get(TriageSession, checks[0]['session_id']) is None
        assert db.get(TriageSession, checks[1]['session_id']) is not None


def test_scheduled_production_requires_delivery_and_scheduler_secrets():
    settings = production_settings(); settings.mail_backend = 'resend'; settings.deployment_mode = 'scheduled'
    with pytest.raises(RuntimeError): settings.validate_production()
    settings.resend_api_key = 'configured'; settings.qstash_token = 'configured'; settings.qstash_current_signing_key = 'configured'; settings.qstash_next_signing_key = 'configured'
    settings.validate_production()
    settings.qstash_url = 'https://attacker.example'
    with pytest.raises(RuntimeError): settings.validate_production()


def test_release_entrypoint_mounts_api_without_caching_or_spa_shadowing(client, monkeypatch, tmp_path):
    import server
    (tmp_path / 'index.html').write_text('<html>Release frontend</html>')
    monkeypatch.setattr(server, 'PUBLIC', tmp_path)
    with TestClient(server.app) as release:
        assert release.get('/api/health').json() == {'status': 'ok'}
        assert release.get('/api/auth/me').status_code == 401
        assert release.get('/api/auth/me').headers['cache-control'] == 'no-store'
        assert release.get('/api/unknown', headers={'Accept': 'text/html'}).status_code == 404
        assert release.get('/learn', headers={'Accept': 'text/html'}).text == '<html>Release frontend</html>'
        assert release.get('/missing.js').status_code == 404
        response = release.post('/api/auth/signup', json={'email': 'release@example.com', 'password': 'a-long-test-passphrase', 'privacy_policy_accepted': True})
        assert response.status_code == 200 and 'HttpOnly' in response.headers['set-cookie']
        assert release.get('/api/auth/me').status_code == 200
        assert release.post('/api/pets', json={'name': 'Rex', 'species': 'dog'}, headers={'Origin': 'https://attacker.example'}).status_code == 403


def test_forwarded_identity_is_trusted_only_on_vercel(monkeypatch):
    from starlette.requests import Request
    from app.services.rate_limit import client_identity
    scope = {'type': 'http', 'client': ('127.0.0.1', 1234), 'headers': [(b'x-vercel-forwarded-for', b'203.0.113.10')]}
    monkeypatch.delenv('VERCEL', raising=False)
    assert client_identity(Request(scope)) == '127.0.0.1'
    monkeypatch.setenv('VERCEL', '1')
    assert client_identity(Request(scope)) == '203.0.113.10'
    scope['headers'] = [(b'x-vercel-forwarded-for', b'bad-value')]
    assert client_identity(Request(scope)) == '127.0.0.1'


def test_wakeup_sends_only_job_kind_and_redacts_preview_bypass(monkeypatch):
    from app.jobs.dispatch import trigger_mail
    settings = get_settings()
    monkeypatch.setattr(settings, 'deployment_mode', 'scheduled')
    monkeypatch.setattr(settings, 'qstash_token', 'test-token')
    monkeypatch.setattr(settings, 'vercel_automation_bypass_secret', 'test-bypass')
    sender = Mock(return_value=httpx.Response(200, request=httpx.Request('POST', 'https://qstash-eu-central-1.upstash.io')))
    monkeypatch.setattr('app.jobs.dispatch.httpx.post', sender)
    trigger_mail()
    assert sender.call_args.kwargs['json'] == {'kind': 'mail'}
    assert sender.call_args.kwargs['headers']['Upstash-Forward-x-vercel-protection-bypass'] == 'test-bypass'
    assert sender.call_args.kwargs['headers']['Upstash-Redact-Fields'] == 'headers'


def test_mail_batch_leaves_overflow_for_scheduler_retry(client, scheduled):
    from app.models.schema import Owner
    from app.services.mail import queue_mail
    signup(client, 'batch@example.com')
    with Session(test_engine) as db:
        owner = db.exec(select(Owner)).one()
        for index in range(4):
            queue_mail(db, owner, f'Synthetic message {index}', 'Test only', utcnow()+timedelta(hours=1))
        db.commit()
    assert post_job(client, scheduled, 'mail').status_code == 503
    with Session(test_engine) as db:
        assert len(db.exec(select(EmailDelivery)).all()) == 2
    assert post_job(client, scheduled, 'mail').status_code == 200


def test_cloud_entrypoint_refuses_local_worker_configuration(client, monkeypatch):
    import server
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    with pytest.raises(RuntimeError, match='DEPLOYMENT_MODE=scheduled'):
        with TestClient(server.app):
            pass


def test_exhausted_mail_budget_keeps_queued_work(client):
    import time
    from app.services.mail import deliver_pending
    signup(client, 'budget@example.com')
    with Session(test_engine) as db:
        assert deliver_pending(db, limit=3, deadline=time.monotonic()-1) == 0
        assert len(db.exec(select(EmailDelivery)).all()) == 1


def test_schedule_plan_has_no_external_effects_and_apply_separates_sites(monkeypatch, capsys):
    import importlib.util
    from pathlib import Path
    import sys
    spec = importlib.util.spec_from_file_location('configure_jobs', Path('scripts/configure_jobs.py'))
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    settings = get_settings()
    for field, value in {'app_env': 'production', 'deployment_mode': 'scheduled', 'public_web_url': 'https://preview.example', 'vercel_automation_bypass_secret': 'private-test-bypass'}.items():
        monkeypatch.setattr(settings, field, value)
    monkeypatch.setattr(type(settings), 'validate_production', lambda self: None)
    sender = Mock(return_value=httpx.Response(200, request=httpx.Request('POST', 'https://qstash-eu-central-1.upstash.io')))
    monkeypatch.setattr(helper.httpx, 'post', sender)
    monkeypatch.setattr(sys, 'argv', ['configure_jobs'])
    helper.main(); sender.assert_not_called()
    assert 'private-test-bypass' not in capsys.readouterr().out
    monkeypatch.setattr(sys, 'argv', ['configure_jobs', '--apply'])
    helper.main()
    assert sender.call_count == 3  # Two schedules, then initial maintenance.
    preview_ids = [call.kwargs['headers']['Upstash-Schedule-Id'] for call in sender.call_args_list[:2]]
    assert sender.call_args.kwargs['json'] == {'kind': 'maintenance'}
    assert sender.call_args.kwargs['headers']['Upstash-Redact-Fields'] == 'headers'
    monkeypatch.setattr(settings, 'public_web_url', 'https://production.example')
    sender.reset_mock(); helper.main()
    production_ids = [call.kwargs['headers']['Upstash-Schedule-Id'] for call in sender.call_args_list[:2]]
    assert not set(preview_ids) & set(production_ids)
    assert 'private-test-bypass' not in capsys.readouterr().out
