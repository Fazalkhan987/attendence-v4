import { useState } from "react";
import { Badge, Empty, Loading, Stat, Field } from "../../components/ui";
import { get } from "../../services/api";
import { addDays, fmtDate, fmtMinutes, fmtTime, hhmm, todayStr } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

export default function MyAttendance() {
  const [from, setFrom] = useState(addDays(todayStr(), -30));
  const [to, setTo] = useState(todayStr());
  const { data, loading, error } = useFetch(() => get("/me/attendance", { date_from: from, date_to: to }), [from, to], []);

  const count = (s) => data.filter((r) => r.status === s).length;
  return (
    <>
      <div className="page-head"><div><h1>My attendance</h1><div className="muted">Your check-in and check-out history</div></div></div>
      <div className="filters">
        <Field label="From"><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="To"><input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
      </div>
      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Stat value={count("present")} label="Present" tone="green" />
        <Stat value={count("late")} label="Late" tone="amber" />
        <Stat value={count("absent")} label="Absent" tone="red" />
        <Stat value={count("on_leave")} label="On leave" tone="blue" />
      </div>
      <Loading loading={loading} error={error}>
        {data.length === 0 ? <Empty>No attendance records in this period.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Session</th><th>Check-in</th><th>Check-out</th><th>Worked</th><th>Status</th><th>Notes</th></tr></thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.id}>
                    <td className="nowrap">{fmtDate(r.work_date)}</td>
                    <td>{r.session_name} <span className="muted small">{hhmm(r.session_start)}–{hhmm(r.session_end)}</span></td>
                    <td>{fmtTime(r.check_in_time)}</td>
                    <td>{fmtTime(r.check_out_time)}</td>
                    <td>{fmtMinutes(r.working_minutes)}</td>
                    <td><Badge value={r.status} />{r.late_minutes > 0 && <span className="muted small"> +{r.late_minutes}m</span>}</td>
                    <td className="small muted">{[r.early_departure && "Left early", r.source === "manual" && "Edited by admin", r.remarks].filter(Boolean).join(" · ")}</td>
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
