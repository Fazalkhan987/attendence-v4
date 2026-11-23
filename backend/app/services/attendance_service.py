"""Attendance decision engine.

The face engine only reports *who was seen where and when*. Everything below - schedules, windows,
leave, late/present, duplicate handling, check-in vs check-out - is decided here, in the backend.
"""
import hashlib
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Attendance,
    AttendanceCorrection,
    Camera,
    Employee,
    RecognitionEvent,
    Schedule,
    ScheduleAssignment,
    ScheduleSession,
    User,
)
from app.models.enums import (
    AttendanceSource,
    AttendanceStatus,
    CameraPurpose,
    EmploymentStatus,
    EventOutcome,
)
from app.schemas.recognition import RecognitionEventIn
from app.services.leave_service import approved_leave_exists, ensure_on_leave_rows
from app.services.schedule_service import sessions_for
from app.utils.timeutils import at_local, ensure_utc, local_date, minutes_between, now_utc, to_local


# ----------------------------------------------------------------------------
# Recognition events -> attendance
# ----------------------------------------------------------------------------
def _event_uid(p: RecognitionEventIn) -> str:
    if p.event_id:
        return p.event_id
    raw = f"{p.employee_id}|{p.camera_id}|{ensure_utc(p.timestamp).isoformat()}"
    return "auto-" + hashlib.sha256(raw.encode()).hexdigest()[:40]


def _reject(ev: RecognitionEvent, reason: str, outcome: EventOutcome = EventOutcome.rejected) -> None:
    ev.outcome = outcome
    ev.reason = reason


def process_recognition_event(db: Session, camera: Camera, p: RecognitionEventIn) -> tuple[RecognitionEvent, bool]:
    """Returns (event, replayed). `replayed` is True when the same event_id was already processed."""
    uid = _event_uid(p)
    existing = db.scalar(select(RecognitionEvent).where(RecognitionEvent.event_id == uid))
    if existing:
        return existing, True

    ts = ensure_utc(p.timestamp)
    ev = RecognitionEvent(
        event_id=uid,
        employee_code=p.employee_id,
        camera_id=camera.id,
        camera_code=camera.camera_code,
        confidence=p.confidence,
        event_timestamp=ts,
        outcome=EventOutcome.rejected,
    )
    try:
        with db.begin_nested():
            db.add(ev)
            db.flush()
    except IntegrityError:  # concurrent replay
        db.rollback()
        existing = db.scalar(select(RecognitionEvent).where(RecognitionEvent.event_id == uid))
        return existing, True

    camera.last_seen_at = now_utc()
    _decide(db, camera, ev, ts)
    db.commit()
    return ev, False


def _decide(db: Session, camera: Camera, ev: RecognitionEvent, ts: datetime) -> None:
    now = now_utc()
    age = (now - ts).total_seconds()
    if age > settings.EVENT_MAX_AGE_SECONDS:
        return _reject(ev, "stale_timestamp")
    if age < -settings.EVENT_MAX_FUTURE_SECONDS:
        return _reject(ev, "timestamp_in_future")
    if ev.confidence < settings.RECOGNITION_MIN_CONFIDENCE:
        return _reject(ev, "low_confidence")

    # Row lock serialises concurrent events of the same employee (no double check-ins).
    emp = db.scalar(select(Employee).where(Employee.employee_code == ev.employee_code).with_for_update())
    if emp is None:
        return _reject(ev, "unknown_employee")
    ev.employee_id = emp.id
    if emp.employment_status != EmploymentStatus.active:
        return _reject(ev, "employee_not_active")
    if not emp.face_consent:
        return _reject(ev, "no_biometric_consent")
    if camera.department_id and camera.department_id != emp.department_id:
        return _reject(ev, "camera_department_mismatch")

    window = timedelta(seconds=settings.DUPLICATE_EVENT_WINDOW_SECONDS)
    dup = db.scalar(
        select(func.count(RecognitionEvent.id)).where(
            RecognitionEvent.employee_id == emp.id,
            RecognitionEvent.camera_id == camera.id,
            RecognitionEvent.outcome == EventOutcome.accepted,
            RecognitionEvent.event_timestamp >= ts - window,
            RecognitionEvent.event_timestamp <= ts + window,
            RecognitionEvent.id != ev.id,
        )
    )
    if dup:
        return _reject(ev, "duplicate_within_window", EventOutcome.duplicate)

    d = local_date(ts)
    pairs = sessions_for(db, emp.id, d)
    if not pairs:
        return _reject(ev, "no_schedule_today", EventOutcome.ignored)
    pairs = [(s, ss) for s, ss in pairs if not s.cameras or camera.id in {c.id for c in s.cameras}]
    if not pairs:
        return _reject(ev, "camera_not_assigned_to_schedule", EventOutcome.ignored)
    if approved_leave_exists(db, emp.id, d):
        ensure_on_leave_rows(db, emp.id, d)
        return _reject(ev, "employee_on_approved_leave", EventOutcome.ignored)

    rows = {
        a.session_id: a
        for a in db.scalars(
            select(Attendance).where(
                Attendance.employee_id == emp.id,
                Attendance.work_date == d,
                Attendance.session_id.in_([ss.id for _, ss in pairs]),
            )
        )
    }
    min_gap = timedelta(minutes=settings.MIN_CHECKOUT_AFTER_CHECKIN_MINUTES)

    # ---- 1. check-out (only on exit / both cameras)
    if camera.purpose in (CameraPurpose.exit, CameraPurpose.both):
        for sched, sess in pairs:
            att = rows.get(sess.id)
            if not att or att.check_in_time is None or att.check_out_time is not None:
                continue
            if ts - att.check_in_time < min_gap:
                continue
            end = at_local(d, sess.end_time)
            w_open = end - timedelta(minutes=sched.checkout_open_minutes)
            w_close = end + timedelta(minutes=sched.checkout_close_minutes)
            if w_open <= ts <= w_close:
                return _do_checkout(db, ev, att, sess, ts, early=False)
            if camera.purpose == CameraPurpose.exit and ts < w_open:
                return _do_checkout(db, ev, att, sess, ts, early=True)

    # ---- 2. check-in (only on entry / both cameras)
    if camera.purpose in (CameraPurpose.entry, CameraPurpose.both):
        for sched, sess in pairs:
            if rows.get(sess.id) is not None:
                continue
            start = at_local(d, sess.start_time)
            end = at_local(d, sess.end_time)
            if start - timedelta(minutes=sched.checkin_open_minutes) <= ts <= end:
                return _do_checkin(db, ev, emp, sched, sess, d, ts, start)

    # ---- nothing to do
    if any(a.check_in_time for a in rows.values()):
        return _reject(ev, "already_recorded", EventOutcome.ignored)
    if camera.purpose == CameraPurpose.exit:
        return _reject(ev, "no_open_attendance_for_exit_camera", EventOutcome.ignored)
    return _reject(ev, "outside_attendance_window", EventOutcome.ignored)


