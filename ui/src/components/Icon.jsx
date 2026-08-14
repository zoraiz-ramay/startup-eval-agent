import React, { useMemo } from "react";

/**
 * A Siemens iX icon, painted in currentColor.
 *
 * @siemens/ix-icons ships each glyph as a `data:image/svg+xml;utf8,…` string whose markup
 * carries `fill='none'` on its outer group: the artwork expects the host to paint it. That
 * is why the SVG is inlined into the DOM here rather than handed to an <img> or a CSS
 * mask — both of those rasterise the file as written and come out blank. <ix-icon> solves
 * it the same way (inline, then override the fill in CSS); this component is that, minus a
 * Stencil web component that would not render under jsdom in the Vitest suite.
 *
 * The markup is a build-time constant imported from the vendored package. Nothing
 * user-supplied reaches dangerouslySetInnerHTML, and nothing can: `icon` is only ever one
 * of the exported iconXxx bindings.
 */
const DATA_PREFIX = "data:image/svg+xml;utf8,";

export default function Icon({ icon, size = 16, className = "" }) {
  const svg = useMemo(() => {
    const raw = String(icon || "").replace(DATA_PREFIX, "");
    // The payload is written unencoded, but a handful of glyphs escape characters. Decoding
    // a string that was never encoded throws on a bare '%', so fall back to it verbatim.
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }, [icon]);

  return (
    <span
      className={"ix-i" + (className ? " " + className : "")}
      style={{ width: size, height: size }}
      // Decorative: every control that uses this carries its own accessible name, so a
      // second announcement of the glyph would just be noise.
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
