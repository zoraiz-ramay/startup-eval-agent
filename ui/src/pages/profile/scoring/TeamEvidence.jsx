import React from "react";
import EvidenceList from "./EvidenceList.jsx";
import { Sources } from "./TractionLookup.jsx";
import ConfirmedTag from "../../../components/ConfirmedTag.jsx";
import { personKey } from "../people.js";

/* A Team & Ecosystem criterion's evidence as the people and organisations it rests on, instead of
   a list of record quotes. A criterion cites records such as `deep_profile.founders[1].background`;
   each cited record is resolved back to its entity in the run (a founder, a programme, an investor,
   an advisor, a customer) and drawn once, as a profile card. An entity whose cited name no longer
   matches the run is left out rather than guessed at. Anything cited that is not an entity (the
   summary, a funding line) stays underneath as a quote.

   For each kind the criterion cites, every entity of that kind on record is listed — the cited ones
   first, marked as cited. Listing only the cited ones made a refresh look like data loss: Radical
   Dot held 15 sourced investors on every run, but the model cited two of them, a different two
   each time, so the panel showed 2. The citation is the model's choice; what the run holds is not.

   A name is shown once across the four criteria. Each person or organisation belongs to the first
   criterion (in rubric order) that lists it; a later criterion resting on the same names says so in
   one line that opens the earlier one, instead of repeating the cards. Before this, Strategic
   network repeated External validation's programmes and investors, and Domain expertise repeated
   the founder cards: four boxes, two lists. A later criterion's own quotes about a person (their
   background) stay visible, without the card.

   A photo is shown only when the research recorded one; no image is looked up by name, because a
   name search returns a namesake's face as readily as the founder's. */
const ENTITY = /^deep_profile\.(founders|key_team|advisors|programs|commercial\.investors|reference_customers)\[(\d+)\](?:\.(\w+))?$/;
const PATH = { founders: "founders", key_team: "key_team", advisors: "advisors", programs: "programs",
  "commercial.investors": "investors", reference_customers: "customers" };
const GROUP = [
  ["founders", "Founders"], ["key_team", "Key team"], ["advisors", "Advisors"],
  ["programs", "Programmes"], ["investors", "Investors"], ["customers", "Customers"],
];
const PEOPLE = ["founders", "key_team", "advisors"];
const NOUN = { founders: ["founder", "founders"], key_team: ["team member", "team members"],
  advisors: ["advisor", "advisors"], programs: ["programme", "programmes"],
  investors: ["investor", "investors"], customers: ["customer", "customers"] };
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
    const found = list.find((x) => x.index === index);
    if (found) found.evidence.push(e);
    else list.push({ index, item, evidence: [e] });
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

function Cited() {
  return <span className="org-claim cited">Cited in this assessment</span>;
}

function Person({ item, cited }) {
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
        {(cited || item.last_confirmed_at) && <span className="org-tags">{cited && <Cited />}<ConfirmedTag item={item} /></span>}
        {(item.role || item.affiliation) && <span className="person-role">{[item.role, item.affiliation].filter(Boolean).join(" · ")}</span>}
        {lines.length > 0 && <ul className="person-facts">{lines.map((l) => <li key={l}>{l}</li>)}</ul>}
        <Sources items={links} label="Profile" />
      </div>
    </li>
  );
}

function Org({ item, kind, cited, confirmed }) {
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
          {cited && <Cited />}
          <ConfirmedTag item={confirmed} />
        </span>
        {(item?.source_url || confirmed?.source_url) &&
          <Sources items={[{ title: "", url: item?.source_url || confirmed.source_url }]} label="Source" />}
      </div>
    </li>
  );
}

const nameOf = (item) => (typeof item === "string" ? item : item?.name || "");
const entityKey = (kind, item) => (PEOPLE.includes(kind) ? `p:${personKey(nameOf(item))}` : `o:${norm(nameOf(item))}`);

/** Every entity of a kind on record, the cited ones first. */
export function onRecord(dp, kind, cited) {
  const citedIdx = new Set(cited.map((e) => e.index));
  const others = listFor(dp, kind).map((item, index) => ({ index, item })).filter((e) => !citedIdx.has(e.index));
  return [...cited.map((e) => ({ ...e, cited: true })), ...others.map((e) => ({ ...e, cited: false }))];
}

