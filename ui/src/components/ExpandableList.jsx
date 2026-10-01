import React, { useId, useState } from "react";

/* A list that shows its first `max` items and grows in place on request. The toggle sits below
   the list and reads "Show fewer" once open: a native <details> put the extra items under a
   summary that stayed where it was, so the control ended up in the middle of what it revealed. */
export default function ExpandableList({ items, max = 3, className = "", renderItem, itemKey }) {
  const [all, setAll] = useState(false);
  const id = useId();
  if (!items?.length) return null;
  const shown = all ? items : items.slice(0, max);
  return (
    <>
      <ul id={id} className={className}>{shown.map((item, i) => <React.Fragment key={itemKey ? itemKey(item) : i}>{renderItem(item)}</React.Fragment>)}</ul>
      {items.length > max && (
        <button type="button" className="link-btn list-more" aria-expanded={all} aria-controls={id}
          onClick={() => setAll((v) => !v)}>{all ? "Show fewer" : `Show all ${items.length}`}</button>
      )}
    </>
  );
}
