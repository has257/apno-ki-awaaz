from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


TEST_JWT_SECRET = "test-jwt-secret-that-is-at-least-32-bytes-long"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.main.engine", None)
    monkeypatch.setattr("app.main.start_scheduler", lambda _service: None)
    monkeypatch.setattr("app.main.stop_scheduler", lambda: None)
    monkeypatch.setattr("app.config.settings.jwt_secret", TEST_JWT_SECRET)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def create_user(client: TestClient, name: str, phone: str, role: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": name,
            "phone_number": phone,
            "role": role,
            "password": "valid-test-password-123",
        },
    )
    assert response.status_code == 201
    result = response.json()
    user = result["user"]
    user["access_token"] = result["access_token"]
    return user


def headers(user: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['access_token']}"}


def approve_link(client: TestClient, family: dict, elderly: dict) -> None:
    requested = client.post(
        "/api/links/request",
        json={"elderly_user_id": elderly["id"]},
        headers=headers(family),
    )
    assert requested.status_code == 201
    approved = client.patch(
        f"/api/links/{requested.json()['id']}/approve",
        headers=headers(elderly),
    )
    assert approved.status_code == 200


def reminder_payload(elderly_user_id: int, created_by: int) -> dict:
    return {
        "title": "Evening medicine",
        "message": "Please take your medicine",
        "elderly_user_id": elderly_user_id,
        "scheduled_at": "2030-01-01T18:00:00+05:30",
        "recurrence": "DAILY",
    }


def test_user_apis_normalize_phone_and_reject_duplicates(client: TestClient) -> None:
    created = create_user(client, "Asha Rao", "+91 98765-43210", "FAMILY")

    duplicate = client.post(
        "/api/auth/register",
        json={
            "full_name": "Another Family Member",
            "phone_number": "+919876543210",
            "role": "FAMILY",
            "password": "valid-test-password-123",
        },
    )
    listed = client.get("/api/users", headers=headers(created))
    fetched = client.get(f"/api/users/{created['id']}", headers=headers(created))
    missing = client.get("/api/users/9999", headers=headers(created))

    assert created["phone_number"] == "+919876543210"
    assert duplicate.status_code == 409
    assert listed.status_code == 200 and len(listed.json()) == 1
    assert fetched.status_code == 200 and fetched.json()["id"] == created["id"]
    assert missing.status_code == 404


def test_reminder_role_validation_and_created_log(client: TestClient) -> None:
    family = create_user(client, "Family", "+919876543201", "FAMILY")
    elderly = create_user(client, "Elderly", "+919876543202", "ELDERLY")
    approve_link(client, family, elderly)

    created = client.post(
        "/api/reminders",
        json=reminder_payload(elderly["id"], family["id"]),
        headers=headers(family),
    )
    reminder = created.json()
    wrong_recipient = client.post(
        "/api/reminders",
        json=reminder_payload(family["id"], family["id"]),
        headers=headers(family),
    )
    wrong_creator = client.post(
        "/api/reminders",
        json={**reminder_payload(elderly["id"], family["id"]), "created_by": elderly["id"]},
        headers=headers(family),
    )
    filtered = client.get(
        "/api/reminders",
        params={"elderly_user_id": elderly["id"], "status": "PENDING"},
        headers=headers(family),
    )

    assert created.status_code == 201
    assert reminder["status"] == "PENDING"
    assert [log["event_type"] for log in reminder["logs"]] == ["CREATED"]
    assert wrong_recipient.status_code == 422
    assert wrong_creator.status_code == 422
    assert [item["id"] for item in filtered.json()] == [reminder["id"]]


def test_reminder_update_complete_and_cancel_preserve_logs(
    client: TestClient,
) -> None:
    family = create_user(client, "Family", "+919876543211", "FAMILY")
    elderly = create_user(client, "Elderly", "+919876543212", "ELDERLY")
    approve_link(client, family, elderly)
    created = client.post(
        "/api/reminders",
        json=reminder_payload(elderly["id"], family["id"]),
        headers=headers(family),
    ).json()

    update = client.put(
        f"/api/reminders/{created['id']}",
        json={
            "title": "Updated medicine",
            "message": "Take the updated dose",
            "elderly_user_id": elderly["id"],
            "scheduled_at": "2030-01-02T18:00:00+05:30",
            "recurrence": "WEEKLY",
        },
        headers=headers(family),
    )
    completed = client.patch(
        f"/api/reminders/{created['id']}/complete", headers=headers(elderly)
    )
    repeated_completion = client.patch(
        f"/api/reminders/{created['id']}/complete", headers=headers(elderly)
    )
    delete_completed = client.delete(
        f"/api/reminders/{created['id']}", headers=headers(family)
    )

    assert update.status_code == 200
    assert update.json()["title"] == "Updated medicine"
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    assert [log["event_type"] for log in completed.json()["logs"]] == [
        "CREATED",
        "COMPLETED",
    ]
    assert len(repeated_completion.json()["logs"]) == 2
    assert delete_completed.status_code == 409

    pending = client.post(
        "/api/reminders",
        json=reminder_payload(elderly["id"], family["id"]),
        headers=headers(family),
    ).json()
    cancelled = client.delete(
        f"/api/reminders/{pending['id']}", headers=headers(family)
    )
    fetched_cancelled = client.get(
        f"/api/reminders/{pending['id']}", headers=headers(elderly)
    )

    assert cancelled.status_code == 204
    assert fetched_cancelled.json()["status"] == "CANCELLED"
    assert [log["event_type"] for log in fetched_cancelled.json()["logs"]] == [
        "CREATED"
    ]
    audio_metadata = client.get(
        f"/api/reminders/{pending['id']}/audio", headers=headers(elderly)
    )
    assert audio_metadata.status_code == 200
    assert audio_metadata.json()["occurrences"] == []
    assert "audio_file_path" not in audio_metadata.text


def test_scheduler_status_endpoint(client: TestClient) -> None:
    user = create_user(client, "Family", "+919876543299", "FAMILY")
    response = client.get("/api/scheduler/status", headers=headers(user))

    assert response.status_code == 200
    assert response.json()["poll_interval_seconds"] == 15
    assert response.json()["max_attempts"] == 3