import { Link } from "react-router-dom";
import { BookOpen, Feather, Skull, Trash2, Lock } from "lucide-react";
import api from "@/lib/api";

const TYPE_ICON = { novel: BookOpen, memoir: Feather, biography: Skull };

const STATUS_LABEL = {
  pending: "queued",
  generating: "writing",
  completed: "complete",
  failed: "failed",
};

export function BookCard({ book, onDeleted }) {
  const Icon = TYPE_ICON[book.book_type] || BookOpen;

  const handleDelete = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm("Delete this book permanently?")) return;
    await api.delete(`/books/${book.id}`);
    onDeleted?.(book.id);
  };

  const target = book.status === "completed" ? `/books/${book.id}/read` : `/books/${book.id}/generating`;

  return (
    <Link
      to={target}
      className="gilt-corners group block border border-border bg-card hover:border-primary/60 hover:shadow-[0_22px_48px_rgba(0,0,0,0.65),0_0_28px_rgba(111,242,212,0.09)] hover:-translate-y-1.5 transition-all duration-300 relative overflow-hidden"
      data-testid={`book-card-${book.id}`}
    >
      <button
        onClick={handleDelete}
        className="absolute top-3 right-3 z-10 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
        data-testid={`book-delete-button-${book.id}`}
      >
        <Trash2 className="w-4 h-4" />
      </button>

      {book.cover_image_url ? (
        <img src={book.cover_image_url} alt={book.title} loading="lazy" className="w-full aspect-[16/9] object-cover border-b border-border" data-testid={`book-cover-${book.id}`} />
      ) : book.has_cover_image ? (
        <div className="w-full aspect-[16/9] border-b border-border flex items-center justify-center gap-2 text-muted-foreground font-mono text-xs" data-testid={`book-cover-locked-${book.id}`}>
          <Lock className="w-3.5 h-3.5" /> cover locked
        </div>
      ) : null}

      <div className="p-5">
        <Icon className="w-6 h-6 text-primary mb-4" />
        <h3 className="font-serif italic text-xl text-foreground mb-1 line-clamp-2" data-testid={`book-title-${book.id}`}>
          {book.title}
        </h3>
        <p className="text-xs uppercase tracking-wide text-muted-foreground font-mono mb-3">{book.book_type} · {book.length}</p>
        <div className="flex items-center justify-between text-xs font-mono">
          <span
            className={
              book.status === "completed"
                ? "text-primary"
                : book.status === "failed"
                ? "text-destructive"
                : "text-secondary"
            }
            data-testid={`book-status-${book.id}`}
          >
            [{STATUS_LABEL[book.status] || book.status}]
          </span>
          {book.total_chapters > 0 && (
            <span className="text-muted-foreground">
              {book.current_chapter}/{book.total_chapters} ch
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
