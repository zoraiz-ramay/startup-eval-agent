import React from "react";
import { useNavigate } from "react-router-dom";
import { IxCardList, IxEventListItem, IxIconButton, IxEmptyState } from "@siemens/ix-react";
import { iconBookmark, iconTrashcan } from "@siemens/ix-icons/icons";
import { useApp } from "../state.jsx";

export default function Saved() {
  const nav = useNavigate();
  const { savedViews, removeView } = useApp();
  return (
    <div>
      <div className="crumb">Workspace &gt; Saved views</div>
      <div className="page-head"><h1 className="page-title">Saved views</h1>
        <span className="page-meta">{savedViews.length} views</span></div>
      {savedViews.length === 0 ? (
        <IxEmptyState
          header="No saved views yet"
          subHeader="Open Database, customise the columns, and save the configuration as a view."
          icon={iconBookmark}
          action="Open Database"
          onActionClick={() => nav("/explore")}
        />
      ) : (
        <div className="panel">
          <IxCardList>
            {savedViews.map((v) => (
              // IxEventListItem's own click listener (verified against compiled source,
              // event-list-item.js) only binds to mouse click — tabIndex + Enter/Space here is
              // what makes the row itself keyboard-reachable (UI-12), on top of the click handler.
              <IxEventListItem
                key={v.name}
                chevron
                tabIndex={0}
                onClick={() => nav(`/explore?view=${encodeURIComponent(v.name)}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    nav(`/explore?view=${encodeURIComponent(v.name)}`);
                  }
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <strong>{v.name}</strong>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {v.columns.length} columns{v.filters?.q ? ` · filter “${v.filters.q}”` : ""}
                      {v.filters?.pillar ? ` · ${v.filters.pillar}` : ""}
                    </div>
                  </div>
                  {/* IxEventListItem's prop table (components.md) has no trailing-action slot, so
                      the delete action is a plain icon button placed after the label content;
                      stopPropagation keeps its click from also triggering the row's own onClick. */}
                  <IxIconButton icon={iconTrashcan} variant="danger-secondary" aria-label={`Delete view ${v.name}`}
                    onClick={(e) => { e.stopPropagation(); removeView(v.name); }} />
                </div>
              </IxEventListItem>
            ))}
          </IxCardList>
        </div>
      )}
    </div>
  );
}
