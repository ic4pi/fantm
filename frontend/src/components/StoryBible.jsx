import { useEffect, useState } from "react";
import api from "@/lib/api";
import ListInput from "@/components/ListInput";
import RevealsInput from "@/components/RevealsInput";
import { POV_OPTIONS } from "@/lib/storyBible";
import { BookOpen, Plus, Trash2, Save } from "lucide-react";

// Plain-text Story Bible fields (books.bible) — edited and saved as one group.
const TEXT_FIELDS = ["setting", "backstory", "pov", "style_notes", "influences", "special_instructions", "subject", "period"];

function bibleText(bible) {
  return Object.fromEntries(TEXT_FIELDS.map((k) => [k, bible?.[k] || ""]));
}

export default function StoryBible({ bookId, book, onSaved }) {
  const [premise, setPremise] = useState(book.premise || "");
  const [characters, setCharacters] = useState(book.characters || []);
  const [plotThreads, setPlotThreads] = useState(book.plot_threads || []);
  const [worldRules, setWorldRules] = useState(book.world_rules || []);
  const [text, setText] = useState(bibleText(book.bible));
  const [themes, setThemes] = useState(book.bible?.themes || []);
  const [reveals, setReveals] = useState(book.bible?.reveals || []);
  const [charName, setCharName] = useState("");
  const [charRole, setCharRole] = useState("");
  const [charDesc, setCharDesc] = useState("");
  const [newThread, setNewThread] = useState("");
  const [newRule, setNewRule] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Re-sync if the book was refetched elsewhere (e.g. after a chapter
  // finishes and generation's own continuity update lands) — but never
  // while this panel already has unsaved edits sitting in it.
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    if (dirty) return;
    setPremise(book.premise || "");
    setCharacters(book.characters || []);
    setPlotThreads(book.plot_threads || []);
    setWorldRules(book.world_rules || []);
    setText(bibleText(book.bible));
    setThemes(book.bible?.themes || []);
    setReveals(book.bible?.reveals || []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [book.premise, book.characters, book.plot_threads, book.world_rules, book.bible]);

  const markDirty = () => {
    setDirty(true);
    setSaved(false);
  };

  const setField = (key) => (e) => {
    setText((t) => ({ ...t, [key]: e.target.value }));
    markDirty();
  };

  const addCharacter = () => {
    if (!charName.trim()) return;
    setCharacters((c) => [...c, { name: charName.trim(), role: charRole.trim(), description: charDesc.trim() }]);
    setCharName("");
    setCharRole("");
    setCharDesc("");
    markDirty();
  };
  const removeCharacter = (idx) => {
    setCharacters((c) => c.filter((_, i) => i !== idx));
    markDirty();
  };

  const addThread = () => {
    if (!newThread.trim()) return;
    setPlotThreads((t) => [...t, newThread.trim()]);
    setNewThread("");
    markDirty();
  };
  const removeThread = (idx) => {
    setPlotThreads((t) => t.filter((_, i) => i !== idx));
    markDirty();
  };

  const addRule = () => {
    if (!newRule.trim()) return;
    setWorldRules((r) => [...r, newRule.trim()]);
    setNewRule("");
    markDirty();
  };
  const removeRule = (idx) => {
    setWorldRules((r) => r.filter((_, i) => i !== idx));
    markDirty();
  };

  const handleSave = async () => {
    setSaving(true);
    await api.patch(`/books/${bookId}/bible`, { premise, characters, plot_threads: plotThreads, world_rules: worldRules, themes, reveals, ...text });
    setSaving(false);
    setDirty(false);
    setSaved(true);
    onSaved?.();
  };

  return (
    <div className="max-w-6xl mx-auto px-6 pb-10" data-testid="story-bible-section">
      <div className="flex items-center gap-2 mb-4 pt-10 border-t border-border">
        <BookOpen className="w-4 h-4 text-accent" />
        <p className="font-mono text-accent text-xs tracking-widest">// STORY BIBLE</p>
      </div>
      <p className="font-mono text-xs text-muted-foreground mb-4">
        What the AI is tracking as it writes. Edit it if it got a name wrong or you want to steer what happens next —
        changes here reach the next chapter it writes, not the ones already generated.
      </p>

      <div className="space-y-6 font-mono text-sm">
        <div>
          <label className="block text-muted-foreground mb-2">premise</label>
          <textarea
            rows={3}
            value={premise}
            onChange={(e) => { setPremise(e.target.value); markDirty(); }}
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none"
            data-testid="story-bible-premise-input"
          />
        </div>

        {book.book_type !== "novel" && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-muted-foreground mb-2">subject</label>
              <input value={text.subject} onChange={setField("subject")} maxLength={200}
                className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2" data-testid="story-bible-subject-input" />
            </div>
            <div>
              <label className="block text-muted-foreground mb-2">time period covered</label>
              <input value={text.period} onChange={setField("period")} maxLength={200}
                className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2" data-testid="story-bible-period-input" />
            </div>
          </div>
        )}

        <div>
          <label className="block text-muted-foreground mb-2">setting</label>
          <textarea rows={2} value={text.setting} onChange={setField("setting")} maxLength={2000}
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none" data-testid="story-bible-setting-input" />
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">backstory</label>
          <textarea rows={2} value={text.backstory} onChange={setField("backstory")} maxLength={3000}
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none" data-testid="story-bible-backstory-input" />
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">themes</label>
          <ListInput items={themes} onChange={(next) => { setThemes(next); markDirty(); }} max={15} placeholder="a theme to keep returning to..." testId="story-bible-theme" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-muted-foreground mb-2">point of view</label>
            <select value={text.pov} onChange={setField("pov")}
              className="w-full bg-background border border-border focus:border-primary outline-none px-3 py-2" data-testid="story-bible-pov-select">
              {POV_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-muted-foreground mb-2">influences</label>
            <input value={text.influences} onChange={setField("influences")} maxLength={500}
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2" data-testid="story-bible-influences-input" />
          </div>
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">style notes</label>
          <textarea rows={2} value={text.style_notes} onChange={setField("style_notes")} maxLength={2000}
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none" data-testid="story-bible-style-notes-input" />
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">special instructions <span className="opacity-60">(followed in every chapter — no twists here)</span></label>
          <textarea rows={3} value={text.special_instructions} onChange={setField("special_instructions")} maxLength={4000}
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 resize-none" data-testid="story-bible-special-instructions-input" />
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">reveals <span className="opacity-60">(kept from the writer until their chapter)</span></label>
          <RevealsInput reveals={reveals} onChange={(next) => { setReveals(next); markDirty(); }} testId="story-bible-reveal" />
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">characters</label>
          {characters.length > 0 && (
            <div className="space-y-2 mb-3">
              {characters.map((c, i) => (
                <div key={i} className="flex items-start justify-between gap-3 border border-border px-3 py-2" data-testid={`story-bible-character-${i}`}>
                  <div>
                    <span className="text-primary">{c.name}</span>
                    {c.role && <span className="text-muted-foreground"> — {c.role}</span>}
                    {c.description && <div className="text-[11px] text-muted-foreground opacity-80">{c.description}</div>}
                  </div>
                  <button onClick={() => removeCharacter(i)} className="text-destructive text-xs shrink-0" data-testid={`story-bible-character-remove-${i}`}>
                    remove
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <input value={charName} onChange={(e) => setCharName(e.target.value)} placeholder="name"
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2" data-testid="story-bible-character-name-input" />
            <input value={charRole} onChange={(e) => setCharRole(e.target.value)} placeholder="role"
              className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2" data-testid="story-bible-character-role-input" />
            <input value={charDesc} onChange={(e) => setCharDesc(e.target.value)} placeholder="description"
              className="col-span-2 w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2" data-testid="story-bible-character-description-input" />
            <button type="button" onClick={addCharacter} disabled={!charName.trim()}
              className="col-span-2 py-2 border border-primary/50 text-primary hover:border-primary transition-colors disabled:opacity-40" data-testid="story-bible-character-add-button">
              <span className="inline-flex items-center gap-1"><Plus className="w-3 h-3" /> add character</span>
            </button>
          </div>
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">plot threads</label>
          {plotThreads.length > 0 && (
            <div className="space-y-2 mb-3">
              {plotThreads.map((t, i) => (
                <div key={i} className="flex items-center justify-between gap-3 border border-border px-3 py-2" data-testid={`story-bible-thread-${i}`}>
                  <span className="text-foreground/90">{t}</span>
                  <button onClick={() => removeThread(i)} className="text-destructive shrink-0" data-testid={`story-bible-thread-remove-${i}`}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-3">
            <input
              value={newThread}
              onChange={(e) => setNewThread(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addThread(); } }}
              placeholder="a thread the story should keep paying off..."
              className="flex-1 bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
              data-testid="story-bible-thread-input"
            />
            <button type="button" onClick={addThread} disabled={!newThread.trim()}
              className="py-2 px-4 border border-primary/50 text-primary hover:border-primary transition-colors disabled:opacity-40" data-testid="story-bible-thread-add-button">
              + add
            </button>
          </div>
        </div>

        <div>
          <label className="block text-muted-foreground mb-2">world rules <span className="opacity-60">(special logic, satire hooks)</span></label>
          {worldRules.length > 0 && (
            <div className="space-y-2 mb-3">
              {worldRules.map((r, i) => (
                <div key={i} className="flex items-center justify-between gap-3 border border-border px-3 py-2" data-testid={`story-bible-rule-${i}`}>
                  <span className="text-foreground/90">{r}</span>
                  <button onClick={() => removeRule(i)} className="text-destructive shrink-0" data-testid={`story-bible-rule-remove-${i}`}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-3">
            <input
              value={newRule}
              onChange={(e) => setNewRule(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRule(); } }}
              placeholder='e.g. "Everyone in town forgets Tuesdays ever happened"'
              className="flex-1 bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
              data-testid="story-bible-rule-input"
            />
            <button type="button" onClick={addRule} disabled={!newRule.trim()}
              className="py-2 px-4 border border-primary/50 text-primary hover:border-primary transition-colors disabled:opacity-40" data-testid="story-bible-rule-add-button">
              + add
            </button>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          className="flex items-center gap-2 py-3 px-6 bg-primary text-primary-foreground uppercase tracking-wide hover:shadow-[0_0_18px_rgba(111,242,212,0.35)] transition-shadow disabled:opacity-50"
          data-testid="story-bible-save-button"
        >
          <Save className="w-4 h-4" /> {saving ? "saving..." : saved ? "saved" : "save changes"}
        </button>
      </div>
    </div>
  );
}
