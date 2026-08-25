import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { BookCard } from "@/components/BookCard";
import { Plus, Zap } from "lucide-react";

export default function Dashboard() {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [books, setBooks] = useState([]);

  const { data } = useQuery({
    queryKey: ["books"],
    queryFn: async () => (await api.get("/books")).data,
  });

  const { data: balanceData } = useQuery({
    queryKey: ["credits-balance"],
    queryFn: async () => (await api.get("/credits/balance")).data,
  });

  useEffect(() => {
    if (data) setBooks(data);
  }, [data]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const handleDeleted = (id) => setBooks((b) => b.filter((x) => x.id !== id));

  return (
    <div className="max-w-6xl mx-auto px-6 py-12" data-testid="dashboard-page">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-10">
        <div>
          <p className="font-mono text-primary text-xs mb-2">// YOUR LIBRARY</p>
          <h1 className="font-serif text-4xl tracking-tight">Manuscripts</h1>
          {balanceData && (
            <p className="font-mono text-xs text-muted-foreground mt-2 flex items-center gap-1.5" data-testid="dashboard-balance">
              <Zap className="w-3.5 h-3.5 text-primary" /> {balanceData.balance.toLocaleString()} NC · {balanceData.tier_name} tier
            </p>
          )}
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => navigate("/store")}
            className="px-5 py-3 border border-accent text-accent hover:bg-accent hover:text-accent-foreground transition-colors font-mono text-sm uppercase"
            data-testid="dashboard-store-button"
          >
            Store
          </button>
          <button
            onClick={() => navigate("/books/new")}
            className="px-5 py-3 bg-primary text-primary-foreground hover:bg-primary/80 transition-colors font-mono text-sm uppercase flex items-center gap-2"
            data-testid="dashboard-new-book-button"
          >
            <Plus className="w-4 h-4" /> New Book
          </button>
        </div>
      </div>

      {books.length === 0 ? (
        <div className="border border-dashed border-border p-16 text-center font-mono text-muted-foreground" data-testid="dashboard-empty-state">
          No manuscripts yet. Start your first one.
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="dashboard-book-grid">
          {books.map((b) => (
            <BookCard key={b.id} book={b} onDeleted={handleDeleted} />
          ))}
        </div>
      )}
    </div>
  );
}
