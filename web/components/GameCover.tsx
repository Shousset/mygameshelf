"use client";

import { Gamepad2 } from "lucide-react";

type Variant = "header" | "library" | "capsule";

const URLS: Record<Variant, (appid: string) => string> = {
  header: (appid) => `https://cdn.akamai.steamstatic.com/steam/apps/${appid}/header.jpg`,
  library: (appid) => `https://cdn.akamai.steamstatic.com/steam/apps/${appid}/library_600x900.jpg`,
  capsule: (appid) => `https://cdn.akamai.steamstatic.com/steam/apps/${appid}/capsule_231x87.jpg`,
};

export default function GameCover({
  appid,
  title,
  variant = "header",
  width,
  height,
  rounded = 6,
  fit = "cover",
  fallbackBackground = "linear-gradient(135deg, #2a475e, #1b2838)",
}: {
  appid: string | number | null | undefined;
  title?: string;
  variant?: Variant;
  width: number | string;
  height: number | string;
  rounded?: number;
  fit?: "cover" | "contain";
  fallbackBackground?: string;
}) {
  const hasAppid = appid !== null && appid !== undefined && String(appid).length > 0;
  const src = hasAppid ? URLS[variant](String(appid)) : null;

  if (!src) {
    return (
      <div
        aria-label={title}
        style={{
          width,
          height,
          borderRadius: rounded,
          background: fallbackBackground,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#8f98a0",
          flexShrink: 0,
        }}
      >
        <Gamepad2 size={22} />
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={title || ""}
      width={typeof width === "number" ? width : undefined}
      height={typeof height === "number" ? height : undefined}
      style={{
        width,
        height,
        objectFit: fit,
        borderRadius: rounded,
        display: "block",
        flexShrink: 0,
        background: fallbackBackground,
      }}
      onError={(e) => {
        // Some appids don't have header art; hide and show fallback box
        const target = e.currentTarget as HTMLImageElement;
        target.style.visibility = "hidden";
      }}
    />
  );
}
