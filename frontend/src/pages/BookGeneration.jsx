import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Loader2, Zap } from "lucide-react";

export default function BookGeneration() {
  const { id } = useParams();
  const navigate = useNavigate();

  const queryClient = useQueryClient();

  const { data: book } = useQuery({
    queryKey: ["book", id],
    queryFn: async () => (await api.get(`/books/${id}`)).data,
    refetchInterval: (query) => (["completed", "failed"].includes(query.state.data?.status) ? false : 2500),
  });
  const { data: balanceData } = useQuery({
    queryKey: ["credits-balance"],
    queryFn: async () => (await api.get("/credits/balance")).data,
  });

  // The unused part of the up-front hold is refunded when the book ends, so
  // re-read the balance then rather than showing the held amount.
  const ended = book && ["completed", "failed"].includes(book.status);
  useEffect(() => {
    if (ended) queryClient.invalidateQueries({ queryKey: ["credits-balance"] });
  }, [ended, queryClient]);

  if (!book) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center font-mono text-primary" data-testid="generation-loading">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> loading...
      </div>
    );
  }

  const outline = book.outline || [];
  const total = book.total_chapters || outline.length || 0;
  const doneChapters = book.status === "completed" ? total : Math.max(0, (book.current_chapter || 1) - 1);
  const percent = book.status === "completed" ? 100 : total ? Math.round((doneChapters / total) * 100) : 0;

  return (
    <div className="max-w-3xl mx-auto px-6 py-12" data-testid="book-generation-page">
      <p className="font-mono text-accent text-xs tracking-widest mb-2">// THE SITTING</p>
      <h1 className="font-serif text-4xl tracking-tight mb-2" data-testid="generation-book-title">{book.title}</h1>
      <p className="font-mono text-xs text-muted-foreground mb-8 tracking-wide">{book.book_type} · {book.length} · {book.genre || "no genre"}</p>

      <div className="mb-6" data-testid="generation-progress">
        <div className="flex items-end justify-between font-mono mb-2">
          <span className="text-4xl sm:text-5xl text-primary crt-glow" data-testid="generation-percent">{percent}%</span>
          <span className="text-xs text-muted-foreground tracking-wide">
            {book.status === "failed" ? "stopped" : book.status === "completed" ? "finished" : total ? `chapter ${Math.min(doneChapters + 1, total)} of ${total}` : "planning the outline"}
          </span>
        </div>
        <div className="h-3 border border-primary/40 bg-card" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
          <div className={`h-full transition-all duration-700 ${book.status === "failed" ? "bg-destructive" : "bg-primary"}`} style={{ width: `${percent}%` }} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-xs text-muted-foreground mt-3">
          <Link to="/store" className="flex items-center gap-1.5 text-primary" data-testid="generation-balance">
            <Zap className="w-3.5 h-3.5" /> {balanceData ? balanceData.balance.toLocaleString() : "···"} NC
          </Link>
          <span>An estimate was held up front. Whatever isn't used comes back when the book finishes.</span>
        </div>
      </div>

      <div className="gilt-corners border border-primary/40 bg-card p-6 font-mono text-sm shadow-[0_0_24px_rgba(111,242,212,0.10)]" data-testid="generation-terminal">
        {book.status === "pending" && (
          <p className="text-primary">[architecting outline...] <span className="blink-cursor">█</span></p>
        )}

        {outline.length === 0 && book.status !== "pending" && book.status !== "failed" && (
          <p className="text-primary">[preparing chapters...] <span className="blink-cursor">█</span></p>
        )}

        {outline.map((ch, idx) => {
          const chapterNum = idx + 1;
          const isDone = chapterNum < book.current_chapter || book.status === "completed";
          const isActive = chapterNum === book.current_chapter && book.status === "generating";
          return (
            <p
              key={idx}
              className={isDone ? "text-primary/70" : isActive ? "text-secondary" : "text-muted-foreground"}
              data-testid={`generation-chapter-row-${idx}`}
            >
              [{chapterNum}/{book.total_chapters}] {ch.title}
              {isDone && " ... done"}
              {isActive && <> ... writing <span className="blink-cursor">█</span></>}
            </p>
          );
        })}

        {book.status === "failed" && (
          <p className="text-destructive mt-4" data-testid="generation-error">
            generation failed: {book.error || "unknown error"}. You were only charged for the chapters that were written.
          </p>
        )}

        {book.status === "completed" && (
          <p className="text-primary mt-4" data-testid="generation-complete-message">
            status: complete — {book.total_chapters} chapters ready.
          </p>
        )}
      </div>

      {book.status === "completed" && (
        <button
          onClick={() => navigate(`/books/${id}/read`)}
          className="mt-8 px-8 py-4 bg-primary text-primary-foreground uppercase font-mono text-sm tracking-wide hover:shadow-[0_0_20px_rgba(111,242,212,0.35)] transition-shadow"
          data-testid="generation-read-button"
        >
          Read Book →
        </button>
      )}
    </div>
  );
}
