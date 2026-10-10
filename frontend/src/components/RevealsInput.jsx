import { useState } from "react";
import { Trash2 } from "lucide-react";
import { MAX_REVEALS } from "@/lib/storyBible";

// Twists and secrets, each tied to the chapter where it comes out. The
// writer doesn't see a reveal at all before its chapter, unless "hint" is
// ticked, which lets earlier chapters plant clues without stating it.
export default function RevealsInput({ reveals, onChange, testId }) {
  const [text, setText] = useState("");
  const [chapter, setChapter] = useState("");
  const [hint, setHint] = useState(false);

  const chapterNum = parseInt(chapter, 10);
  const canAdd = text.trim() && chapterNum >= 1 && chapterNum <= 50 && reveals.length < MAX_REVEALS;

  const add = () => {
    if (!canAdd) return;
    onChange([...reveals, { text: text.trim(), chapter: chapterNum, hint }].sort((a, b) => a.chapter - b.chapter));
    setText("");
    setChapter("");
    setHint(false);
  };

  return (
    <div>
      {reveals.length > 0 && (
        <div className="space-y-2 mb-3">
          {reveals.map((r, i) => (
            <div key={i} className="flex items-start justify-between gap-3 border border-border px-3 py-2" data-testid={`${testId}-row-${i}`}>
              <div>
                <span className="text-accent">ch {r.chapter}</span>
                <span className="text-foreground/90"> — {r.text}</span>
                <div className="text-[10px] text-muted-foreground opacity-80">
                  {r.hint ? "earlier chapters may hint at it" : "completely hidden until then"}
                </div>
              </div>
              <button type="button" onClick={() => onChange(reveals.filter((_, j) => j !== i))} className="text-destructive shrink-0" data-testid={`${testId}-remove-${i}`}>
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
      {reveals.length < MAX_REVEALS && (
        <div className="grid grid-cols-[1fr_auto] gap-3">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={1000}
            placeholder="Coach Laroche is Jake's real father"
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
            data-testid={`${testId}-text`}
          />
          <input
            type="number"
            min={1}
            max={50}
            value={chapter}
            onChange={(e) => setChapter(e.target.value)}
            placeholder="ch #"
            className="w-20 bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
            data-testid={`${testId}-chapter`}
          />
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={hint} onChange={(e) => setHint(e.target.checked)} data-testid={`${testId}-hint`} />
            let earlier chapters hint at it
          </label>
          <button
            type="button"
            onClick={add}
            disabled={!canAdd}
            className="py-2 px-4 border border-primary/50 text-primary hover:border-primary transition-colors disabled:opacity-40"
            data-testid={`${testId}-add`}
          >
            + add
          </button>
        </div>
      )}
    </div>
  );
}
