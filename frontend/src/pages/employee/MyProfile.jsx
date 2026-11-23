import { useEffect, useState } from "react";
import { Alert, Avatar, Field, Loading } from "../../components/ui";
import { errorMessage, fetchPhotoUrl, get, post } from "../../services/api";
import { fmtDate, label } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

export default function MyProfile() {
  const { data: p, loading, error } = useFetch(() => get("/me/profile"), []);
  const [photo, setPhoto] = useState(null);
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [msg, setMsg] = useState({});

  useEffect(() => {
    if (p?.has_photo) fetchPhotoUrl(p.id).then(setPhoto).catch(() => {});
  }, [p]);

  const change = async (e) => {
    e.preventDefault();
    try {
      await post("/auth/change-password", pw);
      setMsg({ kind: "ok", text: "Password updated." });
      setPw({ current_password: "", new_password: "" });
    } catch (err) { setMsg({ kind: "error", text: errorMessage(err) }); }
  };

  return (
    <>
      <div className="page-head"><div><h1>My profile</h1></div></div>
      <Loading loading={loading} error={error}>
        {p && (
          <>
            <div className="card row" style={{ gap: 18, alignItems: "flex-start" }}>
              <Avatar name={p.full_name} src={photo} large />
              <div className="form-grid" style={{ flex: 1 }}>
                {[["Name", p.full_name], ["Employee ID", p.employee_code], ["Email", p.email], ["Phone", p.phone || "—"],
                  ["Department", p.department_name], ["Designation", p.designation], ["Joined", fmtDate(p.joining_date)],
                  ["Status", label(p.employment_status)], ["Supervisor", p.supervisor_name || "—"], ["Address", p.address || "—"],
                  ["Face enrolled", p.face_samples > 0 ? `Yes (${p.face_samples} samples)` : "No"]].map(([k, v]) => (
                  <div key={k}><div className="muted small">{k}</div><div>{v}</div></div>
                ))}
              </div>
            </div>
            <form className="card" onSubmit={change}>
              <h2>Change password</h2>
              <Alert kind={msg.kind}>{msg.text}</Alert>
              <div className="form-grid">
                <Field label="Current password"><input type="password" required value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" /></Field>
                <Field label="New password (min 8)"><input type="password" required minLength={8} maxLength={72} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" /></Field>
              </div>
              <div className="modal-foot"><button className="btn primary">Update password</button></div>
            </form>
          </>
        )}
      </Loading>
    </>
  );
}
