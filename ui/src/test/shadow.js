import { within } from "@testing-library/react";

/**
 * Shadow-piercing role queries for Siemens iX shell components.
 *
 * IxMenu, IxMenuItem and IxApplicationHeader (`encapsulation: "shadow"` in the compiled source
 * under ui/node_modules/@siemens/ix/dist/collection/components/<name>/<name>.js) render their
 * actual role-bearing markup — <nav aria-label>, the internal <button role="menuitem">, etc. —
 * inside a shadow root, not as light-DOM children. Testing Library's queries only ever walk the
 * light DOM, so `screen.getByRole(...)` silently finds nothing for those roles even though the
 * element is on screen. These helpers search every shadow root nested under a container
 * (container included) and return the first query that succeeds.
 */
function collectRoots(root, acc = []) {
  acc.push(root);
  const all = typeof root.querySelectorAll === "function" ? root.querySelectorAll("*") : [];
  for (const el of all) {
    if (el.shadowRoot) collectRoots(el.shadowRoot, acc);
  }
  return acc;
}

export function queryShadowRole(container, role, options) {
  for (const root of collectRoots(container)) {
    const match = within(root).queryByRole(role, options);
    if (match) return match;
  }
  return null;
}

export function getShadowRole(container, role, options) {
  const match = queryShadowRole(container, role, options);
  if (!match) {
    throw new Error(
      `No shadow root under the given container exposed role="${role}"` +
      (options?.name ? ` name=${options.name}` : ""),
    );
  }
  return match;
}

export function getAllShadowRole(container, role, options) {
  const found = [];
  for (const root of collectRoots(container)) {
    found.push(...within(root).queryAllByRole(role, options));
  }
  return found;
}

/** Polls until `getShadowRole` succeeds — the shadow-piercing analogue of `findByRole`. */
export async function findShadowRole(container, role, options, waitForOptions) {
  const { waitFor } = await import("@testing-library/react");
  return waitFor(() => getShadowRole(container, role, options), waitForOptions);
}

// Same problem, for text content: IxEmptyState (encapsulation: "shadow" in empty-state.js) puts
// its header/subHeader inside an <ix-typography> in its shadow root, so a 403 message rendered
// through it is invisible to `screen.findByText`.
export function queryShadowText(container, text, options) {
  for (const root of collectRoots(container)) {
    const match = within(root).queryByText(text, options);
    if (match) return match;
  }
  return null;
}

export function getShadowText(container, text, options) {
  const match = queryShadowText(container, text, options);
  if (!match) {
    throw new Error(`No shadow root under the given container contains text matching ${text}`);
  }
  return match;
}

/** Polls until `getShadowText` succeeds — the shadow-piercing analogue of `findByText`. */
export async function findShadowText(container, text, options, waitForOptions) {
  const { waitFor } = await import("@testing-library/react");
  return waitFor(() => getShadowText(container, text, options), waitForOptions);
}
