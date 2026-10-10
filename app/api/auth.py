from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import get_session
from app.models.schema import AccountAction, ActionRequest, AuthSession, EmailDelivery, EmailRequest, GuestAccess, Owner, OwnerLogin, OwnerPublic, OwnerSignup, Pet, ReauthenticateRequest, ResetPasswordRequest, TokenResponse, TriageSession
from app.services.account_actions import consume_action, request_action
from app.services.auth import COOKIE_NAME, clear_session_cookie, find_session, get_current_owner, hash_password, issue_session, require_recent_owner, revoke_all_sessions, set_session_cookie, utcnow, verify_auth_origin, verify_dummy_password, verify_password
from app.services.mail import queue_mail
from app.jobs.dispatch import trigger_mail
from app.services.rate_limit import limit_requests
from app.settings import get_settings

router = APIRouter(prefix='/auth', tags=['auth'], dependencies=[Depends(verify_auth_origin)])
GENERIC_LINK_RESPONSE = {'message': 'If this address belongs to an eligible account, an email will arrive shortly.'}


@router.post('/signup', response_model=TokenResponse, dependencies=[Depends(limit_requests('signup', '10/hour'))])
def signup(payload: OwnerSignup, response: Response, db: Session = Depends(get_session)):
    if db.exec(select(Owner).where(Owner.email == payload.email)).first():
        raise HTTPException(400, 'An account with this email already exists')
    owner = Owner(email=payload.email, hashed_password=hash_password(payload.password), consent_given_at=utcnow(), consent_policy_version=get_settings().privacy_policy_version)
    db.add(owner)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(400, 'An account with this email already exists') from error
    db.refresh(owner)
    request_action(db, owner, 'verify')
    token = issue_session(db, owner)
    set_session_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post('/login', response_model=TokenResponse, dependencies=[Depends(limit_requests('login', '20/minute', '10/minute'))])
def login(payload: OwnerLogin, response: Response, db: Session = Depends(get_session)):
    owner = db.exec(select(Owner).where(Owner.email == payload.email).with_for_update()).first()
    if owner is None:
        verify_dummy_password(payload.password)
        raise HTTPException(401, 'Incorrect email or password')
    if not verify_password(payload.password, owner.hashed_password):
        raise HTTPException(401, 'Incorrect email or password')
    if owner.hashed_password.startswith(('$2a$', '$2b$', '$2y$')):
        owner.hashed_password = hash_password(payload.password)
        db.add(owner)
    token = issue_session(db, owner)
    set_session_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post('/logout')
def logout(request: Request, response: Response, db: Session = Depends(get_session)):
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else request.cookies.get(COOKIE_NAME)
    if token:
        try:
            session = find_session(db, token)
            session.revoked_at = utcnow()
            db.add(session)
            db.commit()
        except HTTPException:
            pass  # Logout also succeeds for an already expired browser cookie.
    clear_session_cookie(response)
    return {'status': 'logged out'}


@router.post('/logout-all')
def logout_all(response: Response, owner: Owner = Depends(require_recent_owner), db: Session = Depends(get_session)):
    revoke_all_sessions(db, owner.id)
    db.commit()
    clear_session_cookie(response)
    return {'status': 'all sessions revoked'}


@router.post('/reauthenticate', dependencies=[Depends(limit_requests('reauthenticate', '10/minute'))])
def reauthenticate(payload: ReauthenticateRequest, request: Request, owner: Owner = Depends(get_current_owner), db: Session = Depends(get_session)):
    if not verify_password(payload.password, owner.hashed_password):
        raise HTTPException(403, 'Incorrect password')
    session = request.state.auth_session
    session.authenticated_at = utcnow()
    db.add(session)
    db.commit()
    return {'status': 'password confirmed'}


