import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import AdminDashboard from "./pages/admin/Dashboard";
import Employees from "./pages/admin/Employees";
import Departments from "./pages/admin/Departments";
import Schedules from "./pages/admin/Schedules";
import Cameras from "./pages/admin/Cameras";
import AttendancePage from "./pages/admin/Attendance";
import LeaveAdmin from "./pages/admin/Leave";
import Reports from "./pages/admin/Reports";
import Events from "./pages/admin/Events";
import AuditLog from "./pages/admin/AuditLog";
import Admins from "./pages/admin/Admins";
import MyAttendance from "./pages/employee/MyAttendance";
import MySchedule from "./pages/employee/MySchedule";
import MyLeave from "./pages/employee/MyLeave";
import MyProfile from "./pages/employee/MyProfile";

function Guard({ role, children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="empty">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={user.role === "admin" ? "/admin" : "/employee"} replace />;
  return children;
}

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <div className="empty">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "admin" ? "/admin" : "/employee"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/admin" element={<Guard role="admin"><Layout role="admin" /></Guard>}>
        <Route index element={<AdminDashboard />} />
        <Route path="employees" element={<Employees />} />
        <Route path="departments" element={<Departments />} />
        <Route path="schedules" element={<Schedules />} />
        <Route path="cameras" element={<Cameras />} />
        <Route path="attendance" element={<AttendancePage />} />
        <Route path="leave" element={<LeaveAdmin />} />
        <Route path="reports" element={<Reports />} />
        <Route path="events" element={<Events />} />
        <Route path="audit" element={<AuditLog />} />
        <Route path="admins" element={<Admins />} />
      </Route>
      <Route path="/employee" element={<Guard role="employee"><Layout role="employee" /></Guard>}>
        <Route index element={<MyAttendance />} />
        <Route path="schedule" element={<MySchedule />} />
        <Route path="leave" element={<MyLeave />} />
        <Route path="profile" element={<MyProfile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
