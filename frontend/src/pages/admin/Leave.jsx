import { useState } from "react";
import { Alert, Badge, Empty, Field, Loading, Modal } from "../../components/ui";
import { errorMessage, get, post, put } from "../../services/api";
import { fmtDate, label } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

export default function LeaveAdmin() {
  const [status, setStatus] = useState("pending");
  const list = useFetch(() => get("/leave", { status: status || undefined }), [status], []);
  const types = useFetch(() => get("/leave/types", { include_inactive: true }), [], []);
  const [decide, setDecide] = useState(null);
  const [showTypes, setShowTypes] = useState(false);

  return (
    <>
      <div className="page-head">
        <div><h1>Leave requests</h1><div className="muted">Approved leave marks the employee “On Leave” instead of absent</div></div>
        <button className="btn" onClick={() => setShowTypes(true)}>Leave types</button>
      </div>
      <div className="filters">
        <Field label="Status">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>{["pending", "approved", "rejected", "cancelled"].map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
        </Field>
      </div>
      <Loading loading={list.loading} error={list.error}>
        {list.data.length === 0 ? <Empty>No leave requests.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Employee</th><th>Type</th><th>From</th><th>To</th><th>Days</th><th>Reason</th><th>Status</th><th /></tr></thead>
              <tbody>
                {list.data.map((l) => (
                  <tr key={l.id}>
                    <td>{l.employee_name}<div className="muted small">{l.employee_code} · {l.department_name}</div></td>
                    <td>{l.leave_type}</td><td>{fmtDate(l.start_date)}</td><td>{fmtDate(l.end_date)}</td><td>{l.days}</td>
                    <td className="small muted" style={{ maxWidth: 220 }}>{l.reason}</td>
                    <td><Badge value={l.status} />{l.reviewed_by_name && <div className="muted small">by {l.reviewed_by_name}</div>}</td>
                    <td className="right nowrap">
                      {l.status === "pending" && <>
                        <button className="btn sm primary" onClick={() => setDecide({ l, decision: "approved" })}>Approve</button>{" "}
                        <button className="btn sm danger" onClick={() => setDecide({ l, decision: "rejected" })}>Reject</button>
                      </>}
                      {l.status === "approved" && <button className="btn sm danger" onClick={() => setDecide({ l, decision: "cancelled" })}>Cancel</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loading>
      {decide && <DecideModal {...decide} onClose={(changed) => { setDecide(null); if (changed) list.reload(); }} />}
      {showTypes && <TypesModal types={types} onClose={() => setShowTypes(false)} />}
    </>
  );
}

function DecideModal({ l, decision, onClose }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const go = async () => {
    try { await post(`/leave/${l.id}/decision`, { decision, note: note || null }); onClose(true); } catch (x) { setErr(errorMessage(x)); }
  };
  return (
    <Modal title={`${label(decision)} leave – ${l.employee_name}`} onClose={() => onClose(false)}
      footer={<><button className="btn" onClick={() => onClose(false)}>Back</button><button className={`btn ${decision === "approved" ? "primary" : "danger"}`} onClick={go}>Confirm {decision}</button></>}>
      <Alert>{err}</Alert>
      <p>{l.leave_type}: {fmtDate(l.start_date)} → {fmtDate(l.end_date)} ({l.days} day(s))</p>
      <Field label="Note (optional)"><textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
    </Modal>
  );
}

function TypesModal({ types, onClose }) {
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const add = async (e) => {
    e.preventDefault();
    try { await post("/leave/types", { name, is_active: true }); setName(""); types.reload(); } catch (x) { setErr(errorMessage(x)); }
  };
  const toggle = async (t) => { try { await put(`/leave/types/${t.id}`, { name: t.name, is_active: !t.is_active }); types.reload(); } catch (x) { setErr(errorMessage(x)); } };
  return (
    <Modal title="Leave types" onClose={onClose} footer={<button className="btn" onClick={onClose}>Close</button>}>
      <Alert>{err}</Alert>
      <div className="table-wrap" style={{ marginBottom: 14 }}>
        <table><tbody>
          {types.data.map((t) => <tr key={t.id}><td>{t.name}</td><td><Badge value={t.is_active ? "active" : "inactive"} /></td><td className="right"><button className="btn sm" onClick={() => toggle(t)}>{t.is_active ? "Disable" : "Enable"}</button></td></tr>)}
        </tbody></table>
      </div>
      <form className="row" onSubmit={add}>
        <input required minLength={2} placeholder="New leave type" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn primary">Add</button>
      </form>
    </Modal>
  );
}
