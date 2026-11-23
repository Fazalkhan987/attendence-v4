from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Employee, FaceEmbedding


def face_counts(db: Session, employee_ids: list[int] | None = None) -> dict[int, int]:
    stmt = select(FaceEmbedding.employee_id, func.count(FaceEmbedding.id)).where(FaceEmbedding.is_active.is_(True))
    if employee_ids is not None:
        stmt = stmt.where(FaceEmbedding.employee_id.in_(employee_ids))
    return dict(db.execute(stmt.group_by(FaceEmbedding.employee_id)).all())


def employee_query():
    return select(Employee).options(
        selectinload(Employee.department), selectinload(Employee.supervisor), selectinload(Employee.user)
    )


def employee_out(e: Employee, counts: dict[int, int]) -> dict:
    return {
        "id": e.id,
        "employee_code": e.employee_code,
        "full_name": e.full_name,
        "email": e.email,
        "phone": e.phone,
        "address": e.address,
        "has_photo": bool(e.photo_path),
        "department_id": e.department_id,
        "department_name": e.department.name if e.department else "",
        "designation": e.designation,
        "joining_date": e.joining_date,
        "employment_status": e.employment_status,
        "supervisor_id": e.supervisor_id,
        "supervisor_name": e.supervisor.full_name if e.supervisor else None,
        "face_consent": e.face_consent,
        "face_consent_at": e.face_consent_at,
        "face_samples": counts.get(e.id, 0),
        "has_account": e.user is not None,
        "login_email": e.user.email if e.user else None,
        "account_active": e.user.is_active if e.user else None,
    }


def get_employee_or_404(db: Session, employee_id: int) -> Employee:
    e = db.scalar(employee_query().where(Employee.id == employee_id))
    if not e:
        raise HTTPException(404, "Employee not found")
    return e
