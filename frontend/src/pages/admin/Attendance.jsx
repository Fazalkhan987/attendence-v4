import { useState } from "react";
import { Alert, Badge, Empty, Field, Loading, Modal } from "../../components/ui";
import { errorMessage, get, patch, post } from "../../services/api";
import { addDays, fmtDate, fmtDateTime, fmtMinutes, fmtTime, fromLocalInput, hhmm, label, toLocalInput, todayStr } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

const STATUSES = ["present", "late", "absent", "on_leave", "half_day", "incomplete", "excused"];

export default function AttendancePage() {
  const [from, setFrom] = useState(addDays(todayStr(), -7));
  const [to, setTo] = useState(todayStr());
  const [dept, setDept] = useState("");
  const [emp, setEmp] = useState("");
  const [status, setStatus] = useState("");
  const params = { date_from: from, date_to: to, department_id: dept || undefined, employee_id: emp || undefined, status: status || undefined, limit: 1000 };
  const rows = useFetch(() => get("/attendance", params), [from, to, dept, emp, status], []);
  const depts = useFetch(() => get("/departments"), [], []);
  const emps = useFetch(() => get("/employees"), [], []);
  const [edit, setEdit] = useState(null);
  const [history, setHistory] = useState(null);
  const [manual, setManual] = useState(false);

  return (
    <>
      <div className="page-head">
        <div><h1>Attendance</h1><div className="muted">Automatic records from face recognition, with audited manual corrections</div></div>
        <button className="btn primary" onClick={() => setManual(true)}>+ Manual entry</button>
      </div>
      <div className="filters">
        <Field label="From"><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="To"><input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
        <Field label="Department"><select value={dept} onChange={(e) => setDept(e.target.value)}><option value="">All</option>{depts.data.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
        <Field label="Employee"><select value={emp} onChange={(e) => setEmp(e.target.value)}><option value="">All</option>{emps.data.map((x) => <option key={x.id} value={x.id}>{x.employee_code} – {x.full_name}</option>)}</select></Field>
        <Field label="Status"><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select></Field>
      </div>
      <Loading loading={rows.loading} error={rows.error}>
        {rows.data.length === 0 ? <Empty>No attendance records for these filters.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Employee</th><th>Session</th><th>In</th><th>Out</th><th>Worked</th><th>Status</th><th>Source</th><th /></tr></thead>
              <tbody>
                {rows.data.map((r) => (
                  <tr key={r.id}>
                    <td className="nowrap">{fmtDate(r.work_date)}</td>
                    <td>{r.employee_name}<div className="muted small">{r.employee_code} · {r.department_name}</div></td>
                    <td>{r.session_name}<div className="muted small">{hhmm(r.session_start)}–{hhmm(r.session_end)}</div></td>
                    <td>{fmtTime(r.check_in_time)}</td><td>{fmtTime(r.check_out_time)}{r.early_departure && <span className="muted small"> early</span>}</td>
                    <td>{fmtMinutes(r.working_minutes)}</td>
                    <td><Badge value={r.status} />{r.late_minutes > 0 && <span className="muted small"> +{r.late_minutes}m</span>}</td>
                    <td className="small muted">{label(r.source)}</td>
                    <td className="right nowrap">
                      <button className="btn sm" onClick={() => setEdit(r)}>Edit</button>{" "}
                      <button className="btn sm" onClick={() => setHistory(r)}>History</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loading>
      {edit && <EditModal row={edit} onClose={(changed) => { setEdit(null); if (changed) rows.reload(); }} />}
      {history && <HistoryModal row={history} onClose={() => setHistory(null)} />}
      {manual && <ManualModal emps={emps.data} onClose={(changed) => { setManual(false); if (changed) rows.reload(); }} />}
    </>
  );
}

function EditModal({ row, onClose }) {
  const [f, setF] = useState({ check_in: toLocalInput(row.check_in_time), check_out: toLocalInput(row.check_out_time), status: row.status, remarks: row.remarks || "", reason: "" });
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    const body = { status: f.status, remarks: f.remarks, reason: f.reason };
    if (f.check_in && f.check_in !== toLocalInput(row.check_in_time)) body.check_in_time = fromLocalInput(f.check_in);
    if (f.check_out && f.check_out !== toLocalInput(row.check_out_time)) body.check_out_time = fromLocalInput(f.check_out);
    if (!f.check_out && row.check_out_time) body.clear_check_out = true;
    try { await patch(`/attendance/${row.id}`, body); onClose(true); } catch (x) { setErr(errorMessage(x)); }
  };
  return (
    <Modal title={`Edit attendance – ${row.employee_name}`} onClose={() => onClose(false)}>
      <div className="muted small" style={{ marginBottom: 10 }}>{fmtDate(row.work_date)} · {row.session_name}. The previous values are kept in the correction history.</div>
      <form onSubmit={submit}>
        <Alert>{err}</Alert>
        <div className="form-grid">
          <Field label="Status"><select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>{STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select></Field>
          <Field label="Check-in"><input type="datetime-local" value={f.check_in} onChange={(e) => setF({ ...f, check_in: e.target.value })} /></Field>
          <Field label="Check-out"><input type="datetime-local" value={f.check_out} onChange={(e) => setF({ ...f, check_out: e.target.value })} /></Field>
          <Field label="Remarks"><input value={f.remarks} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></Field>
          <Field label="Reason for change (required)" full><textarea required minLength={3} rows={2} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field>
        </div>
        <div className="modal-foot"><button type="button" className="btn" onClick={() => onClose(false)}>Cancel</button><button className="btn primary">Save correction</button></div>
      </form>
    </Modal>
  );
}

function HistoryModal({ row, onClose }) {
  const { data, loading, error } = useFetch(() => get(`/attendance/${row.id}/corrections`), [], []);
  const show = (v) => (v ? `${label(v.status)} · in ${v.check_in_time ? fmtTime(v.check_in_time) : "—"} · out ${v.check_out_time ? fmtTime(v.check_out_time) : "—"}${v.remarks ? ` · ${v.remarks}` : ""}` : "(created)");
  return (
    <Modal title={`Correction history – ${row.employee_name}`} onClose={onClose} footer={<button className="btn" onClick={onClose}>Close</button>}>
      <Loading loading={loading} error={error}>
        {data.length === 0 ? <Empty>No manual changes. This record is exactly as the system produced it.</Empty> : data.map((c) => (
          <div className="card" key={c.id} style={{ padding: 12 }}>
            <div className="row between small"><strong>{c.corrected_by_name || "Unknown"}</strong><span className="muted">{fmtDateTime(c.created_at)}</span></div>
            <div className="small" style={{ marginTop: 6 }}><span className="muted">Before:</span> {show(c.old_values)}</div>
            <div className="small"><span className="muted">After:</span> {show(c.new_values)}</div>
            <div className="small" style={{ marginTop: 6 }}><span className="muted">Reason:</span> {c.reason}</div>
          </div>
        ))}
      </Loading>
    </Modal>
  );
}

function ManualModal({ emps, onClose }) {
  const [f, setF] = useState({ employee_id: "", session_id: "", work_date: todayStr(), status: "present", check_in: "", check_out: "", remarks: "", reason: "" });
  const [sessions, setSessions] = useState([]);
  const [err, setErr] = useState("");

  const pickEmployee = async (id) => {
    setF((x) => ({ ...x, employee_id: id, session_id: "" }));
    setSessions([]);
    if (!id) return;
    try {
      const asg = await get("/schedules");
      const list = [];
      for (const s of asg) {
        const a = await get(`/schedules/${s.id}/assignments`);
        if (a.some((x) => x.employee_id === Number(id))) s.sessions.forEach((ss) => list.push({ id: ss.id, text: `${s.name} – ${ss.name} (${hhmm(ss.start_time)}–${hhmm(ss.end_time)})` }));
      }
      setSessions(list);
    } catch (x) { setErr(errorMessage(x)); }
  };

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      await post("/attendance/manual", {
        employee_id: Number(f.employee_id), session_id: Number(f.session_id), work_date: f.work_date, status: f.status,
        check_in_time: fromLocalInput(f.check_in), check_out_time: fromLocalInput(f.check_out), remarks: f.remarks || null, reason: f.reason,
      });
      onClose(true);
    } catch (x) { setErr(errorMessage(x)); }
  };

  return (
    <Modal title="Manual attendance entry" onClose={() => onClose(false)}>
      <form onSubmit={submit}>
        <Alert>{err}</Alert>
        <div className="form-grid">
          <Field label="Employee"><select required value={f.employee_id} onChange={(e) => pickEmployee(e.target.value)}><option value="">Select…</option>{emps.map((x) => <option key={x.id} value={x.id}>{x.employee_code} – {x.full_name}</option>)}</select></Field>
          <Field label="Session"><select required value={f.session_id} onChange={(e) => setF({ ...f, session_id: e.target.value })}><option value="">{f.employee_id ? (sessions.length ? "Select…" : "No schedule assigned") : "Pick an employee first"}</option>{sessions.map((s) => <option key={s.id} value={s.id}>{s.text}</option>)}</select></Field>
          <Field label="Date"><input type="date" required value={f.work_date} onChange={(e) => setF({ ...f, work_date: e.target.value })} /></Field>
          <Field label="Status"><select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>{STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select></Field>
          <Field label="Check-in"><input type="datetime-local" value={f.check_in} onChange={(e) => setF({ ...f, check_in: e.target.value })} /></Field>
          <Field label="Check-out"><input type="datetime-local" value={f.check_out} onChange={(e) => setF({ ...f, check_out: e.target.value })} /></Field>
          <Field label="Remarks" full><input value={f.remarks} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></Field>
          <Field label="Reason (required)" full><textarea required minLength={3} rows={2} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field>
        </div>
        <div className="modal-foot"><button type="button" className="btn" onClick={() => onClose(false)}>Cancel</button><button className="btn primary">Create record</button></div>
      </form>
    </Modal>
  );
}
