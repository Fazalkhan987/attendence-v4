import { useState } from "react";
import { Alert, Badge, Empty, Field, Loading } from "../../components/ui";
import { del, errorMessage, get, post } from "../../services/api";
import { fmtDate, todayStr } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

export default function MyLeave() {
  const types = useFetch(() => get("/me/leave-types"), [], []);
  const list = useFetch(() => get("/me/leave"), [], []);
  const [form, setForm] = useState({ leave_type_id: "", start_date: todayStr(), end_date: todayStr(), reason: "" });
  const [msg, setMsg] = useState({ kind: "", text: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg({});
    try {
      await post("/me/leave", { ...form, leave_type_id: Number(form.leave_type_id) });
      setMsg({ kind: "ok", text: "Leave request submitted." });
      setForm((f) => ({ ...f, reason: "" }));
      list.reload();
    } catch (err) {
      setMsg({ kind: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (id) => {
    if (!window.confirm("Cancel this leave request?")) return;
    try { await del(`/me/leave/${id}`); list.reload(); } catch (err) { setMsg({ kind: "error", text: errorMessage(err) }); }
  };

  return (
    <>
      <div className="page-head"><div><h1>Leave</h1><div className="muted">One request per day — overlapping requests are not allowed</div></div></div>
      <form className="card" onSubmit={submit}>
        <h2>New request</h2>
        <Alert kind={msg.kind}>{msg.text}</Alert>
        <div className="form-grid">
          <Field label="Leave type">
            <select value={form.leave_type_id} onChange={set("leave_type_id")} required>
              <option value="">Select…</option>
              {types.data.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </Field>
          <Field label="From"><input type="date" min={todayStr()} value={form.start_date} onChange={set("start_date")} required /></Field>
          <Field label="To"><input type="date" min={form.start_date} value={form.end_date} onChange={set("end_date")} required /></Field>
          <Field label="Reason" full><textarea rows={2} maxLength={1000} value={form.reason} onChange={set("reason")} /></Field>
        </div>
        <div className="modal-foot"><button className="btn primary" disabled={busy}>{busy ? "Submitting…" : "Submit request"}</button></div>
      </form>
      <h2>My requests</h2>
      <Loading loading={list.loading} error={list.error}>
        {list.data.length === 0 ? <Empty>No leave requests yet.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Type</th><th>From</th><th>To</th><th>Days</th><th>Status</th><th>Reviewer note</th><th /></tr></thead>
              <tbody>
                {list.data.map((l) => (
                  <tr key={l.id}>
                    <td>{l.leave_type}</td><td>{fmtDate(l.start_date)}</td><td>{fmtDate(l.end_date)}</td><td>{l.days}</td>
                    <td><Badge value={l.status} /></td>
                    <td className="small muted">{l.review_note || (l.reviewed_by_name ? `by ${l.reviewed_by_name}` : "")}</td>
                    <td className="right">{l.status === "pending" && <button className="btn sm danger" onClick={() => cancel(l.id)}>Cancel</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loading>
    </>
  );
}
