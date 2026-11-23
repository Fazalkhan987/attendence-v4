import { Empty, Loading } from "../../components/ui";
import { get } from "../../services/api";
import { DAYS, hhmm } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

export default function MySchedule() {
  const { data, loading, error } = useFetch(() => get("/me/schedules"), [], []);
  return (
    <>
      <div className="page-head"><div><h1>My schedule</h1><div className="muted">Your assigned working hours</div></div></div>
      <Loading loading={loading} error={error}>
        {data.length === 0 ? <Empty>No schedule has been assigned to you yet.</Empty> : (
          <div className="grid cols-2">
            {data.map((s) => (
              <div className="card" key={s.id}>
                <h3>{s.name}</h3>
                <div className="muted small" style={{ marginBottom: 10 }}>{s.department_name}</div>
                <div className="chips" style={{ marginBottom: 12 }}>
                  {DAYS.map((d, i) => <span key={d} className={`chip ${s.working_days.includes(i) ? "on" : ""}`} style={{ cursor: "default" }}>{d}</span>)}
                </div>
                {s.sessions.map((x) => <div key={x.id} className="row between"><span>{x.name}</span><strong>{hhmm(x.start_time)} – {hhmm(x.end_time)}</strong></div>)}
                <div className="muted small" style={{ marginTop: 10 }}>Grace period: {s.grace_minutes} min{s.camera_codes.length ? ` · Cameras: ${s.camera_codes.join(", ")}` : ""}</div>
              </div>
            ))}
          </div>
        )}
      </Loading>
    </>
  );
}
