import React from "react";
import { sectionLabel } from "./sections.js";

/* One addressable section of the profile.
 *
 * The id is the rail's link target and the scroll-spy's handle, and `.profile-section`'s
 * `scroll-margin-top` (styles.css) is what keeps the heading clear of the sticky header when the
 * browser scrolls here. Every view builds from this one component, so a section cannot exist
 * without being reachable.
 *
 * The accessible name comes from the registry, not from a prop: a <section> is a landmark, and six
 * unnamed landmarks in a row are read out as "region, region, region". Taking the name from the
 * same list the rail reads means the entry and its destination cannot be spelled differently.
 */
export default function Section({ id, children, className = "panel" }) {
  return (
    <section id={id} className={`profile-section ${className}`} aria-label={sectionLabel(id)}>
      {children}
    </section>
  );
}
