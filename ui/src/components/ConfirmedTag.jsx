import React from "react";

/* Marks evidence an earlier evaluation found that this refresh did not find again.

   A refresh no longer drops sourced evidence (core/carry_forward.py): an investor, founder or
   competitor found once stays, with its own source link. What changes is how current it is, and
   presenting a months-old finding exactly like one this run re-confirmed would overstate it.
   Items found by this run carry no `last_confirmed_at`, so nothing renders for them. */

const FORMAT = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

export function confirmedLabel(iso) {
  const when = new Date(iso);
  return Number.isNaN(when.getTime()) ? "" : `last confirmed ${FORMAT.format(when)}`;
}

export default function ConfirmedTag({ item }) {
  const label = item?.last_confirmed_at ? confirmedLabel(item.last_confirmed_at) : "";
  if (!label) return null;
  return (
    <span className="confirmed-tag" title="Found by an earlier evaluation; this refresh did not find it again">
      {label}
    </span>
  );
}