@router.post('/forgot-password', status_code=202, dependencies=[Depends(limit_requests('recovery', '10/hour', '3/hour'))])
def forgot_password(payload: EmailRequest, db: Session = Depends(get_session)):
    verify_dummy_password('recovery-request')  # Both known and unknown accounts incur password-hash work.
    owner = db.exec(select(Owner).where(Owner.email == payload.email)).first()
    if owner:
        request_action(db, owner, 'reset')
    else:
        trigger_mail()
    return GENERIC_LINK_RESPONSE


@router.post('/resend-verification', status_code=202, dependencies=[Depends(limit_requests('verification-request', '10/hour', '3/hour'))])
def resend_verification(payload: EmailRequest, db: Session = Depends(get_session)):
    verify_dummy_password('verification-request')
    owner = db.exec(select(Owner).where(Owner.email == payload.email)).first()
    if owner and owner.email_verified_at is None:
        request_action(db, owner, 'verify')
    else:
        trigger_mail()
    return GENERIC_LINK_RESPONSE


@router.post('/verify-email', dependencies=[Depends(limit_requests('verify-email', '20/minute'))])
def verify_email(payload: ActionRequest, db: Session = Depends(get_session)):
    owner = consume_action(db, payload.token, 'verify')
    owner.email_verified_at = utcnow()
    db.add(owner)
    db.commit()
    return {'message': 'Email verified. You can now sign in and save your pet profiles.'}


@router.post('/reset-password', dependencies=[Depends(limit_requests('reset-password', '10/minute'))])
def reset_password(payload: ResetPasswordRequest, response: Response, db: Session = Depends(get_session)):
    new_hash = hash_password(payload.password)
    owner = consume_action(db, payload.token, 'reset')
    owner.hashed_password = new_hash
    db.add(owner)
    revoke_all_sessions(db, owner.id)
    for action in db.exec(select(AccountAction).where(AccountAction.owner_id == owner.id, AccountAction.kind == 'reset', AccountAction.used_at.is_(None))).all():
        action.used_at = utcnow()
        db.add(action)
    queue_mail(db, owner, 'Your PETAdvice password was changed', 'Your password was changed and all active sessions were signed out. If you did not make this change, request a new password reset immediately.', utcnow() + timedelta(hours=24))
    db.commit()
    trigger_mail()
    clear_session_cookie(response)
    return {'message': 'Password changed. Sign in with your new password.'}


@router.get('/me', response_model=OwnerPublic)
def read_current_owner(owner: Owner = Depends(get_current_owner)):
    return OwnerPublic(**owner.model_dump(), email_verification_required=get_settings().email_verification_required)


@router.get('/me/export')
def export_my_data(current_owner: Owner = Depends(require_recent_owner), db: Session = Depends(get_session)):
    pets = db.exec(select(Pet).where(Pet.owner_id == current_owner.id)).all()
    sessions = db.exec(select(TriageSession).where(TriageSession.pet_id.in_([pet.id for pet in pets]))).all() if pets else []
    return {'owner': current_owner.model_dump(exclude={'hashed_password'}), 'pets': [pet.model_dump() for pet in pets], 'triage_sessions': [session.model_dump() for session in sessions]}


@router.delete('/me')
def delete_my_account(response: Response, current_owner: Owner = Depends(require_recent_owner), db: Session = Depends(get_session)):
    for model in [EmailDelivery, AccountAction, AuthSession]:
        for record in db.exec(select(model).where(model.owner_id == current_owner.id)).all():
            db.delete(record)
    db.flush()
    for pet in db.exec(select(Pet).where(Pet.owner_id == current_owner.id)).all():
        for session in db.exec(select(TriageSession).where(TriageSession.pet_id == pet.id)).all():
            guest = db.get(GuestAccess, session.id)
            if guest:
                db.delete(guest)
                db.flush()
            db.delete(session)
        db.flush()
        db.delete(pet)
    db.flush()
    db.delete(current_owner)
    db.commit()
    clear_session_cookie(response)
    return {'status': 'account and all associated data deleted'}
