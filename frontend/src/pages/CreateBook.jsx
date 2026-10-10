import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api, { formatApiErrorDetail } from "@/lib/api";
import { InsufficientCreditsModal } from "@/components/InsufficientCreditsModal";
import ListInput from "@/components/ListInput";
import RevealsInput from "@/components/RevealsInput";
import { NewTableForm, TableGrid } from "@/components/TableGrid";
import { MAX_TABLES, POV_OPTIONS } from "@/lib/storyBible";
import { FileUp, Lock, Zap } from "lucide-react";

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

const MAX_THEMES = 15;

function SectionHeading({ children, note }) {
  return (
    <div className="pt-4 border-t border-border">
      <p className="font-mono text-accent text-xs tracking-widest">{children}</p>
      {note && <p className="text-[11px] text-muted-foreground mt-1 opacity-80">{note}</p>}
    </div>
  );
}

// A book premise can take a while to dictate. Nothing else on this page
// persists it, so a stray reload/backgrounded-tab reset used to wipe
// whatever the user had typed with no way back — draft it to localStorage
// as they go and restore it on mount.
const DRAFT_KEY = "fantm:create-book-draft";

function loadDraft() {
  try {
    return JSON.parse(localStorage.getItem(DRAFT_KEY)) || {};
  } catch {
    return {};
  }
}

