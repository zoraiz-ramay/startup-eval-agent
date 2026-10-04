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

/** First-seen order; a later duplicate only fills fields the kept entry left blank. */
export function dedupePeople(people) {
  const out = [];
  const byKey = new Map();
  for (const item of people || []) {
    const key = personKey(item?.name);
    const kept = key && byKey.get(key);
    if (!kept) {
      const entry = { ...item };
      if (key) byKey.set(key, entry);
      out.push(entry);
      continue;
    }
    for (const [field, value] of Object.entries(item)) {
      if (field !== "name" && String(value ?? "").trim() && !String(kept[field] ?? "").trim()) kept[field] = value;
    }
  }
  return out;
}
