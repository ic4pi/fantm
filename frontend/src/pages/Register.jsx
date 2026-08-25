import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const res = await register(name, email, password);
    setLoading(false);
    if (res.ok) navigate("/dashboard");
    else setError(res.error);
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-6" data-testid="register-page">
      <div className="gilt-corners w-full max-w-sm border border-border bg-card p-8">
        <p className="font-mono text-accent text-xs tracking-widest mb-2">// NEW USER</p>
        <h1 className="font-serif italic text-3xl mb-6">Create account</h1>
        <form onSubmit={handleSubmit} className="space-y-4 font-mono text-sm">
          <div>
            <label className="block text-muted-foreground mb-1">name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
              data-testid="register-name-input"
            />
          </div>
          <div>
            <label className="block text-muted-foreground mb-1">email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
              data-testid="register-email-input"
            />
          </div>
          <div>
            <label className="block text-muted-foreground mb-1">password (min 6 chars)</label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
              data-testid="register-password-input"
            />
          </div>
          {error && <p className="text-destructive" data-testid="register-error">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-primary text-primary-foreground uppercase tracking-wide hover:shadow-[0_0_18px_rgba(111,242,212,0.35)] transition-shadow disabled:opacity-50"
            data-testid="register-submit-button"
          >
            {loading ? "creating..." : "create account"}
          </button>
        </form>
        <p className="font-mono text-xs text-muted-foreground mt-6">
          Already have an account? <Link to="/login" className="text-primary" data-testid="register-login-link">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
