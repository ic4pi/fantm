import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Plus, Trash2, Table2 } from "lucide-react";

const MAX_TABLES = 20;

function TableCard({ table, bookId, onChanged }) {
  const [rows, setRows] = useState(table.rows);
  const [newColumn, setNewColumn] = useState("");

  const save = async (nextRows) => {
    setRows(nextRows);
    await api.patch(`/books/${bookId}/tables/${table.id}`, { rows: nextRows });
    onChanged();
  };

  const setCell = (rowIdx, col, value) => {
    const next = rows.map((r, i) => (i === rowIdx ? { ...r, [col]: value } : r));
    setRows(next);
  };

  const addRow = () => save([...rows, Object.fromEntries(table.columns.map((c) => [c, ""]))]);
  const removeRow = (rowIdx) => save(rows.filter((_, i) => i !== rowIdx));

  const addColumn = async () => {
    const col = newColumn.trim();
    if (!col || table.columns.includes(col)) return;
    const columns = [...table.columns, col];
    const nextRows = rows.map((r) => ({ ...r, [col]: r[col] ?? "" }));
    setNewColumn("");
    await api.patch(`/books/${bookId}/tables/${table.id}`, { columns, rows: nextRows });
    onChanged();
  };

  const deleteTable = async () => {
    await api.delete(`/books/${bookId}/tables/${table.id}`);
    onChanged();
  };

  return (
    <div className="border border-border p-4" data-testid={`book-table-${table.id}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-serif italic text-lg">{table.name}</h3>
        <button onClick={deleteTable} className="text-destructive text-xs flex items-center gap-1" data-testid={`book-table-delete-${table.id}`}>
          <Trash2 className="w-3.5 h-3.5" /> delete table
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full font-mono text-xs border-collapse">
          <thead>
            <tr>
              {table.columns.map((col) => (
                <th key={col} className="text-left border-b border-border px-2 py-1 text-muted-foreground">{col}</th>
              ))}
              <th className="border-b border-border w-8"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr key={rowIdx}>
                {table.columns.map((col) => (
                  <td key={col} className="border-b border-border/50 px-2 py-1">
                    <input
                      value={row[col] ?? ""}
                      onChange={(e) => setCell(rowIdx, col, e.target.value)}
                      onBlur={() => save(rows)}
                      className="w-full bg-transparent outline-none focus:border-b focus:border-primary"
                      data-testid={`book-table-cell-${table.id}-${rowIdx}-${col}`}
                    />
                  </td>
                ))}
                <td className="border-b border-border/50 px-2 py-1">
                  <button onClick={() => removeRow(rowIdx)} className="text-destructive" data-testid={`book-table-remove-row-${table.id}-${rowIdx}`}>
                    <Trash2 className="w-3 h-3" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3 mt-3">
        <button onClick={addRow} className="text-primary text-xs flex items-center gap-1" data-testid={`book-table-add-row-${table.id}`}>
          <Plus className="w-3 h-3" /> add row
        </button>
        <div className="flex items-center gap-1">
          <input
            value={newColumn}
            onChange={(e) => setNewColumn(e.target.value)}
            placeholder="new column"
            className="bg-transparent border border-border px-2 py-1 text-xs w-28"
            data-testid={`book-table-new-column-${table.id}`}
          />
          <button onClick={addColumn} disabled={!newColumn.trim()} className="text-primary text-xs disabled:opacity-40" data-testid={`book-table-add-column-${table.id}`}>
            + add
          </button>
        </div>
      </div>
    </div>
  );
}

export default function BookTables({ bookId }) {
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");
  const [newColumns, setNewColumns] = useState("");
  const [creating, setCreating] = useState(false);

  const { data: tables, refetch } = useQuery({
    queryKey: ["book-tables", bookId],
    queryFn: async () => (await api.get(`/books/${bookId}/tables`)).data,
  });

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    const columns = newColumns.split(",").map((c) => c.trim()).filter(Boolean);
    await api.post(`/books/${bookId}/tables`, { name: newName.trim(), columns });
    setNewName("");
    setNewColumns("");
    setCreating(false);
    refetch();
    queryClient.invalidateQueries({ queryKey: ["book-tables", bookId] });
  };

  if (!tables) return null;

  return (
    <div className="max-w-6xl mx-auto px-6 pb-16" data-testid="book-tables-section">
      <div className="flex items-center gap-2 mb-4 pt-6 border-t border-border">
        <Table2 className="w-4 h-4 text-accent" />
        <p className="font-mono text-accent text-xs tracking-widest">// REFERENCE TABLES</p>
      </div>
      <p className="font-mono text-xs text-muted-foreground mb-4">
        Anything you want tracked and fed back into generation — a schedule, a timeline, a map of locations. Add whatever tables this story needs; none are required.
      </p>

      <div className="space-y-4 mb-6">
        {tables.map((t) => (
          <TableCard key={t.id} table={t} bookId={bookId} onChanged={refetch} />
        ))}
      </div>

      {tables.length < MAX_TABLES && (
        <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-3 font-mono text-sm border border-border p-4" data-testid="book-table-create-form">
          <div>
            <label className="block text-muted-foreground text-xs mb-1">table name</label>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Away Team Schedule"
              className="bg-transparent border border-border px-3 py-2"
              data-testid="book-table-new-name"
            />
          </div>
          <div>
            <label className="block text-muted-foreground text-xs mb-1">columns (comma-separated)</label>
            <input
              value={newColumns}
              onChange={(e) => setNewColumns(e.target.value)}
              placeholder="Date, Opponent, Score"
              className="bg-transparent border border-border px-3 py-2 w-64"
              data-testid="book-table-new-columns"
            />
          </div>
          <button
            type="submit"
            disabled={creating || !newName.trim()}
            className="py-2 px-4 border border-primary/50 text-primary hover:border-primary transition-colors disabled:opacity-40"
            data-testid="book-table-create-button"
          >
            + add table
          </button>
        </form>
      )}
    </div>
  );
}
