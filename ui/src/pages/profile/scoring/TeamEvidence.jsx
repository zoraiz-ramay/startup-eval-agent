import React from "react";
import EvidenceList from "./EvidenceList.jsx";
import { Sources } from "./TractionLookup.jsx";

/* A Team & Ecosystem criterion's evidence as the people and organisations it rests on, instead of
   a list of record quotes. A criterion cites records such as `deep_profile.founders[1].background`;
   each cited record is resolved back to its entity in the run (a founder, a programme, an investor,
   an advisor, a customer) and drawn once, as a profile card. Only cited entities appear — the card
   is the evidence, not a directory — and an entity whose cited name no longer matches the run is
   left out rather than guessed at. Anything cited that is not an entity (the summary, a funding
   line) stays underneath as a quote.

   A photo is shown only when the research recorded one; no image is looked up by name, because a
   name search returns a namesake's face as readily as the founder's. */
const ENTITY = /^deep_profile\.(founders|key_team|advisors|programs|commercial\.investors|reference_customers)\[(\d+)\](?:\.(\w+))?$/;
const PATH = { founders: "founders", key_team: "key_team", advisors: "advisors", programs: "programs",
  "commercial.investors": "investors", reference_customers: "customers" };
const GROUP = [
  ["founders", "Founders"], ["key_team", "Key team"], ["advisors", "Advisors"],
  ["programs", "Programmes"], ["investors", "Investors"], ["customers", "Customers"],
];
const PHOTO_FIELDS = ["photo", "photo_url", "image", "image_url", "avatar"];

const initials = (name) => String(name || "?").replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter(Boolean)
  .slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
const norm = (s) => String(s || "").toLowerCase().replace(/\s+/g, " ").trim();

function listFor(dp, kind) {
  if (kind === "investors") return dp.commercial?.investors || [];
  if (kind === "customers") return dp.reference_customers || [];
  return dp[kind] || [];
}

/** {entities: {kind: [{index, item}]}, rest: [evidence not about an entity]} */
export function resolveEvidence(evidence, dp) {
  const entities = {};
  const rest = [];
  for (const e of evidence || []) {
    const m = String(e.source || "").match(ENTITY);
    if (!m) { rest.push(e); continue; }
    const kind = PATH[m[1]];
    const index = Number(m[2]);
    const item = listFor(dp, kind)[index];
    const name = typeof item === "string" ? item : item?.name;
    // A cited name must still be this entity's name; stored lists can change after the citation.
    if (!item || (m[3] === "name" && norm(e.quote) !== norm(name)) || (kind === "customers" && norm(e.quote) !== norm(name))) continue;
    const list = (entities[kind] = entities[kind] || []);
    if (!list.some((x) => x.index === index)) list.push({ index, item });
  }
  return { entities, rest };
}

function Avatar({ name, item }) {
  const photo = PHOTO_FIELDS.map((f) => item?.[f]).find((u) => /^https:\/\//.test(String(u || "")));
  return photo
    ? <img className="team-avatar" src={photo} alt={`Photo of ${name}`} loading="lazy" referrerPolicy="no-referrer" />
    : <span className="team-avatar" aria-hidden="true">{initials(name)}</span>;
}

/* "PhD from Cambridge; previously Hydrogen Lead at ETC" reads better as two lines than as one
   run-on sentence, so a background is split on the separators research sources use. */
const facts = (background) => String(background || "").split(/\s*[;·•]\s*|\s+\|\s+/).map((s) => s.trim()).filter(Boolean).slice(0, 6);

function Person({ item }) {
  const name = item.name || item.role || "Unnamed";
  // Named by where they actually go: research sometimes files a Crunchbase page under "linkedin".
  const isLinkedIn = (u) => /(^|\.)linkedin\.com$/i.test((() => { try { return new URL(u).hostname; } catch { return ""; } })());
  const links = [item.linkedin && { title: isLinkedIn(item.linkedin) ? "LinkedIn" : "", url: item.linkedin },
    item.source_url && item.source_url !== item.linkedin && { title: "", url: item.source_url }].filter(Boolean);
  const lines = facts(item.background);
  return (
    <li className="person-card">
      <Avatar name={name} item={item} />
      <div className="person-body">
        <strong className="person-name">{name}</strong>
        {(item.role || item.affiliation) && <span className="person-role">{[item.role, item.affiliation].filter(Boolean).join(" · ")}</span>}
        {lines.length > 0 && <ul className="person-facts">{lines.map((l) => <li key={l}>{l}</li>)}</ul>}
        <Sources items={links} label="Profile" />
      </div>
    </li>
  );
}

function Org({ item, kind }) {
  const name = typeof item === "string" ? item : item.name;
  const claimed = String(item?.confidence || "").toLowerCase() === "self_asserted";
  return (
    <li className="org-card">
      <span className="org-mark" aria-hidden="true">{initials(name)}</span>
      <div className="person-body">
        <strong className="person-name">{name}</strong>
        <span className="org-tags">
          {item?.type && <span className="kind-tag">{String(item.type).replace(/_/g, " ")}</span>}
          {kind === "programs" && (claimed
            ? <span className="org-claim claimed">Company-claimed</span>
            : <span className="org-claim">Independently corroborated</span>)}
          {item?.prestige === "tier1" && <span className="org-claim top">Top-tier programme</span>}
        </span>
        {item?.source_url && <Sources items={[{ title: "", url: item.source_url }]} label="Source" />}
      </div>
    </li>
  );
}

/** A one-line preview for a criterion's box: the people as initials, or the first organisations
    by name, "+N" for the rest. Decorative in the box — the box's own label carries the score. */
export function EvidencePreview({ criterion, res }) {
  const { entities } = resolveEvidence(criterion.evidence, res?.deep_profile || {});
  const all = GROUP.flatMap(([kind]) => (entities[kind] || []).map(({ item }) => ({ kind, item })));
  if (!all.length) return null;
  const people = all.filter((e) => ["founders", "key_team", "advisors"].includes(e.kind));
  const shown = (people.length ? people : all).slice(0, 3);
  const more = (people.length ? people : all).length - shown.length;
  return (
    <span className="team-box-preview" aria-hidden="true">
      {shown.map(({ kind, item }, i) => {
        const name = typeof item === "string" ? item : item.name || item.role;
        return people.length
          ? <span key={i} className="preview-person"><span className="preview-dot">{initials(name)}</span>{name}</span>
          : <span key={i} className={`preview-org ${kind}`}>{name}</span>;
      })}
      {more > 0 && <span className="preview-more">+{more}</span>}
    </span>
  );
}

export default function TeamEvidence({ criterion, res }) {
  const { entities, rest } = resolveEvidence(criterion.evidence, res?.deep_profile || {});
  const groups = GROUP.filter(([kind]) => entities[kind]?.length);
  if (!groups.length) return <><h5>Startup evidence</h5><EvidenceList items={criterion.evidence} audit={false} /></>;
  return (
    <>
      {groups.map(([kind, label]) => {
        const people = ["founders", "key_team", "advisors"].includes(kind);
        return (
          <div key={kind} className="team-evidence-group">
            <h5>{label}</h5>
            <ul className={people ? "person-list" : "org-list"} aria-label={label}>
              {entities[kind].map(({ index, item }) => (people
                ? <Person key={index} item={item} />
                : <Org key={index} item={item} kind={kind} />))}
            </ul>
          </div>
        );
      })}
      {rest.length > 0 && <><h5>Other evidence</h5><EvidenceList items={rest} audit={false} /></>}
    </>
  );
}
