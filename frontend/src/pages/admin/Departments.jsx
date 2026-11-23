import { useState } from "react";
import { Alert, Badge, Empty, Field, Loading, Modal } from "../../components/ui";
import { del, errorMessage, get, post, put } from "../../services/api";
import { useFetch } from "../../utils/hooks";

const blank = { code: "", name: "", description: "", is_active: true };

export default function Departments() {
  const { data, loading, error, reload } = useFetch(() => get("/departments"), [], []);
  const [edit, setEdit] = useState(null);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");

  const save = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      if (edit.id) await put(`/departments/${edit.id}`, edit); else await post("/departments", edit);
      setEdit(null);
      reload();
    } catch (x) { setErr(errorMessage(x)); }
  };

  const remove = async (d) => {
    if (!window.confirm(`Delete department "${d.name}"? If it is in use it will be deactivated instead.`)) return;
    try { const r = await del(`/departments/${d.id}`); setNote(r.detail); reload(); } catch (x) { setNote(errorMessage(x)); }
  };

  return (
    <>
      <div className="page-head">
        <div><h1>Departments</h1></div>
        <button className="btn primary" onClick={() => { setErr(""); setEdit({ ...blank }); }}>+ New department</button>
      </div>
      <Alert kind="info">{note}</Alert>
      <Loading loading={loading} error={error}>
        {data.length === 0 ? <Empty>No departments yet.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Code</th><th>Name</th><th>Description</th><th>Employees</th><th>Status</th><th /></tr></thead>
              <tbody>
                {data.map((d) => (
                  <tr key={d.id}>
                    <td><strong>{d.code}</strong></td><td>{d.name}</td><td className="muted">{d.description}</td><td>{d.employee_count}</td>
                    <td><Badge value={d.is_active ? "active" : "inactive"} /></td>
                    <td className="right nowrap">
                      <button className="btn sm" onClick={() => { setErr(""); setEdit({ ...d }); }}>Edit</button>{" "}
                      <button className="btn sm danger" onClick={() => remove(d)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loading>
      {edit && (
        <Modal title={edit.id ? "Edit department" : "New department"} onClose={() => setEdit(null)}>
          <form onSubmit={save}>
            <Alert>{err}</Alert>
            <div className="form-grid">
              <Field label="Code"><input required maxLength={20} value={edit.code} onChange={(e) => setEdit({ ...edit, code: e.target.value })} /></Field>
              <Field label="Name"><input required minLength={2} maxLength={120} value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
              <Field label="Description" full><textarea rows={2} value={edit.description || ""} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></Field>
              <label className="check"><input type="checkbox" checked={edit.is_active} onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} /> Active</label>
            </div>
            <div className="modal-foot"><button type="button" className="btn" onClick={() => setEdit(null)}>Cancel</button><button className="btn primary">Save</button></div>
          </form>
        </Modal>
      )}
    </>
  );
}
