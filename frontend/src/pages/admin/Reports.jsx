import { useState } from "react";
import { Alert, Empty, Field, Loading } from "../../components/ui";
import { downloadFile, errorMessage, get } from "../../services/api";
import { addDays, todayStr } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

export default function Reports() {
  const [from, setFrom] = useState(addDays(todayStr(), -30));
  const [to, setTo] = useState(todayStr());
  const [dept, setDept] = useState("");
  const depts = useFetch(() => get("/departments"), [], []);
  const rep = useFetch(() => get("/reports/attendance-summary", { date_from: from, date_to: to, department_id: dept || undefined }), [from, to, dept], []);
  const [err, setErr] = useState("");

  const csv = async () => {
    setErr("");
    try { await downloadFile("/reports/attendance.csv", { date_from: from, date_to: to, department_id: dept || undefined }, `attendance_${from}_${to}.csv`); } catch (x) { setErr(errorMessage(x)); }
  };

  return (
    <>
      <div className="page-head">
        <div><h1>Reports</h1><div className="muted">Per-employee attendance summary</div></div>
        <button className="btn primary" onClick={csv}>Download detailed CSV</button>
      </div>
      <Alert>{err}</Alert>
      <div className="filters">
        <Field label="From"><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="To"><input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
        <Field label="Department"><select value={dept} onChange={(e) => setDept(e.target.value)}><option value="">All</option>{depts.data.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
      </div>
      <Loading loading={rep.loading} error={rep.error}>
        {rep.data.length === 0 ? <Empty>No attendance data in this period.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Employee</th><th>Department</th><th>Present</th><th>Late</th><th>Absent</th><th>On leave</th><th>Half day</th><th>Incomplete</th><th>Excused</th><th>Hours</th><th>Rate</th></tr></thead>
              <tbody>
                {rep.data.map((r) => (
                  <tr key={r.employee_id}>
                    <td>{r.employee_name}<div className="muted small">{r.employee_code}</div></td><td>{r.department_name}</td>
                    <td>{r.present}</td><td>{r.late}</td><td>{r.absent}</td><td>{r.on_leave}</td><td>{r.half_day}</td><td>{r.incomplete}</td><td>{r.excused}</td>
                    <td>{r.worked_hours}</td><td><strong>{r.attendance_rate}%</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loading>
      <div className="muted small" style={{ marginTop: 10 }}>Rate = (present + late + half day + excused) ÷ (all sessions − on leave).</div>
    </>
  );
}
