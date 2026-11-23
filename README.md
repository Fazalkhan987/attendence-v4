# Smart Employee Attendance Management System (Face Recognition)

FastAPI + PostgreSQL + React + InsightFace (ArcFace). Roles: **Administrator** (everything) and **Employee** (own attendance,
schedule, leave). Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
smart-attendance/
├── backend/       FastAPI app (api, models, schemas, services, core), tests, backup script
├── face_engine/   live recognition loop + enrollment service (independent of backend logic)
├── frontend/      React (Vite) admin and employee portals
└── docs/
```

## 1. Database

```bash
createdb smart_attendance        # or use pgAdmin; default URL: postgres:postgres@localhost:5432
```

## 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env     # (a development .env is already included) then edit DATABASE_URL and secrets
python -m app.seed --demo          # admin account, leave types, demo department/schedule/camera/employee
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```

Default admin: `admin@company.com` / `Admin@12345` (from `.env`; change it). `--demo` prints the demo camera API key once.
Run tests: `pytest -q` (uses SQLite, no face engine needed).

## 3. Frontend

```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

## 4. Face engine (needs Python 3.10+, a webcam, first run downloads the InsightFace model)

```bash
pip install -r face_engine/requirements.txt
cp face_engine/.env.example face_engine/.env   # set CAMERA_CODE/CAMERA_KEY and SERVICE_KEY
# from the project root (smart-attendance/):
python -m face_engine.service      # enrollment service on :8100 (backend calls it)
python -m face_engine.main         # live recognition loop (press q in the preview window to stop)
```

`SERVICE_KEY` (face_engine/.env) must equal `FACE_ENGINE_SERVICE_KEY` (backend/.env). For a CCTV camera set
`VIDEO_SOURCE=rtsp://user:pass@ip:554/stream`.

## First run walk-through

1. Sign in as admin → **Departments** → create one.
2. **Cameras** → new camera (`CAM-01`, purpose *Entry and exit* for a single webcam) → copy the API key into `face_engine/.env`.
3. **Schedules** → create sessions, grace period, working days, camera → *Assign employees* later.
4. **Employees** → register (tick biometric consent, create login) → **Face** → open camera → guided capture → Enroll.
5. Assign the employee to the schedule, start `face_engine.main`, look at the camera → check **Recognition events** and **Attendance**.
6. Sign in as the employee to see attendance, schedule and to request leave.

## Event API (face engine → backend)

`POST /api/v1/recognition/events` with headers `X-Camera-Code`, `X-Camera-Key`:

```json
{"employee_id": "EMP-001", "camera_id": "CAM-01", "confidence": 0.91, "timestamp": "2026-11-23T09:15:00+05:00", "event_id": "uuid"}
```

Naive timestamps are read as company time (`TIMEZONE`, default Asia/Karachi).

## Tuning

`SIMILARITY_THRESHOLD` (0.50 default for ArcFace cosine), `CONFIRM_FRAMES`, `EVENT_COOLDOWN_SECONDS` in `face_engine/.env`;
attendance windows per schedule in the UI; global limits in `backend/.env`.

## Backups

`backend/scripts/backup_db.sh` (pg_dump + rotation). Keep `BIOMETRIC_ENCRYPTION_KEY` safe: without it embeddings cannot be decrypted.
