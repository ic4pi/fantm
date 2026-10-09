export const POV_OPTIONS = [
  { value: "", label: "let the AI decide" },
  { value: "first_person", label: "first person (I)" },
  { value: "third_limited", label: "third person, close" },
  { value: "third_omniscient", label: "third person, omniscient" },
  { value: "second_person", label: "second person (you)" },
];

export const MAX_TABLES = 20;
export const MAX_TABLE_ROWS = 500;

// One click starts a table with sensible columns; the author can add or
// drop columns after. Sports presets first — a season is the case that
// most needs hard data the AI must not contradict.
export const TABLE_PRESETS = [
  { name: "Opponents", columns: ["Team", "City", "Coach", "Star Player", "Strengths", "Weaknesses", "History With Us"] },
  { name: "Schedule", columns: ["Game", "Date", "Opponent", "Home/Away", "Venue"] },
  { name: "Results", columns: ["Game", "Opponent", "Score", "W/L", "Key Moment"] },
  { name: "Roster", columns: ["Name", "Position", "Number", "Notes"] },
  { name: "Locations", columns: ["Place", "Description", "Why It Matters"] },
  { name: "Life Events", columns: ["Date", "Event", "Impact"] },
];

function splitCsvLine(line) {
  const out = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else if (ch === '"') {
        quoted = false;
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

// Rows copied out of a spreadsheet arrive tab-separated; typed or exported
// CSV uses commas. A table with no columns yet takes them from the first
// line; otherwise a first line that just repeats the column names is dropped.
export function parsePastedRows(text, columns) {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (!lines.length) return { columns, rows: [] };
  const split = lines.some((l) => l.includes("\t")) ? (l) => l.split("\t") : splitCsvLine;
  let cells = lines.map((l) => split(l).map((c) => c.trim()));
  let cols = columns;
  if (!cols.length) {
    cols = cells[0].filter(Boolean);
    cells = cells.slice(1);
  } else if (cells[0].join("|").toLowerCase() === cols.join("|").toLowerCase()) {
    cells = cells.slice(1);
  }
  return { columns: cols, rows: cells.map((row) => Object.fromEntries(cols.map((col, i) => [col, row[i] ?? ""]))) };
}
