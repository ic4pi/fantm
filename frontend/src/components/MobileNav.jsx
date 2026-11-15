import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, LogOut, PenLine, Zap } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

// Phone-only bottom bar for signed-in users: the four things you actually
// do, each a large thumb target. The top bar hides its links below md and
// keeps just the logo and credit badge.
export function MobileNav() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { data } = useQuery({
    queryKey: ["credits-balance"],
    queryFn: async () => (await api.get("/credits/balance")).data,
    staleTime: 15000,
    enabled: !!user,
  });

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  const item = (active) =>
    `flex flex-1 flex-col items-center justify-center gap-1 py-2 font-mono text-[11px] tracking-wide transition-colors ${active ? "text-primary" : "text-foreground/70"}`;

  return (
    <>
      <div className="h-24 md:hidden" aria-hidden="true" />
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-50 border-t border-border navbar-glass flex items-stretch pb-[env(safe-area-inset-bottom)]"
        data-testid="mobile-nav"
      >
        <Link to="/dashboard" className={item(pathname === "/dashboard")} data-testid="mobile-nav-library">
          <BookOpen className="w-6 h-6" /> library
        </Link>
        <Link to="/books/new" className={item(pathname === "/books/new")} data-testid="mobile-nav-new">
          <span className="flex items-center justify-center w-12 h-12 -mt-5 rounded-full bg-primary text-primary-foreground shadow-[0_0_18px_rgba(111,242,212,0.35)]">
            <PenLine className="w-6 h-6" />
          </span>
          new book
        </Link>
        <Link to="/store" className={item(pathname === "/store")} data-testid="mobile-nav-credits">
          <Zap className="w-6 h-6" /> {data ? `${data.balance.toLocaleString()} NC` : "credits"}
        </Link>
        <button type="button" onClick={handleLogout} className={item(false)} data-testid="mobile-nav-exit">
          <LogOut className="w-6 h-6" /> exit
        </button>
      </nav>
    </>
  );
}
