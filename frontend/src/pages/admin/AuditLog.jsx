import { useState } from "react";
import { Empty, Field, Loading } from "../../components/ui";
import { get } from "../../services/api";
import { fmtDateTime } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

export default function AuditLog() {
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const { data, loading, error } = useFetch(() => get("/audit-logs", { action: action || undefined, entity_type: entity || undefined, limit: 300 }), [action, entity], []);
  return (
    <>
      <div className="page-head"><div><h1>Audit log</h1><div className="muted">Every administrative action, newest first</div></div></div>
      <div className="filters">
        <Field label="Action"><input placeholder="e.g. attendance_corrected" value={action} onChange={(e) => setAction(e.target.value.trim())} /></Field>
        <Field label="Entity">
          <select value={entity} onChange={(e) => setEntity(e.target.value)}>
            <option value="">All</option>
            {["user", "employee", "department", "schedule", "schedule_assignment", "camera", "attendance", "leave_request", "leave_type"].map((x) => <option key={x}>{x}</option>)}
          </select>
        </Field>
      </div>
      <Loading loading={loading} error={error}>
        {data.length === 0 ? <Empty>No log entries.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Details</th><th>IP</th></tr></thead>
              <tbody>
                {data.map((a) => (
                  <tr key={a.id}>
                    <td className="nowrap small">{fmtDateTime(a.created_at)}</td><td>{a.user_email || "system"}</td><td>{a.action}</td>
                    <td>{a.entity_type}{a.entity_id ? ` #${a.entity_id}` : ""}</td>
                    <td className="small muted" style={{ maxWidth: 360, wordBreak: "break-word" }}>{a.details ? JSON.stringify(a.details) : ""}</td>
                    <td className="small muted">{a.ip_address}</td>
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
