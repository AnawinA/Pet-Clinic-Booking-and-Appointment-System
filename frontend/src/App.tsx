import { Navigate, Route, Routes } from "react-router-dom";
import { homeFor, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Spinner } from "./components/ui";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import NotificationsPage from "./pages/NotificationsPage";
import PetsPage from "./pages/owner/PetsPage";
import BookPage from "./pages/owner/BookPage";
import AppointmentsPage from "./pages/owner/AppointmentsPage";
import AppointmentDetailPage from "./pages/owner/AppointmentDetailPage";
import QueuePage from "./pages/owner/QueuePage";
import VetSchedulePage from "./pages/vet/SchedulePage";
import CaseDetailPage from "./pages/vet/CaseDetailPage";
import BoardPage from "./pages/staff/BoardPage";
import ShiftsPage from "./pages/staff/ShiftsPage";
import RescheduleApprovalsPage from "./pages/staff/RescheduleApprovalsPage";
import AuditPage from "./pages/staff/AuditPage";
import AccountsPage from "./pages/staff/AccountsPage";

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  return <Navigate to={user ? homeFor(user.role) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        element={
          <ProtectedRoute role="OWNER">
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/owner/appointments" element={<AppointmentsPage />} />
        <Route path="/owner/appointments/:id" element={<AppointmentDetailPage />} />
        <Route path="/owner/book" element={<BookPage />} />
        <Route path="/owner/pets" element={<PetsPage />} />
        <Route path="/owner/queue" element={<QueuePage />} />
        <Route path="/owner/notifications" element={<NotificationsPage />} />
      </Route>

      <Route
        element={
          <ProtectedRoute role="VET">
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/vet/schedule" element={<VetSchedulePage />} />
        <Route path="/vet/cases/:id" element={<CaseDetailPage />} />
        <Route path="/vet/notifications" element={<NotificationsPage />} />
      </Route>

      <Route
        element={
          <ProtectedRoute role="STAFF">
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/staff/board" element={<BoardPage />} />
        <Route path="/staff/shifts" element={<ShiftsPage />} />
        <Route path="/staff/reschedule-requests" element={<RescheduleApprovalsPage />} />
        <Route path="/staff/audit" element={<AuditPage />} />
        <Route path="/staff/accounts" element={<AccountsPage />} />
        <Route path="/staff/notifications" element={<NotificationsPage />} />
      </Route>

      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  );
}
