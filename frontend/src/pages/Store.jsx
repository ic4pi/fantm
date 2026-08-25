import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Zap, Check } from "lucide-react";

function useEconomyData() {
  const balance = useQuery({ queryKey: ["credits-balance"], queryFn: async () => (await api.get("/credits/balance")).data });
  const tiers = useQuery({ queryKey: ["credits-tiers"], queryFn: async () => (await api.get("/credits/tiers")).data });
  const store = useQuery({ queryKey: ["credits-store"], queryFn: async () => (await api.get("/credits/store")).data });
  const refills = useQuery({ queryKey: ["credits-refills"], queryFn: async () => (await api.get("/credits/refill-packs")).data });
  const transactions = useQuery({ queryKey: ["credits-transactions"], queryFn: async () => (await api.get("/credits/transactions")).data });
  return { balance, tiers, store, refills, transactions };
}

export default function Store() {
  const { user } = useAuth();
  const { balance, tiers, store, refills, transactions } = useEconomyData();
  const [pending, setPending] = useState(null);

  const checkout = async (purpose, key) => {
    setPending(key);
    try {
      const { data } = await api.post("/payments/checkout", { purpose, key, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch (e) {
      setPending(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-12" data-testid="store-page">
      <p className="font-mono text-accent text-xs tracking-widest mb-2">// THE AGENCY STORE</p>
      <h1 className="font-serif text-4xl tracking-tight mb-2">Neural Credits</h1>
      <p className="font-mono text-sm text-muted-foreground mb-10 flex items-center gap-2">
        <Zap className="w-4 h-4 text-primary" /> Current balance: <span className="text-foreground" data-testid="store-current-balance">{balance.data?.balance?.toLocaleString() ?? "···"} NC</span>
      </p>

      <section className="mb-14">
        <h2 className="font-serif italic text-2xl mb-6">Subscription Tiers</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {tiers.data?.map((t) => {
            const isCurrent = user?.tier === t.key;
            return (
              <div key={t.key} className={`gilt-corners border p-6 bg-card ${isCurrent ? "border-primary/60" : "border-border"}`} data-testid={`tier-card-${t.key}`}>
                <p className="font-mono text-xs uppercase tracking-wide text-muted-foreground mb-1">{t.access}</p>
                <h3 className="font-serif text-2xl mb-3">{t.name}</h3>
                <p className="font-mono text-3xl mb-1">{t.price_usd === 0 ? "Free" : `$${t.price_usd}`}{t.price_usd > 0 && <span className="text-sm text-muted-foreground">/mo</span>}</p>
                <p className="font-mono text-xs text-muted-foreground mb-6">{t.stipend.toLocaleString()} NC / month, rolls over</p>
                {isCurrent ? (
                  <div className="flex items-center gap-2 text-primary font-mono text-xs uppercase" data-testid={`tier-current-${t.key}`}>
                    <Check className="w-4 h-4" /> current plan
                  </div>
                ) : t.lookup_key ? (
                  <button
                    onClick={() => checkout("subscription", t.key)}
                    disabled={pending === t.key}
                    className="w-full py-3 border border-primary text-primary hover:bg-primary hover:text-primary-foreground transition-colors font-mono text-xs uppercase tracking-wide disabled:opacity-50"
                    data-testid={`tier-subscribe-${t.key}`}
                  >
                    {pending === t.key ? "redirecting..." : `Subscribe`}
                  </button>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>

      <section className="mb-14">
        <h2 className="font-serif italic text-2xl mb-6">Agency Store</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {store.data?.map((item) => (
            <div key={item.key} className="gilt-corners border border-border p-6 bg-card flex flex-col" data-testid={`store-item-${item.key}`}>
              <h3 className="font-serif text-xl mb-2">{item.name}</h3>
              <p className="font-mono text-xs text-muted-foreground mb-4 flex-1">{item.desc}</p>
              <p className="font-mono text-sm text-primary mb-4">{item.nc.toLocaleString()} NC</p>
              <button
                onClick={() => checkout("store", item.key)}
                disabled={pending === item.key}
                className="w-full py-3 bg-primary text-primary-foreground hover:shadow-[0_0_16px_rgba(111,242,212,0.3)] transition-shadow font-mono text-xs uppercase tracking-wide disabled:opacity-50"
                data-testid={`store-buy-${item.key}`}
              >
                {pending === item.key ? "redirecting..." : `Buy — $${item.usd.toFixed(2)}`}
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-14">
        <h2 className="font-serif italic text-2xl mb-6">Credit Refills</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {refills.data?.map((pack) => (
            <div key={pack.key} className="gilt-corners border border-border p-6 bg-card" data-testid={`refill-pack-${pack.key}`}>
              <h3 className="font-serif text-xl mb-2">{pack.name}</h3>
              <p className="font-mono text-sm text-primary mb-4">{pack.nc.toLocaleString()} NC</p>
              <button
                onClick={() => checkout("refill", pack.key)}
                disabled={pending === pack.key}
                className="w-full py-3 border border-accent/50 text-accent hover:border-accent hover:text-foreground transition-colors font-mono text-xs uppercase tracking-wide disabled:opacity-50"
                data-testid={`refill-buy-${pack.key}`}
              >
                {pending === pack.key ? "redirecting..." : `Buy — $${pack.usd.toFixed(2)}`}
              </button>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-serif italic text-2xl mb-6">Ledger</h2>
        <div className="gilt-corners border border-border bg-card font-mono text-xs" data-testid="credit-ledger">
          {transactions.data?.length ? (
            transactions.data.map((t) => (
              <div key={t.id} className="flex items-center justify-between px-4 py-3 border-b border-border last:border-b-0" data-testid={`ledger-row-${t.id}`}>
                <span className="text-muted-foreground">{t.description}</span>
                <span className={t.amount >= 0 ? "text-primary" : "text-secondary"}>{t.amount >= 0 ? "+" : ""}{t.amount.toLocaleString()} NC</span>
              </div>
            ))
          ) : (
            <p className="px-4 py-6 text-muted-foreground">No transactions yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}
