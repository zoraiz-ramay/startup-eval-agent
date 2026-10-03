import React from "react";

/* Which department this startup suits best for Collaborate, and how every other one compares.

   An evaluation is assessed for every department at once (core/assessment.build_all): Empower and
   Connect are shared, Collaborate is matched against each department's own stated needs, and the
   run is headed by the department whose needs it answers best. Selecting another department
   shows that department's assessment in every panel below — it is already in the run, so nothing
   is fetched and nothing is re-scored. */

/** The run as seen for one department: its assessment, route and total in place of the headline. */
export function viewAs(res, departmentId) {
  const entry = res?.departments?.ranked?.find((e) => e.department?.id === departmentId);
  if (!entry) return res;
  return { ...res, department: entry.department, assessment: entry.assessment, routing: entry.routing,
           score: entry.score || res.score };
}

const BAND = { strong: "strong match", review: "worth a review", no_match: "no match" };

function collaborateOf(entry) {
  return entry.assessment?.pillars?.Collaborate || {};
}

export default function DepartmentRanking({ res, selected, onSelect }) {
  const block = res.departments;
  const shownId = selected || res.department?.id;
  return (
    <div className="fit-context dept-ranking" id="scoring-department">
      <p className="dept-ranking-lead">
        {block.recommended
          ? <>Best fit for Collaborate: <strong>{res.departments.ranked[0].department.label}</strong>, the department whose stated needs this startup answers best.</>
          : <>No department's needs could be assessed for Collaborate, so none is recommended. Empower and Connect are scored the same for every department.</>}
      </p>
      <ol className="dept-ranking-list" aria-label="Departments, best Collaborate fit first">
        {block.ranked.map((entry) => {
          const c = collaborateOf(entry);
          const id = entry.department.id;
          const total = entry.assessment?.total;
          return (
            <li key={id}>
              <button type="button" className={`dept-ranking-item${id === shownId ? " on" : ""}`}
                aria-pressed={id === shownId} onClick={() => onSelect(id)}>
                <span className="dept-ranking-name">{entry.department.label}
                  {id === block.recommended && <span className="pill pill-ok">Recommended</span>}</span>
                <span className="dept-ranking-score">
                  {c.status === "assessed" ? `Collaborate ${c.total}/9 · ${BAND[c.band] || c.band}` : "Collaborate not assessed"}
                  {typeof total === "number" ? ` · total ${total}` : ""}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
