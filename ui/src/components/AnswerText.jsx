import React from "react";

/* An assistant answer, laid out the way core/chat.py asks the model to write it: one sentence that
   answers (shown as the lead), "- " bullets with the facts behind it, a pipe table only for a
   comparison, and a closing "Not covered:" line, shown as a note. Citation markers "[n]" — Gemini's
   grounding and the evaluation's own facts are both numbered this way — become links to source n.

   Never HTML: the text is model output, so it is only ever turned into React elements. */

const TOKEN = /(\*\*[^*]+\*\*|\[\d+\])/g;
const BULLET = /^\s*[-*•]\s+/;
const TABLE = /^\s*\|.*\|\s*$/;
const NOT_COVERED = /^\s*not covered:/i;

function Inline({ text, sources }) {
  return String(text).split(TOKEN).map((part, i) => {
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={i}>{part.slice(2, -2)}</strong>;
    const cite = part.match(/^\[(\d+)\]$/);
    if (!cite) return part;
    const s = sources?.[Number(cite[1]) - 1];
    return (
      <sup key={i} className="dock-cite">
        {s?.url
          ? <a href={s.url} target="_blank" rel="noopener noreferrer" aria-label={`Source ${cite[1]}${s.title ? `: ${s.title}` : ""}`}>{cite[1]}</a>
          : cite[1]}
      </sup>
    );
  });
}

const cells = (line) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

/** Consecutive lines of one kind form a block: paragraph, list, table or note. */
function blocks(text) {
  const out = [];
  for (const line of String(text || "").split("\n")) {
    if (!line.trim()) { out.push(null); continue; }
    const kind = NOT_COVERED.test(line) ? "note" : TABLE.test(line) ? "table" : BULLET.test(line) ? "list" : "para";
    const last = out[out.length - 1];
    if (last && last.kind === kind && kind !== "note") last.lines.push(line);
    else out.push({ kind, lines: [line] });
  }
  return out.filter(Boolean);
}

export default function AnswerText({ text, sources }) {
  const parts = blocks(text);
  const lead = parts.findIndex((b) => b.kind === "para");
  return parts.map((b, i) => {
    if (b.kind === "list") {
      return <ul key={i}>{b.lines.map((l, j) => <li key={j}><Inline text={l.replace(BULLET, "")} sources={sources} /></li>)}</ul>;
    }
    if (b.kind === "table") {
      const rows = b.lines.filter((l) => !/^\s*\|?[\s:|-]+\|?\s*$/.test(l)).map(cells);
      const [head, ...body] = rows;
      return (
        <div key={i} className="dock-table-wrap">
          <table className="dock-table">
            <thead><tr>{head.map((c, j) => <th key={j} scope="col"><Inline text={c} sources={sources} /></th>)}</tr></thead>
            <tbody>{body.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}><Inline text={c} sources={sources} /></td>)}</tr>)}</tbody>
          </table>
        </div>
      );
    }
    if (b.kind === "note") return <p key={i} className="dock-gap"><Inline text={b.lines[0]} sources={sources} /></p>;
    return (
      <p key={i} className={i === lead ? "dock-lead" : undefined}>
        {b.lines.map((l, j) => <React.Fragment key={j}>{j > 0 && <br />}<Inline text={l} sources={sources} /></React.Fragment>)}
      </p>
    );
  });
}
