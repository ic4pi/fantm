import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export function ProtectedRoute({ children }) {
  const { user } = useAuth();
  if (user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-primary font-mono" data-testid="auth-loading">
        <span className="blink-cursor">█</span>&nbsp;checking session...
      </div>
    );
  }
  if (user === false) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
