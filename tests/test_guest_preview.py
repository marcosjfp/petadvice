"""The private preview cannot create accounts or use existing account sessions."""
import pytest
from sqlmodel import Session, select

from app.models.schema import AccountAction, EmailDelivery, Owner
from app.settings import get_settings
from tests.test_auth import client, reset_db, signup, test_engine  # noqa: F401
from tests.test_hardening import production_settings
from tests.test_serverless import post_job, scheduled  # noqa: F401


def test_guest_preview_blocks_accounts_and_ignores_existing_sessions(client, monkeypatch):
    headers = signup(client, 'preview@example.com')
    monkeypatch.setattr(get_settings(), 'guest_only_preview', True)
    for method, path in [('get', '/auth/me'), ('post', '/auth/login'),
                         ('post', '/auth/signup'), ('post', '/auth/forgot-password'),
                         ('get', '/pets'), ('post', '/pets')]:
        assert getattr(client, method)(path, headers=headers).status_code == 403
    assert client.get('/triage/history/unknown', headers=headers).status_code == 401
    started = client.post('/triage/start', headers=headers, json={'symptom_tag': 'vomiting'})
    assert started.status_code == 200
    check = started.json()
    assert check['guest_token']
    assert client.get(f"/triage/{check['session_id']}/result").status_code == 404
    while check['next_question']:
        question = check['next_question']
        answered = client.post(f"/triage/{started.json()['session_id']}/answer",
                               headers={'X-Guest-Token': started.json()['guest_token']},
                               json={'question_id': question['id'], 'answer': question['options'][0]})
        assert answered.status_code == 200
        check = answered.json()
    assert client.get(f"/triage/{started.json()['session_id']}/result",
                      headers={'X-Guest-Token': started.json()['guest_token']}).status_code == 200
    with Session(test_engine) as db:
        assert len(db.exec(select(Owner)).all()) == 1
        assert len(db.exec(select(EmailDelivery)).all()) == 1  # Only the pre-preview signup.


@pytest.mark.parametrize('mode', ['guest_only_preview', 'accounts_without_email_preview'])
def test_guest_preview_configuration_cannot_be_used_for_production_release(monkeypatch, mode):
    settings = production_settings(**{mode: True})
    for name in ['smtp_host', 'smtp_from', 'mail_encryption_key', 'privacy_operator',
                 'privacy_email', 'privacy_policy_url']:
        setattr(settings, name, '')
    settings.mail_backend = 'file'
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    settings.validate_production()
    monkeypatch.setenv('VERCEL_ENV', 'production')
    with pytest.raises(RuntimeError, match='restricted to Vercel preview'):
        settings.validate_production()
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    setattr(settings, mode, False)
    with pytest.raises(RuntimeError):
        settings.validate_production()


def test_guest_preview_keeps_signed_retention_but_rejects_email_jobs(client, scheduled, monkeypatch):
    monkeypatch.setattr(get_settings(), 'guest_only_preview', True)
    assert client.post('/jobs/run', json={'kind': 'maintenance'}).status_code == 401
    assert post_job(client, scheduled, 'mail').status_code == 403
    assert post_job(client, scheduled, 'maintenance').status_code == 200
    assert client.get('/ready').status_code == 200


@pytest.mark.parametrize('mode', ['accounts_without_email_preview', 'accounts_without_email_beta'])
def test_account_preview_supports_hashed_passwords_without_email_or_recovery(client, monkeypatch, mode):
    monkeypatch.setattr(get_settings(), mode, True)
    headers = signup(client, 'private-preview@example.com')
    assert client.get('/auth/me', headers=headers).json()['email_verification_required'] is False
    assert client.post('/pets', headers=headers, json={'name': 'Preview cat', 'species': 'cat'}).status_code == 200
    for path in ['forgot-password', 'reset-password', 'verify-email', 'resend-verification']:
        assert client.post('/auth/' + path, json={'email': 'private-preview@example.com'}).status_code == 403
    with Session(test_engine) as db:
        owner = db.exec(select(Owner)).one()
        assert owner.hashed_password.startswith('$argon2id$')
        assert owner.hashed_password != 'a-long-test-passphrase'
        assert owner.email_verified_at is None
        assert db.exec(select(EmailDelivery)).all() == []
        assert db.exec(select(AccountAction)).all() == []
    assert client.post('/auth/logout', headers=headers).status_code == 200
    assert client.get('/auth/me', headers=headers).status_code == 401
    assert client.post('/auth/login', json={'email': 'private-preview@example.com', 'password': 'a-long-test-passphrase'}).status_code == 200


def test_account_beta_requires_explicit_production_target_and_retains_security(monkeypatch):
    settings = production_settings(accounts_without_email_beta=True)
    settings.mail_backend = 'file'
    for name in ['smtp_host', 'smtp_from', 'mail_encryption_key', 'privacy_operator', 'privacy_email', 'privacy_policy_url']:
        setattr(settings, name, '')
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    with pytest.raises(RuntimeError, match='explicit Vercel production'):
        settings.validate_production()
    monkeypatch.setenv('VERCEL_ENV', 'production')
    settings.validate_production()
    assert settings.email_disabled and not settings.email_verification_required
    settings.rate_limit_storage_uri = 'memory://'
    with pytest.raises(RuntimeError, match='shared Redis'):
        settings.validate_production()
