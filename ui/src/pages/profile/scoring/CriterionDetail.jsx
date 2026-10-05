import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ExtLink } from "../../../components/widgets.jsx";
import EvidenceList from "./EvidenceList.jsx";
import HelpTip from "../../../components/HelpTip.jsx";

/* One criterion, opened from the cell or box that shows its score: the whole scale with the level
   this startup reached marked on it, why it reached it, and what it was measured against.

   It opens full width under the row of cells rather than inside the cell's card, because evidence
   quotes need the width, and a pointer on its top edge ties it back to the cell it belongs to.
   Focus stays on the cell, so pressing it again closes the panel and pressing its neighbour
   switches to that one — criteria are read one at a time, in place. */

/** Where the opened cell's centre falls along the panel's top edge, kept right on resize. */
function useCaret(ref, anchorId) {
  const [x, setX] = useState(null);
  useLayoutEffect(() => {
    const place = () => {
      const anchor = document.getElementById(anchorId);
      if (!anchor || !ref.current) return;
      const a = anchor.getBoundingClientRect();
      setX(Math.round(a.left + a.width / 2 - ref.current.getBoundingClientRect().left));
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [ref, anchorId]);
  return x;
}

/* A criterion can cite the entry it was held against and still score 0, so the heading says
   "compared against" unless the level shows an actual fit. */
function CatalogMatches({ items, what, matched }) {
  if (!items?.length) return null;
  return (
    <>
      <h5>{matched ? "Matched" : "Compared against"} {what}</h5>
      <ul className="crit-catalog">
        {items.map((e) => (
          <li key={e.id}>
            <span className="crit-catalog-name">{e.url ? <ExtLink href={e.url}>{e.name}</ExtLink> : e.name}
              {(e.division || e.kind) && <span className="kind-tag">{e.division || e.kind}</span>}</span>
            {e.description && <span className="muted">{e.description}</span>}
          </li>
        ))}
      </ul>
    </>
  );
}

const OVERLAP = { equivalent: ["Same offering", 0], overlapping: ["Partly overlaps", 1], distinct: ["Different offering", 2] };

/* Connect's Ecosystem gap: the Xcelerator sellers nearest the startup's offering, each with how far
   it overlaps and, for one that sells the same thing, what evidence sets the startup apart. The
   score is computed from these labels, so they are the "why", not a list of matches. */
function Neighbours({ items }) {
  if (!items?.length) return null;
  const sorted = [...items].sort((a, b) => (OVERLAP[a.overlap]?.[1] ?? 3) - (OVERLAP[b.overlap]?.[1] ?? 3));
  return (
    <>
      <h5>Nearest Xcelerator sellers</h5>
      <ul className="crit-catalog">
        {sorted.map((n) => (
          <li key={n.id}>
            <span className="crit-catalog-name">{n.url ? <ExtLink href={n.url}>{n.name}</ExtLink> : n.name}
              <span className="kind-tag">{OVERLAP[n.overlap]?.[0] || n.overlap}{n.unlabelled ? " · not labelled" : ""}</span></span>
            {n.overlap === "equivalent" && (n.differentiator
              ? <span className="muted">Differs: {n.differentiator}</span>
              : <span className="muted">Nothing evidenced sets the startup apart.</span>)}
          </li>
        ))}
      </ul>
    </>
  );
}

/* Connect's derived signals. Rubric v5's Market signals (path "market") lists each good cited
   signal; v4's Ecosystem value also counted the fit; v3 runs, kept as history, carry the ecosystem
   audience the model named — shown as one line of names, because Siemens partners with the startup
   directly and a paragraph per seller answered a question Connect no longer asks. Only the
   signals a run holds are listed. */
const SIGNALS = [["audience", "An ecosystem audience"], ["industry_topic", "A clear industry & topic fit"],
  ["market", "A good market signal"], ["market_size", "A good cited market size"],
  ["market_growth", "A good cited market growth"], ["funded_peers", "Funded peers in the niche"]];
const PATHS = { market: "Good market signals", partnership: "Direct partnership: fit plus market signals", audience: "Audience path",
  open_space: "Open space: no ecosystem audience" };

function ValueSignals({ c }) {
  return (
    <>
      <h5>{PATHS[c.path] || PATHS.open_space}</h5>
      <ul className="value-signals">
        {SIGNALS.filter(([k]) => k in c.signals).map(([k, label]) => (
          <li key={k}><span className={`pill ${c.signals[k] ? "pill-ok" : "pill-neutral"}`}>{c.signals[k] ? "Yes" : "No"}</span> {label}</li>
        ))}
      </ul>
      {c.audience?.length > 0 && <>
        <h5>Ecosystem audience (earlier rubric)</h5>
        <p className="muted">{c.audience.map((a) => a.name).join(", ")}. Counted by the rubric this run was scored
          with; the current one asks only whether Siemens should partner with the startup. Re-evaluate for the current score.</p>
      </>}
    </>
  );
}

/* Connect's similar sellers (rubric v5): every Xcelerator seller the search found selling the same
   kind of solution, nearest first, with what evidence sets the startup apart from each. */
function SimilarSellers({ similar }) {
  return (
    <>
      <h5>Similar sellers in Xcelerator</h5>
      {similar.count === 0 ? <p className="muted">None of the {similar.searched} nearest sellers sells the same kind of solution.</p>
        : <ul className="crit-catalog">
          {similar.sellers.map((s) => (
            <li key={s.id}>
              <span className="crit-catalog-name">{s.url ? <ExtLink href={s.url}>{s.name}</ExtLink> : s.name}
                <span className="kind-tag">Sells the same kind of solution</span></span>
              <span className="muted">{s.differentiator ? `Differs: ${s.differentiator}` : "Nothing evidenced sets the startup apart."}</span>
            </li>
          ))}
        </ul>}
    </>
  );
}

/** The panel's shell, shared by every "open one item's detail" interaction on Scoring & Fit: a
    pointer back at the control that opened it, a header with the item's score, Close and Escape,
    and a two-column body — where it sits on its scale (`scale`), and why (`children`). */
export function DetailPanel({ id, anchorId, context, title, score, max, question, onClose, scale, children }) {
  const ref = useRef(null);
  const caret = useCaret(ref, anchorId);
  useEffect(() => { ref.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" }); }, [anchorId]);
  return (
    <div id={id} ref={ref} className="crit-drawer" role="region" aria-label={`${context}: ${title}`}
      style={caret != null ? { "--caret-x": `${caret}px` } : undefined}
      onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } }}>
      <div className="crit-drawer-head">
        <div>
          <span className="eyebrow">{context}</span>
          <h4>{title}<span className="crit-score">{score}<small> / {max}</small></span></h4>
          {question && <p className="muted crit-question">{question}</p>}
        </div>
        <button type="button" className="link-btn" onClick={onClose}>Close</button>
      </div>
      <div className="crit-drawer-body">
        <div>{scale}</div>
        <div className="crit-why">{children}</div>
      </div>
    </div>
  );
}

export default function CriterionDetail({ id, anchorId, context, criterion: c, max, scale, question, notes = [], catalogLabel = "catalog entries",
  similar = null, scaleHelp = "", evidenceView = null, onClose }) {
  // The scale reads top-down like a ladder, best level first; without the rubric's scale (an
  // older API) only the level reached is shown, never a guessed one.
  const levels = Array.isArray(scale) && scale.length === max + 1
    ? scale.map((anchor, level) => ({ level, anchor })).reverse()
    : [{ level: c.score, anchor: c.anchor }];
  return (
    <DetailPanel id={id} anchorId={anchorId} context={context} title={c.label} score={c.score} max={max}
      question={question} onClose={onClose} scale={<>
        <h5 className="crit-scale-head">Where this startup sits
          {scaleHelp && <HelpTip id={`${id}-scale-help`} label={`How ${c.label} is scored`} text={scaleHelp} />}</h5>
        <ol className="crit-scale" aria-label={`${c.label} scale, 0 to ${max}`}>
          {levels.map((l) => (
            <li key={l.level} className={l.level === c.score ? "on" : ""} aria-current={l.level === c.score ? "true" : undefined}>
              <span className="crit-level">{l.level}</span>
              <span>{l.anchor}{l.level === c.score && <strong className="crit-here">This startup</strong>}</span>
            </li>
          ))}
        </ol></>}>
      <h5>Why this level</h5>
      {c.rationale ? <p>{c.rationale}</p> : <p className="muted">No rationale was recorded.</p>}
      {notes.map((n) => <p key={n} className="crit-note">{n}</p>)}
      {c.counted === false && <p className="crit-note">Not counted: other sellers already sell this, so Connect is scored from how many.</p>}
      {similar && <SimilarSellers similar={similar} />}
      {c.neighbours ? <Neighbours items={c.neighbours} />
        : c.signals ? <ValueSignals c={c} />
        : <CatalogMatches items={c.catalog} what={catalogLabel} matched={c.score > 0} />}
      {/* A caller that can show the evidence as what it is about (Team & Ecosystem: people and
          organisations) replaces the plain quote list. */}
      {evidenceView || <><h5>Startup evidence</h5><EvidenceList items={c.evidence} audit={false} /></>}
    </DetailPanel>
  );
}
