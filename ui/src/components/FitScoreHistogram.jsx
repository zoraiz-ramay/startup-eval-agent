import React, { useMemo } from "react";

const BUCKETS = [
  { key: "0-20", label: "0-20", min: 0, max: 20 },
  { key: "21-40", label: "21-40", min: 21, max: 40 },
  { key: "41-60", label: "41-60", min: 41, max: 60 },
  { key: "61-80", label: "61-80", min: 61, max: 80 },
  { key: "81-100", label: "81-100", min: 81, max: 100 },
];

function clampScore(value) {
  const num = Number(value);
  if (Number.isNaN(num)) {
    return null;
  }
  return Math.max(0, Math.min(100, num));
}

function getBucketKey(score) {
  if (score === null) {
    return null;
  }
  return BUCKETS.find((bucket) => score >= bucket.min && score <= bucket.max)?.key || null;
}

export default function FitScoreHistogram({ runs }) {
  const histogram = useMemo(() => {
    const counts = BUCKETS.reduce((acc, bucket) => {
      acc[bucket.key] = 0;
      return acc;
    }, {});

    (runs || []).forEach((run) => {
      const key = getBucketKey(clampScore(run.final_score));
      if (key) {
        counts[key] += 1;
      }
    });

    const maxCount = Math.max(...Object.values(counts), 0);

    return BUCKETS.map((bucket) => ({
      ...bucket,
      count: counts[bucket.key],
      heightPercent: maxCount > 0 ? Math.max((counts[bucket.key] / maxCount) * 100, 8) : 0,
    }));
  }, [runs]);

  const totalCount = histogram.reduce((sum, bucket) => sum + bucket.count, 0);

  if (!totalCount) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        No fit scores available yet. Run an evaluation to populate the distribution.
      </p>
    );
  }

  return (
    <div>
      <div
        aria-label="Fit score distribution histogram"
        role="img"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
          gap: 12,
          alignItems: "end",
          minHeight: 220,
          width: "100%",
        }}
      >
        {histogram.map((bucket) => (
          <div
            key={bucket.key}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "flex-end",
              gap: 8,
              minWidth: 0,
            }}
          >
            <span
              className="muted"
              style={{ fontSize: 12, lineHeight: 1, minHeight: 14 }}
            >
              {bucket.count}
            </span>
            <div
              aria-label={`Score ${bucket.label}: ${bucket.count} companies`}
              role="img"
              style={{
                width: "100%",
                maxWidth: 72,
                minWidth: 24,
                height: Math.max(bucket.heightPercent * 1.5, 6),
                minHeight: 6,
                borderRadius: "10px 10px 4px 4px",
                background:
                  "linear-gradient(180deg, var(--accent, #5aa9ff) 0%, rgba(90, 169, 255, 0.45) 100%)",
                boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.08)",
              }}
            />
            <span
              className="muted"
              style={{ fontSize: 11.5, textAlign: "center", wordBreak: "break-word" }}
            >
              {bucket.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
