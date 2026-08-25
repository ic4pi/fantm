import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { formatApiErrorDetail } from "@/lib/api";
import { InsufficientCreditsModal } from "@/components/InsufficientCreditsModal";
import { PenLine, Save, FileDown, ImageOff, Lock, Zap } from "lucide-react";

const ILLUSTRATION_UNLOCK_COST = 2000;
const PDF_EXPORT_COST = 5000;

export default function BookReader() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const [activeIdx, setActiveIdx] = useState(0);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [insufficient, setInsufficient] = useState(null);
  const [saving, setSaving] = useState(false);
  const [unlocking, setUnlocking] = useState(false);
  const [exporting, setExporting] = useState(false);

  const { data: book, refetch: refetchBook } = useQuery({
    queryKey: ["book", id],
    queryFn: async () => (await api.get(`/books/${id}`)).data,
  });

  const { data: chapters, refetch } = useQuery({
    queryKey: ["chapters", id],
    queryFn: async () => (await api.get(`/books/${id}/chapters`)).data,
    enabled: !!book,
  });

  const active = chapters?.[activeIdx];

  useEffect(() => {
    if (active) setDraft(active.content);
  }, [active?.id]);

  const handleSave = async () => {
    setSaving(true);
    await api.patch(`/books/${id}/chapters/${active.id}`, { content: draft });
    setSaving(false);
    setEditing(false);
    refetch();
  };

  const handleUnlockIllustrations = async () => {
    setUnlocking(true);
    try {
      await api.post(`/books/${id}/unlock-illustrations`);
      await refetchBook();
      await refetch();
      queryClient.invalidateQueries({ queryKey: ["credits-balance"] });
    } catch (e) {
      if (e.response?.status === 402) {
        setInsufficient({ required: ILLUSTRATION_UNLOCK_COST, available: queryClient.getQueryData(["credits-balance"])?.balance ?? 0 });
      }
    }
    setUnlocking(false);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await api.get(`/books/${id}/pdf`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${book.title}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      await refetchBook();
      queryClient.invalidateQueries({ queryKey: ["credits-balance"] });
    } catch (e) {
      if (e.response?.status === 402) {
        setInsufficient({ required: PDF_EXPORT_COST, available: queryClient.getQueryData(["credits-balance"])?.balance ?? 0 });
      }
    }
    setExporting(false);
  };

  if (!book || !chapters) {
    return <div className="min-h-[70vh] flex items-center justify-center font-mono text-primary" data-testid="reader-loading">loading manuscript...</div>;
  }

  return (
    <div className="flex flex-col lg:flex-row max-w-6xl mx-auto px-6 py-12 gap-10" data-testid="book-reader-page">
      <aside className="lg:w-64 shrink-0">
        <p className="font-mono text-primary text-xs mb-3">// CONTENTS</p>
        {book.cover_image_url ? (
          <img
            src={book.cover_image_url}
            alt={book.title}
            loading="lazy"
            className="w-full aspect-[2/3] object-cover border border-border mb-4"
            data-testid="reader-cover-image"
          />
        ) : book.has_cover_image && !book.illustrations_unlocked ? (
          <button
            onClick={handleUnlockIllustrations}
            disabled={unlocking}
            className="w-full aspect-[2/3] border border-border flex flex-col items-center justify-center gap-2 text-muted-foreground font-mono text-xs mb-4 hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
            data-testid="reader-cover-locked"
          >
            <Lock className="w-4 h-4" /> {unlocking ? "unlocking..." : `unlock — ${ILLUSTRATION_UNLOCK_COST.toLocaleString()} NC`}
          </button>
        ) : null}
        <h2 className="font-serif text-2xl mb-4">{book.title}</h2>
        <div className="flex flex-col gap-1 font-mono text-sm mb-6" data-testid="reader-chapter-list">
          {chapters.map((c, idx) => (
            <button
              key={c.id}
              onClick={() => { setActiveIdx(idx); setEditing(false); }}
              className={`text-left px-3 py-2 border-l-2 transition-colors ${idx === activeIdx ? "border-primary text-primary bg-secondary" : "border-border text-muted-foreground hover:text-foreground"}`}
              data-testid={`reader-chapter-nav-${idx}`}
            >
              {idx + 1}. {c.title}
            </button>
          ))}
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 border border-border hover:border-primary transition-colors font-mono text-xs uppercase disabled:opacity-50"
          data-testid="reader-export-pdf-button"
        >
          <FileDown className="w-4 h-4" />
          {exporting ? "exporting..." : book.pdf_unlocked ? "export pdf" : (
            <span className="flex items-center gap-1"><Zap className="w-3 h-3" /> export — {PDF_EXPORT_COST.toLocaleString()} NC</span>
          )}
        </button>
      </aside>

      <main className="flex-1 max-w-2xl">
        <div className="flex items-center justify-between mb-6">
          <p className="font-mono text-xs text-muted-foreground">Chapter {activeIdx + 1} of {chapters.length}</p>
          {!editing ? (
            <button
              onClick={() => setEditing(true)}
              className="flex items-center gap-1.5 text-xs font-mono uppercase text-muted-foreground hover:text-primary transition-colors"
              data-testid="reader-edit-button"
            >
              <PenLine className="w-3.5 h-3.5" /> edit
            </button>
          ) : (
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 text-xs font-mono uppercase text-primary"
              data-testid="reader-save-button"
            >
              <Save className="w-3.5 h-3.5" /> {saving ? "saving..." : "save"}
            </button>
          )}
        </div>

        <h1 className="font-serif text-3xl mb-6" data-testid="reader-chapter-title">{active?.title}</h1>

        {active?.image_url ? (
          <img
            src={active.image_url}
            alt={active.title}
            loading="lazy"
            className="mb-8 w-full aspect-[16/9] object-cover border border-border"
            data-testid="reader-illustration-image"
          />
        ) : active?.has_image && !book.illustrations_unlocked ? (
          <button
            onClick={handleUnlockIllustrations}
            disabled={unlocking}
            className="mb-8 w-full aspect-[16/9] border border-border flex items-center justify-center text-muted-foreground font-mono text-xs gap-2 hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
            data-testid="reader-illustration-locked"
          >
            <Lock className="w-4 h-4" /> {unlocking ? "unlocking..." : `unlock illustrations — ${ILLUSTRATION_UNLOCK_COST.toLocaleString()} NC`}
          </button>
        ) : (
          <div className="mb-8 aspect-[16/9] border border-border flex items-center justify-center text-muted-foreground font-mono text-xs gap-2" data-testid="reader-illustration-placeholder">
            <ImageOff className="w-4 h-4" /> illustration generating...
          </div>
        )}

        {editing ? (
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={20}
            className="w-full bg-transparent border border-primary outline-none px-4 py-3 font-serif text-lg leading-relaxed resize-none"
            data-testid="reader-edit-textarea"
          />
        ) : (
          <div className="font-serif text-lg leading-relaxed whitespace-pre-wrap text-foreground/90" data-testid="reader-chapter-content">
            {active?.content}
          </div>
        )}
      </main>

      {insufficient && (
        <InsufficientCreditsModal
          onClose={() => setInsufficient(null)}
          requiredNC={insufficient.required}
          availableNC={insufficient.available}
          actionLabel="This action"
        />
      )}
    </div>
  );
}
