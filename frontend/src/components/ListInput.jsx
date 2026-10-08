import { useState } from "react";
import { Trash2 } from "lucide-react";

// A list of short strings with add/remove — themes, and anything else
// shaped like them.
export default function ListInput({ items, onChange, max, placeholder, testId }) {
  const [value, setValue] = useState("");

  const add = () => {
    if (!value.trim() || items.length >= max) return;
    onChange([...items, value.trim()]);
    setValue("");
  };

  return (
    <div>
      {items.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {items.map((item, i) => (
            <span key={i} className="inline-flex items-center gap-2 border border-border px-2 py-1" data-testid={`${testId}-item-${i}`}>
              {item}
              <button type="button" onClick={() => onChange(items.filter((_, j) => j !== i))} className="text-destructive" data-testid={`${testId}-remove-${i}`}>
                <Trash2 className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      {items.length < max && (
        <div className="flex gap-3">
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
            placeholder={placeholder}
            className="flex-1 bg-transparent border border-border focus:border-primary outline-none px-3 py-2"
            data-testid={`${testId}-input`}
          />
          <button
            type="button"
            onClick={add}
            disabled={!value.trim()}
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
