import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api, { formatApiErrorDetail } from "@/lib/api";
import { InsufficientCreditsModal } from "@/components/InsufficientCreditsModal";
import { Lock, Zap } from "lucide-react";

const BOOK_TYPES = [
  { value: "novel", label: "Novel" },
  { value: "memoir", label: "Memoir" },
  { value: "biography", label: "Biography" },
];

const LENGTHS = [
  { value: "short", label: "Short", chapters: 5 },
  { value: "medium", label: "Medium", chapters: 8 },
  { value: "long", label: "Long", chapters: 12 },
];

const WORDS_PER_CHAPTER = 900;

export default function CreateBook() {
  const navigate = useNavigate();

  const { data: styles } = useQuery({ queryKey: ["credits-styles"], queryFn: async () => (await api.get("/credits/styles")).data });
  const { data: balanceData } = useQuery({ queryKey: ["credits-balance"], queryFn: async () => (await api.get("/credits/balance")).data });

  const [bookType, setBookType] = useState("novel");
  const [prompt, setPrompt] = useState("");
  const [genre, setGenre] = useState("");
  const [tone, setTone] = useState("");
  const [length, setLength] = useState("short");
  const [style, setStyle] = useState("house");
  const [chimeraA, setChimeraA] = useState("gothic_romantic");
  const [chimeraB, setChimeraB] = useState("noir_detective");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [insufficient, setInsufficient] = useState(null);

  const selectedStyle = styles?.find((s) => s.key === style);
  const multiplier = useMemo(() => {
    if (style === "chimera") {
      // Mirror pricing.style_multiplier's Chimera formula exactly: price off
      // the pricier of the two blended voices, plus a fixed blend premium.
      const a = styles?.find((s) => s.key === chimeraA)?.multiplier ?? 1.0;
      const b = styles?.find((s) => s.key === chimeraB)?.multiplier ?? 1.0;
      return Math.round((Math.max(a, b) + 0.5) * 4) / 4;
    }
    return selectedStyle?.multiplier ?? 1.0;
  }, [style, chimeraA, chimeraB, styles, selectedStyle]);
  const chapters = LENGTHS.find((l) => l.value === length)?.chapters || 5;
  const estimatedCost = useMemo(() => Math.ceil(chapters * WORDS_PER_CHAPTER * multiplier), [chapters, multiplier]);
  const balance = balanceData?.balance ?? 0;
  const canAfford = balance >= estimatedCost;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canAfford) {
      setInsufficient({ required: estimatedCost, available: balance });
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = { book_type: bookType, prompt, genre, tone, length, style };
      if (style === "chimera") {
        payload.style_secondary_a = chimeraA;
        payload.style_secondary_b = chimeraB;
      }
      const { data } = await api.post("/books", payload);
      navigate(`/books/${data.id}/generating`);
    } catch (e) {
      const detail = formatApiErrorDetail(e.response?.data?.detail) || e.message;
      if (e.response?.status === 402) {
        setInsufficient({ required: estimatedCost, available: balance });
      } else {
        setError(detail);
      }
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-12" data-testid="create-book-page">
      <p className="font-mono text-primary text-xs mb-2">// NEW MANUSCRIPT</p>
      <h1 className="font-serif text-4xl tracking-tight mb-8">Describe your book</h1>

      <form onSubmit={handleSubmit} className="space-y-8 font-mono text-sm">
        <div>
          <label className="block text-muted-foreground mb-2">book type</label>
          <div className="grid grid-cols-3 gap-3">
            {BOOK_TYPES.map((t) => (
              <button
                type="button"
                key={t.value}
                onClick={() => setBookType(t.value)}
                className={`py-3 border transition-colors ${bookType === t.value ? "border-primary bg-primary text-primary-foreground" : "border-border hover:border-primary"}`}
                data-testid={`booktype-option-${t.value}`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">prompt / premise</label>
          <textarea
            required
            minLength={10}
            rows={5}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="A lighthouse keeper discovers her predecessor never actually left the island..."
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none"
            data-testid="create-book-prompt-input"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-muted-foreground mb-2">genre</label>
            <input
              value={genre}
              onChange={(e) => setGenre(e.target.value)}
              placeholder="gothic horror"
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
              data-testid="create-book-genre-input"
            />
          </div>
          <div>
            <label className="block text-muted-foreground mb-2">tone</label>
            <input
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              placeholder="melancholic, eerie"
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
              data-testid="create-book-tone-input"
            />
          </div>
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">length</label>
          <div className="grid grid-cols-3 gap-3">
            {LENGTHS.map((l) => (
              <button
                type="button"
                key={l.value}
                onClick={() => setLength(l.value)}
                className={`py-3 border transition-colors text-center ${length === l.value ? "border-primary bg-primary text-primary-foreground" : "border-border hover:border-primary"}`}
                data-testid={`length-option-${l.value}`}
              >
                <div>{l.label}</div>
                <div className="text-[10px] opacity-70">~{l.chapters} chapters</div>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">agency writer style</label>
          <div className="grid grid-cols-2 gap-3">
            {styles?.map((s) => (
              <button
                type="button"
                key={s.key}
                disabled={!s.unlocked}
                onClick={() => setStyle(s.key)}
                className={`py-3 px-3 border transition-colors text-left ${style === s.key ? "border-primary bg-primary text-primary-foreground" : "border-border hover:border-primary"} ${!s.unlocked ? "opacity-40 cursor-not-allowed" : ""}`}
                data-testid={`style-option-${s.key}`}
              >
                <div className="flex items-center gap-1.5">
                  {!s.unlocked && <Lock className="w-3 h-3" />}
                  {s.name}
                </div>
                <div className="text-[10px] opacity-70">
                  {s.key === "chimera" ? `${s.multiplier_min}–${s.multiplier_max}x NC/word (depends on blend)` : `${s.multiplier}x NC/word`}
                  {!s.unlocked && ` · requires ${s.tier_req}`}
                </div>
              </button>
            ))}
          </div>
          {style === "chimera" && (
            <div className="grid grid-cols-2 gap-3 mt-3">
              <select value={chimeraA} onChange={(e) => setChimeraA(e.target.value)} className="bg-transparent border border-border px-3 py-2" data-testid="chimera-style-a">
                {styles?.filter((s) => s.key !== "chimera" && s.key !== "house").map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
              </select>
              <select value={chimeraB} onChange={(e) => setChimeraB(e.target.value)} className="bg-transparent border border-border px-3 py-2" data-testid="chimera-style-b">
                {styles?.filter((s) => s.key !== "chimera" && s.key !== "house").map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
              </select>
            </div>
          )}
        </div>

        <div className="border border-border p-4 flex items-center justify-between" data-testid="create-book-cost-estimate">
          <span className="flex items-center gap-2 text-muted-foreground"><Zap className="w-4 h-4 text-primary" /> estimated cost</span>
          <span className={canAfford ? "text-primary" : "text-destructive"}>{estimatedCost.toLocaleString()} NC (balance: {balance.toLocaleString()} NC)</span>
        </div>

        {error && <p className="text-destructive" data-testid="create-book-error">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-4 bg-primary text-primary-foreground uppercase hover:bg-primary/80 transition-colors disabled:opacity-50"
          data-testid="create-book-submit-button"
        >
          {loading ? "spinning up the engine..." : "generate book"}
        </button>
      </form>

      {insufficient && (
        <InsufficientCreditsModal
          onClose={() => setInsufficient(null)}
          requiredNC={insufficient.required}
          availableNC={insufficient.available}
          actionLabel="Generating this book"
        />
      )}
    </div>
  );
}
