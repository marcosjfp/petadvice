"""Opt-in HTTP smoke tests for an isolated local deployment; synthetic data only."""
import os
import uuid

import httpx
import pytest

BASE = os.getenv('TEST_APP_URL')
pytestmark = pytest.mark.skipif(not BASE, reason='Set TEST_APP_URL for a disposable local deployment smoke test')


def test_same_origin_guest_flow():
    with httpx.Client(base_url=BASE, timeout=10) as client:
        assert client.get('/ready').status_code == 200
        started = client.post('/triage/start', json={'symptom_tag': 'vomiting', 'species': 'dog'}).json()
        headers = {'X-Guest-Token': started['guest_token']}
        path = '/triage/' + started['session_id']
        try:
            assert client.get(path + '/export').status_code == 404
            first = started['next_question']
            next_question = client.post(path + '/answer', headers=headers, json={'question_id': first['id'], 'answer': 'Once'}).json()['next_question']
            answered = client.post(path + '/answer', headers=headers, json={'question_id': next_question['id'], 'answer': 'Yes'})
            assert answered.status_code == 200 and answered.json()['flow_complete']
            result = client.get(path + '/result', headers=headers)
            assert result.status_code == 200 and result.json()['resulting_urgency'] == 'emergency_now'
            assert result.headers['cache-control'] == 'no-store'
            assert client.get(path + '/export', headers=headers).status_code == 200
        finally:
            assert client.delete(path, headers=headers).status_code == 200
        assert client.get(path + '/export', headers=headers).status_code == 404


def test_same_origin_account_cookie_and_revocation():
    email = 'smoke-' + uuid.uuid4().hex + '@example.com'
    password = 'synthetic-smoke-test-passphrase'
    origin = str(httpx.URL(BASE).copy_with(path='', query=None, fragment=None)).rstrip('/')
    with httpx.Client(base_url=BASE, timeout=10, headers={'Origin': origin}) as client:
        signup = client.post('/auth/signup', json={'email': email, 'password': password, 'privacy_policy_accepted': True})
        assert signup.status_code == 200
        bearer = {'Authorization': 'Bearer ' + signup.json()['access_token']}
        try:
            assert 'HttpOnly' in signup.headers['set-cookie']
            assert client.get('/auth/me').status_code == 200
            pet = client.post('/pets', json={'name': 'Synthetic Rex', 'species': 'dog'})
            assert pet.status_code == 200
            export = client.get('/auth/me/export')
            assert export.status_code == 200 and len(export.json()['pets']) == 1
            assert 'hashed_password' not in export.json()['owner']
            assert client.post('/auth/logout').status_code == 200
            assert client.get('/auth/me', headers=bearer).status_code == 401
            login = client.post('/auth/login', json={'email': email, 'password': password})
            assert login.status_code == 200
            assert client.post('/auth/reauthenticate', json={'password': password}).status_code == 200
        finally:
            # This account was created solely for this test, and cannot contain user data.
            assert client.delete('/auth/me').status_code == 200
        assert client.get('/auth/me').status_code == 401
