import { useState } from "react";
import { Alert, Badge, Empty, Field, Loading, Modal } from "../../components/ui";
import { del, errorMessage, get, post, put } from "../../services/api";
import { fmtDateTime, label } from "../../utils/format";
import { useFetch } from "../../utils/hooks";

const blank = { camera_code: "", name: "", location: "", department_id: "", purpose: "both", source: "", is_active: true };

export default function Cameras() {
  const cams = useFetch(() => get("/cameras"), [], []);
  const depts = useFetch(() => get("/departments"), [], []);
  const [edit, setEdit] = useState(null);
  const [err, setErr] = useState("");
  const [secret, setSecret] = useState(null);

  const save = async (e) => {
    e.preventDefault();
    setErr("");
    const body = { ...edit, department_id: edit.department_id ? Number(edit.department_id) : null };
    try {
      if (edit.id) await put(`/cameras/${edit.id}`, body);
      else setSecret(await post("/cameras", body));
      setEdit(null);
      cams.reload();
    } catch (x) { setErr(errorMessage(x)); }
  };

  const rotate = async (c) => {
    if (!window.confirm("Generate a new API key? The old key stops working immediately.")) return;
    try { setSecret(await post(`/cameras/${c.id}/rotate-key`)); } catch (x) { alert(errorMessage(x)); }
  };
  const remove = async (c) => {
    if (!window.confirm(`Delete camera ${c.camera_code}?`)) return;
    try { await del(`/cameras/${c.id}`); cams.reload(); } catch (x) { alert(errorMessage(x)); }
  };
  const deptName = (id) => depts.data.find((d) => d.id === id)?.name || "Any";

  return (
    <>
      <div className="page-head">
        <div><h1>Cameras</h1><div className="muted">Each camera authenticates to the backend with its own API key</div></div>
        <button className="btn primary" onClick={() => { setErr(""); setEdit({ ...blank }); }}>+ New camera</button>
      </div>
      <Loading loading={cams.loading} error={cams.error}>
        {cams.data.length === 0 ? <Empty>No cameras registered.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Code</th><th>Name</th><th>Location</th><th>Department</th><th>Purpose</th><th>Last seen</th><th>Status</th><th /></tr></thead>
              <tbody>
                {cams.data.map((c) => (
                  <tr key={c.id}>
                    <td><strong>{c.camera_code}</strong></td><td>{c.name}</td><td className="muted">{c.location}</td><td>{deptName(c.department_id)}</td>
                    <td>{label(c.purpose)}</td><td className="small">{fmtDateTime(c.last_seen_at)}</td>
                    <td><Badge value={c.is_active ? "active" : "inactive"} /></td>
                    <td className="right nowrap">
                      <button className="btn sm" onClick={() => { setErr(""); setEdit({ ...c, department_id: c.department_id || "" }); }}>Edit</button>{" "}
                      <button className="btn sm" onClick={() => rotate(c)}>New key</button>{" "}
                      <button className="btn sm danger" onClick={() => remove(c)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loading>
      {edit && (
        <Modal title={edit.id ? `Edit ${edit.camera_code}` : "New camera"} onClose={() => setEdit(null)}>
          <form onSubmit={save}>
            <Alert>{err}</Alert>
            <div className="form-grid">
              <Field label="Camera code"><input required disabled={!!edit.id} maxLength={50} placeholder="CAM-01" value={edit.camera_code} onChange={(e) => setEdit({ ...edit, camera_code: e.target.value })} /></Field>
              <Field label="Name"><input required minLength={2} value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
              <Field label="Location"><input value={edit.location || ""} onChange={(e) => setEdit({ ...edit, location: e.target.value })} /></Field>
              <Field label="Department (optional restriction)">
                <select value={edit.department_id} onChange={(e) => setEdit({ ...edit, department_id: e.target.value })}>
                  <option value="">Any department</option>
                  {depts.data.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </Field>
              <Field label="Purpose">
                <select value={edit.purpose} onChange={(e) => setEdit({ ...edit, purpose: e.target.value })}>
                  <option value="both">Entry and exit</option><option value="entry">Entry only (check-in)</option><option value="exit">Exit only (check-out)</option>
                </select>
              </Field>
              <Field label="Source note"><input placeholder="webcam:0 or rtsp://…" value={edit.source || ""} onChange={(e) => setEdit({ ...edit, source: e.target.value })} /></Field>
              <label className="check"><input type="checkbox" checked={edit.is_active} onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} /> Active</label>
            </div>
            <div className="modal-foot"><button type="button" className="btn" onClick={() => setEdit(null)}>Cancel</button><button className="btn primary">Save</button></div>
          </form>
        </Modal>
      )}
      {secret && (
        <Modal title="Camera API key" onClose={() => setSecret(null)} footer={<button className="btn primary" onClick={() => setSecret(null)}>I have copied it</button>}>
          <Alert kind="info">This key is shown only once. Put it in <code>face_engine/.env</code> as <code>CAMERA_KEY</code>.</Alert>
          <div className="card" style={{ wordBreak: "break-all", fontFamily: "monospace" }}>
            CAMERA_CODE={secret.camera_code}<br />CAMERA_KEY={secret.api_key}
          </div>
          <button className="btn" onClick={() => navigator.clipboard?.writeText(`CAMERA_CODE=${secret.camera_code}\nCAMERA_KEY=${secret.api_key}`)}>Copy</button>
        </Modal>
      )}
    </>
  );
}
