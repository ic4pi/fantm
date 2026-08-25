import { Link } from "react-router-dom";

export default function PaymentCancel() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-6" data-testid="payment-cancel-page">
      <div className="max-w-md text-center font-mono">
        <p className="text-muted-foreground mb-4">Checkout cancelled. No charge was made.</p>
        <Link to="/dashboard" className="px-6 py-3 border border-primary text-primary uppercase" data-testid="payment-cancel-dashboard-link">
          Back to Library
        </Link>
      </div>
    </div>
  );
}
