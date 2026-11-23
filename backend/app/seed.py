"""Seed data.

    python -m app.seed            # tables + admin account + leave types
    python -m app.seed --demo     # also a demo department, schedule, camera and employee
"""
import sys
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_camera_key, hash_camera_key, hash_password
from app.database import SessionLocal, engine
from app.models import Base, Camera, Department, Employee, LeaveType, Schedule, ScheduleAssignment, ScheduleSession, User
from app.models.enums import CameraPurpose, Role
from app.utils.timeutils import local_date, now_utc

DEFAULT_LEAVE_TYPES = ["Casual Leave", "Sick Leave", "Annual Leave", "Other"]


def ensure_leave_types(db: Session) -> None:
    existing = {n for (n,) in db.execute(select(LeaveType.name))}
    for name in DEFAULT_LEAVE_TYPES:
        if name not in existing:
            db.add(LeaveType(name=name))
    db.commit()


def ensure_admin(db: Session) -> None:
    if db.scalar(select(User).where(User.email == settings.ADMIN_EMAIL.lower())):
        return
    db.add(User(email=settings.ADMIN_EMAIL.lower(), full_name=settings.ADMIN_NAME, password_hash=hash_password(settings.ADMIN_PASSWORD), role=Role.admin))
    db.commit()
    print(f"Created admin: {settings.ADMIN_EMAIL}  (change the password after first login)")


def create_demo(db: Session) -> None:
    dept = db.scalar(select(Department).where(Department.code == "ENG"))
    if not dept:
        dept = Department(code="ENG", name="Engineering", description="Demo department")
        db.add(dept)
        db.flush()
    cam = db.scalar(select(Camera).where(Camera.camera_code == "CAM-01"))
    if not cam:
        key = generate_camera_key()
        cam = Camera(camera_code="CAM-01", name="Main Entrance (webcam)", location="Main entrance", purpose=CameraPurpose.both,
                     source="webcam:0", api_key_hash=hash_camera_key(key))
        db.add(cam)
        db.flush()
        print(f"Created camera CAM-01. API key (shown once, put it in face_engine/.env): {key}")
    sched = db.scalar(select(Schedule).where(Schedule.name == "Day Shift"))
    if not sched:
        sched = Schedule(name="Day Shift", department_id=dept.id, working_days=[0, 1, 2, 3, 4], grace_minutes=20)
        sched.sessions = [
            ScheduleSession(name="Morning", start_time=time(9, 0), end_time=time(12, 0)),
            ScheduleSession(name="Afternoon", start_time=time(13, 0), end_time=time(17, 0)),
        ]
        sched.cameras = [cam]
        db.add(sched)
        db.flush()
    emp = db.scalar(select(Employee).where(Employee.employee_code == "EMP-001"))
    if not emp:
        emp = Employee(employee_code="EMP-001", full_name="Demo Employee", email="demo.employee@company.com", department_id=dept.id,
                       designation="Software Engineer", joining_date=local_date(now_utc()), face_consent=True, face_consent_at=now_utc())
        db.add(emp)
        db.flush()
        db.add(User(email="employee@company.com", full_name=emp.full_name, password_hash=hash_password("Employee@123"), role=Role.employee, employee_id=emp.id))
        db.add(ScheduleAssignment(schedule_id=sched.id, employee_id=emp.id, effective_from=local_date(now_utc())))
        print("Created demo employee EMP-001  (login employee@company.com / Employee@123)")
    db.commit()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        ensure_leave_types(session)
        ensure_admin(session)
        if "--demo" in sys.argv:
            create_demo(session)
    print("Seed complete.")
