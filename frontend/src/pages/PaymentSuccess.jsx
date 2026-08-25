import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function PaymentSuccess() {
  const [params] = useSearchParams();
  const { refreshUser } = useAuth();
  const sessionId = params.get("session_id");
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    if (!sessionId) {
      setStatus("error");
      return;
    }
    let attempts = 0;
    const poll = async () => {
      attempts += 1;
      try {
        const { data } = await api.get(`/payments/status/${sessionId}`);
        if (data.payment_status === "paid") {
          setStatus("paid");
          await refreshUser();
          return;
        }
      } catch {
        // keep polling
      }
      if (attempts < 10) setTimeout(poll, 2000);
      else setStatus("timeout");
    };
    poll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-6" data-testid="payment-success-page">
      <div className="max-w-md text-center font-mono">
        {status === "checking" && <p className="text-primary">confirming payment <span className="blink-cursor">█</span></p>}
        {status === "paid" && (
          <>
            <p className="text-primary text-lg mb-4" data-testid="payment-success-message">Premium unlocked. Welcome to the dark side.</p>
            <Link to="/dashboard" className="px-6 py-3 bg-primary text-primary-foreground uppercase" data-testid="payment-success-dashboard-link">
              Go to Library
            </Link>
          </>
        )}
        {(status === "timeout" || status === "error") && (
          <p className="text-destructive" data-testid="payment-error-message">Could not confirm payment. Check your library in a moment.</p>
        )}
      </div>
    </div>
  );
}
