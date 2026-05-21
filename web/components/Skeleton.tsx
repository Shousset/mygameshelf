"use client";

export function Skeleton({
  width = "100%",
  height = "1rem",
  rounded = 3,
  style,
}: {
  width?: number | string;
  height?: number | string;
  rounded?: number | string;
  style?: React.CSSProperties;
}) {
  return (
    <span
      className="skeleton"
      style={{
        width,
        height,
        borderRadius: rounded,
        ...style,
      }}
      aria-hidden
    />
  );
}

export function SkeletonRow({ height = "1rem" }: { height?: string }) {
  return <Skeleton height={height} style={{ display: "block", marginBottom: "0.5rem" }} />;
}

export function CoverCardSkeleton() {
  return (
    <div className="cover-card" style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Skeleton height={250} rounded={0} />
      <div style={{ padding: "0.55rem 0.75rem 0.7rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
        <Skeleton height="0.85rem" width="80%" />
        <Skeleton height="0.7rem" width="55%" />
      </div>
    </div>
  );
}

export function PickerRowSkeleton() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", padding: "0.5rem 0.6rem" }}>
      <Skeleton width={62} height={29} rounded={3} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.3rem" }}>
        <Skeleton height="0.8rem" width="75%" />
        <Skeleton height="0.65rem" width="40%" />
      </div>
    </div>
  );
}

export function StatCardSkeleton() {
  return (
    <div className="glass" style={{ padding: "0.95rem 1.1rem" }}>
      <Skeleton height="0.7rem" width="60%" style={{ display: "block", marginBottom: "0.5rem" }} />
      <Skeleton height="1.5rem" width="50%" />
    </div>
  );
}
