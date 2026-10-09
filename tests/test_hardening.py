import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from sqlmodel import Session, select

from tests.test_auth import client, reset_db, signup, test_engine  # noqa: F401
from app.jobs.cleanup import cleanup
from app.models.schema import AccountAction, AuthSession, EmailDelivery, GuestAccess, Owner, Pet, TriageSession
from app.services.auth import utcnow
from app.services.mail import deliver_pending, mail_cipher
from app.settings import Settings, get_settings


def action_token(kind):
    with Session(test_engine) as db:
        mails = db.exec(select(EmailDelivery).order_by(EmailDelivery.created_at)).all()
        for mail in reversed(mails):
            payload = json.loads(mail_cipher().decrypt(mail.encrypted_payload.encode()))
            for line in payload['body'].splitlines():
                if '#action=' in line:
                    values = parse_qs(urlparse(line).fragment)
                    if values['action'] == [kind]:
                        return values['token'][0]
    raise AssertionError('No queued action link')


def test_logout_revokes_copied_bearer(client):
    headers = signup(client, 'revoke@example.com')
    assert client.post('/auth/logout', headers=headers).status_code == 200
    assert client.get('/auth/me', headers=headers).status_code == 401


def test_logout_all_revokes_other_device(client):
    original = signup(client, 'devices@example.com')
    second = client.post('/auth/login', json={'email': 'devices@example.com', 'password': 'a-long-test-passphrase'}).json()['access_token']
    assert client.post('/auth/logout-all', headers=original).status_code == 200
    assert client.get('/auth/me', headers={'Authorization': f'Bearer {second}'}).status_code == 401


def test_recovery_is_generic_single_use_and_revokes_sessions(client):
    headers = signup(client, 'recover@example.com')
    known = client.post('/auth/forgot-password', json={'email': 'recover@example.com'})
    unknown = client.post('/auth/forgot-password', json={'email': 'unknown@example.com'})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    token = action_token('reset')
    payload = {'token': token, 'password': 'a-new-long-test-passphrase'}
    assert client.post('/auth/reset-password', json=payload).status_code == 200
    assert client.get('/auth/me', headers=headers).status_code == 401
    assert client.post('/auth/reset-password', json=payload).status_code == 400
    assert client.post('/auth/login', json={'email': 'recover@example.com', 'password': 'a-long-test-passphrase'}).status_code == 401
    assert client.post('/auth/login', json={'email': 'recover@example.com', 'password': payload['password']}).status_code == 200


def test_reset_links_expire_and_resends_supersede_previous_links(client):
    signup(client, 'expire@example.com')
    client.post('/auth/forgot-password', json={'email': 'expire@example.com'})
    first = action_token('reset')
    client.post('/auth/forgot-password', json={'email': 'expire@example.com'})
    second = action_token('reset')
    assert first != second
    assert client.post('/auth/reset-password', json={'token': first, 'password': 'replacement-password-long'}).status_code == 400
    with Session(test_engine) as db:
        action = db.exec(select(AccountAction).where(AccountAction.kind == 'reset', AccountAction.used_at.is_(None))).one()
        action.expires_at = utcnow() - timedelta(seconds=1)
        db.add(action); db.commit()
    assert client.post('/auth/reset-password', json={'token': second, 'password': 'replacement-password-long'}).status_code == 400


def test_email_verification_gates_profiles_but_not_privacy_controls(client, monkeypatch):
    monkeypatch.setattr(get_settings(), 'require_email_verification', True)
    headers = signup(client, 'verify@example.com')
    assert client.get('/auth/me', headers=headers).json()['email_verification_required'] is True
    assert client.post('/pets', headers=headers, json={'name': 'Miso', 'species': 'cat'}).status_code == 403
    assert client.get('/auth/me/export', headers=headers).status_code == 200
    token = action_token('verify')
    assert client.post('/auth/verify-email', json={'token': token}).status_code == 200
    assert client.post('/auth/verify-email', json={'token': token}).status_code == 400
    assert client.post('/pets', headers=headers, json={'name': 'Miso', 'species': 'cat'}).status_code == 200