def _do_checkin(db, ev, emp, sched: Schedule, sess: ScheduleSession, d: date, ts: datetime, start: datetime) -> None:
    grace_end = start + timedelta(minutes=sched.grace_minutes)
    is_late = ts > grace_end
    att = Attendance(
        employee_id=emp.id,
        schedule_id=sched.id,
        session_id=sess.id,
        work_date=d,
        check_in_time=ts,
        status=AttendanceStatus.late if is_late else AttendanceStatus.present,
        late_minutes=max(0, minutes_between(start, ts)) if is_late else 0,
        source=AttendanceSource.auto,
    )
    try:
        with db.begin_nested():
            db.add(att)
            db.flush()
    except IntegrityError:
        return _reject(ev, "attendance_already_exists", EventOutcome.duplicate)
    ev.outcome = EventOutcome.accepted
    ev.action = "check_in"
    ev.reason = None
    ev.attendance_id = att.id


def _do_checkout(db, ev, att: Attendance, sess: ScheduleSession, ts: datetime, early: bool) -> None:
    att.check_out_time = ts
    att.early_departure = early
    att.working_minutes = minutes_between(att.check_in_time, ts)
    session_len = minutes_between(at_local(att.work_date, sess.start_time), at_local(att.work_date, sess.end_time))
    if session_len > 0 and att.working_minutes < settings.HALF_DAY_RATIO * session_len:
        att.status = AttendanceStatus.half_day
    ev.outcome = EventOutcome.accepted
    ev.action = "early_check_out" if early else "check_out"
    ev.reason = None
    ev.attendance_id = att.id


