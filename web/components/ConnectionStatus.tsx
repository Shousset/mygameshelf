"use client";

import { useEffect, useState } from "react";
import { WifiOff, AlertTriangle } from "lucide-react";
import { getHealth, OfflineError } from "@/lib/api";

type Status = "checking" | "online" | "offline";

export default function ConnectionStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [browserOnline, setBrowserOnline] = useState(true);

  useEffect(() => {
    setBrowserOnline(navigator.onLine);
    const onOnline = () => setBrowserOnline(true);
    const onOffline = () => setBrowserOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      try {
        const h = await getHealth();
        if (!cancelled) setStatus(h.ok ? "online" : "offline");
      } catch (e) {
        if (!cancelled) setStatus(e instanceof OfflineError ? "offline" : "online");
      }
    };
    ping();
    const id = setInterval(ping, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (status !== "offline" && browserOnline) return null;

  const browserOffline = !browserOnline;
  const label = browserOffline
    ? "You're offline. Showing the last known data; changes will fail until you reconnect."
    : "Backend unreachable. Start the FastAPI server (uvicorn api.main:app --reload --port 8000).";

  return (
    <div
      role="status"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        gap: "0.6rem",
        padding: "0.6rem 1rem",
        background: browserOffline ? "rgba(234, 179, 8, 0.12)" : "rgba(239, 68, 68, 0.12)",
        borderBottom: `1px solid ${browserOffline ? "rgba(234, 179, 8, 0.35)" : "rgba(239, 68, 68, 0.35)"}`,
        color: browserOffline ? "#fde68a" : "#fca5a5",
        fontSize: "0.85rem",
      }}
    >
      {browserOffline ? <WifiOff size={16} /> : <AlertTriangle size={16} />}
      <span>{label}</span>
    </div>
  );
}
