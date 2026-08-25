import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { BookOpen, LogOut } from "lucide-react";
import { CreditBadge } from "@/components/CreditBadge";
import { LogoRotator } from "@/components/LogoRotator";

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <nav className="border-b border-border navbar-glass sticky top-0 z-50" data-testid="main-navbar">
      <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-3.5">
        <Link to="/" className="flex items-center font-serif text-2xl tracking-tight text-foreground" data-testid="navbar-logo">
          <LogoRotator />
        </Link>
        <div className="flex items-center gap-4 font-mono text-sm">
          {user ? (
            <>
              <Link to="/dashboard" className="flex items-center gap-1.5 text-foreground/80 hover:text-primary transition-colors" data-testid="navbar-dashboard-link">
                <BookOpen className="w-4 h-4" /> library
              </Link>
              <span className="px-2 py-1 border border-accent/40 text-accent text-xs uppercase tracking-wider" data-testid="navbar-tier-badge">
                {user.tier_name || "Apprentice"}
              </span>
              <CreditBadge />
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-foreground/80 hover:text-secondary transition-colors"
                data-testid="navbar-logout-button"
              >
                <LogOut className="w-4 h-4" /> exit
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-foreground/80 hover:text-primary transition-colors" data-testid="navbar-login-link">
                login
              </Link>
              <Link
                to="/register"
                className="px-4 py-2 border border-primary text-primary hover:bg-primary hover:text-primary-foreground hover:shadow-[0_0_18px_rgba(111,242,212,0.35)] transition-all"
                data-testid="navbar-register-link"
              >
                sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
