import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Zap } from "lucide-react";

export function CreditBadge() {
  const { data } = useQuery({
    queryKey: ["credits-balance"],
    queryFn: async () => (await api.get("/credits/balance")).data,
    staleTime: 15000,
  });

  return (
    <Link
      to="/store"
      className="flex items-center gap-1.5 px-2 py-1 border border-primary/50 text-primary hover:bg-primary hover:text-primary-foreground transition-colors font-mono text-xs"
      data-testid="navbar-credit-badge"
    >
      <Zap className="w-3.5 h-3.5" />
      {data ? data.balance.toLocaleString() : "···"} NC
    </Link>
  );
}
