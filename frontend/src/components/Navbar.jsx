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
    <nav className="border-b border-border bg-background/95 backdrop-blur sticky top-0 z-50" data-testid="main-navbar">
      <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
        <Link to="/" className="flex items-center font-serif text-2xl tracking-tight text-foreground" data-testid="navbar-logo">
          <LogoRotator />
        </Link>
        <div className="flex items-center gap-4 font-mono text-sm">
          {user ? (
            <>
              <Link to="/dashboard" className="flex items-center gap-1.5 text-foreground/80 hover:text-primary transition-colors" data-testid="navbar-dashboard-link">
                <BookOpen className="w-4 h-4" /> library
              </Link>
              <span className="px-2 py-1 border border-border text-muted-foreground text-xs uppercase" data-testid="navbar-tier-badge">
                {user.tier_name || "Apprentice"}
              </span>
              <CreditBadge />
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-foreground/80 hover:text-accent transition-colors"
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
                className="px-4 py-2 border border-primary text-primary hover:bg-primary hover:text-primary-foreground transition-colors"
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
