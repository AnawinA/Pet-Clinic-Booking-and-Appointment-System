import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { homeFor, useAuth } from "../auth/AuthContext";
import type { UserRole } from "../api/types";
import { Spinner } from "./ui";

export function ProtectedRoute({
  role,
  children,
}: {
  role?: UserRole;
  children: ReactNode;
}) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <Spinner label="กำลังตรวจสอบสิทธิ์..." />;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (role && user.role !== role) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}
