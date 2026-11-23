# Architecture

```
 Browser (React)  ──REST/JWT──▶  FastAPI backend  ──SQLAlchemy──▶  PostgreSQL
                                   ▲      │
        camera API key (REST)      │      └─ REST (service key) ─▶ Face engine service (enrollment only)
 Face engine (live loop) ──────────┘
   webcam / RTSP → detect → embed → match → confirm over N frames → POST /recognition/events
```

* The **browser** only talks to the backend. It never touches the database or the model.
* The **face engine** never writes attendance. It sends `{employee_id, camera_id, confidence, timestamp, event_id}` for
  *confirmed* sightings. The backend authenticates the camera (`X-Camera-Code` + `X-Camera-Key`), validates everything and decides.
* Enrollment: browser webcam → backend → face engine `/v1/embed` (quality checks) → backend encrypts embeddings (Fernet) and stores them.

## Backend decision pipeline (`services/attendance_service.py`)
1. Idempotency: same `event_id` → returns the earlier result (replay protection).
2. Timestamp must be ≤ 5 min old and not in the future; confidence ≥ threshold.
3. Employee exists, is `active`, has biometric consent; camera department matches.
4. Duplicate sighting inside 60 s on the same camera → `duplicate`.
5. Today's sessions from schedule assignments (working day, effective dates); camera must be assigned to the schedule.
6. Approved leave → On Leave rows, event ignored.
7. Check-out (exit/both cameras) if an open check-in exists and the time is inside the check-out window
   (or any time before it on a dedicated *exit* camera → early departure). Otherwise check-in if inside
   `[start − check-in-open, session end]`: Present up to start+grace, Late after.
8. Row lock on the employee + unique constraint `(employee_id, session_id, work_date)` prevent double check-ins.

The background finalizer (every 60 s) creates **Absent** only after `session end + verification minutes`, **On Leave** for approved
leave days, and **Incomplete** for sessions with a check-in but no check-out after the check-out window closes.

## Database
`users`, `employees`, `departments`, `face_embeddings` (encrypted), `cameras` (hashed API keys), `schedules`, `schedule_sessions`,
`schedule_cameras`, `schedule_assignments`, `recognition_events`, `attendance`, `attendance_corrections`, `leave_types`,
`leave_requests`, `audit_logs`. Notable constraints: unique attendance per employee/session/day, check-out ≥ check-in,
session end > start, leave end ≥ start, unique event ids.

## Privacy
Only encrypted 512-d embeddings are stored (no face images; only the chosen profile photo). Consent is required before enrollment;
withdrawing it erases embeddings. Embeddings are decrypted only to serve the camera-authenticated gallery endpoint. Recognition
events are purged after `RECOGNITION_RETENTION_DAYS` (default 90).

## Known limits
* Liveness checks are heuristics (see `face_engine/liveness.py`); add a trained anti-spoof model for production.
* Login throttling is in-memory per process (use Redis behind several workers).
* Tables are created with `create_all`; add Alembic migrations before changing the schema on real data.
* Serve everything over HTTPS in production and set `ENVIRONMENT=production`.
