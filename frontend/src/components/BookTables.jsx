import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Table2 } from "lucide-react";
import { MAX_TABLES } from "@/lib/storyBible";
import { NewTableForm, TableGrid } from "@/components/TableGrid";

function TableCard({ table, bookId, onChanged }) {
  const [draft, setDraft] = useState(table);

  const save = async (next) => {
    await api.patch(`/books/${bookId}/tables/${table.id}`, { columns: next.columns, rows: next.rows });
    onChanged();
  };

  const deleteTable = async () => {
    await api.delete(`/books/${bookId}/tables/${table.id}`);
    onChanged();
  };

  return <TableGrid table={draft} onChange={setDraft} onCommit={save} onDelete={deleteTable} testId={`book-table-${table.id}`} />;
}

export default function BookTables({ bookId }) {
  const { data: tables, refetch } = useQuery({
    queryKey: ["book-tables", bookId],
    queryFn: async () => (await api.get(`/books/${bookId}/tables`)).data,
  });

  const handleCreate = async ({ name, columns }) => {
    await api.post(`/books/${bookId}/tables`, { name, columns });
    refetch();
  };

  if (!tables) return null;

  return (
    <div className="max-w-6xl mx-auto px-6 pb-16" data-testid="book-tables-section">
      <div className="flex items-center gap-2 mb-4 pt-6 border-t border-border">
        <Table2 className="w-4 h-4 text-accent" />
        <p className="font-mono text-accent text-xs tracking-widest">// REFERENCE TABLES</p>
      </div>
      <p className="font-mono text-xs text-muted-foreground mb-4">
        Canon the AI re-reads before every chapter — opponents, a schedule, results, a roster. It won't contradict a date, score or result logged here.
        Changes reach the next chapter it writes.
      </p>

      <div className="space-y-4 mb-6">
        {tables.map((t) => (
          <TableCard key={t.id} table={t} bookId={bookId} onChanged={refetch} />
        ))}
      </div>

      {tables.length < MAX_TABLES && (
        <NewTableForm existingNames={tables.map((t) => t.name)} onCreate={handleCreate} testId="book-table-create-form" />
      )}
    </div>
  );
}
