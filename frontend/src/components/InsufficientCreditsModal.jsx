import { Link } from "react-router-dom";
import { X, Zap } from "lucide-react";

export function InsufficientCreditsModal({ onClose, requiredNC, availableNC, actionLabel }) {
  return (
    <div className="fixed inset-0 bg-black/80 z-[200] flex items-center justify-center p-4" data-testid="insufficient-credits-modal">
      <div className="bg-card border border-accent max-w-md w-full p-8 relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-muted-foreground hover:text-accent" data-testid="insufficient-credits-close">
          <X className="w-5 h-5" />
        </button>
        <Zap className="w-7 h-7 text-accent mb-4" />
        <h2 className="font-serif text-3xl text-accent mb-2 crt-glow">Not Enough Neural Credits</h2>
        <p className="text-sm text-muted-foreground font-mono mb-6">
          {actionLabel || "This action"} needs <span className="text-foreground">{requiredNC?.toLocaleString()} NC</span>.
          {" "}You have <span className="text-foreground">{availableNC?.toLocaleString() ?? 0} NC</span>.
        </p>
        <Link
          to="/store"
          onClick={onClose}
          className="block w-full text-center py-3 bg-accent text-accent-foreground hover:bg-accent/80 transition-colors font-mono uppercase"
          data-testid="insufficient-credits-store-link"
        >
          Visit the Store
        </Link>
      </div>
    </div>
  );
}
