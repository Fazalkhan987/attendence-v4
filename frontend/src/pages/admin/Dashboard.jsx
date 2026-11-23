import { Loading, Stat } from "../../components/ui";
import { get } from "../../services/api";
import { fmtDate } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

const SEGMENTS = [["present", "Present"], ["late", "Late"], ["absent", "Absent"], ["on_leave", "On leave"]];

export default function Dashboard() {
  const { data: d, loading, error } = useFetch(() => get("/reports/dashboard"), []);
  const days = d ? Object.keys(d.week_trend).sort() : [];
  const max = d ? Math.max(1, ...days.map((k) => Object.values(d.week_trend[k]).reduce((a, b) => a + b, 0))) : 1;

  return (
    <>
      <div className="page-head"><div><h1>Dashboard</h1><div className="muted">{d ? fmtDate(d.date) : ""}</div></div></div>
      <Loading loading={loading} error={error}>
        {d && (
          <>
            <div className="grid cols-4" style={{ marginBottom: 18 }}>
              <Stat value={d.active_employees} label="Active employees" />
              <Stat value={d.enrolled_employees} label="Face enrolled" />
              <Stat value={d.today.present} label="Present today" tone="green" />
              <Stat value={d.today.late} label="Late today" tone="amber" />
              <Stat value={d.today.absent} label="Absent today" tone="red" />
              <Stat value={d.today.on_leave} label="On leave today" tone="blue" />
              <Stat value={d.pending_leave} label="Pending leave requests" />
              <Stat value={`${d.accepted_events_today}/${d.events_today}`} label="Accepted / total recognition events (24h)" />
            </div>
            <div className="card">
              <h2>Last 7 days</h2>
              {days.length === 0 ? <div className="muted">No attendance recorded yet.</div> : (
                <>
                  <div className="bars">
                    {days.map((day) => {
                      const t = d.week_trend[day];
                      const total = Object.values(t).reduce((a, b) => a + b, 0);
                      return (
                        <div className="bar-col" key={day} title={SEGMENTS.map(([k, l]) => `${l}: ${t[k] || 0}`).join(", ")}>
                          <div className="bar-stack" style={{ height: `${(total / max) * 100}%`, minHeight: 4 }}>
                            {SEGMENTS.map(([k]) => t[k] ? <div key={k} className={`seg-${k}`} style={{ flex: t[k] }} /> : null)}
                          </div>
                          <span className="small muted">{day.slice(5)}</span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="row small muted" style={{ marginTop: 10 }}>
                    {SEGMENTS.map(([k, l]) => <span key={k}><span className={`badge ${k}`}>{l}</span></span>)}
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </Loading>
    </>
  );
}
