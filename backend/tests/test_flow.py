"""End-to-end smoke test of the backend rules (runs on SQLite, no face engine needed).

    cd backend && pytest -q
"""
import os
import uuid
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_attendance.db"
os.environ["ENABLE_BACKGROUND_JOBS"] = "false"
os.environ.setdefault("BIOMETRIC_ENCRYPTION_KEY", "zJZruMBIE1RUlPApiLkeszezJ2SEntFudM5RiThyyo8=")

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.main import app
from app.models import Base
from app.seed import ensure_admin, ensure_leave_types
from app.services import face_service
from app.services.attendance_service import finalize_attendance
from app.utils.timeutils import LOCAL_TZ, now_utc, to_local

PREFIX = "/api/v1"


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_leave_types(db)
        ensure_admin(db)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test_attendance.db"):
        os.remove("test_attendance.db")


def _login(c, email, password):
    r = c.post(f"{PREFIX}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _event(c, cam_headers, code, cam_code, ts, conf=0.9, event_id=None):
    body = {"employee_id": code, "camera_id": cam_code, "confidence": conf, "timestamp": ts.isoformat(), "event_id": event_id or str(uuid.uuid4())}
    return c.post(f"{PREFIX}/recognition/events", json=body, headers=cam_headers)


def test_full_flow(client, monkeypatch):
    c = client
    now = now_utc()
    local_now = to_local(now)
    if local_now.hour in (0, 23):
        pytest.skip("too close to midnight for window-based test")

    admin = _login(c, "admin@company.com", "Admin@12345")
    assert c.get(f"{PREFIX}/employees").status_code == 401
    assert c.get(f"{PREFIX}/employees", headers=admin).status_code == 200
    assert c.post(f"{PREFIX}/auth/login", json={"email": "admin@company.com", "password": "bad"}).status_code == 401

    dept = c.post(f"{PREFIX}/departments", json={"code": "ENG", "name": "Engineering"}, headers=admin).json()
    cam = c.post(f"{PREFIX}/cameras", json={"camera_code": "CAM-01", "name": "Door", "purpose": "both"}, headers=admin).json()
    cam_h = {"X-Camera-Code": "CAM-01", "X-Camera-Key": cam["api_key"]}
    assert c.post(f"{PREFIX}/recognition/events", json={}, headers={"X-Camera-Code": "CAM-01", "X-Camera-Key": "wrong"}).status_code == 401

    # schedule: session started 5 minutes ago (inside grace), ends in 3 hours
    start = (local_now - timedelta(minutes=5)).replace(second=0, microsecond=0)
    end = start + timedelta(hours=3)
    sched = c.post(
        f"{PREFIX}/schedules",
        json={
            "name": "Test shift", "department_id": dept["id"], "working_days": list(range(7)), "grace_minutes": 20,
            "camera_ids": [cam["id"]],
            "sessions": [{"name": "Main", "start_time": start.strftime("%H:%M:%S"), "end_time": end.strftime("%H:%M:%S")}],
        },
        headers=admin,
    )
    assert sched.status_code == 201, sched.text
    sched = sched.json()

    emp = c.post(
        f"{PREFIX}/employees",
        json={
            "employee_code": "EMP-001", "full_name": "Ayesha Khan", "email": "ayesha@company.com", "department_id": dept["id"],
            "designation": "Engineer", "joining_date": "2026-01-01", "face_consent": True,
            "account": {"login_email": "ayesha.login@company.com", "password": "Passw0rd!x"},
        },
        headers=admin,
    )
    assert emp.status_code == 201, emp.text
    emp = emp.json()
    a = c.post(f"{PREFIX}/schedules/{sched['id']}/assignments", json={"employee_ids": [emp["id"]], "effective_from": "2026-01-01"}, headers=admin)
    assert a.status_code == 201, a.text

    # --- enrollment (face engine mocked)
    rng = np.random.default_rng(1)
    vecs = [rng.normal(size=512).tolist() for _ in range(4)]
    monkeypatch.setattr(
        face_service, "request_embeddings",
        lambda imgs: [{"ok": True, "embedding": vecs[i % 4], "quality": 0.9} for i in range(len(imgs))],
    )
    r = c.post(f"{PREFIX}/employees/{emp['id']}/face/enroll", json={"images": ["aGVsbG8="] * 4}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] == 4
    g = c.get(f"{PREFIX}/recognition/gallery", headers=cam_h).json()
    assert g["employees"][0]["employee_id"] == "EMP-001" and len(g["employees"][0]["embeddings"]) == 4
    assert c.get(f"{PREFIX}/recognition/gallery?since_version={g['version']}", headers=cam_h).json()["unchanged"] is True

    # --- check-in (within grace => present)
    r = _event(c, cam_h, "EMP-001", "CAM-01", now).json()
    assert r["outcome"] == "accepted" and r["action"] == "check_in", r
    # replay of the same event id
    eid = str(uuid.uuid4())
    _event(c, cam_h, "EMP-001", "CAM-01", now, event_id=eid)
    assert _event(c, cam_h, "EMP-001", "CAM-01", now, event_id=eid).json()["reason"] == "replayed_event"
    # duplicate sighting right after
    r = _event(c, cam_h, "EMP-001", "CAM-01", now + timedelta(seconds=5)).json()
    assert r["outcome"] in ("duplicate", "ignored"), r
    # validation failures
    assert _event(c, cam_h, "EMP-999", "CAM-01", now).json()["reason"] == "unknown_employee"
    assert _event(c, cam_h, "EMP-001", "CAM-01", now, conf=0.2).json()["reason"] == "low_confidence"
    assert _event(c, cam_h, "EMP-001", "CAM-01", now - timedelta(hours=2)).json()["reason"] == "stale_timestamp"
    assert c.post(f"{PREFIX}/recognition/events", json={"employee_id": "EMP-001", "camera_id": "CAM-02", "confidence": 0.9, "timestamp": now.isoformat()}, headers=cam_h).status_code == 403

    # employee view
    emp_h = _login(c, "ayesha.login@company.com", "Passw0rd!x")
    att = c.get(f"{PREFIX}/me/attendance", headers=emp_h).json()
    assert len(att) == 1 and att[0]["status"] == "present" and att[0]["check_in_time"]
    assert c.get(f"{PREFIX}/employees", headers=emp_h).status_code == 403
    assert c.get(f"{PREFIX}/attendance", headers=emp_h).status_code == 403

    # --- manual correction with audit trail
    att_id = att[0]["id"]
    r = c.patch(f"{PREFIX}/attendance/{att_id}", json={"status": "excused", "reason": "Approved by manager"}, headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "excused" and r.json()["source"] == "manual"
    corr = c.get(f"{PREFIX}/attendance/{att_id}/corrections", headers=admin).json()
    assert corr[0]["old_values"]["status"] == "present" and corr[0]["new_values"]["status"] == "excused"
    assert c.patch(f"{PREFIX}/attendance/{att_id}", json={"status": "present"}, headers=admin).status_code == 422  # reason required

    # --- leave: one request per day, approval marks On Leave
    tomorrow = (local_now + timedelta(days=1)).date()
    types = c.get(f"{PREFIX}/me/leave-types", headers=emp_h).json()
    lv = c.post(f"{PREFIX}/me/leave", json={"leave_type_id": types[0]["id"], "start_date": str(tomorrow), "end_date": str(tomorrow)}, headers=emp_h)
    assert lv.status_code == 201, lv.text
    assert c.post(f"{PREFIX}/me/leave", json={"leave_type_id": types[0]["id"], "start_date": str(tomorrow), "end_date": str(tomorrow)}, headers=emp_h).status_code == 409
    d = c.post(f"{PREFIX}/leave/{lv.json()['id']}/decision", json={"decision": "approved"}, headers=admin)
    assert d.status_code == 200 and d.json()["status"] == "approved"

    # --- summary / csv / dashboard
    today = str(local_now.date())
    assert c.get(f"{PREFIX}/reports/attendance-summary?date_from={today}&date_to={today}", headers=admin).status_code == 200
    csv = c.get(f"{PREFIX}/reports/attendance.csv?date_from={today}&date_to={today}", headers=admin)
    assert csv.status_code == 200 and "EMP-001" in csv.text
    dash = c.get(f"{PREFIX}/reports/dashboard", headers=admin).json()
    assert dash["active_employees"] == 1

    # --- finalizer: after the verification period, no-shows become Absent, open sessions Incomplete
    stats = finalize_attendance(SessionLocal(), now=now + timedelta(days=0, hours=3, minutes=45))
    # past days in the lookback window with no recognition become Absent; today's manual record is untouched
    assert stats["absent"] >= 1
    todays = c.get(f"{PREFIX}/attendance?date_from={today}&date_to={today}", headers=admin).json()
    assert len(todays) == 1 and todays[0]["status"] == "excused"
    absent = c.get(f"{PREFIX}/me/attendance?date_to={today}", headers=emp_h).json()
    assert any(r["status"] == "absent" for r in absent)
    audit = c.get(f"{PREFIX}/audit-logs?action=attendance_corrected", headers=admin).json()
    assert audit and audit[0]["details"]["reason"] == "Approved by manager"


def test_late_checkout_and_half_day(client, monkeypatch):
    from app.core.config import settings

    c = client
    now = now_utc()
    local_now = to_local(now)
    if local_now.hour in (0, 23):
        pytest.skip("too close to midnight for window-based test")
    monkeypatch.setattr(settings, "MIN_CHECKOUT_AFTER_CHECKIN_MINUTES", 0)
    admin = _login(c, "admin@company.com", "Admin@12345")
    dept = c.post(f"{PREFIX}/departments", json={"code": "OPS", "name": "Operations"}, headers=admin).json()
    cam = c.post(f"{PREFIX}/cameras", json={"camera_code": "CAM-02", "name": "Gate", "purpose": "both"}, headers=admin).json()
    cam_h = {"X-Camera-Code": "CAM-02", "X-Camera-Key": cam["api_key"]}
    start = (local_now - timedelta(minutes=40)).replace(second=0, microsecond=0)
    end = (local_now + timedelta(minutes=10)).replace(second=0, microsecond=0)
    sched = c.post(
        f"{PREFIX}/schedules",
        json={"name": "Late shift", "department_id": dept["id"], "working_days": list(range(7)), "grace_minutes": 20,
              "sessions": [{"name": "S1", "start_time": start.strftime("%H:%M:%S"), "end_time": end.strftime("%H:%M:%S")}]},
        headers=admin,
    ).json()
    emp = c.post(
        f"{PREFIX}/employees",
        json={"employee_code": "EMP-002", "full_name": "Bilal Ahmed", "email": "bilal@company.com", "department_id": dept["id"],
              "designation": "Analyst", "joining_date": "2026-01-01", "face_consent": True},
        headers=admin,
    ).json()
    c.post(f"{PREFIX}/schedules/{sched['id']}/assignments", json={"employee_ids": [emp["id"]], "effective_from": "2026-01-01"}, headers=admin)

    r = _event(c, cam_h, "EMP-002", "CAM-02", now - timedelta(seconds=120)).json()
    assert r["action"] == "check_in", r
    rows = c.get(f"{PREFIX}/attendance?employee_id={emp['id']}&date_from={local_now.date()}&date_to={local_now.date()}", headers=admin).json()
    assert rows[0]["status"] == "late" and rows[0]["late_minutes"] >= 35

    r = _event(c, cam_h, "EMP-002", "CAM-02", now).json()
    assert r["action"] == "check_out", r
    rows = c.get(f"{PREFIX}/attendance?employee_id={emp['id']}&date_from={local_now.date()}&date_to={local_now.date()}", headers=admin).json()
    assert rows[0]["check_out_time"] and rows[0]["status"] == "half_day"
    # a third sighting does nothing
    assert _event(c, cam_h, "EMP-002", "CAM-02", now + timedelta(seconds=10)).json()["outcome"] in ("ignored", "duplicate")
