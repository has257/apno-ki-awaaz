from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.enums import ReminderRecurrence, ReminderStatus, UserRole
from app.main import app
from app.models.family_elderly_link import FamilyElderlyLink
from app.models.reminder import Reminder
from app.models.reminder_occurrence import ReminderOccurrence
from app.models.user import User
from app.security import DUMMY_PASSWORD_HASH, password_hasher
from app.services import reminder_service


TEST_SECRET = "auth-tests-use-a-unique-secret-at-least-32-bytes"
TEST_PASSWORD = "test-password-long-enough-123"


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.main.engine", None)
    monkeypatch.setattr("app.main.start_scheduler", lambda _service: None)
    monkeypatch.setattr("app.main.stop_scheduler", lambda: None)
    monkeypatch.setattr(settings, "jwt_secret", TEST_SECRET)
    monkeypatch.setattr(reminder_service, "GENERATED_AUDIO_DIR", tmp_path / "generated_audio")
    try:
        with TestClient(app) as test_client:
            yield test_client, session
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def register(
    client: TestClient,
    *,
    name: str,
    phone: str,
    role: UserRole,
    password: str = TEST_PASSWORD,
) -> tuple[dict, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "phone_number": phone,
            "role": role.value,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return data["user"], data["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_approved_link(
    client: TestClient,
    family_token: str,
    elderly_token: str,
    elderly_id: int,
) -> int:
    response = client.post(
        "/api/links/request",
        json={"elderly_user_id": elderly_id},
        headers=bearer(family_token),
    )
    assert response.status_code == 201
    link_id = response.json()["id"]
    approved = client.patch(
        f"/api/links/{link_id}/approve",
        headers=bearer(elderly_token),
    )
    assert approved.status_code == 200
    return link_id


def reminder_payload(elderly_id: int) -> dict:
    return {
        "title": "Morning medicine",
        "message": "Take the morning medicine",
        "elderly_user_id": elderly_id,
        "scheduled_at": "2031-02-03T08:30:00+05:30",
        "recurrence": ReminderRecurrence.ONCE.value,
    }


def test_registration_login_and_me(client) -> None:
    http, session = client
    user, access_token = register(
        http,
        name="Family Account",
        phone="+919876500101",
        role=UserRole.FAMILY,
    )

    login = http.post(
        "/api/auth/login",
        json={"phone_number": "+91 98765-00101", "password": TEST_PASSWORD},
    )
    me = http.get("/api/auth/me", headers=bearer(access_token))
    stored = session.get(User, user["id"])

    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]
    assert "password_hash" not in login.text
    assert stored.password_hash.startswith("$argon2id$")
    assert TEST_PASSWORD not in stored.password_hash


def test_invalid_password_and_malformed_hash_fail_generically(client) -> None:
    http, session = client
    user, _ = register(
        http,
        name="Credentialed User",
        phone="+919876500104",
        role=UserRole.FAMILY,
    )

    invalid_password = http.post(
        "/api/auth/login",
        json={"phone_number": user["phone_number"], "password": "wrong-password"},
    )
    stored = session.get(User, user["id"])
    stored.password_hash = "not-an-argon2-hash"
    session.flush()
    invalid_hash = http.post(
        "/api/auth/login",
        json={"phone_number": user["phone_number"], "password": TEST_PASSWORD},
    )

    assert invalid_password.status_code == 401
    assert invalid_hash.status_code == 401
    assert invalid_password.json() == invalid_hash.json()
    assert invalid_password.json()["detail"] == "Invalid phone number or password"


def test_invalid_credentials_and_legacy_password_setup(client, monkeypatch) -> None:
    http, session = client
    legacy = User(
        full_name="Legacy User",
        phone_number="+919876500102",
        role=UserRole.ELDERLY,
        password_hash=None,
    )
    session.add(legacy)
    session.flush()
    user_id = legacy.id

    verified_hashes = []
    original_verify = PasswordHasher.verify

    def recording_verify(
        hasher: PasswordHasher,
        password_hash: str,
        password: str,
    ) -> bool:
        verified_hashes.append(password_hash)
        return original_verify(hasher, password_hash, password)

    monkeypatch.setattr(PasswordHasher, "verify", recording_verify)

    bad_login = http.post(
        "/api/auth/login",
        json={"phone_number": legacy.phone_number, "password": TEST_PASSWORD},
    )
    unknown_login = http.post(
        "/api/auth/login",
        json={"phone_number": "+919876509999", "password": TEST_PASSWORD},
    )
    setup_token = jwt.encode(
        {
            "sub": str(user_id),
            "iss": "apno-ki-awaaz",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
            "purpose": "password_setup",
        },
        TEST_SECRET,
        algorithm="HS256",
    )
    setup = http.post(
        "/api/auth/password/setup",
        json={"setup_token": setup_token, "new_password": TEST_PASSWORD},
    )
    replay = http.post(
        "/api/auth/password/setup",
        json={"setup_token": setup_token, "new_password": "another-password-123"},
    )

    assert bad_login.status_code == 401
    assert bad_login.json()["detail"] == "Invalid phone number or password"
    assert unknown_login.status_code == 401
    assert unknown_login.json() == bad_login.json()
    assert verified_hashes == [DUMMY_PASSWORD_HASH, DUMMY_PASSWORD_HASH]
    assert setup.status_code == 200
    assert replay.status_code == 409
    assert session.get(User, user_id).password_hash.startswith("$argon2id$")