def test_sensitive_actions_require_recent_password(client):
    headers = signup(client, 'reauth@example.com')
    with Session(test_engine) as db:
        session = db.exec(select(AuthSession)).one()
        session.authenticated_at = utcnow() - timedelta(minutes=11)
        db.add(session); db.commit()
    assert client.get('/auth/me/export', headers=headers).status_code == 403
    assert client.delete('/auth/me', headers=headers).status_code == 403
    assert client.post('/auth/reauthenticate', headers=headers, json={'password': 'wrong'}).status_code == 403
    assert client.post('/auth/reauthenticate', headers=headers, json={'password': 'a-long-test-passphrase'}).status_code == 200
    assert client.get('/auth/me/export', headers=headers).status_code == 200


def test_mail_is_encrypted_and_worker_delivers_private_development_mail(client):
    signup(client, 'mail@example.com')
    token = action_token('verify')
    with Session(test_engine) as db:
        delivery = db.exec(select(EmailDelivery)).one()
        assert 'mail@example.com' not in delivery.encrypted_payload and token not in delivery.encrypted_payload
        assert deliver_pending(db) == 1
        assert db.exec(select(EmailDelivery)).all() == []
    from pathlib import Path
    files = list(Path(get_settings().mail_directory).glob('*.eml'))
    assert len(files) == 1 and files[0].stat().st_mode & 0o777 == 0o600
    assert 'mail@example.com' in files[0].read_text()


def test_account_deletion_removes_security_and_pending_mail(client):
    headers = signup(client, 'delete@example.com')
    client.post('/auth/forgot-password', json={'email': 'delete@example.com'})
    assert client.delete('/auth/me', headers=headers).status_code == 200
    with Session(test_engine) as db:
        for model in [Owner, AuthSession, AccountAction, EmailDelivery]:
            assert db.exec(select(model)).all() == []


def start_guest(client):
    check = client.post('/triage/start', json={'symptom_tag': 'vomiting'}).json()
    return check, {'X-Guest-Token': check['guest_token']}


def test_guest_checks_need_token_and_can_be_downloaded_and_deleted(client):
    check, headers = start_guest(client)
    endpoint = f"/triage/{check['session_id']}"
    assert client.get(endpoint + '/export').status_code == 404
    assert client.get(endpoint + '/export', headers={'X-Guest-Token': 'wrong'}).status_code == 404
    assert client.get(endpoint + '/export', headers=headers).status_code == 200
    assert client.delete(endpoint, headers=headers).status_code == 200
    assert client.get(endpoint + '/export', headers=headers).status_code == 404
    with Session(test_engine) as db:
        for model in [Pet, TriageSession, GuestAccess]:
            assert db.exec(select(model)).all() == []


def test_cleanup_dry_run_and_expiry_keep_account_data(client):
    headers = signup(client, 'retained@example.com')
    pet = client.post('/pets', json={'name': 'Rex', 'species': 'dog'}, headers=headers).json()
    saved = client.post('/triage/start', json={'pet_id': pet['id'], 'symptom_tag': 'vomiting'}, headers=headers).json()
    client.cookies.clear()
    guest, guest_headers = start_guest(client)
    with Session(test_engine) as db:
        access = db.get(GuestAccess, guest['session_id'])
        access.expires_at = utcnow() - timedelta(seconds=1)
        db.add(access); db.commit()
        assert cleanup(db)['guest_checks'] == 1
        assert db.get(TriageSession, guest['session_id']) is not None
        assert cleanup(db, apply=True)['guest_checks'] == 1
        assert db.get(TriageSession, guest['session_id']) is None
        assert db.get(TriageSession, saved['session_id']) is not None
        assert db.get(Pet, pet['id']) is not None
    assert client.get(f"/triage/{guest['session_id']}/export", headers=guest_headers).status_code == 404


