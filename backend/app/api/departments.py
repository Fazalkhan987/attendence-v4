from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import Department, Employee, Schedule, User
from app.schemas.organization import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services.audit_service import log_action

router = APIRouter(prefix="/departments", tags=["departments"])


def _out(d: Department, count: int) -> dict:
    return {"id": d.id, "code": d.code, "name": d.name, "description": d.description, "is_active": d.is_active, "employee_count": count}


@router.get("", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    counts = dict(db.execute(select(Employee.department_id, func.count(Employee.id)).group_by(Employee.department_id)).all())
    return [_out(d, counts.get(d.id, 0)) for d in db.scalars(select(Department).order_by(Department.name))]


@router.post("", response_model=DepartmentOut, status_code=201)
def create_department(body: DepartmentCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    d = Department(**body.model_dump())
    db.add(d)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Department code or name already exists")
    log_action(db, admin, "department_created", "department", d.id, body.model_dump(), request)
    db.commit()
    return _out(d, 0)


@router.put("/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int, body: DepartmentUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    d = db.get(Department, department_id)
    if not d:
        raise HTTPException(404, "Department not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Department code or name already exists")
    log_action(db, admin, "department_updated", "department", d.id, body.model_dump(exclude_unset=True), request)
    db.commit()
    count = db.scalar(select(func.count(Employee.id)).where(Employee.department_id == d.id)) or 0
    return _out(d, count)


@router.delete("/{department_id}")
def delete_department(department_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Hard delete only when unused; otherwise the department is deactivated."""
    d = db.get(Department, department_id)
    if not d:
        raise HTTPException(404, "Department not found")
    in_use = db.scalar(select(func.count(Employee.id)).where(Employee.department_id == d.id)) or 0
    in_use += db.scalar(select(func.count(Schedule.id)).where(Schedule.department_id == d.id)) or 0
    if in_use:
        d.is_active = False
        log_action(db, admin, "department_deactivated", "department", d.id, None, request)
        db.commit()
        return {"detail": "Department is in use and was deactivated instead of deleted", "deleted": False}
    log_action(db, admin, "department_deleted", "department", d.id, {"name": d.name}, request)
    db.delete(d)
    db.commit()
    return {"detail": "Department deleted", "deleted": True}
