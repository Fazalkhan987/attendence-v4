import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const ADMIN_NAV = [
  ["/admin", "Dashboard", true], ["/admin/employees", "Employees"], ["/admin/departments", "Departments"],
  ["/admin/schedules", "Schedules"], ["/admin/cameras", "Cameras"], ["/admin/attendance", "Attendance"],
  ["/admin/leave", "Leave requests"], ["/admin/reports", "Reports"], ["/admin/events", "Recognition events"],
  ["/admin/audit", "Audit log"], ["/admin/admins", "Administrators"],
];
const EMP_NAV = [
  ["/employee", "My attendance", true], ["/employee/schedule", "My schedule"], ["/employee/leave", "Leave"], ["/employee/profile", "My profile"],
];

export default function Layout({ role }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const items = role === "admin" ? ADMIN_NAV : EMP_NAV;
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand"><span className="dot" /> Smart Attendance</div>
        <nav className="nav" onClick={() => setOpen(false)}>
          {items.map(([to, text, end]) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>{text}</NavLink>
          ))}
        </nav>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn sm menu-btn" onClick={() => setOpen((o) => !o)} aria-label="Menu">☰</button>
          <span className="muted">{role === "admin" ? "Administrator" : "Employee"} portal</span>
          <div className="row">
            <span className="small">{user?.full_name || user?.email}</span>
            <button className="btn sm" onClick={() => { logout(); nav("/login"); }}>Sign out</button>
          </div>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  );
}
