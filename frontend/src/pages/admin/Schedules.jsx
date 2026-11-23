import { useState } from "react";
import { Alert, Badge, Empty, Field, Loading, Modal } from "../../components/ui";
import { del, errorMessage, get, patch, post, put } from "../../services/api";
import { DAYS, fmtDate, hhmm, todayStr } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

const blank = () => ({
  name: "", department_id: "", working_days: [0, 1, 2, 3, 4], grace_minutes: 15, checkin_open_minutes: 30, checkout_open_minutes: 15,
  checkout_close_minutes: 120, absent_verification_minutes: 30, camera_ids: [], is_active: true,
  sessions: [{ name: "Session 1", start_time: "09:00", end_time: "17:00" }],
});

export default function Schedules() {
  const list = useFetch(() => get("/schedules"), [], []);
  const depts = useFetch(() => get("/departments"), [], []);
  const cams = useFetch(() => get("/cameras"), [], []);
  const [edit, setEdit] = useState(null);
  const [err, setErr] = useState("");
  const [assign, setAssign] = useState(null);

  const open = (s) => {
    setErr("");
    setEdit(s ? { ...s, sessions: s.sessions.map((x) => ({ ...x, start_time: hhmm(x.start_time), end_time: hhmm(x.end_time) })) } : blank());
  };
  const toggleDay = (i) => setEdit((e) => ({ ...e, working_days: e.working_days.includes(i) ? e.working_days.filter((d) => d !== i) : [...e.working_days, i].sort() }));
  const toggleCam = (id) => setEdit((e) => ({ ...e, camera_ids: e.camera_ids.includes(id) ? e.camera_ids.filter((c) => c !== id) : [...e.camera_ids, id] }));
  const setSession = (i, k, v) => setEdit((e) => ({ ...e, sessions: e.sessions.map((s, j) => (j === i ? { ...s, [k]: v } : s)) }));
  const num = (k) => (e) => setEdit({ ...edit, [k]: Number(e.target.value) });

  const save = async (ev) => {
    ev.preventDefault();
    setErr("");
    const body = {
      name: edit.name, department_id: Number(edit.department_id), working_days: edit.working_days, grace_minutes: edit.grace_minutes,
      checkin_open_minutes: edit.checkin_open_minutes, checkout_open_minutes: edit.checkout_open_minutes,
      checkout_close_minutes: edit.checkout_close_minutes, absent_verification_minutes: edit.absent_verification_minutes,
      camera_ids: edit.camera_ids, is_active: edit.is_active,
      sessions: edit.sessions.map((s) => ({ id: s.id || null, name: s.name, start_time: s.start_time.length === 5 ? `${s.start_time}:00` : s.start_time, end_time: s.end_time.length === 5 ? `${s.end_time}:00` : s.end_time })),
    };
    try {
      if (edit.id) await put(`/schedules/${edit.id}`, body); else await post("/schedules", body);
      setEdit(null);
      list.reload();
    } catch (x) { setErr(errorMessage(x)); }
  };

  const remove = async (s) => {
    if (!window.confirm(`Delete schedule "${s.name}"? Schedules with attendance history are deactivated instead.`)) return;
    try { await del(`/schedules/${s.id}`); list.reload(); } catch (x) { alert(errorMessage(x)); }
  };

  return (
    <>
      <div className="page-head">
        <div><h1>Schedules</h1><div className="muted">Working days, sessions, grace periods and cameras</div></div>
        <button className="btn primary" onClick={() => open(null)}>+ New schedule</button>
      </div>
      <Loading loading={list.loading} error={list.error}>
        {list.data.length === 0 ? <Empty>No schedules yet.</Empty> : (
          <div className="grid cols-2">
            {list.data.map((s) => (
              <div className="card" key={s.id} style={{ marginBottom: 0 }}>
                <div className="row between"><h3 style={{ margin: 0 }}>{s.name}</h3><Badge value={s.is_active ? "active" : "inactive"} /></div>
                <div className="muted small" style={{ margin: "4px 0 10px" }}>{s.department_name} · {s.assigned_count} assigned · grace {s.grace_minutes} min</div>
                <div className="chips" style={{ marginBottom: 10 }}>{DAYS.map((d, i) => <span key={d} className={`chip ${s.working_days.includes(i) ? "on" : ""}`} style={{ cursor: "default" }}>{d}</span>)}</div>
                {s.sessions.map((x) => <div key={x.id} className="row between small"><span>{x.name}</span><strong>{hhmm(x.start_time)} – {hhmm(x.end_time)}</strong></div>)}
                <div className="muted small" style={{ marginTop: 8 }}>Cameras: {s.camera_codes.join(", ") || "any"}</div>
                <div className="row" style={{ marginTop: 12 }}>
                  <button className="btn sm primary" onClick={() => setAssign(s)}>Assign employees</button>
                  <button className="btn sm" onClick={() => open(s)}>Edit</button>
                  <button className="btn sm danger" onClick={() => remove(s)}>Delete</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Loading>

      {edit && (
        <Modal title={edit.id ? "Edit schedule" : "New schedule"} wide onClose={() => setEdit(null)}>
          <form onSubmit={save}>
            <Alert>{err}</Alert>
            <div className="form-grid">
              <Field label="Schedule name"><input required value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
              <Field label="Department">
                <select required value={edit.department_id} onChange={(e) => setEdit({ ...edit, department_id: e.target.value })}>
                  <option value="">Select…</option>{depts.data.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </Field>
              <Field label="Working days" full>
                <div className="chips">{DAYS.map((d, i) => <span key={d} className={`chip ${edit.working_days.includes(i) ? "on" : ""}`} onClick={() => toggleDay(i)}>{d}</span>)}</div>
              </Field>
            </div>
            <h3 style={{ marginTop: 18 }}>Sessions</h3>
            {edit.sessions.map((s, i) => (
              <div className="row" key={i} style={{ marginBottom: 8 }}>
                <input required placeholder="Name" value={s.name} onChange={(e) => setSession(i, "name", e.target.value)} style={{ width: 160 }} />
                <input type="time" required value={s.start_time} onChange={(e) => setSession(i, "start_time", e.target.value)} />
                <span>to</span>
                <input type="time" required value={s.end_time} onChange={(e) => setSession(i, "end_time", e.target.value)} />
                {edit.sessions.length > 1 && <button type="button" className="btn sm danger" onClick={() => setEdit({ ...edit, sessions: edit.sessions.filter((_, j) => j !== i) })}>Remove</button>}
              </div>
            ))}
            <button type="button" className="btn sm" onClick={() => setEdit({ ...edit, sessions: [...edit.sessions, { name: `Session ${edit.sessions.length + 1}`, start_time: "13:00", end_time: "17:00" }] })}>+ Add session</button>
            <h3 style={{ marginTop: 18 }}>Attendance rules (minutes)</h3>
            <div className="form-grid">
              <Field label="Grace period after start"><input type="number" min={0} value={edit.grace_minutes} onChange={num("grace_minutes")} /></Field>
              <Field label="Check-in opens before start"><input type="number" min={0} value={edit.checkin_open_minutes} onChange={num("checkin_open_minutes")} /></Field>
              <Field label="Check-out opens before end"><input type="number" min={0} value={edit.checkout_open_minutes} onChange={num("checkout_open_minutes")} /></Field>
              <Field label="Check-out closes after end"><input type="number" min={0} value={edit.checkout_close_minutes} onChange={num("checkout_close_minutes")} /></Field>
              <Field label="Absent verification after end"><input type="number" min={0} value={edit.absent_verification_minutes} onChange={num("absent_verification_minutes")} /></Field>
            </div>
            <h3 style={{ marginTop: 18 }}>Cameras / locations</h3>
            <div className="chips">{cams.data.map((c) => <span key={c.id} className={`chip ${edit.camera_ids.includes(c.id) ? "on" : ""}`} onClick={() => toggleCam(c.id)}>{c.camera_code} · {c.name}</span>)}</div>
            <div className="muted small" style={{ marginTop: 6 }}>Leave empty to accept recognition from any camera.</div>
            <label className="check" style={{ marginTop: 14 }}><input type="checkbox" checked={edit.is_active} onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} /> Active</label>
            <div className="modal-foot"><button type="button" className="btn" onClick={() => setEdit(null)}>Cancel</button><button className="btn primary">Save schedule</button></div>
          </form>
        </Modal>
      )}
      {assign && <AssignModal schedule={assign} onClose={() => { setAssign(null); list.reload(); }} />}
    </>
  );
}

function AssignModal({ schedule, onClose }) {
  const emps = useFetch(() => get("/employees", { department_id: schedule.department_id, status: "active" }), [], []);
  const asg = useFetch(() => get(`/schedules/${schedule.id}/assignments`), [], []);
  const [picked, setPicked] = useState([]);
  const [from, setFrom] = useState(todayStr());
  const [to, setTo] = useState("");
  const [msg, setMsg] = useState({});

  const assigned = new Set(asg.data.filter((a) => !a.effective_to).map((a) => a.employee_id));
  const free = emps.data.filter((e) => !assigned.has(e.id));

  const submit = async () => {
    setMsg({});
    try {
      await post(`/schedules/${schedule.id}/assignments`, { employee_ids: picked, effective_from: from, effective_to: to || null });
      setPicked([]);
      asg.reload();
      setMsg({ kind: "ok", text: "Employees assigned." });
    } catch (x) { setMsg({ kind: "error", text: errorMessage(x) }); }
  };
  const endNow = async (a) => { try { await patch(`/schedules/assignments/${a.id}`, { effective_to: todayStr() }); asg.reload(); } catch (x) { setMsg({ kind: "error", text: errorMessage(x) }); } };
  const remove = async (a) => { if (!window.confirm("Remove this assignment?")) return; try { await del(`/schedules/assignments/${a.id}`); asg.reload(); } catch (x) { setMsg({ kind: "error", text: errorMessage(x) }); } };

  return (
    <Modal title={`Assign employees – ${schedule.name}`} wide onClose={onClose} footer={<button className="btn" onClick={onClose}>Close</button>}>
      <Alert kind={msg.kind}>{msg.text}</Alert>
      <div className="grid cols-2">
        <div>
          <h3>Add ({schedule.department_name})</h3>
          <div className="row" style={{ marginBottom: 10 }}>
            <Field label="Effective from"><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
            <Field label="Until (optional)"><input type="date" min={from} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
          </div>
          <div className="card" style={{ maxHeight: 240, overflowY: "auto", padding: 10 }}>
            {free.length === 0 && <div className="muted small">All active employees in this department are assigned.</div>}
            {free.map((e) => (
              <label className="check" key={e.id} style={{ padding: "3px 0" }}>
                <input type="checkbox" checked={picked.includes(e.id)} onChange={() => setPicked((p) => (p.includes(e.id) ? p.filter((x) => x !== e.id) : [...p, e.id]))} />
                {e.employee_code} – {e.full_name}
              </label>
            ))}
          </div>
          <button className="btn primary" disabled={!picked.length} onClick={submit}>Assign {picked.length || ""} selected</button>
        </div>
        <div>
          <h3>Assigned</h3>
          {asg.data.length === 0 ? <div className="muted small">Nobody yet.</div> : (
            <div className="table-wrap">
              <table>
                <tbody>
                  {asg.data.map((a) => (
                    <tr key={a.id}>
                      <td>{a.employee_code}<div className="small">{a.employee_name}</div></td>
                      <td className="small muted">{fmtDate(a.effective_from)} → {a.effective_to ? fmtDate(a.effective_to) : "ongoing"}</td>
                      <td className="right nowrap">
                        {!a.effective_to && <button className="btn sm" onClick={() => endNow(a)}>End today</button>}{" "}
                        <button className="btn sm danger" onClick={() => remove(a)}>✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
