import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function BookGeneration() {
  const { id } = useParams();
  const navigate = useNavigate();

  const { data: book } = useQuery({
    queryKey: ["book", id],
    queryFn: async () => (await api.get(`/books/${id}`)).data,
    refetchInterval: (query) => (["completed", "failed"].includes(query.state.data?.status) ? false : 2500),
  });

  if (!book) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center font-mono text-primary" data-testid="generation-loading">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> loading...
      </div>
    );
  }

  const outline = book.outline || [];

  return (
    <div className="max-w-3xl mx-auto px-6 py-12" data-testid="book-generation-page">
      <p className="font-mono text-primary text-xs mb-2">// LIVE GENERATION</p>
      <h1 className="font-serif text-4xl tracking-tight mb-2" data-testid="generation-book-title">{book.title}</h1>
      <p className="font-mono text-xs text-muted-foreground mb-8">{book.book_type} · {book.length} · {book.genre || "no genre"}</p>

      <div className="border border-primary bg-card p-6 font-mono text-sm shadow-[0_0_20px_rgba(57,255,20,0.08)]" data-testid="generation-terminal">
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
              className={isDone ? "text-primary/70" : isActive ? "text-primary" : "text-muted-foreground"}
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
            generation failed: {book.error || "unknown error"}
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
          className="mt-8 px-8 py-4 bg-primary text-primary-foreground uppercase font-mono text-sm hover:bg-primary/80 transition-colors"
          data-testid="generation-read-button"
        >
          Read Book →
        </button>
      )}
    </div>
  );
}
