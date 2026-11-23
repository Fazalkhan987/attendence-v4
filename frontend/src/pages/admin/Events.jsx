import { useState } from "react";
import { Badge, Empty, Field, Loading } from "../../components/ui";
import { get } from "../../services/api";
import { fmtDateTime, label } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

export default function Events() {
  const [outcome, setOutcome] = useState("");
  const { data, loading, error, reload } = useFetch(() => get("/recognition/events", { outcome: outcome || undefined, limit: 300 }), [outcome], []);
  return (
    <>
      <div className="page-head">
        <div><h1>Recognition events</h1><div className="muted">Everything the face engine reported and what the backend decided</div></div>
        <button className="btn" onClick={reload}>Refresh</button>
      </div>
      <div className="filters">
        <Field label="Outcome">
          <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
            <option value="">All</option>
            {["accepted", "duplicate", "ignored", "rejected"].map((o) => <option key={o} value={o}>{label(o)}</option>)}
          </select>
        </Field>
      </div>
      <Loading loading={loading} error={error}>
        {data.length === 0 ? <Empty>No events yet.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Time</th><th>Employee</th><th>Camera</th><th>Confidence</th><th>Outcome</th><th>Action</th><th>Reason</th></tr></thead>
              <tbody>
                {data.map((e) => (
                  <tr key={e.id}>
                    <td className="nowrap small">{fmtDateTime(e.event_timestamp)}</td>
                    <td>{e.employee_name || "—"} <span className="muted small">{e.employee_code}</span></td>
                    <td>{e.camera_code}</td><td>{(e.confidence * 100).toFixed(0)}%</td>
                    <td><Badge value={e.outcome} /></td><td>{label(e.action) || "—"}</td><td className="small muted">{label(e.reason)}</td>
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