export default function CreateBook() {
  const navigate = useNavigate();
  const draft = useMemo(loadDraft, []);

  const { data: styles } = useQuery({ queryKey: ["credits-styles"], queryFn: async () => (await api.get("/credits/styles")).data });
  const { data: balanceData } = useQuery({ queryKey: ["credits-balance"], queryFn: async () => (await api.get("/credits/balance")).data });

  const [bookType, setBookType] = useState(draft.bookType ?? "novel");
  const [title, setTitle] = useState(draft.title ?? "");
  const [prompt, setPrompt] = useState(draft.prompt ?? "");
  const [subject, setSubject] = useState(draft.subject ?? "");
  const [period, setPeriod] = useState(draft.period ?? "");
  const [themes, setThemes] = useState(draft.themes ?? []);
  const [pov, setPov] = useState(draft.pov ?? "");
  const [styleNotes, setStyleNotes] = useState(draft.styleNotes ?? "");
  const [influences, setInfluences] = useState(draft.influences ?? "");
  const [tables, setTables] = useState(draft.tables ?? []);
  const [reveals, setReveals] = useState(draft.reveals ?? []);
  const [setting, setSetting] = useState(draft.setting ?? "");
  const [backstory, setBackstory] = useState(draft.backstory ?? "");
  const [chapterOutline, setChapterOutline] = useState(draft.chapterOutline ?? "");
  const [timeline, setTimeline] = useState(draft.timeline ?? "");
  const [worldRules, setWorldRules] = useState(draft.worldRules ?? []);
  const [newRule, setNewRule] = useState("");
  const [characters, setCharacters] = useState(draft.characters ?? []);
  const [charName, setCharName] = useState("");
  const [charRole, setCharRole] = useState("");
  const [charDesc, setCharDesc] = useState("");

  const MAX_WORLD_RULES = 30;
  const addWorldRule = () => {
    if (!newRule.trim() || worldRules.length >= MAX_WORLD_RULES) return;
    setWorldRules((r) => [...r, newRule.trim()]);
    setNewRule("");
  };
  const removeWorldRule = (idx) => setWorldRules((r) => r.filter((_, i) => i !== idx));
  const [genre, setGenre] = useState(draft.genre ?? "");
  const [tone, setTone] = useState(draft.tone ?? "");
  const [length, setLength] = useState(draft.length ?? "short");
  const [style, setStyle] = useState(draft.style ?? "house");
  const [chimeraA, setChimeraA] = useState(draft.chimeraA ?? "anne_rousseau");
  const [chimeraB, setChimeraB] = useState(draft.chimeraB ?? "raymond_chandley");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [insufficient, setInsufficient] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importReport, setImportReport] = useState(null);

  const MAX_CHARACTERS = 12;

  const addCharacter = () => {
    if (!charName.trim() || characters.length >= MAX_CHARACTERS) return;
    setCharacters((c) => [...c, { name: charName.trim(), role: charRole.trim(), description: charDesc.trim() }]);
    setCharName("");
    setCharRole("");
    setCharDesc("");
  };
  const removeCharacter = (idx) => setCharacters((c) => c.filter((_, i) => i !== idx));

  const addTable = ({ name, columns }) =>
    setTables((ts) => [...ts, { key: `${Date.now()}-${ts.length}`, name, columns, rows: [] }]);
  const updateTable = (key, next) => setTables((ts) => ts.map((t) => (t.key === key ? next : t)));
  const removeTable = (key) => setTables((ts) => ts.filter((t) => t.key !== key));

  useEffect(() => {
    try {
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({
          bookType, title, prompt, subject, period, setting, backstory, themes, chapterOutline, timeline, worldRules, reveals, characters, tables,
          genre, tone, pov, styleNotes, influences, length, style, chimeraA, chimeraB,
        })
      );
    } catch {
      // best-effort — private browsing / storage full shouldn't block writing
    }
  }, [
    bookType, title, prompt, subject, period, setting, backstory, themes, chapterOutline, timeline, worldRules, reveals, characters, tables,
    genre, tone, pov, styleNotes, influences, length, style, chimeraA, chimeraB,
  ]);

  // Fill only what's still empty: an import never overwrites anything the
  // author already typed. Lists append (deduped), tables are added.
  const applyImport = (fileName, data) => {
    const filled = [];
    const kept = [];
    const textFields = [
      ["title", title, setTitle, "title"],
      ["premise", prompt, setPrompt, "prompt"],
      ["subject", subject, setSubject, "subject"],
      ["time period", period, setPeriod, "period"],
      ["setting", setting, setSetting, "setting"],
      ["backstory", backstory, setBackstory, "backstory"],
      ["chapter outline", chapterOutline, setChapterOutline, "chapter_outline"],
      ["timeline", timeline, setTimeline, "timeline"],
      ["genre", genre, setGenre, "genre"],
      ["tone", tone, setTone, "tone"],
      ["point of view", pov, setPov, "pov"],
      ["style notes", styleNotes, setStyleNotes, "style_notes"],
      ["influences", influences, setInfluences, "influences"],
    ];
    if (data.book_type && !prompt.trim()) setBookType(data.book_type);
    for (const [label, current, set, key] of textFields) {
      if (!data[key]) continue;
      if (current.trim()) kept.push(label);
      else {
        set(data[key]);
        filled.push(label);
      }
    }
    const addStrings = (label, current, set, incoming, cap) => {
      const have = new Set(current.map((x) => x.toLowerCase()));
      const fresh = (incoming || []).filter((x) => !have.has(x.toLowerCase()));
      const next = [...current, ...fresh].slice(0, cap);
      if (next.length > current.length) {
        set(next);
        filled.push(`${label} (+${next.length - current.length})`);
      }
    };
    addStrings("themes", themes, setThemes, data.themes, MAX_THEMES);
    addStrings("world rules", worldRules, setWorldRules, data.world_rules, MAX_WORLD_RULES);
    const names = new Set(characters.map((c) => c.name.toLowerCase()));
    const newChars = (data.characters || []).filter((c) => !names.has(c.name.toLowerCase()));
    const nextChars = [...characters, ...newChars].slice(0, MAX_CHARACTERS);
    if (nextChars.length > characters.length) {
      setCharacters(nextChars);
      filled.push(`characters (+${nextChars.length - characters.length})`);
    }
    const room = MAX_TABLES - tables.length;
    const newTables = (data.tables || []).slice(0, room);
    if (newTables.length) {
      setTables((ts) => [...ts, ...newTables.map((t, i) => ({ ...t, key: `${Date.now()}-import-${i}` }))]);
      filled.push(`tables: ${newTables.map((t) => t.name).join(", ")}`);
    }
    setImportReport({ fileName, filled, kept, partial: data.chars_read < data.chars_total, read: data.chars_read, total: data.chars_total });
  };

  const handleImport = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    setError("");
    setImportReport(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post("/books/extract", form);
      applyImport(file.name, data);
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setImporting(false);
    }
  };

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
      const isLife = bookType !== "novel";
      const payload = {
        book_type: bookType, title, prompt, setting, backstory, themes,
        subject: isLife ? subject : "", period: isLife ? period : "",
        chapter_outline: chapterOutline, timeline, world_rules: worldRules, reveals,
        characters, genre, tone, pov, style_notes: styleNotes, influences, length, style,
        tables: tables.map(({ name, columns, rows }) => ({ name, columns, rows })),
      };
      if (style === "chimera") {
        payload.style_secondary_a = chimeraA;
        payload.style_secondary_b = chimeraB;
      }
      const { data } = await api.post("/books", payload);
      try {
        localStorage.removeItem(DRAFT_KEY);
      } catch {
        // ignore
      }
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
      <p className="font-mono text-accent text-xs tracking-widest mb-2">// NEW MANUSCRIPT</p>
      <h1 className="font-serif text-4xl tracking-tight mb-8">Describe your book</h1>

      <div className="border border-border p-4 mb-8 font-mono text-sm" data-testid="create-book-import">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-foreground/90">Already have notes?</p>
            <p className="text-[11px] text-muted-foreground opacity-80">
              Upload a .txt, .md, .docx or .pdf. The AI pulls out what's there and fills the form, only where it's still empty. Nothing generates until you've checked it.
            </p>
          </div>
          <label className={`shrink-0 flex items-center gap-2 py-2 px-4 border border-primary/50 text-primary hover:border-primary transition-colors cursor-pointer ${importing ? "opacity-50 pointer-events-none" : ""}`}>
            <FileUp className="w-4 h-4" /> {importing ? "reading your document..." : "import a document"}
            <input type="file" accept=".txt,.md,.docx,.pdf" onChange={handleImport} className="hidden" disabled={importing} data-testid="create-book-import-input" />
          </label>
        </div>
        {importReport && (
          <div className="mt-3 pt-3 border-t border-border text-[11px] space-y-1" data-testid="create-book-import-report">
            <p className="text-primary">Imported from {importReport.fileName}. Review every field below for accuracy before generating.</p>
            <p className="text-muted-foreground">
              {importReport.filled.length ? `Filled: ${importReport.filled.join(" · ")}` : "Nothing new found to fill."}
            </p>
            {importReport.kept.length > 0 && (
              <p className="text-muted-foreground">Kept what you'd already typed for: {importReport.kept.join(", ")}</p>
            )}
            {importReport.partial && (
              <p className="text-destructive">
                Only the first {importReport.read.toLocaleString()} of {importReport.total.toLocaleString()} characters were read. Import the rest as a second file, or add it by hand.
              </p>
            )}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-8 font-mono text-sm">
        <div>
          <label className="block text-muted-foreground mb-2">book type</label>
          <div className="grid grid-cols-3 gap-3">
            {BOOK_TYPES.map((t) => (
              <button
                type="button"
                key={t.value}
                onClick={() => setBookType(t.value)}
                className={`py-3 border transition-all ${bookType === t.value ? "border-primary text-primary shadow-[0_0_14px_rgba(111,242,212,0.25)]" : "border-border hover:border-primary/50"}`}
                data-testid={`booktype-option-${t.value}`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">title <span className="opacity-60">(optional — leave blank and the AI names it)</span></label>
          <input
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Blue Line"
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
            data-testid="create-book-title-input"
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-muted-foreground">prompt / premise</label>
            <span className="text-[10px] text-muted-foreground">{prompt.length}/4000</span>
          </div>
          <textarea
            required
            minLength={10}
            maxLength={4000}
            rows={5}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="A lighthouse keeper discovers her predecessor never actually left the island..."
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none"
            data-testid="create-book-prompt-input"
          />
        </div>

        {bookType !== "novel" && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-muted-foreground mb-2">{bookType === "memoir" ? "whose memoir" : "subject"}</label>
              <input
                maxLength={200}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder={bookType === "memoir" ? "you, or the name you write under" : "Amelia Earhart"}
                className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
                data-testid="create-book-subject-input"
              />
            </div>
            <div>
              <label className="block text-muted-foreground mb-2">time period covered</label>
              <input
                maxLength={200}
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                placeholder="1897 – 1937"
                className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
                data-testid="create-book-period-input"
              />
            </div>
          </div>
        )}

        <SectionHeading note="Everything below is canon. The AI plans the outline around it and re-reads it before every chapter. All optional.">
          // STORY BIBLE
        </SectionHeading>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-muted-foreground">setting <span className="opacity-60">(optional)</span></label>
            <span className="text-[10px] text-muted-foreground">{setting.length}/2000</span>
          </div>
          <textarea
            rows={3}
            maxLength={2000}
            value={setting}
            onChange={(e) => setSetting(e.target.value)}
            placeholder="A fog-locked archipelago in 1920s Maine, decades before radio reached the outer islands..."
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none"
            data-testid="create-book-setting-input"
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-muted-foreground">backstory / history <span className="opacity-60">(optional)</span></label>
            <span className="text-[10px] text-muted-foreground">{backstory.length}/3000</span>
          </div>
          <textarea
            rows={3}
            maxLength={3000}
            value={backstory}
            onChange={(e) => setBackstory(e.target.value)}
            placeholder="The lighthouse has changed keepers seven times in forty years. None have stayed past a year..."
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none"
            data-testid="create-book-backstory-input"
          />
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">themes <span className="opacity-60">(optional — up to {MAX_THEMES})</span></label>
          <ListInput items={themes} onChange={setThemes} max={MAX_THEMES} placeholder="redemption, loyalty, what winning costs..." testId="create-book-theme" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-muted-foreground">chapter outline <span className="opacity-60">(optional — paste a rough one, or write it here)</span></label>
            <span className="text-[10px] text-muted-foreground">{chapterOutline.length}/6000</span>
          </div>
          <textarea
            rows={6}
            maxLength={6000}
            value={chapterOutline}
            onChange={(e) => setChapterOutline(e.target.value)}
            placeholder={"Ch 1: Mara arrives at the lighthouse, finds the logbook mid-sentence.\nCh 2: The first storm, radio goes dead...\n(one line or a paragraph per chapter — as rough as you want)"}
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none"
            data-testid="create-book-chapter-outline-input"
          />
          <p className="text-[10px] text-muted-foreground mt-1 opacity-70">
            Leave blank and the AI builds the outline from your premise instead. Fill this in and it builds from your chapters, not its own.
          </p>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-muted-foreground">timeline <span className="opacity-60">(optional — a simpler alternative to a chapter outline)</span></label>
            <span className="text-[10px] text-muted-foreground">{timeline.length}/6000</span>
          </div>
          <textarea
            rows={4}
            maxLength={6000}
            value={timeline}
            onChange={(e) => setTimeline(e.target.value)}
            placeholder={"Day 1: Mara arrives.\nDay 12: first storm, radio goes dead.\nDay 40: the flood.\n(just the sequence of events — the AI still decides how to split it into chapters)"}
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none"
            data-testid="create-book-timeline-input"
          />
          <p className="text-[10px] text-muted-foreground mt-1 opacity-70">
            Use this instead of a chapter outline if you just want the order of events right, not a full chapter-by-chapter breakdown.
          </p>
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">
            world rules <span className="opacity-60">(optional — special logic, satire hooks, "fucked up things" the story can draw on)</span>
          </label>
          {worldRules.length > 0 && (
            <div className="space-y-2 mb-3">
              {worldRules.map((rule, i) => (
                <div key={i} className="flex items-center justify-between gap-3 border border-border px-3 py-2" data-testid={`world-rule-row-${i}`}>
                  <span className="text-foreground/90">{rule}</span>
                  <button type="button" onClick={() => removeWorldRule(i)} className="text-destructive text-xs shrink-0" data-testid={`world-rule-remove-${i}`}>
                    remove
                  </button>
                </div>
              ))}
            </div>
          )}
          {worldRules.length < MAX_WORLD_RULES && (
            <div className="flex gap-3">
              <input
                value={newRule}
                onChange={(e) => setNewRule(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addWorldRule(); } }}
                placeholder={'e.g. "Everyone in town forgets Tuesdays ever happened" — doesn\'t have to be used, just available'}
                className="flex-1 bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
                data-testid="world-rule-input"
              />
              <button
                type="button"
                onClick={addWorldRule}
                disabled={!newRule.trim()}
                className="py-2 px-4 border border-primary/50 text-primary hover:border-primary transition-colors disabled:opacity-40"
                data-testid="world-rule-add-button"
              >
                + add
              </button>
            </div>
          )}
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">
            reveals <span className="opacity-60">(optional — twists and secrets, each kept from the writer until its chapter)</span>
          </label>
          <RevealsInput reveals={reveals} onChange={setReveals} testId="create-book-reveal" />
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">characters <span className="opacity-60">(optional — up to {MAX_CHARACTERS})</span></label>
          {characters.length > 0 && (
            <div className="space-y-2 mb-3">
              {characters.map((c, i) => (
                <div key={i} className="flex items-start justify-between gap-3 border border-border px-3 py-2" data-testid={`character-row-${i}`}>
                  <div>
                    <span className="text-primary">{c.name}</span>
                    {c.role && <span className="text-muted-foreground"> — {c.role}</span>}
                    {c.description && <div className="text-[11px] text-muted-foreground opacity-80">{c.description}</div>}
                  </div>
                  <button type="button" onClick={() => removeCharacter(i)} className="text-destructive text-xs shrink-0" data-testid={`character-remove-${i}`}>
                    remove
                  </button>
                </div>
              ))}
            </div>
          )}
          {characters.length < MAX_CHARACTERS && (
            <div className="grid grid-cols-2 gap-3">
              <input
                value={charName}
                onChange={(e) => setCharName(e.target.value)}
                placeholder="name"
                className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
                data-testid="character-name-input"
              />
              <input
                value={charRole}
                onChange={(e) => setCharRole(e.target.value)}
                placeholder="role (protagonist, rival...)"
                className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
                data-testid="character-role-input"
              />
              <input
                value={charDesc}
                onChange={(e) => setCharDesc(e.target.value)}
                placeholder="short description"
                className="col-span-2 w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
                data-testid="character-description-input"
              />
              <button
                type="button"
                onClick={addCharacter}
                disabled={!charName.trim()}
                className="col-span-2 py-2 border border-primary/50 text-primary hover:border-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                data-testid="character-add-button"
              >
                + add character
              </button>
            </div>
          )}
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">
            reference tables <span className="opacity-60">(optional — opponents, schedule, results, a roster... hard data the AI must not contradict. Give a table a Chapter column and each row stays hidden until that chapter.)</span>
          </label>
          <div className="space-y-4 mb-3">
            {tables.map((t, i) => (
              <TableGrid key={t.key} table={t} onChange={(next) => updateTable(t.key, next)} onDelete={() => removeTable(t.key)} testId={`create-book-table-${i}`} />
            ))}
          </div>
          {tables.length < MAX_TABLES && (
            <NewTableForm existingNames={tables.map((t) => t.name)} onCreate={addTable} testId="create-book-new-table" />
          )}
        </div>

        <SectionHeading>// VOICE</SectionHeading>

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
          <label className="block text-muted-foreground mb-2">point of view</label>
          <select
            value={pov}
            onChange={(e) => setPov(e.target.value)}
            className="w-full bg-background border border-border focus:border-primary outline-none px-3 py-2"
            data-testid="create-book-pov-select"
          >
            {POV_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-muted-foreground">style notes <span className="opacity-60">(optional — how you want it written)</span></label>
            <span className="text-[10px] text-muted-foreground">{styleNotes.length}/2000</span>
          </div>
          <textarea
            rows={3}
            maxLength={2000}
            value={styleNotes}
            onChange={(e) => setStyleNotes(e.target.value)}
            placeholder="Short punchy sentences during games, slower and quieter off the ice. Locker-room dialogue stays profane. No epilogue."
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none"
            data-testid="create-book-style-notes-input"
          />
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">influences <span className="opacity-60">(optional — books or authors to draw on)</span></label>
          <input
            maxLength={500}
            value={influences}
            onChange={(e) => setInfluences(e.target.value)}
            placeholder="Friday Night Lights, Moneyball"
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
            data-testid="create-book-influences-input"
          />
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">length</label>
          <div className="grid grid-cols-3 gap-3">
            {LENGTHS.map((l) => (
              <button
                type="button"
                key={l.value}
                onClick={() => setLength(l.value)}
                className={`py-3 border transition-all text-center ${length === l.value ? "border-primary text-primary shadow-[0_0_14px_rgba(111,242,212,0.25)]" : "border-border hover:border-primary/50"}`}
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
                className={`py-3 px-3 border transition-all text-left ${style === s.key ? "border-primary text-primary shadow-[0_0_14px_rgba(111,242,212,0.25)]" : "border-border hover:border-primary/50"} ${!s.unlocked ? "opacity-40 cursor-not-allowed" : ""}`}
                data-testid={`style-option-${s.key}`}
              >
                <div className="flex items-center gap-1.5">
                  {!s.unlocked && <Lock className="w-3 h-3" />}
                  {s.name}
                  {s.uncensored && (
                    <span className="text-[9px] px-1.5 py-0.5 border border-destructive/50 text-destructive uppercase tracking-wide">
                      uncensored
                    </span>
                  )}
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
          {style === "chimera" && (styles?.find((s) => s.key === chimeraA)?.uncensored || styles?.find((s) => s.key === chimeraB)?.uncensored) && (
            <p className="text-[10px] text-destructive mt-2 uppercase tracking-wide">this blend includes an uncensored voice</p>
          )}
        </div>

        <div className="gilt-corners border border-border p-4 flex items-center justify-between" data-testid="create-book-cost-estimate">
          <span className="flex items-center gap-2 text-muted-foreground"><Zap className="w-4 h-4 text-primary" /> estimated cost</span>
          <span className={canAfford ? "text-primary" : "text-destructive"}>{estimatedCost.toLocaleString()} NC (balance: {balance.toLocaleString()} NC)</span>
        </div>

        {error && <p className="text-destructive" data-testid="create-book-error">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-4 bg-primary text-primary-foreground uppercase tracking-wide hover:shadow-[0_0_18px_rgba(111,242,212,0.35)] transition-shadow disabled:opacity-50"
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
