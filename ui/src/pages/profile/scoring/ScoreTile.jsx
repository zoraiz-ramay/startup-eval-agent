import React from "react";
import { IxCard, IxCardContent } from "@siemens/ix-react";
export default function ScoreTile({ label, value }) {
  return <IxCard className="score-tile"><IxCardContent><span className="score-tile-label">{label}</span><div className="score-tile-value">{Number.isFinite(value) ? value.toFixed(0) : "—"}<span> / 100</span></div></IxCardContent></IxCard>;
}
