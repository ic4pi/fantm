import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function ForgotPassword() {
  const { forgotPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const res = await forgotPassword(email);
    setLoading(false);
    if (res.ok) setSent(true);
    else setError(res.error);
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-6" data-testid="forgot-password-page">
      <div className="gilt-corners w-full max-w-sm border border-border bg-card p-8">
        <p className="font-mono text-accent text-xs tracking-widest mb-2">// AUTH</p>
        <h1 className="font-serif italic text-3xl mb-6">Reset password</h1>

        {sent ? (
          <p className="font-mono text-sm text-muted-foreground" data-testid="forgot-password-sent">
            If an account exists for that email, a reset link is on its way. It expires in 30 minutes.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 font-mono text-sm">
            <div>
              <label className="block text-muted-foreground mb-1">email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
                data-testid="forgot-password-email-input"
              />
            </div>
            {error && <p className="text-destructive" data-testid="forgot-password-error">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-primary text-primary-foreground uppercase tracking-wide hover:shadow-[0_0_18px_rgba(111,242,212,0.35)] transition-shadow disabled:opacity-50"
              data-testid="forgot-password-submit-button"
            >
              {loading ? "sending..." : "send reset link"}
            </button>
          </form>
        )}

        <p className="font-mono text-xs text-muted-foreground mt-6">
          <Link to="/login" className="text-primary" data-testid="forgot-password-login-link">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