def test_guest_expiry_denies_access_before_cleanup(client):
    guest, headers = start_guest(client)
    with Session(test_engine) as db:
        access = db.get(GuestAccess, guest['session_id'])
        access.expires_at = utcnow() - timedelta(seconds=1)
        db.add(access); db.commit()
    assert client.get(f"/triage/{guest['session_id']}/export", headers=headers).status_code == 404


def test_shared_protection_throttles_and_fails_closed(client, monkeypatch):
    from app.services.rate_limit import get_limiter
    for _ in range(10):
        response = client.post('/auth/login', json={'email': 'absent@example.com', 'password': 'wrong'})
        assert response.status_code == 401
    response = client.post('/auth/login', json={'email': 'absent@example.com', 'password': 'wrong'})
    assert response.status_code == 429 and 'retry-after' in response.headers
    monkeypatch.setattr(get_limiter().storage, 'incr', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('offline')))
    assert client.post('/triage/start', json={'symptom_tag': 'vomiting'}).status_code == 503


def test_logs_use_route_template_and_omit_private_identifiers(client, caplog):
    import logging
    caplog.set_level(logging.INFO, logger='petadvice.requests')
    guest, headers = start_guest(client)
    client.get(f"/triage/{guest['session_id']}/export?private=secret", headers=headers)
    logs = '\n'.join(record.message for record in caplog.records if record.name == 'petadvice.requests')
    assert guest['session_id'] not in logs and guest['guest_token'] not in logs and 'private=secret' not in logs
    assert '/triage/{session_id}/export' in logs


def test_draft_privacy_and_unknown_host(client):
    notice = client.get('/privacy').json()
    assert notice['status'] == 'draft' and notice['guest_retention_hours'] == 24
    assert client.get('/health', headers={'Host': 'attacker.example'}).status_code == 400


def production_settings(**overrides):
    from cryptography.fernet import Fernet
    return Settings(_env_file=None, app_env='production', jwt_secret_key='x' * 48, database_url='postgresql+psycopg://localhost/petadvice', rate_limit_storage_uri='rediss://localhost/0', cors_origins='https://petadvice.example', public_web_url='https://petadvice.example', trusted_hosts='petadvice.example', mail_backend='smtp', mail_encryption_key=Fernet.generate_key().decode(), smtp_host='smtp.example', smtp_from='privacy@petadvice.example', privacy_operator='Test operator', privacy_email='privacy@petadvice.example', privacy_policy_url='https://petadvice.example/privacy', **overrides)


def test_public_release_requires_complete_configuration():
    production_settings().validate_production()
    settings = production_settings()
    for field, invalid in [('database_url', 'sqlite:///prod.db'), ('rate_limit_storage_uri', 'memory://'), ('privacy_operator', ''), ('cors_origins', '*'), ('trusted_hosts', '*'), ('mail_backend', 'file')]:
        value = getattr(settings, field)
        setattr(settings, field, invalid)
        with pytest.raises(RuntimeError):
            settings.validate_production()
        setattr(settings, field, value)
    with pytest.raises(RuntimeError):
        Settings(_env_file=None, app_env='production').validate_production()


def test_readiness_requires_a_fresh_worker_heartbeat(client):
    from app.models.schema import MaintenanceStatus
    assert client.get('/ready').status_code == 503
    with Session(test_engine) as db:
        db.add(MaintenanceStatus(job='maintenance', last_success_at=utcnow()))
        db.commit()
    assert client.get('/ready').status_code == 200
    with Session(test_engine) as db:
        status = db.get(MaintenanceStatus, 'maintenance')
        status.last_success_at = utcnow() - timedelta(minutes=3)
        db.add(status); db.commit()
    assert client.get('/ready').status_code == 503


def test_superseded_links_are_not_delivered(client):
    signup(client, 'superseded@example.com')
    client.post('/auth/forgot-password', json={'email': 'superseded@example.com'})
    client.post('/auth/forgot-password', json={'email': 'superseded@example.com'})
    with Session(test_engine) as db:
        assert len(db.exec(select(EmailDelivery)).all()) == 3
        assert deliver_pending(db) == 2  # Verification and the latest reset only.
        assert db.exec(select(EmailDelivery)).all() == []
