import { useEffect, useState } from "react";
import WebcamCapture from "../../components/WebcamCapture";
import { Alert, Avatar, Badge, Empty, Field, Loading, Modal } from "../../components/ui";
import { del, errorMessage, fetchPhotoUrl, get, post, put } from "../../services/api";
import { fmtDate, label, todayStr } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

const STATUSES = ["active", "probation", "suspended", "resigned", "terminated"];
const blank = {
  employee_code: "", full_name: "", email: "", phone: "", address: "", department_id: "", designation: "",
  joining_date: todayStr(), employment_status: "active", supervisor_id: "", face_consent: false,
  create_account: true, login_email: "", password: "",
};

function Thumb({ e }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url;
    if (e.has_photo) fetchPhotoUrl(e.id).then((u) => { url = u; setSrc(u); }).catch(() => {});
    return () => url && URL.revokeObjectURL(url);
  }, [e.id, e.has_photo]);
  return <Avatar name={e.full_name} src={src} />;
}

export default function Employees() {
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("");
  const [status, setStatus] = useState("");
  const emps = useFetch(() => get("/employees", { q: q || undefined, department_id: dept || undefined, status: status || undefined }), [q, dept, status], []);
  const depts = useFetch(() => get("/departments"), [], []);
  const [edit, setEdit] = useState(null);
  const [err, setErr] = useState("");
  const [enroll, setEnroll] = useState(null);

  const open = (e) => {
    setErr("");
    if (!e) return setEdit({ ...blank });
    setEdit({
      ...e, phone: e.phone || "", address: e.address || "", supervisor_id: e.supervisor_id || "",
      create_account: false, login_email: e.login_email || "", password: "",
    });
  };

  const save = async (ev) => {
    ev.preventDefault();
    setErr("");
    const base = {
      employee_code: edit.employee_code, full_name: edit.full_name, email: edit.email, phone: edit.phone || null, address: edit.address || null,
      department_id: Number(edit.department_id), designation: edit.designation, joining_date: edit.joining_date,
      employment_status: edit.employment_status, supervisor_id: edit.supervisor_id ? Number(edit.supervisor_id) : null,
      face_consent: edit.face_consent,
    };
    try {
      if (edit.id) {
        await put(`/employees/${edit.id}`, base);
        if (edit.login_email || edit.password) {
          const acct = {};
          if (edit.login_email && edit.login_email !== (edit.original_login || "")) acct.login_email = edit.login_email;
          if (edit.password) acct.password = edit.password;
          if (Object.keys(acct).length && (edit.has_account || (acct.login_email && acct.password))) await put(`/employees/${edit.id}/account`, acct);
        }
      } else {
        const body = { ...base };
        if (edit.create_account) body.account = { login_email: edit.login_email || edit.email, password: edit.password, is_active: true };
        await post("/employees", body);
      }
      setEdit(null);
      emps.reload();
    } catch (x) { setErr(errorMessage(x)); }
  };

  const remove = async (e) => {
    if (!window.confirm(`Remove ${e.full_name}? With attendance history the employee is terminated and face data erased instead.`)) return;
    try { await del(`/employees/${e.id}`); emps.reload(); } catch (x) { alert(errorMessage(x)); }
  };

  return (
    <>
      <div className="page-head">
        <div><h1>Employees</h1></div>
        <button className="btn primary" onClick={() => open(null)}>+ Register employee</button>
      </div>
      <div className="filters">
        <Field label="Search"><input placeholder="Name, ID or email" value={q} onChange={(e) => setQ(e.target.value)} /></Field>
        <Field label="Department">
          <select value={dept} onChange={(e) => setDept(e.target.value)}><option value="">All</option>{depts.data.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
        </Field>
        <Field label="Status">
          <select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
        </Field>
      </div>
      <Loading loading={emps.loading} error={emps.error}>
        {emps.data.length === 0 ? <Empty>No employees found.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th /><th>ID</th><th>Name</th><th>Department</th><th>Designation</th><th>Status</th><th>Face</th><th>Login</th><th /></tr></thead>
              <tbody>
                {emps.data.map((e) => (
                  <tr key={e.id}>
                    <td><Thumb e={e} /></td>
                    <td><strong>{e.employee_code}</strong></td>
                    <td>{e.full_name}<div className="muted small">{e.email}</div></td>
                    <td>{e.department_name}</td><td>{e.designation}</td>
                    <td><Badge value={e.employment_status} /></td>
                    <td>{e.face_samples > 0 ? <span className="badge present">{e.face_samples} samples</span> : <span className="badge inactive">Not enrolled</span>}</td>
                    <td>{e.has_account ? <Badge value={e.account_active ? "active" : "inactive"} /> : <span className="muted small">none</span>}</td>
                    <td className="right nowrap">
                      <button className="btn sm primary" onClick={() => setEnroll(e)}>Face</button>{" "}
                      <button className="btn sm" onClick={() => open({ ...e, original_login: e.login_email })}>Edit</button>{" "}
                      <button className="btn sm danger" onClick={() => remove(e)}>Remove</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loading>

      {edit && (
        <Modal title={edit.id ? `Edit ${edit.employee_code}` : "Register employee"} wide onClose={() => setEdit(null)}>
          <form onSubmit={save}>
            <Alert>{err}</Alert>
            <h3>Personal information</h3>
            <div className="form-grid">
              <Field label="Employee ID"><input required maxLength={50} value={edit.employee_code} onChange={(e) => setEdit({ ...edit, employee_code: e.target.value })} placeholder="EMP-001" /></Field>
              <Field label="Full name"><input required minLength={2} value={edit.full_name} onChange={(e) => setEdit({ ...edit, full_name: e.target.value })} /></Field>
              <Field label="Email"><input type="email" required value={edit.email} onChange={(e) => setEdit({ ...edit, email: e.target.value })} /></Field>
              <Field label="Phone"><input value={edit.phone} onChange={(e) => setEdit({ ...edit, phone: e.target.value })} /></Field>
              <Field label="Address" full><textarea rows={2} value={edit.address} onChange={(e) => setEdit({ ...edit, address: e.target.value })} /></Field>
            </div>
            <h3 style={{ marginTop: 18 }}>Employment</h3>
            <div className="form-grid">
              <Field label="Department">
                <select required value={edit.department_id} onChange={(e) => setEdit({ ...edit, department_id: e.target.value })}>
                  <option value="">Select…</option>{depts.data.filter((d) => d.is_active || d.id === edit.department_id).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </Field>
              <Field label="Designation"><input required value={edit.designation} onChange={(e) => setEdit({ ...edit, designation: e.target.value })} /></Field>
              <Field label="Joining date"><input type="date" required value={edit.joining_date} onChange={(e) => setEdit({ ...edit, joining_date: e.target.value })} /></Field>
              <Field label="Employment status">
                <select value={edit.employment_status} onChange={(e) => setEdit({ ...edit, employment_status: e.target.value })}>{STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
              </Field>
              <Field label="Supervisor">
                <select value={edit.supervisor_id} onChange={(e) => setEdit({ ...edit, supervisor_id: e.target.value })}>
                  <option value="">None</option>{emps.data.filter((x) => x.id !== edit.id).map((x) => <option key={x.id} value={x.id}>{x.employee_code} – {x.full_name}</option>)}
                </select>
              </Field>
            </div>
            <h3 style={{ marginTop: 18 }}>System account</h3>
            {!edit.id && <label className="check" style={{ marginBottom: 10 }}><input type="checkbox" checked={edit.create_account} onChange={(e) => setEdit({ ...edit, create_account: e.target.checked })} /> Create a login so the employee can view their attendance</label>}
            {(edit.id || edit.create_account) && (
              <div className="form-grid">
                <Field label="Login email"><input type="email" value={edit.login_email} onChange={(e) => setEdit({ ...edit, login_email: e.target.value })} placeholder={edit.id ? "" : edit.email} /></Field>
                <Field label={edit.id ? "New password (leave blank to keep)" : "Password (min 8)"}>
                  <input type="password" minLength={8} maxLength={72} required={!edit.id && edit.create_account} value={edit.password} onChange={(e) => setEdit({ ...edit, password: e.target.value })} autoComplete="new-password" />
                </Field>
              </div>
            )}
            <h3 style={{ marginTop: 18 }}>Biometric consent</h3>
            <label className="check">
              <input type="checkbox" checked={edit.face_consent} onChange={(e) => setEdit({ ...edit, face_consent: e.target.checked })} />
              The employee has given explicit consent for face recognition attendance. Withdrawing consent permanently erases their face data.
            </label>
            <div className="modal-foot"><button type="button" className="btn" onClick={() => setEdit(null)}>Cancel</button><button className="btn primary">{edit.id ? "Save changes" : "Register"}</button></div>
          </form>
        </Modal>
      )}
      {enroll && <EnrollModal employee={enroll} onClose={() => { setEnroll(null); emps.reload(); }} />}
    </>
  );
}

function EnrollModal({ employee, onClose }) {
  const [shots, setShots] = useState([]);
  const [msg, setMsg] = useState({});
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setMsg({});
    try {
      const r = await post(`/employees/${employee.id}/face/enroll`, { images: shots, replace_existing: true, set_profile_photo: true });
      const rej = r.rejected.length ? ` ${r.rejected.length} photo(s) rejected: ${r.rejected.map((x) => label(x.reason)).join(", ")}.` : "";
      setMsg({ kind: "ok", text: `Enrollment successful: ${r.accepted} samples stored.${rej}` });
    } catch (x) { setMsg({ kind: "error", text: errorMessage(x) }); } finally { setBusy(false); }
  };
  const erase = async () => {
    if (!window.confirm("Erase all stored face data for this employee?")) return;
    try { await del(`/employees/${employee.id}/face`); setMsg({ kind: "ok", text: "Face data erased." }); } catch (x) { setMsg({ kind: "error", text: errorMessage(x) }); }
  };

  return (
    <Modal title={`Face enrollment – ${employee.full_name}`} onClose={onClose}
      footer={<>
        {employee.face_samples > 0 && <button className="btn danger" onClick={erase}>Erase face data</button>}
        <button className="btn" onClick={onClose}>Close</button>
        <button className="btn primary" disabled={busy || shots.length < 3} onClick={submit}>{busy ? "Processing…" : `Enroll ${shots.length} photos`}</button>
      </>}>
      {!employee.face_consent && <Alert>This employee has not given biometric consent. Tick the consent box in the employee form first.</Alert>}
      <Alert kind={msg.kind}>{msg.text}</Alert>
      <div className="muted small" style={{ marginBottom: 10 }}>Capture at least 3 clear, well-lit photos (5–8 recommended) with small head movements. Only encrypted embeddings are stored; the best photo becomes the profile picture.</div>
      <WebcamCapture target={6} onChange={setShots} />
    </Modal>
  );
}