def test_expired_invalid_and_missing_jwts_are_rejected(client) -> None:
    http, _ = client
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": "1",
            "iss": "apno-ki-awaaz",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "purpose": "access",
        },
        TEST_SECRET,
        algorithm="HS256",
    )
    wrong_signature = jwt.encode(
        {
            "sub": "1",
            "iss": "apno-ki-awaaz",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "purpose": "access",
        },
        "incorrect-signing-secret-that-is-long-enough",
        algorithm="HS256",
    )

    assert http.get("/api/auth/me").status_code == 401
    assert http.get("/api/auth/me", headers=bearer(expired)).status_code == 401
    assert http.get("/api/auth/me", headers=bearer(wrong_signature)).status_code == 401


def test_links_require_roles_consent_and_prevent_duplicates(client) -> None:
    http, _ = client
    family, family_token = register(
        http, name="Family", phone="+919876500111", role=UserRole.FAMILY
    )
    elderly, elderly_token = register(
        http, name="Elderly", phone="+919876500112", role=UserRole.ELDERLY
    )
    other_family, other_family_token = register(
        http, name="Other Family", phone="+919876500113", role=UserRole.FAMILY
    )

    request = http.post(
        "/api/links/request",
        json={"elderly_user_id": elderly["id"]},
        headers=bearer(family_token),
    )
    forged_requester = http.post(
        "/api/links/request",
        json={
            "elderly_user_id": elderly["id"],
            "family_user_id": other_family["id"],
        },
        headers=bearer(family_token),
    )
    duplicate = http.post(
        "/api/links/request",
        json={"elderly_user_id": elderly["id"]},
        headers=bearer(family_token),
    )
    family_approval = http.patch(
        f"/api/links/{request.json()['id']}/approve",
        headers=bearer(family_token),
    )
    wrong_target = http.patch(
        f"/api/links/{request.json()['id']}/approve",
        headers=bearer(other_family_token),
    )
    received = http.get("/api/links/received", headers=bearer(elderly_token))
    sent = http.get("/api/links/sent", headers=bearer(family_token))
    self_link = http.post(
        "/api/links/request",
        json={"elderly_user_id": family["id"]},
        headers=bearer(family_token),
    )
    wrong_target_role = http.post(
        "/api/links/request",
        json={"elderly_user_id": other_family["id"]},
        headers=bearer(family_token),
    )

    assert request.status_code == 201
    assert forged_requester.status_code == 422
    assert duplicate.status_code == 409
    assert family_approval.status_code == 403
    assert wrong_target.status_code == 403
    assert received.json()[0]["id"] == request.json()["id"]
    assert sent.json()[0]["id"] == request.json()["id"]
    assert "phone_number" not in request.text
    assert self_link.status_code == 422
    assert wrong_target_role.status_code == 422


