import { useState } from "react";
import { Plus, Trash2, X, ClipboardPaste } from "lucide-react";
import { MAX_TABLE_ROWS, TABLE_PRESETS, parsePastedRows } from "@/lib/storyBible";

// Shared by the create form (tables held in local state until submit) and
// the reader (each table saved to the API). onChange fires on every edit;
// onCommit fires only when an edit should be persisted — a cell losing
// focus, or a structural change like adding a row.
export function TableGrid({ table, onChange, onCommit, onDelete, testId }) {
  const [newColumn, setNewColumn] = useState("");
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const { columns, rows } = table;

  const apply = (patch) => {
    const next = { ...table, ...patch };
    onChange(next);
    onCommit?.(next);
  };

  const setCell = (rowIdx, col, value) =>
    onChange({ ...table, rows: rows.map((r, i) => (i === rowIdx ? { ...r, [col]: value } : r)) });

  const addRow = () => apply({ rows: [...rows, Object.fromEntries(columns.map((c) => [c, ""]))] });
  const removeRow = (rowIdx) => apply({ rows: rows.filter((_, i) => i !== rowIdx) });

  const addColumn = () => {
    const col = newColumn.trim();
    if (!col || columns.includes(col)) return;
    setNewColumn("");
    apply({ columns: [...columns, col], rows: rows.map((r) => ({ ...r, [col]: r[col] ?? "" })) });
  };

  const removeColumn = (col) =>
    apply({
      columns: columns.filter((c) => c !== col),
      rows: rows.map((r) => {
        const next = { ...r };
        delete next[col];
        return next;
      }),
    });

  const addPasted = () => {
    const parsed = parsePastedRows(pasteText, columns);
    apply({ columns: parsed.columns, rows: [...rows, ...parsed.rows].slice(0, MAX_TABLE_ROWS) });
    setPasteText("");
    setPasteOpen(false);
  };

  return (
    <div className="border border-border p-4" data-testid={testId}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-serif italic text-lg">{table.name}</h3>
        <button type="button" onClick={onDelete} className="text-destructive text-xs flex items-center gap-1" data-testid={`${testId}-delete`}>
          <Trash2 className="w-3.5 h-3.5" /> delete table
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full font-mono text-xs border-collapse">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col} className="text-left border-b border-border px-2 py-1 text-muted-foreground whitespace-nowrap">
                  <span className="inline-flex items-center gap-1">
                    {col}
                    <button type="button" onClick={() => removeColumn(col)} className="opacity-40 hover:opacity-100 hover:text-destructive" title={`remove column ${col}`} data-testid={`${testId}-remove-column-${col}`}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                </th>
              ))}
              <th className="border-b border-border w-8"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr key={rowIdx}>
                {columns.map((col) => (
                  <td key={col} className="border-b border-border/50 px-2 py-1 min-w-[6rem]">
                    <input
                      value={row[col] ?? ""}
                      onChange={(e) => setCell(rowIdx, col, e.target.value)}
                      onBlur={() => onCommit?.(table)}
                      className="w-full bg-transparent outline-none focus:border-b focus:border-primary"
                      data-testid={`${testId}-cell-${rowIdx}-${col}`}
                    />
                  </td>
                ))}
                <td className="border-b border-border/50 px-2 py-1">
                  <button type="button" onClick={() => removeRow(rowIdx)} className="text-destructive" data-testid={`${testId}-remove-row-${rowIdx}`}>
                    <Trash2 className="w-3 h-3" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-3 mt-3">
        {columns.length > 0 && rows.length < MAX_TABLE_ROWS && (
          <button type="button" onClick={addRow} className="text-primary text-xs flex items-center gap-1" data-testid={`${testId}-add-row`}>
            <Plus className="w-3 h-3" /> add row
          </button>
        )}
        <button type="button" onClick={() => setPasteOpen((o) => !o)} className="text-primary text-xs flex items-center gap-1" data-testid={`${testId}-paste-toggle`}>
          <ClipboardPaste className="w-3 h-3" /> paste rows
        </button>
        <div className="flex items-center gap-1">
          <input
            value={newColumn}
            onChange={(e) => setNewColumn(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addColumn(); } }}
            placeholder="new column"
            className="bg-transparent border border-border px-2 py-1 text-xs w-28"
            data-testid={`${testId}-new-column`}
          />
          <button type="button" onClick={addColumn} disabled={!newColumn.trim()} className="text-primary text-xs disabled:opacity-40" data-testid={`${testId}-add-column`}>
            + add
          </button>
        </div>
      </div>
      {pasteOpen && (
        <div className="mt-3 space-y-2">
          <textarea
            rows={4}
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder={columns.length
              ? `One row per line, copied from a spreadsheet or comma-separated, in column order:\n${columns.join(", ")}`
              : "First line = column names, then one row per line (copied from a spreadsheet or comma-separated)"}
            className="w-full bg-transparent border border-border focus:border-primary outline-none px-3 py-2 font-mono text-xs resize-none"
            data-testid={`${testId}-paste-input`}
          />
          <button type="button" onClick={addPasted} disabled={!pasteText.trim()} className="py-1 px-3 border border-primary/50 text-primary text-xs disabled:opacity-40" data-testid={`${testId}-paste-add`}>
            add pasted rows
          </button>
        </div>
      )}
    </div>
  );
}

export function NewTableForm({ existingNames = [], onCreate, testId = "new-table" }) {
  const [name, setName] = useState("");
  const [columns, setColumns] = useState("");

  const create = () => {
    if (!name.trim()) return;
    onCreate({ name: name.trim(), columns: columns.split(",").map((c) => c.trim()).filter(Boolean) });
    setName("");
    setColumns("");
  };
  const onEnter = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      create();
    }
  };

  return (
    <div className="border border-border p-4 font-mono text-sm space-y-3" data-testid={testId}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground text-xs">quick add:</span>
        {TABLE_PRESETS.map((p) => (
          <button
            type="button"
            key={p.name}
            disabled={existingNames.includes(p.name)}
            onClick={() => onCreate({ name: p.name, columns: p.columns })}
            className="py-1 px-2 border border-primary/50 text-primary text-xs hover:border-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            data-testid={`${testId}-preset-${p.name.toLowerCase().replace(/\s+/g, "-")}`}
          >
            + {p.name}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-muted-foreground text-xs mb-1">or a custom table</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={onEnter}
            placeholder="Trade Deadline Moves"
            className="bg-transparent border border-border px-3 py-2"
            data-testid={`${testId}-name`}
          />
        </div>
        <div>
          <label className="block text-muted-foreground text-xs mb-1">columns (comma-separated)</label>
          <input
            value={columns}
            onChange={(e) => setColumns(e.target.value)}
            onKeyDown={onEnter}
            placeholder="Date, Player, Traded To"
            className="bg-transparent border border-border px-3 py-2 w-64"
            data-testid={`${testId}-columns`}
          />
        </div>
        <button
          type="button"
          onClick={create}
          disabled={!name.trim()}
          className="py-2 px-4 border border-primary/50 text-primary hover:border-primary transition-colors disabled:opacity-40"
          data-testid={`${testId}-create`}
        >
          + add table
        </button>
      </div>
    </div>
  );
}
