import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ProfileSectionNav from "./ProfileSectionNav.jsx";
import { PROFILE_VIEWS } from "../pages/profile/sections.js";

/**
 * The profile's navigation.
 *
 * This rail replaced a pipeline ribbon and a tab bar stacked above the content. It is now the ONLY
 * way to move around a profile, which raises the bar on these assertions: a decorative list of
 * dots was tolerable when the tabs were still there to fall back on, and is not now.
 *
 * Two properties break silently and are pinned here:
 *   - exactly one group open. Two expanded groups mean two `aria-expanded="true"` and a reader is
 *     told two views are showing when only one is.
 *   - exactly one item current. A scroll-spy that briefly agrees with two neighbours renders two
 *     marked dots, which reads to a screen reader as two current locations.
 *
 * Presentation only — it is handed views, the current view and the current section, so everything
 * below is about the contract, never about the company being profiled.
 */
const SECTIONS = PROFILE_VIEWS[0].sections;
const active = "profile-team-ecosystem";

function renderNav(props = {}) {
  return render(
    <ProfileSectionNav views={PROFILE_VIEWS} activeView="Overview" sections={SECTIONS}
                       activeId={active} {...props} />,
  );
}

const groupButton = (name) => screen.getByRole("button", { name });

describe("ProfileSectionNav — groups", () => {
  it("offers every view as a group", () => {
    renderNav();
    for (const view of PROFILE_VIEWS) {
      expect(groupButton(view.label)).toBeInTheDocument();
    }
  });

  it("expands exactly one group, and it is the active view", () => {
    renderNav();
    const expanded = screen.getAllByRole("button")
      .filter((b) => b.getAttribute("aria-expanded") === "true");
    expect(expanded).toHaveLength(1);
    expect(expanded[0]).toHaveAccessibleName("Profile");
  });

  it("moves the expansion when the active view changes", () => {
    const { rerender } = renderNav();
    rerender(<ProfileSectionNav views={PROFILE_VIEWS} activeView="Evidence" sections={[]}
                                activeId="" />);
    expect(groupButton("Profile")).toHaveAttribute("aria-expanded", "false");
    expect(groupButton("Evidence")).toHaveAttribute("aria-expanded", "true");
  });

  it("selects a view when its group is activated", () => {
    const onSelectView = vi.fn();
    renderNav({ onSelectView });
    groupButton("Market & Risk").click();
    expect(onSelectView).toHaveBeenCalledWith("Market & Risk");
  });

  it("points each group at a list that really exists, open or closed", () => {
    // aria-controls naming a missing element is worse than no aria-controls: assistive tech
    // announces a relationship it then cannot follow.
    const { container } = renderNav();
    for (const view of PROFILE_VIEWS) {
      const id = groupButton(view.label).getAttribute("aria-controls");
      expect(container.querySelector(`#${CSS.escape(id)}`)).toBeInTheDocument();
    }
  });

  it("hides a closed group's sections from the reader", () => {
    renderNav();
    const id = groupButton("Evidence").getAttribute("aria-controls");
    expect(document.getElementById(id)).toHaveAttribute("hidden");
  });

  it("still renders when the open view has no sections on the page yet", () => {
    // The rail is the only navigation now. A view whose content has not arrived must not take the
    // way out of it with it.
    renderNav({ sections: [], activeId: "" });
    expect(screen.getByRole("navigation", { name: "Profile navigation" })).toBeInTheDocument();
    expect(groupButton("Scoring & Fit")).toBeInTheDocument();
  });
});

describe("ProfileSectionNav — sections", () => {
  it("renders every section it is given, in order", () => {
    renderNav();
    expect(screen.getAllByRole("link").map((a) => a.textContent))
      .toEqual(SECTIONS.map((s) => s.label));
  });

  it("points each item at its section's id", () => {
    renderNav();
    for (const s of SECTIONS) {
      expect(screen.getByRole("link", { name: s.label })).toHaveAttribute("href", `#${s.id}`);
    }
  });

  it("marks exactly one item as the current location", () => {
    renderNav();
    const current = screen.getAllByRole("link").filter((a) => a.getAttribute("aria-current"));
    expect(current).toHaveLength(1);
    // "location", not "page": this is a place within the page, not the current page in a site nav.
    expect(current[0]).toHaveAttribute("aria-current", "location");
    expect(current[0]).toHaveAccessibleName("Team & ecosystem");
  });

  it("moves the current marker when the active section changes", () => {
    const { rerender } = renderNav({ activeId: "profile-key-metrics" });
    expect(screen.getByRole("link", { name: "Key metrics" }))
      .toHaveAttribute("aria-current", "location");

    rerender(<ProfileSectionNav views={PROFILE_VIEWS} activeView="Overview" sections={SECTIONS}
                                activeId="profile-recent-signals" />);
    expect(screen.getByRole("link", { name: "Key metrics" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Recent signals" }))
      .toHaveAttribute("aria-current", "location");
  });

  it("marks nothing when no section is active, rather than guessing", () => {
    renderNav({ activeId: "" });
    expect(screen.getAllByRole("link").filter((a) => a.getAttribute("aria-current")))
      .toHaveLength(0);
  });

  it("keeps the decorative timeline out of the accessible name", () => {
    renderNav();
    const link = screen.getByRole("link", { name: "Recent signals" });
    // The dot is a styled span; if it ever stops being aria-hidden a screen reader starts
    // announcing a circle before every label.
    expect(within(link).queryByText("●")).toBeNull();
    expect(link).toHaveAccessibleName("Recent signals");
  });

  it("tells the page which section was clicked, so the spy can stop fighting the scroll", () => {
    const onNavigate = vi.fn();
    renderNav({ onNavigate });
    screen.getByRole("link", { name: "Headcount trend" }).click();
    expect(onNavigate).toHaveBeenCalledWith("profile-headcount-trend");
  });

  it("renders nothing at all when there are no views to offer", () => {
    const { container } = render(<ProfileSectionNav views={[]} activeView="" sections={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
