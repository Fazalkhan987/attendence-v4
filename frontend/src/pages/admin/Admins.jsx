import { useState } from "react";
import { Alert, Badge, Field, Loading, Modal } from "../../components/ui";
import { useAuth } from "../../context/AuthContext";
import { errorMessage, get, patch, post } from "../../services/api";
import { useFetch } from "../../utils/hooks";

export default function Admins() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch(() => get("/users/admins"), [], []);
  const [form, setForm] = useState(null);
  const [err, setErr] = useState("");

  const create = async (e) => {
    e.preventDefault();
    setErr("");
    try { await post("/users/admins", form); setForm(null); reload(); } catch (x) { setErr(errorMessage(x)); }
  };
  const toggle = async (u) => {
    try { await patch(`/users/admins/${u.id}`, { is_active: !u.is_active }); reload(); } catch (x) { alert(errorMessage(x)); }
  };

  return (
    <>
      <div className="page-head">
        <div><h1>Administrators</h1></div>
        <button className="btn primary" onClick={() => { setErr(""); setForm({ email: "", full_name: "", password: "" }); }}>+ New administrator</button>
      </div>
      <Loading loading={loading} error={error}>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Email</th><th>Status</th><th /></tr></thead>
            <tbody>
              {data.map((u) => (
                <tr key={u.id}>
                  <td>{u.full_name}</td><td>{u.email}</td><td><Badge value={u.is_active ? "active" : "inactive"} /></td>
                  <td className="right">{u.id !== user.id && <button className="btn sm" onClick={() => toggle(u)}>{u.is_active ? "Deactivate" : "Activate"}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Loading>
      {form && (
        <Modal title="New administrator" onClose={() => setForm(null)}>
          <form onSubmit={create}>
            <Alert>{err}</Alert>
            <div className="form-grid">
              <Field label="Full name"><input required minLength={2} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
              <Field label="Email"><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
              <Field label="Password (min 8)"><input type="password" required minLength={8} maxLength={72} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" /></Field>
            </div>
            <div className="modal-foot"><button type="button" className="btn" onClick={() => setForm(null)}>Cancel</button><button className="btn primary">Create</button></div>
          </form>
        </Modal>
      )}
    </>
  );
}