# ----------------------------------------------------------------------------
# Background finalisation (absent / incomplete / on-leave)
# ----------------------------------------------------------------------------
def finalize_attendance(db: Session, now: datetime | None = None) -> dict:
    now = now or now_utc()
    today = local_date(now)
    stats = {"absent": 0, "on_leave": 0, "incomplete": 0}

    for offset in range(settings.FINALIZER_LOOKBACK_DAYS, -1, -1):
        d = today - timedelta(days=offset)
        rows = db.execute(
            select(ScheduleAssignment, Schedule)
            .join(Schedule, Schedule.id == ScheduleAssignment.schedule_id)
            .where(
                Schedule.is_active.is_(True),
                ScheduleAssignment.effective_from <= d,
                (ScheduleAssignment.effective_to.is_(None)) | (ScheduleAssignment.effective_to >= d),
            )
        ).all()
        existing = {
            (a.employee_id, a.session_id): a for a in db.scalars(select(Attendance).where(Attendance.work_date == d))
        }
        for asg, sched in rows:
            if d.weekday() not in (sched.working_days or []):
                continue
            emp = db.get(Employee, asg.employee_id)
            if emp is None or emp.employment_status != EmploymentStatus.active:
                continue
            on_leave = approved_leave_exists(db, emp.id, d)
            for sess in sched.sessions:
                att = existing.get((emp.id, sess.id))
                end = at_local(d, sess.end_time)
                if att is None:
                    new_status = None
                    if on_leave:
                        new_status = AttendanceStatus.on_leave
                    elif now >= end + timedelta(minutes=sched.absent_verification_minutes):
                        new_status = AttendanceStatus.absent
                    if new_status is None:
                        continue
                    try:
                        with db.begin_nested():
                            a = Attendance(
                                employee_id=emp.id,
                                schedule_id=sched.id,
                                session_id=sess.id,
                                work_date=d,
                                status=new_status,
                                source=AttendanceSource.auto,
                                remarks="Approved leave" if on_leave else "No recognition during session",
                            )
                            db.add(a)
                            db.flush()
                        existing[(emp.id, sess.id)] = a
                        stats["on_leave" if on_leave else "absent"] += 1
                    except IntegrityError:
                        pass
                elif (
                    att.check_in_time
                    and att.check_out_time is None
                    and att.status in (AttendanceStatus.present, AttendanceStatus.late)
                    and att.source == AttendanceSource.auto
                    and now > end + timedelta(minutes=sched.checkout_close_minutes)
                ):
                    att.status = AttendanceStatus.incomplete
                    att.remarks = "No check-out recorded"
                    stats["incomplete"] += 1
    db.commit()
    return stats


# ----------------------------------------------------------------------------
# Presentation / manual corrections
# ----------------------------------------------------------------------------
def attendance_out(a: Attendance) -> dict:
    return {
        "id": a.id,
        "employee_id": a.employee_id,
        "employee_code": a.employee.employee_code,
        "employee_name": a.employee.full_name,
        "department_name": a.employee.department.name if a.employee.department else "",
        "schedule_name": a.schedule.name,
        "session_id": a.session_id,
        "session_name": a.session.name,
        "session_start": a.session.start_time,
        "session_end": a.session.end_time,
        "work_date": a.work_date,
        "check_in_time": a.check_in_time,
        "check_out_time": a.check_out_time,
        "status": a.status,
        "late_minutes": a.late_minutes,
        "working_minutes": a.working_minutes,
        "early_departure": a.early_departure,
        "source": a.source,
        "remarks": a.remarks,
    }


def snapshot(a: Attendance) -> dict:
    return {
        "check_in_time": a.check_in_time.isoformat() if a.check_in_time else None,
        "check_out_time": a.check_out_time.isoformat() if a.check_out_time else None,
        "status": a.status.value,
        "late_minutes": a.late_minutes,
        "working_minutes": a.working_minutes,
        "remarks": a.remarks,
    }


def recompute_duration(a: Attendance) -> None:
    if a.check_in_time and a.check_out_time:
        a.working_minutes = minutes_between(a.check_in_time, a.check_out_time)
    else:
        a.working_minutes = None


def apply_correction(db: Session, user: User, att: Attendance, changes: dict, reason: str) -> AttendanceCorrection:
    old = snapshot(att)
    if "check_in_time" in changes and changes["check_in_time"] is not None:
        att.check_in_time = ensure_utc(changes["check_in_time"])
    if changes.get("clear_check_out"):
        att.check_out_time = None
    elif changes.get("check_out_time") is not None:
        att.check_out_time = ensure_utc(changes["check_out_time"])
    if att.check_in_time and att.check_out_time and att.check_out_time < att.check_in_time:
        raise ValueError("check_out_time cannot be before check_in_time")
    if changes.get("status") is not None:
        att.status = changes["status"]
    if changes.get("remarks") is not None:
        att.remarks = changes["remarks"]
    recompute_duration(att)
    if att.status in (AttendanceStatus.present, AttendanceStatus.late, AttendanceStatus.half_day) and att.check_in_time is None:
        raise ValueError("A check-in time is required for this status")
    att.source = AttendanceSource.manual
    corr = AttendanceCorrection(
        attendance_id=att.id,
        employee_id=att.employee_id,
        old_values=old,
        new_values=snapshot(att),
        reason=reason,
        corrected_by=user.id,
    )
    db.add(corr)
    return corr


def employee_sessions_pair(db: Session, employee_id: int, session_id: int) -> Schedule | None:
    """Schedule through which this employee is (or was) assigned to the session, if any."""
    return db.scalar(
        select(Schedule)
        .join(ScheduleSession, ScheduleSession.schedule_id == Schedule.id)
        .join(ScheduleAssignment, ScheduleAssignment.schedule_id == Schedule.id)
        .where(ScheduleSession.id == session_id, ScheduleAssignment.employee_id == employee_id)
        .limit(1)
    )


def format_local(dt: datetime | None) -> str:
    return to_local(dt).strftime("%Y-%m-%d %H:%M") if dt else ""
