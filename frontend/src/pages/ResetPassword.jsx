import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function ResetPassword() {
  const { resetPassword } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setLoading(true);
    setError("");
    const res = await resetPassword(token, password);
    setLoading(false);
    if (res.ok) navigate("/login");
    else setError(res.error);
  };

  if (!token) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-6" data-testid="reset-password-page">
        <div className="gilt-corners w-full max-w-sm border border-border bg-card p-8 font-mono text-sm">
          <p className="text-destructive" data-testid="reset-password-no-token">
            This reset link is missing its token. Request a new one from the{" "}
            <Link to="/forgot-password" className="text-primary">forgot password</Link> page.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-6" data-testid="reset-password-page">
      <div className="gilt-corners w-full max-w-sm border border-border bg-card p-8">
        <p className="font-mono text-accent text-xs tracking-widest mb-2">// AUTH</p>
        <h1 className="font-serif italic text-3xl mb-6">Set a new password</h1>
        <form onSubmit={handleSubmit} className="space-y-4 font-mono text-sm">
          <div>
            <label className="block text-muted-foreground mb-1">new password (min 6 chars)</label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
              data-testid="reset-password-password-input"
            />
          </div>
          <div>
            <label className="block text-muted-foreground mb-1">confirm password</label>
            <input
              type="password"
              required
              minLength={6}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
              data-testid="reset-password-confirm-input"
            />
          </div>
          {error && <p className="text-destructive" data-testid="reset-password-error">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-primary text-primary-foreground uppercase tracking-wide hover:shadow-[0_0_18px_rgba(111,242,212,0.35)] transition-shadow disabled:opacity-50"
            data-testid="reset-password-submit-button"
          >
            {loading ? "saving..." : "set new password"}
          </button>
        </form>
      </div>
    </div>
  );
}
