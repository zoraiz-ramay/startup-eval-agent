import React, { useRef } from "react";
import DepartmentPicker from "./DepartmentPicker.jsx";

const MAX_SEGMENTS = 5;

/* The department a search is assessed for, chosen at the top of the search page.

   A segmented control rather than a row of cards: the choice is one of a few, so the control
   stays one line and the page stays quiet. It keeps radio semantics — one tab stop, arrow keys
   move the choice. Past five departments a row of segments stops fitting, and the shared
   dropdown takes over. */
export default function DepartmentChooser({ departments, value, onChange, disabled, invalid }) {
  const refs = useRef([]);
  if (departments.length > MAX_SEGMENTS) {
    return <DepartmentPicker departments={departments} value={value} onChange={onChange} disabled={disabled}
      label="Assess for department" />;
  }
  const current = Math.max(0, departments.findIndex((d) => d.id === value));
  const move = (e, i) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const next = (i + step + departments.length) % departments.length;
    onChange(departments[next].id);
    refs.current[next]?.focus();
  };
  return (
    <div className={`dept-segments${invalid ? " invalid" : ""}`} role="radiogroup" aria-label="Assess for department">
      {departments.map((d, i) => {
        const on = d.id === value;
        return (
          <button key={d.id} ref={(el) => { refs.current[i] = el; }} type="button" role="radio" aria-checked={on}
            tabIndex={on || (!value && i === current) ? 0 : -1} disabled={disabled}
            className={`dept-segment${on ? " on" : ""}`} onClick={() => onChange(d.id)} onKeyDown={(e) => move(e, i)}>
            <span className="dept-segment-dot" aria-hidden="true" />{d.label}
          </button>
        );
      })}
    </div>
  );
}