def test_rejection_revocation_and_immediate_reminder_access_changes(client) -> None:
    http, session = client
    family, family_token = register(
        http, name="Family", phone="+919876500121", role=UserRole.FAMILY
    )
    elderly, elderly_token = register(
        http, name="Elderly", phone="+919876500122", role=UserRole.ELDERLY
    )
    other_elderly, other_elderly_token = register(
        http, name="Other Elderly", phone="+919876500123", role=UserRole.ELDERLY
    )
    rejected = http.post(
        "/api/links/request",
        json={"elderly_user_id": elderly["id"]},
        headers=bearer(family_token),
    ).json()
    reject_response = http.patch(
        f"/api/links/{rejected['id']}/reject", headers=bearer(elderly_token)
    )
    blocked_before_approval = http.post(
        "/api/reminders",
        json=reminder_payload(elderly["id"]),
        headers=bearer(family_token),
    )

    approved_link_id = http.post(
        "/api/links/request",
        json={"elderly_user_id": elderly["id"]},
        headers=bearer(family_token),
    ).json()["id"]
    approved = http.patch(
        f"/api/links/{approved_link_id}/approve",
        headers=bearer(elderly_token),
    )
    created = http.post(
        "/api/reminders",
        json=reminder_payload(elderly["id"]),
        headers=bearer(family_token),
    )
    reminder_id = created.json()["id"]
    unauthorized_retarget = http.put(
        f"/api/reminders/{reminder_id}",
        json={
            "title": "Retargeted medicine",
            "message": "Must not be reassigned without consent",
            "elderly_user_id": other_elderly["id"],
            "scheduled_at": "2031-02-04T08:30:00+05:30",
            "recurrence": ReminderRecurrence.ONCE.value,
        },
        headers=bearer(family_token),
    )
    other_elderly_view = http.get(
        f"/api/reminders/{reminder_id}", headers=bearer(other_elderly_token)
    )
    elderly_view = http.get(
        f"/api/reminders/{reminder_id}", headers=bearer(elderly_token)
    )
    revoked = http.patch(
        f"/api/links/{approved_link_id}/revoke",
        headers=bearer(elderly_token),
    )
    family_view_after_revoke = http.get(
        f"/api/reminders/{reminder_id}", headers=bearer(family_token)
    )
    elderly_view_after_revoke = http.get(
        f"/api/reminders/{reminder_id}", headers=bearer(elderly_token)
    )
    family_cancel_after_revoke = http.delete(
        f"/api/reminders/{reminder_id}", headers=bearer(family_token)
    )

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "REJECTED"
    assert blocked_before_approval.status_code == 403
    assert approved.status_code == 200
    assert created.status_code == 201
    assert unauthorized_retarget.status_code == 403
    assert other_elderly_view.status_code == 404
    assert elderly_view.status_code == 200
    assert revoked.status_code == 200 and revoked.json()["status"] == "REVOKED"
    assert family_view_after_revoke.status_code == 404
    assert elderly_view_after_revoke.status_code == 200
    assert family_cancel_after_revoke.status_code == 404
    assert session.get(Reminder, reminder_id).status == ReminderStatus.PENDING


def test_audio_retrieval_permissions_missing_files_and_path_traversal(client, tmp_path) -> None:
    http, session = client
    family, family_token = register(
        http, name="Family", phone="+919876500131", role=UserRole.FAMILY
    )
    elderly, elderly_token = register(
        http, name="Elderly", phone="+919876500132", role=UserRole.ELDERLY
    )
    stranger, stranger_token = register(
        http, name="Stranger", phone="+919876500133", role=UserRole.ELDERLY
    )
    create_approved_link(http, family_token, elderly_token, elderly["id"])
    created = http.post(
        "/api/reminders",
        json=reminder_payload(elderly["id"]),
        headers=bearer(family_token),
    ).json()
    reminder = session.get(Reminder, created["id"])
    occurrence = ReminderOccurrence(
        reminder_id=reminder.id,
        occurrence_at=reminder.scheduled_at,
        status=ReminderStatus.AUDIO_READY,
        attempt_count=1,
        audio_file_path="generated_audio/test-audio.wav",
        generated_at=datetime.now(timezone.utc),
    )
    session.add(occurrence)
    session.flush()
    audio_root = tmp_path / "generated_audio"
    audio_root.mkdir()
    expected_audio = audio_root / "test-audio.wav"
    expected_audio.write_bytes(b"RIFF\x04\x00\x00\x00WAVE")
    outside_audio = tmp_path / "outside.wav"
    outside_audio.write_bytes(b"RIFF\x04\x00\x00\x00WAVE")

    elderly_audio = http.get(
        f"/api/reminders/{reminder.id}/audio/content",
        headers=bearer(elderly_token),
    )
    family_audio = http.get(
        f"/api/reminders/{reminder.id}/audio/content",
        headers=bearer(family_token),
    )
    unauthorized_audio = http.get(
        f"/api/reminders/{reminder.id}/audio/content",
        headers=bearer(stranger_token),
    )
    assert elderly_audio.status_code == 200
    assert elderly_audio.headers["content-type"] == "audio/wav"
    assert elderly_audio.content == expected_audio.read_bytes()
    assert family_audio.status_code == 200
    assert unauthorized_audio.status_code == 404

    occurrence.audio_file_path = "generated_audio/../outside.wav"
    session.flush()
    traversal = http.get(
        f"/api/reminders/{reminder.id}/audio/content",
        headers=bearer(elderly_token),
    )
    assert traversal.status_code == 404
    assert outside_audio.exists()

    occurrence.audio_file_path = "generated_audio/missing.wav"
    session.flush()
    missing_file = http.get(
        f"/api/reminders/{reminder.id}/audio/content",
        headers=bearer(elderly_token),
    )
    assert missing_file.status_code == 404