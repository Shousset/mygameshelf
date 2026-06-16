"use client";

import { useEffect, useState } from "react";
import { ExternalLink, RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";
import { getSyncStatus, syncAll, steamOpenIdLogin, steamOpenIdVerify, getPlan, OfflineError, type SyncStatus, type PlanInfo } from "@/lib/api";

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
    // Poll faster while a job is queued/running so progress shows up quickly.
    const ms = status?.in_progress ? 4_000 : 15_000;
    const id = setInterval(refresh, ms);
    return () => clearInterval(id);
  }, [status?.in_progress]);

  // Handle the return from "Sign in through Steam": Steam redirects back here
  // with openid.* params; POST them to the backend to link the SteamID.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const sp = new URLSearchParams(window.location.search);
    if (sp.get("openid.mode") !== "id_res") return;
    const params: Record<string, string> = {};
    sp.forEach((v, k) => { if (k.startsWith("openid.")) params[k] = v; });
    (async () => {
      try {
        const res = await steamOpenIdVerify(params);
        setMsg({ kind: "ok", text: `Steam account linked (${res.steam_id}).` });
        await refresh();
      } catch (e) {
        setMsg({ kind: "err", text: (e as Error).message || "Steam sign-in failed." });
      } finally {
        // Strip the openid params so a refresh doesn't re-trigger verification.
        window.history.replaceState({}, "", window.location.pathname);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLinkSteam = async () => {
    try {
      const { redirect_url } = await steamOpenIdLogin();
      window.location.href = redirect_url;
    } catch (e) {
      const text = e instanceof OfflineError
        ? "Backend unreachable. Start the FastAPI server, then try again."
        : (e as Error).message || "Could not start Steam sign-in.";
      setMsg({ kind: "err", text });
    }
  };

  const handleSync = async () => {
    setLoading(true);
    setMsg(null);
    try {
      // Sync now runs in the background worker; this just queues it.
      await syncAll();
      setMsg({
        kind: "ok",
        text: "Sync queued — running in the background. This page updates automatically.",
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
  const activeStatus = status?.active_job?.status;
  const btnLabel = loading
    ? "Queuing..."
    : activeStatus === "running"
      ? "Syncing..."
      : activeStatus === "queued"
        ? "Queued..."
        : "Sync now";
  const lastRun = status?.last_run;

  return (
    <Section title="🔄 Auto-Sync">
      <p style={{ margin: "0 0 1rem", color: "#8f98a0", fontSize: "0.875rem" }}>
        Re-fetches Steam playtime and achievements for every game linked to a Steam AppID. Runs automatically every 6 hours; you can also trigger it manually here.
      </p>

      <InfoRow label="Steam account" value={status?.steam_linked ? "Linked ✓" : "Not linked"} />
      <div style={{ marginTop: "0.75rem", marginBottom: "1rem" }}>
        <button className="btn-primary" onClick={handleLinkSteam}>
          {status?.steam_configured ? "Re-link Steam account" : "Sign in through Steam"}
        </button>
        <span style={{ marginLeft: "0.75rem", color: "#8f98a0", fontSize: "0.8rem" }}>
          Links your SteamID automatically — no need to paste your 17-digit ID.
        </span>
      </div>
      <InfoRow label="Last sync" value={fmtTime(lastRun?.finished_at ?? lastRun?.started_at ?? null)} />
      <InfoRow label="Last result" value={lastRun ? `${lastRun.games_synced} synced, ${lastRun.errors} errors (${lastRun.trigger ?? "?"})` : "—"} />
      <InfoRow label="Next scheduled run" value={fmtTime(status?.next_run_at ?? null)} mono />
      <InfoRow label="Steam API calls today" value={status?.steam_calls_today != null ? String(status.steam_calls_today) : "—"} mono />

      <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <button
          className="btn-primary"
          onClick={handleSync}
          disabled={inProgress || !status?.steam_configured}
          title={!status?.steam_configured ? "Set STEAM_API_KEY and STEAM_ID in mygameshelf/.env first" : undefined}
        >
          <RefreshCw size={14} style={{ marginRight: "0.4rem", display: "inline", animation: inProgress ? "spin 1s linear infinite" : undefined }} />
          {btnLabel}
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

function PlanSection() {
  const [plan, setPlan] = useState<PlanInfo | null>(null);

  useEffect(() => {
    getPlan().then(setPlan).catch(() => {});
  }, []);

  const unlimited = plan?.max_games == null;
  const pct = plan && plan.max_games
    ? Math.min(100, Math.round((plan.games_used / plan.max_games) * 100))
    : 0;
  const near = !unlimited && pct >= 80;

  return (
    <Section title="💳 Plan">
      <InfoRow label="Current plan" value={plan ? (plan.plan === "pro" ? "Pro" : "Free") : "—"} />
      <InfoRow
        label="Library usage"
        value={plan ? (unlimited ? `${plan.games_used} games (unlimited)` : `${plan.games_used} / ${plan.max_games} games`) : "—"}
      />
      {plan && !unlimited && (
        <div style={{ marginTop: "0.75rem" }}>
          <div style={{ height: 8, borderRadius: 6, background: "rgba(102,192,244,0.15)", overflow: "hidden" }}>
            <div style={{ width: `${pct}%`, height: "100%", background: near ? "#fbbf24" : "#66c0f4", transition: "width 0.3s" }} />
          </div>
          {plan.games_remaining === 0 ? (
            <p style={{ margin: "0.6rem 0 0", color: "#fca5a5", fontSize: "0.82rem" }}>
              Library full. Upgrade to Pro for unlimited games.
            </p>
          ) : near ? (
            <p style={{ margin: "0.6rem 0 0", color: "#fbbf24", fontSize: "0.82rem" }}>
              {plan.games_remaining} slot(s) left on Free. Upgrade to Pro for unlimited.
            </p>
          ) : null}
        </div>
      )}
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

      <PlanSection />

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
