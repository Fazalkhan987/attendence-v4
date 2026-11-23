from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.security import hash_password
from app.database import get_db
from app.models import Attendance, Department, Employee, FaceEmbedding, User
from app.models.enums import EmploymentStatus, Role
from app.schemas.organization import (
    AccountIn,
    AccountUpdate,
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    EnrollRequest,
    EnrollResult,
)
from app.services import employee_service as es
from app.services.audit_service import log_action
from app.services.face_service import enroll_employee, photo_dir
from app.utils.timeutils import now_utc

router = APIRouter(prefix="/employees", tags=["employees"])


def _check_refs(db: Session, department_id: int | None, supervisor_id: int | None, self_id: int | None = None):
    if department_id is not None and not db.get(Department, department_id):
        raise HTTPException(400, "Department does not exist")
    if supervisor_id is not None:
        if supervisor_id == self_id:
            raise HTTPException(400, "An employee cannot supervise themselves")
        if not db.get(Employee, supervisor_id):
            raise HTTPException(400, "Supervisor does not exist")


def _dup_error():
    return HTTPException(409, "Employee ID, employee email or login email already exists")


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    q: str | None = None,
    department_id: int | None = None,
    status: EmploymentStatus | None = None,
    limit: int = Query(500, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = es.employee_query()
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Employee.full_name).like(like), func.lower(Employee.employee_code).like(like), func.lower(Employee.email).like(like)))
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if status:
        stmt = stmt.where(Employee.employment_status == status)
    emps = db.scalars(stmt.order_by(Employee.employee_code).limit(limit).offset(offset)).all()
    counts = es.face_counts(db)
    return [es.employee_out(e, counts) for e in emps]


@router.post("", response_model=EmployeeOut, status_code=201)
def create_employee(body: EmployeeCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _check_refs(db, body.department_id, body.supervisor_id)
    data = body.model_dump(exclude={"account"})
    data["email"] = data["email"].lower()
    emp = Employee(**data)
    if body.face_consent:
        emp.face_consent_at = now_utc()
    db.add(emp)
    try:
        db.flush()
        if body.account:
            db.add(
                User(
                    email=body.account.login_email.lower(),
                    full_name=emp.full_name,
                    password_hash=hash_password(body.account.password),
                    role=Role.employee,
                    is_active=body.account.is_active,
                    employee_id=emp.id,
                )
            )
            db.flush()
    except IntegrityError:
        db.rollback()
        raise _dup_error()
    log_action(db, admin, "employee_created", "employee", emp.id, {"employee_code": emp.employee_code}, request)
    db.commit()
    return es.employee_out(es.get_employee_or_404(db, emp.id), {})


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    e = es.get_employee_or_404(db, employee_id)
    return es.employee_out(e, es.face_counts(db, [e.id]))


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: int, body: EmployeeUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    e = es.get_employee_or_404(db, employee_id)
    changes = body.model_dump(exclude_unset=True)
    _check_refs(db, changes.get("department_id"), changes.get("supervisor_id"), e.id)
    if "email" in changes and changes["email"]:
        changes["email"] = changes["email"].lower()
    if "face_consent" in changes and changes["face_consent"] != e.face_consent:
        e.face_consent_at = now_utc() if changes["face_consent"] else None
        if not changes["face_consent"]:  # withdrawing consent erases biometric data
            db.execute(delete(FaceEmbedding).where(FaceEmbedding.employee_id == e.id))
            log_action(db, admin, "biometric_data_erased", "employee", e.id, {"reason": "consent_withdrawn"}, request)
    for k, v in changes.items():
        setattr(e, k, v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _dup_error()
    log_action(db, admin, "employee_updated", "employee", e.id, {"fields": list(changes.keys())}, request)
    db.commit()
    return es.employee_out(es.get_employee_or_404(db, e.id), es.face_counts(db, [e.id]))


@router.delete("/{employee_id}")
def delete_employee(employee_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    e = es.get_employee_or_404(db, employee_id)
    has_history = db.scalar(select(func.count(Attendance.id)).where(Attendance.employee_id == e.id)) or 0
    if has_history:
        e.employment_status = EmploymentStatus.terminated
        db.execute(delete(FaceEmbedding).where(FaceEmbedding.employee_id == e.id))
        if e.user:
            e.user.is_active = False
        log_action(db, admin, "employee_terminated", "employee", e.id, {"reason": "has attendance history"}, request)
        db.commit()
        return {"detail": "Employee has attendance history: marked as terminated, face data erased, login disabled", "deleted": False}
    if e.user:
        db.delete(e.user)
    log_action(db, admin, "employee_deleted", "employee", e.id, {"employee_code": e.employee_code}, request)
    db.delete(e)
    db.commit()
    return {"detail": "Employee deleted", "deleted": True}


# ---------------- account ----------------
@router.put("/{employee_id}/account", response_model=EmployeeOut)
def upsert_account(
    employee_id: int, body: AccountUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    e = es.get_employee_or_404(db, employee_id)
    if e.user is None:
        if not (body.login_email and body.password):
            raise HTTPException(400, "login_email and password are required to create the account")
        db.add(User(email=body.login_email.lower(), full_name=e.full_name, password_hash=hash_password(body.password),
                    role=Role.employee, is_active=body.is_active if body.is_active is not None else True, employee_id=e.id))
    else:
        if body.login_email:
            e.user.email = body.login_email.lower()
        if body.password:
            e.user.password_hash = hash_password(body.password)
        if body.is_active is not None:
            e.user.is_active = body.is_active
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _dup_error()
    log_action(db, admin, "employee_account_updated", "employee", e.id, {"fields": list(body.model_dump(exclude_none=True).keys())}, request)
    db.commit()
    return es.employee_out(es.get_employee_or_404(db, e.id), es.face_counts(db, [e.id]))


# ---------------- face enrollment ----------------
@router.post("/{employee_id}/face/enroll", response_model=EnrollResult)
def enroll_face(
    employee_id: int, body: EnrollRequest, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    e = es.get_employee_or_404(db, employee_id)
    result = enroll_employee(db, e, body.images, body.replace_existing, body.set_profile_photo)
    log_action(db, admin, "face_enrolled", "employee", e.id, {"samples": result["accepted"]}, request)
    db.commit()
    return result


@router.delete("/{employee_id}/face")
def delete_face_data(employee_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    e = es.get_employee_or_404(db, employee_id)
    db.execute(delete(FaceEmbedding).where(FaceEmbedding.employee_id == e.id))
    log_action(db, admin, "biometric_data_erased", "employee", e.id, None, request)
    db.commit()
    return {"detail": "Face data erased"}


# ---------------- photo ----------------
@router.get("/{employee_id}/photo")
def get_photo(employee_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != Role.admin and user.employee_id != employee_id:
        raise HTTPException(403, "Not allowed")
    e = db.get(Employee, employee_id)
    if not e or not e.photo_path:
        raise HTTPException(404, "No photo")
    path = Path(photo_dir()) / Path(e.photo_path).name
    if not path.exists():
        raise HTTPException(404, "No photo")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})