/** What each criterion shows, in rubric order: its own entity groups, the cited entities an earlier
    criterion already shows (`shared`, with that criterion), and its quotes. An entity belongs to the
    first criterion that lists it, and a person spelled two ways ("Dr. A. Wagner") is one entity. */
export function layout(criteria, dp) {
  const owner = new Map();
  return (criteria || []).map((criterion) => {
    const { entities, rest } = resolveEvidence(criterion.evidence, dp);
    const groups = [];
    const shared = [];
    const quotes = [...rest];
    for (const [kind, label] of GROUP) {
      if (!entities[kind]?.length) continue;
      const items = [];
      for (const entry of onRecord(dp, kind, entities[kind])) {
        const key = entityKey(kind, entry.item);
        const prev = owner.get(key);
        if (prev === undefined) {
          owner.set(key, criterion);
          items.push(entry);
        } else if (prev !== criterion && entry.cited) {
          shared.push({ kind, owner: prev });
          // What this criterion says about the person (a background, a role) is its own evidence.
          if (PEOPLE.includes(kind)) quotes.push(...entry.evidence.filter((e) => !/\.name$/.test(e.source)));
        }
      }
      if (items.length) groups.push({ kind, label, items });
    }
    return { criterion, groups, shared, quotes };
  });
}

function viewOf(criterion, res, criteria) {
  const dp = res?.deep_profile || {};
  const views = layout(criteria?.length ? criteria : [criterion], dp);
  return views.find((v) => v.criterion === criterion) || views.find((v) => v.criterion.id === criterion.id)
    || layout([criterion], dp)[0];
}

/** "2 programmes and 1 investor" */
function counted(entries) {
  const by = new Map();
  entries.forEach(({ kind }) => by.set(kind, (by.get(kind) || 0) + 1));
  const parts = [...by].map(([kind, n]) => `${n} ${NOUN[kind][n === 1 ? 0 : 1]}`);
  return parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : parts[0];
}

function Shared({ shared, onOpen }) {
  const owners = [...new Set(shared.map((s) => s.owner))];
  return owners.map((o) => (
    <p key={o.id} className="team-shared muted">
      Also rests on {counted(shared.filter((s) => s.owner === o))} shown under{" "}
      {onOpen ? <button type="button" className="link-btn" onClick={() => onOpen(o.id)}>{o.label}</button> : o.label}.
    </p>
  ));
}

/** A one-line preview for a criterion's box: the people as initials, or the first organisations
    by name, "+N" for the rest, and only names no earlier box already shows. Decorative in the box;
    the box's own label carries the score. */
export function EvidencePreview({ criterion, res, criteria }) {
  const { groups } = viewOf(criterion, res, criteria);
  const all = groups.flatMap(({ kind, items }) => items.filter((i) => i.cited).map(({ item }) => ({ kind, item })));
  if (!all.length) return null;
  const people = all.filter((e) => PEOPLE.includes(e.kind));
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

export default function TeamEvidence({ criterion, res, criteria, onOpen }) {
  const dp = res?.deep_profile || {};
  const { groups, shared, quotes } = viewOf(criterion, res, criteria);
  if (!groups.length && !shared.length) return <><h5>Startup evidence</h5><EvidenceList items={criterion.evidence} audit={false} /></>;
  return (
    <>
      {shared.length > 0 && <Shared shared={shared} onOpen={onOpen} />}
      {groups.map(({ kind, label, items }) => {
        const people = PEOPLE.includes(kind);
        const cited = items.filter((i) => i.cited).length;
        return (
          <div key={kind} className="team-evidence-group">
            <h5>{label} <span className="muted">· {cited} cited of {items.length} on record</span></h5>
            <ul className={people ? "person-list" : "org-list"} aria-label={label}>
              {items.map(({ index, item, cited: isCited }) => (people
                ? <Person key={index} item={item} cited={isCited} />
                : <Org key={index} item={item} kind={kind} cited={isCited}
                    confirmed={typeof item === "string" ? (dp.customer_evidence || {})[item] : item} />))}
            </ul>
          </div>
        );
      })}
      {quotes.length > 0 && <><h5>{groups.length ? "Other evidence" : "Startup evidence"}</h5><EvidenceList items={quotes} audit={false} /></>}
    </>
  );
}
