"use client";

import { useEffect, useState } from "react";
import { ExternalLink, RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";
import { getSyncStatus, syncAll, OfflineError, type SyncStatus } from "@/lib/api";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass" style={{ padding: "1.5rem", marginBottom: "1.25rem" }}>
      <h2 style={{ margin: "0 0 1rem", fontWeight: 700, fontSize: "1.1rem" }}>{title}</h2>
      {children}
    </div>
  );
}

function InfoRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.6rem 0", borderBottom: "1px solid rgba(102, 192, 244, 0.12)" }}>
      <span style={{ color: "#8f98a0", fontSize: "0.875rem" }}>{label}</span>
      <span style={{ color: "#c7d5e0", fontFamily: mono ? "monospace" : "inherit", fontSize: "0.875rem" }}>{value}</span>
    </div>
  );
}

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function AutoSyncSection() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const refresh = async () => {
    try {
      const s = await getSyncStatus();
      setStatus(s);
    } catch (e) {
      // Backend likely offline — the global banner already tells the user
    }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15_000);
    return () => clearInterval(id);
  }, []);

  const handleSync = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const result = await syncAll();
      setMsg({
        kind: "ok",
        text: result.message
          ? result.message
          : `Synced ${result.synced} game(s)${result.errors ? `, ${result.errors} error(s)` : ""}.`,
      });
      await refresh();
    } catch (e) {
      const text = e instanceof OfflineError
        ? "Backend unreachable. Start the FastAPI server, then try again."
        : (e as Error).message || "Sync failed";
      setMsg({ kind: "err", text });
    } finally {
      setLoading(false);
    }
  };

  const inProgress = status?.in_progress || loading;
  const lastRun = status?.last_run;

  return (
    <Section title="🔄 Auto-Sync">
      <p style={{ margin: "0 0 1rem", color: "#8f98a0", fontSize: "0.875rem" }}>
        Re-fetches Steam playtime and achievements for every game linked to a Steam AppID. Runs automatically every 6 hours; you can also trigger it manually here.
      </p>

      <InfoRow label="Steam credentials" value={status?.steam_configured ? "Loaded from .env" : "Missing — set STEAM_API_KEY and STEAM_ID in .env"} />
      <InfoRow label="Last sync" value={fmtTime(lastRun?.finished_at ?? lastRun?.started_at ?? null)} />
      <InfoRow label="Last result" value={lastRun ? `${lastRun.games_synced} synced, ${lastRun.errors} errors (${lastRun.trigger ?? "?"})` : "—"} />
      <InfoRow label="Next scheduled run" value={fmtTime(status?.next_run_at ?? null)} mono />

      <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <button
          className="btn-primary"
          onClick={handleSync}
          disabled={inProgress || !status?.steam_configured}
          title={!status?.steam_configured ? "Set STEAM_API_KEY and STEAM_ID in mygameshelf/.env first" : undefined}
        >
          <RefreshCw size={14} style={{ marginRight: "0.4rem", display: "inline", animation: inProgress ? "spin 1s linear infinite" : undefined }} />
          {inProgress ? "Syncing..." : "Sync now"}
        </button>
        {msg && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              color: msg.kind === "ok" ? "#4ade80" : "#fca5a5",
              fontSize: "0.85rem",
            }}
          >
            {msg.kind === "ok" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            {msg.text}
          </div>
        )}
      </div>
      <style jsx>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </Section>
  );
}

export default function SettingsPage() {
  return (
    <div>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ margin: 0, fontSize: "2rem", fontWeight: 800 }}>
          <span className="gradient-text">Settings</span> ⚙️
        </h1>
        <p style={{ margin: "0.4rem 0 0", color: "#8f98a0" }}>API configuration and project info</p>
      </div>

      <Section title="🔌 API Connection">
        <InfoRow label="Backend URL" value={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} mono />
        <InfoRow label="Framework" value="FastAPI + Python" />
        <InfoRow label="Start backend" value="uvicorn api.main:app --reload --port 8000" mono />
        <InfoRow label="Start frontend" value="npm run dev (in web/)" mono />
      </Section>

      <AutoSyncSection />

      <Section title="🎮 Steam API">
        <p style={{ margin: "0 0 1rem", color: "#8f98a0", fontSize: "0.875rem" }}>
          You need a free Steam Web API key to import your library. Your Steam profile&apos;s game library must be <strong style={{ color: "#c7d5e0" }}>Public</strong>.
        </p>
        <a
          href="https://steamcommunity.com/dev/apikey"
          target="_blank"
          rel="noreferrer"
          style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", color: "#66c0f4", textDecoration: "none", fontWeight: 600, fontSize: "0.9rem" }}
        >
          Get Steam API Key <ExternalLink size={14} />
        </a>
        <br />
        <a
          href="https://store.steampowered.com/account"
          target="_blank"
          rel="noreferrer"
          style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", color: "#66c0f4", textDecoration: "none", fontWeight: 600, fontSize: "0.9rem", marginTop: "0.5rem" }}
        >
          Find your SteamID (64-bit) <ExternalLink size={14} />
        </a>
        <div style={{ marginTop: "1.25rem", padding: "1rem", background: "rgba(102, 192, 244, 0.10)", borderRadius: "10px", border: "1px solid rgba(102, 192, 244, 0.22)" }}>
          <p style={{ margin: 0, fontSize: "0.82rem", color: "#8f98a0" }}>
            Keys are <strong>never stored</strong> by MyGameShelf — they are sent directly to the Steam API from your browser for each import.
          </p>
        </div>
      </Section>

      <Section title="🟣 Epic Games">
        <p style={{ margin: "0", color: "#8f98a0", fontSize: "0.875rem" }}>
          Epic Games does <strong style={{ color: "#c7d5e0" }}>not provide a public API</strong> for reading your game library.
          Use the <strong style={{ color: "#c7d5e0" }}>Import → Epic Games</strong> tab to manually paste your game titles (one per line) from your Epic library page.
        </p>
        <a
          href="https://store.epicgames.com/en-US/library"
          target="_blank"
          rel="noreferrer"
          style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", color: "#66c0f4", textDecoration: "none", fontWeight: 600, fontSize: "0.9rem", marginTop: "0.75rem" }}
        >
          Open Epic Games Library <ExternalLink size={14} />
        </a>
      </Section>

      <Section title="🗄️ Database">
        <p style={{ margin: "0 0 0.75rem", color: "#8f98a0", fontSize: "0.875rem" }}>
          Configure your PostgreSQL connection in <code style={{ color: "#66c0f4" }}>mygameshelf/.env</code>.
        </p>
        <InfoRow label="DB Host" value="DB_HOST (default: localhost)" mono />
        <InfoRow label="DB Port" value="DB_PORT (default: 5432)" mono />
        <InfoRow label="DB Name" value="DB_NAME (default: mygameshelf)" mono />
      </Section>
    </div>
  );
}
