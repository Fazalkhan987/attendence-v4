from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_admin
from app.database import get_db
from app.models import Attendance, Camera, Department, Employee, Schedule, ScheduleAssignment, ScheduleSession, User
from app.schemas.schedule import (
    AssignmentOut,
    AssignmentUpdate,
    AssignRequest,
    ScheduleCreate,
    ScheduleOut,
    ScheduleUpdate,
)
from app.services.audit_service import log_action
from app.services.schedule_service import check_assignment_conflict, load_schedule, schedule_to_out

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _assigned_counts(db: Session) -> dict[int, int]:
    return dict(
        db.execute(select(ScheduleAssignment.schedule_id, func.count(ScheduleAssignment.id)).group_by(ScheduleAssignment.schedule_id)).all()
    )


def _cameras(db: Session, ids: list[int]) -> list[Camera]:
    if not ids:
        return []
    cams = db.scalars(select(Camera).where(Camera.id.in_(ids))).all()
    if len(cams) != len(set(ids)):
        raise HTTPException(400, "One or more cameras do not exist")
    return list(cams)


@router.get("", response_model=list[ScheduleOut])
def list_schedules(department_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    stmt = select(Schedule).options(selectinload(Schedule.sessions), selectinload(Schedule.cameras), selectinload(Schedule.department))
    if department_id:
        stmt = stmt.where(Schedule.department_id == department_id)
    counts = _assigned_counts(db)
    return [schedule_to_out(s, counts.get(s.id, 0)) for s in db.scalars(stmt.order_by(Schedule.name))]


@router.post("", response_model=ScheduleOut, status_code=201)
def create_schedule(body: ScheduleCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if not db.get(Department, body.department_id):
        raise HTTPException(400, "Department does not exist")
    data = body.model_dump(exclude={"sessions", "camera_ids"})
    s = Schedule(**data)
    s.cameras = _cameras(db, body.camera_ids)
    s.sessions = [ScheduleSession(name=x.name, start_time=x.start_time, end_time=x.end_time) for x in body.sessions]
    db.add(s)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A schedule with this name already exists in the department")
    log_action(db, admin, "schedule_created", "schedule", s.id, {"name": s.name}, request)
    db.commit()
    return schedule_to_out(load_schedule(db, s.id))


@router.get("/{schedule_id}", response_model=ScheduleOut)
def get_schedule(schedule_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    s = load_schedule(db, schedule_id)
    return schedule_to_out(s, _assigned_counts(db).get(s.id, 0))


@router.put("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: int, body: ScheduleUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    s = load_schedule(db, schedule_id)
    if not db.get(Department, body.department_id):
        raise HTTPException(400, "Department does not exist")
    for k, v in body.model_dump(exclude={"sessions", "camera_ids"}).items():
        setattr(s, k, v)
    s.cameras = _cameras(db, body.camera_ids)

    existing = {x.id: x for x in s.sessions}
    keep_ids = {x.id for x in body.sessions if x.id}
    for sid in set(existing) - keep_ids:
        used = db.scalar(select(func.count(Attendance.id)).where(Attendance.session_id == sid)) or 0
        if used:
            raise HTTPException(409, f"Session '{existing[sid].name}' has attendance records and cannot be removed. Deactivate the schedule instead.")
        s.sessions.remove(existing[sid])
    for x in body.sessions:
        if x.id:
            if x.id not in existing:
                raise HTTPException(400, f"Unknown session id {x.id}")
            row = existing[x.id]
            row.name, row.start_time, row.end_time = x.name, x.start_time, x.end_time
        else:
            s.sessions.append(ScheduleSession(name=x.name, start_time=x.start_time, end_time=x.end_time))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A schedule with this name already exists in the department")
    log_action(db, admin, "schedule_updated", "schedule", s.id, {"name": s.name}, request)
    db.commit()
    return schedule_to_out(load_schedule(db, s.id), _assigned_counts(db).get(s.id, 0))


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    s = load_schedule(db, schedule_id)
    used = db.scalar(select(func.count(Attendance.id)).where(Attendance.schedule_id == s.id)) or 0
    if used:
        s.is_active = False
        log_action(db, admin, "schedule_deactivated", "schedule", s.id, None, request)
        db.commit()
        return {"detail": "Schedule has attendance history and was deactivated instead of deleted", "deleted": False}
    log_action(db, admin, "schedule_deleted", "schedule", s.id, {"name": s.name}, request)
    db.delete(s)
    db.commit()
    return {"detail": "Schedule deleted", "deleted": True}


# ---------------- assignments ----------------
def _asg_out(a: ScheduleAssignment) -> dict:
    return {
        "id": a.id,
        "schedule_id": a.schedule_id,
        "employee_id": a.employee_id,
        "employee_code": a.employee.employee_code,
        "employee_name": a.employee.full_name,
        "effective_from": a.effective_from,
        "effective_to": a.effective_to,
    }


@router.get("/{schedule_id}/assignments", response_model=list[AssignmentOut])
def list_assignments(schedule_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    load_schedule(db, schedule_id)
    rows = db.scalars(
        select(ScheduleAssignment)
        .where(ScheduleAssignment.schedule_id == schedule_id)
        .options(selectinload(ScheduleAssignment.employee))
        .order_by(ScheduleAssignment.id)
    ).all()
    return [_asg_out(a) for a in rows]


@router.post("/{schedule_id}/assignments", response_model=list[AssignmentOut], status_code=201)
def assign_employees(
    schedule_id: int, body: AssignRequest, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    s = load_schedule(db, schedule_id)
    created = []
    for emp_id in body.employee_ids:
        emp = db.get(Employee, emp_id)
        if not emp:
            raise HTTPException(404, f"Employee {emp_id} not found")
        check_assignment_conflict(db, s, emp, body.effective_from, body.effective_to)
        a = ScheduleAssignment(schedule_id=s.id, employee_id=emp.id, effective_from=body.effective_from, effective_to=body.effective_to)
        db.add(a)
        created.append(a)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An employee is already assigned with this start date")
    log_action(db, admin, "schedule_assigned", "schedule", s.id, {"employee_ids": body.employee_ids}, request)
    db.commit()
    for a in created:
        db.refresh(a)
    return [_asg_out(a) for a in created]


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int, body: AssignmentUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    a = db.get(ScheduleAssignment, assignment_id)
    if not a:
        raise HTTPException(404, "Assignment not found")
    if body.effective_to and body.effective_to < a.effective_from:
        raise HTTPException(400, "effective_to must not be before effective_from")
    a.effective_to = body.effective_to
    log_action(db, admin, "assignment_updated", "schedule_assignment", a.id, {"effective_to": str(body.effective_to)}, request)
    db.commit()
    return _asg_out(a)


@router.delete("/assignments/{assignment_id}")
def remove_assignment(assignment_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    a = db.get(ScheduleAssignment, assignment_id)
    if not a:
        raise HTTPException(404, "Assignment not found")
    log_action(db, admin, "assignment_removed", "schedule_assignment", a.id, {"employee_id": a.employee_id}, request)
    db.delete(a)
    db.commit()
    return {"detail": "Assignment removed"}
