/* One person, one entry. Research sources spell a founder several ways ("Dr. Andreas Wagner",
   "Andreas Wagner", "Alexandre Krémer (CTO)"), and runs stored before the engine deduplicated
   (core/text.py::person_key) still hold both spellings — stored runs are never rewritten, so the
   profile collapses them as it reads. Mirrors person_key; keep the two in step. */

const AFFIXES = new Set("dr prof professor mr mrs ms dipl ing phd mba msc bsc jr sr dott".split(" "));

export function personKey(name) {
  const text = String(name || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/\([^)]*\)|\[[^\]]*\]/g, " ").split(",")[0];
  return text.split(/[^a-z0-9]+/).filter((w) => w && !AFFIXES.has(w)).join(" ");
}

/* A person's own profile link, normalised: the `linkedin` value, or a LinkedIn profile used as the
   source — not any other source, since a team page names everyone on it. */
function identityLink(item) {
  for (const [value, anyLink] of [[item?.linkedin, true], [item?.source_url, false]]) {
    const text = String(value || "").trim().toLowerCase();
    if (!text || (!anyLink && !text.includes("linkedin.com/in/"))) continue;
    return text.replace(/^https?:\/\/(www\.)?|\/+$/g, "");
  }
  return "";
}

/** Whether two people entries are one person. Mirrors core/text.py::same_person: the name keys
    match, or differ only by initials ("KD Kutadgu Gokalp Demirci" — Phena's co-founder, listed
    twice), or both carry the same profile link and share a name token (a shared link alone once
    merged two colleagues, because research had attached one's LinkedIn to the other). */
export function samePerson(a, b) {
  const pa = typeof a === "string" ? { name: a } : a;
  const pb = typeof b === "string" ? { name: b } : b;
  const ka = personKey(pa?.name);
  const kb = personKey(pb?.name);
  if (!ka || !kb) return false;
  if (ka === kb) return true;
  const ta = ka.split(" ");
  const tb = kb.split(" ");
  const fa = ta.filter((t) => t.length > 2).join(" ");
  const fb = tb.filter((t) => t.length > 2).join(" ");
  if (fa.includes(" ") && fa === fb) return true;
  const la = identityLink(pa);
  return Boolean(la) && la === identityLink(pb) && ta.some((t) => tb.includes(t));
}

/** First-seen order; a later duplicate only fills fields the kept entry left blank. */
export function dedupePeople(people) {
  const out = [];
  for (const item of people || []) {
    const kept = item?.name ? out.find((p) => samePerson(p, item)) : null;
    if (!kept) {
      out.push({ ...item });
      continue;
    }
    for (const [field, value] of Object.entries(item)) {
      if (field !== "name" && String(value ?? "").trim() && !String(kept[field] ?? "").trim()) kept[field] = value;
    }
  }
  return out;
}

/** `people` without anyone already in `above` — a founder also listed as an advisor is shown once,
    as a founder (core/text.py::founders_first). */
export function withoutListed(people, above) {
  return (people || []).filter((p) => !(above || []).some((q) => samePerson(p, q)));
}

/** A stable id per person for one rendering: entries that are the same person share an id, so a
    Map keyed on it holds each person once. */
export function personResolver() {
  const seen = [];
  return (item) => {
    const found = seen.find((s) => samePerson(s.item, item));
    if (found) return found.id;
    const id = personKey(typeof item === "string" ? item : item?.name) || `#${seen.length}`;
    seen.push({ item, id: `${id}#${seen.length}` });
    return seen[seen.length - 1].id;
  };
}
