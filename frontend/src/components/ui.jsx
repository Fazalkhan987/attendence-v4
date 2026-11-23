import { useEffect } from "react";
import { label } from "../utils/format";

export function Badge({ value }) {
  return <span className={`badge ${value}`}>{label(value)}</span>;
}

export function Modal({ title, onClose, children, footer, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true">
        <div className="modal-head">
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="btn sm" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {children}
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Field({ label: text, children, full }) {
  return (
    <label className={`field ${full ? "full" : ""}`}>
      {text}
      {children}
    </label>
  );
}

export function Alert({ kind = "error", children }) {
  if (!children) return null;
  return <div className={`alert ${kind}`}>{children}</div>;
}

export function Loading({ loading, error, children }) {
  if (error) return <Alert>{error}</Alert>;
  if (loading) return <div className="empty">Loading…</div>;
  return children;
}

export function Empty({ children = "Nothing to show." }) {
  return <div className="empty">{children}</div>;
}

export function Stat({ value, label: text, tone }) {
  return (
    <div className="stat">
      <div className="v" style={tone ? { color: `var(--${tone})` } : undefined}>{value}</div>
      <div className="l">{text}</div>
    </div>
  );
}

export function Avatar({ name, src, large }) {
  const initials = (name || "?").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return src ? <img className={`avatar ${large ? "lg" : ""}`} src={src} alt={name} /> : <span className={`avatar ${large ? "lg" : ""}`}>{initials}</span>;
}

export function confirmAction(message) {
  return window.confirm(message);
}
