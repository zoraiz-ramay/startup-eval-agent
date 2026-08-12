import React from "react";
import { useApp } from "../state.jsx";
import {
  DEFAULT_WEIGHTS, DIMENSIONS, DIMENSION_LABELS, isDefaultWeights, normaliseWeights,
} from "../scoring/index.js";
import { weightsWithShare } from "../scoring/routing.js";

/**
 * The six weight sliders, shared by the profile's what-if panel and Explore's portfolio mode.
 *
 * One control and one piece of state (`se.whatIfWeights.v1`) on purpose: "my weighting" is one
 * thing a reviewer has, not a per-screen setting. Adjusting it on a profile and then opening
 * Explore should show the same lens, and a second copy of this state would guarantee the two
 * screens eventually disagreed about what the reviewer's weighting is.
 *
 * Moving one dimension rebalances the other five inside what is left, so the sum stays at 100.
 * The six raw number inputs this replaces let it drift to any value and then normalised it
 * silently, which meant "traction 40" was 40% on one visit and 22% on the next depending on
 * what else had been typed.
 */
export function useWeighting() {
  const { whatIfWeights, setWhatIfWeights } = useApp();
  const active = whatIfWeights || DEFAULT_WEIGHTS;
  const { sum, ok } = normaliseWeights(active);
  const modified = !isDefaultWeights(whatIfWeights);

  const setShare = (k, raw) => {
    const pct = Number(raw);
    if (!Number.isFinite(pct)) return;
    const w = weightsWithShare(active, k, Math.max(0, Math.min(100, pct)) / 100);
    if (!w) return;
    setWhatIfWeights(Object.fromEntries(DIMENSIONS.map((d) => [d, Math.round(w[d] * 1000) / 10])));
  };

  const reset = () => setWhatIfWeights(null);
  const shareOf = (k) => (ok ? Math.round((active[k] / sum) * 100) : 0);

  return { active, ok, sum, modified, setShare, reset, shareOf };
}

export default function WeightSliders({ idPrefix = "w", columns = 2 }) {
  const { ok, setShare, shareOf } = useWeighting();
  return (
    <div className={columns === 2 ? "grid2" : ""} style={{ gap: 4 }}>
      {DIMENSIONS.map((k) => {
        const share = shareOf(k);
        return (
          <div key={k} className="spec" style={{ alignItems: "center" }}>
            <div className="k">
              <label htmlFor={`${idPrefix}-${k}`}>{DIMENSION_LABELS[k]}</label>
            </div>
            <div className="v" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                id={`${idPrefix}-${k}`}
                className="wslider"
                type="range"
                min="0"
                max="100"
                step="1"
                value={share}
                aria-valuetext={`${share} percent`}
                onChange={(e) => setShare(k, e.target.value)}
              />
              <span style={{ fontSize: 12, minWidth: 34, textAlign: "right" }}>
                {ok ? `${share}%` : "—"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
