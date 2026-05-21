"use client";

import { useEffect, useState, useCallback } from "react";
import { getGames, getSessions, logSession, getRecentlyPlayed, getSteamStats, refreshGame, OfflineError, type Game, type Session, type RecentlyPlayedGame, type SteamStats } from "@/lib/api";
import { Timer, Plus, Flame, RefreshCw, Clock } from "lucide-react";
import GameCover from "@/components/GameCover";

export default function SessionsPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [selectedGame, setSelectedGame] = useState<Game | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [recent, setRecent] = useState<RecentlyPlayedGame[] | null>(null);
  const [recentError, setRecentError] = useState<string>("");

  useEffect(() => { getGames().then(setGames); }, []);

  useEffect(() => {
    getRecentlyPlayed()
      .then((r) => setRecent(r.games))
      .catch((e) => {
        if (e instanceof OfflineError) setRecentError("Backend unreachable");
        else setRecentError((e as Error).message || "Couldn't load recent activity");
      });
  }, []);

  const loadSessions = useCallback((game: Game) => {
    setSelectedGame(game);
    setLoadingSessions(true);
    getSessions(game.id).then(setSessions).finally(() => setLoadingSessions(false));
  }, []);

  const openLocalGame = (localId: number) => {
    const g = games.find((x) => x.id === localId);
    if (g) loadSessions(g);
  };

  return (
    <div>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ margin: 0, fontSize: "2rem", fontWeight: 800 }}>
          <span className="gradient-text">Play Sessions</span> ⏱
        </h1>
        <p style={{ margin: "0.4rem 0 0", color: "#8f98a0" }}>Track your gaming sessions</p>
      </div>

      <RecentlyPlayedRail
        recent={recent}
        error={recentError}
        onOpenLocal={openLocalGame}
      />

      <div style={{ display: "grid", gridTemplateColumns: "minmax(200px, 280px) 1fr", gap: "1.5rem", alignItems: "start" }}>
        {/* Game picker */}
        <div className="glass" style={{ padding: "1.25rem" }}>
          <p style={{ margin: "0 0 0.75rem", fontSize: "0.75rem", color: "#8f98a0", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
            Select a game
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", maxHeight: "450px", overflowY: "auto" }}>
            {games.map((g) => {
              const active = selectedGame?.id === g.id;
              return (
                <button
                  key={g.id}
                  onClick={() => loadSessions(g)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.6rem",
                    background: active ? "rgba(102, 192, 244, 0.18)" : "rgba(255,255,255,0.025)",
                    border: `1px solid ${active ? "rgba(102, 192, 244, 0.45)" : "rgba(143, 152, 160, 0.15)"}`,
                    borderRadius: "4px",
                    color: "#c7d5e0",
                    cursor: "pointer",
                    fontFamily: "Outfit, sans-serif",
                    fontSize: "0.85rem",
                    fontWeight: active ? 600 : 400,
                    padding: "0.5rem 0.6rem",
                    textAlign: "left",
                    transition: "background 0.15s, border-color 0.15s",
                  }}
                >
                  <GameCover appid={g.external_id} title={g.title} variant="capsule" width={62} height={29} rounded={3} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{g.title}</div>
                    <div style={{ color: "#8f98a0", fontSize: "0.7rem" }}>{g.hours_played}h · {g.platform || "—"}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Sessions panel */}
        <div>
          {selectedGame ? (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <div>
                  <h2 style={{ margin: 0, fontWeight: 700 }}>{selectedGame.title}</h2>
                  <p style={{ margin: "0.2rem 0 0", color: "#8f98a0", fontSize: "0.85rem" }}>
                    {selectedGame.hours_played}h total · {sessions.length} sessions recorded
                  </p>
                </div>
                <button className="btn-primary" onClick={() => setShowLog(true)}>
                  <Plus size={15} style={{ display: "inline", marginRight: "0.4rem", verticalAlign: "middle" }} />
                  Log Session
                </button>
              </div>

              <SteamStatsPanel
                game={selectedGame}
                onRefreshed={() => loadSessions(selectedGame)}
              />

              <div className="glass" style={{ overflow: "auto" }}>
                {loadingSessions ? (
                  <div style={{ padding: "2rem", textAlign: "center", color: "#8f98a0" }}>Loading…</div>
                ) : sessions.length === 0 ? (
                  <div style={{ padding: "2rem", textAlign: "center", color: "#8f98a0" }}>
                    No sessions logged yet. Hit "Log Session" to start!
                  </div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Hours</th>
                        <th>Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((s, i) => (
                        <tr key={i}>
                          <td style={{ color: "#8f98a0" }}>{s.date}</td>
                          <td style={{ color: "#22d3ee", fontWeight: 600 }}>{s.hours}h</td>
                          <td style={{ color: "#8f98a0" }}>{s.notes || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          ) : (
            <div className="glass" style={{ padding: "3rem", textAlign: "center", color: "#8f98a0" }}>
              <Timer size={36} style={{ marginBottom: "0.75rem", opacity: 0.4 }} />
              <p style={{ margin: 0 }}>Select a game to view or log sessions</p>
            </div>
          )}
        </div>
      </div>

      {showLog && selectedGame && (
        <LogModal
          game={selectedGame}
          onClose={() => {
            setShowLog(false);
            loadSessions(selectedGame);
          }}
        />
      )}
    </div>
  );
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const diffMs = Date.now() - d.getTime();
  const mins = Math.round(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return d.toLocaleDateString();
}

function SteamStatsPanel({
  game,
  onRefreshed,
}: {
  game: Game;
  onRefreshed: () => void;
}) {
  const [stats, setStats] = useState<SteamStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    setStats(null);
    setError("");
    setLoading(true);
    getSteamStats(game.id)
      .then(setStats)
      .catch((e) => setError(e instanceof OfflineError ? "Backend offline" : (e as Error).message))
      .finally(() => setLoading(false));
  }, [game.id]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError("");
    try {
      const fresh = await refreshGame(game.id);
      setStats(fresh);
      onRefreshed();
    } catch (e) {
      setError(e instanceof OfflineError ? "Backend offline" : (e as Error).message);
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return (
      <div className="glass" style={{ padding: "0.85rem 1rem", marginBottom: "1rem", color: "#8f98a0", fontSize: "0.85rem" }}>
        Loading Steam activity…
      </div>
    );
  }

  if (!stats || !stats.is_steam_linked) {
    return null; // Not a Steam game — nothing to show
  }

  return (
    <div className="glass" style={{ padding: "1rem 1.25rem", marginBottom: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <Clock size={14} style={{ color: "#66c0f4" }} />
          <span style={{ fontSize: "0.78rem", color: "#8f98a0", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
            Steam Activity
          </span>
        </div>
        <button
          className="btn-ghost"
          onClick={handleRefresh}
          disabled={refreshing}
          style={{ fontSize: "0.8rem", padding: "0.35rem 0.7rem" }}
          title="Pull latest playtime + achievements + last-played from Steam"
        >
          <RefreshCw size={13} style={{ display: "inline", marginRight: "0.35rem", verticalAlign: "middle", animation: refreshing ? "spin 1s linear infinite" : undefined }} />
          {refreshing ? "Refreshing..." : "Refresh from Steam"}
        </button>
      </div>

      <div style={{ marginTop: "0.85rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "0.85rem" }}>
        <StatTile label="Total on Steam" value={`${stats.total_hours.toFixed(1)}h`} />
        <StatTile label="Last 2 weeks" value={`${stats.hours_2weeks.toFixed(1)}h`} accent={stats.hours_2weeks > 0} />
        <StatTile label="Last played" value={formatRelative(stats.last_played_at)} />
        <StatTile label="Last logged session" value={stats.last_session_date || "—"} />
      </div>

      {error && (
        <p style={{ margin: "0.75rem 0 0", color: "#fca5a5", fontSize: "0.82rem" }}>{error}</p>
      )}
      <style jsx>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

function StatTile({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.03)",
      border: "1px solid rgba(102, 192, 244, 0.18)",
      borderRadius: "8px",
      padding: "0.6rem 0.75rem",
    }}>
      <div style={{ fontSize: "0.7rem", color: "#8f98a0", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ marginTop: "0.25rem", fontSize: "1rem", fontWeight: 700, color: accent ? "#22d3ee" : "#c7d5e0" }}>
        {value}
      </div>
    </div>
  );
}

function RecentlyPlayedRail({
  recent,
  error,
  onOpenLocal,
}: {
  recent: RecentlyPlayedGame[] | null;
  error: string;
  onOpenLocal: (localId: number) => void;
}) {
  if (error) {
    return (
      <div className="glass" style={{ padding: "1rem 1.25rem", marginBottom: "1.5rem", color: "#8f98a0", fontSize: "0.85rem" }}>
        <Flame size={14} style={{ display: "inline", marginRight: "0.4rem", verticalAlign: "middle", color: "#66c0f4" }} />
        Recently played from Steam — <span style={{ color: "#fca5a5" }}>{error}</span>
      </div>
    );
  }
  if (recent === null) {
    return (
      <div className="glass" style={{ padding: "1rem 1.25rem", marginBottom: "1.5rem", color: "#8f98a0", fontSize: "0.85rem" }}>
        Loading recent Steam activity…
      </div>
    );
  }
  if (recent.length === 0) {
    return (
      <div className="glass" style={{ padding: "1rem 1.25rem", marginBottom: "1.5rem", color: "#8f98a0", fontSize: "0.85rem" }}>
        <Flame size={14} style={{ display: "inline", marginRight: "0.4rem", verticalAlign: "middle", color: "#66c0f4" }} />
        No Steam activity in the last 2 weeks.
      </div>
    );
  }
  return (
    <div className="glass" style={{ padding: "1rem 1.25rem", marginBottom: "1.5rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <Flame size={16} style={{ color: "#66c0f4" }} />
        <span style={{ fontSize: "0.78rem", color: "#8f98a0", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
          Recently played on Steam · last 2 weeks
        </span>
      </div>
      <div style={{ display: "flex", gap: "0.75rem", overflowX: "auto", paddingBottom: "0.25rem" }}>
        {recent.map((g) => {
          const headerUrl = `https://cdn.akamai.steamstatic.com/steam/apps/${g.appid}/header.jpg`;
          const clickable = !!g.local_game_id;
          return (
            <button
              key={g.appid}
              onClick={() => g.local_game_id && onOpenLocal(g.local_game_id)}
              disabled={!clickable}
              title={clickable ? `Open ${g.local_title}'s sessions` : "This game is not in your local library"}
              className={clickable ? "lift-on-hover" : ""}
              style={{
                flex: "0 0 240px",
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(102, 192, 244, 0.18)",
                borderRadius: "4px",
                padding: 0,
                overflow: "hidden",
                cursor: clickable ? "pointer" : "default",
                color: "#c7d5e0",
                fontFamily: "Outfit, sans-serif",
                textAlign: "left",
                opacity: clickable ? 1 : 0.65,
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={headerUrl}
                alt=""
                width={240}
                height={112}
                style={{ display: "block", width: "100%", height: "112px", objectFit: "cover" }}
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
              />
              <div style={{ padding: "0.6rem 0.75rem" }}>
                <div style={{ fontWeight: 600, fontSize: "0.85rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {g.name}
                </div>
                <div style={{ marginTop: "0.2rem", fontSize: "0.72rem", color: "#8f98a0" }}>
                  <span style={{ color: "#22d3ee", fontWeight: 600 }}>{g.playtime_2weeks_hours}h</span>
                  {" "}this week · {g.playtime_forever_hours}h total
                </div>
                {!clickable && (
                  <div style={{ marginTop: "0.2rem", fontSize: "0.7rem", color: "#8f98a0", fontStyle: "italic" }}>
                    Not in library
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function LogModal({ game, onClose }: { game: Game; onClose: () => void }) {
  const [hours, setHours] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    const h = parseFloat(hours);
    if (!h || h <= 0) { setError("Enter a valid number of hours"); return; }
    setLoading(true);
    try {
      await logSession(game.id, h, notes);
      onClose();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="glass" style={{ width: "100%", maxWidth: "380px", padding: "2rem" }} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: "0 0 0.5rem", fontWeight: 700 }}>⏱ Log Session</h2>
        <p style={{ margin: "0 0 1.25rem", color: "#8f98a0", fontSize: "0.9rem" }}>{game.title}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
          <input className="form-input" placeholder="Hours played (e.g. 1.5)" type="number" min={0.1} step={0.5} value={hours} onChange={(e) => setHours(e.target.value)} />
          <textarea className="form-input" placeholder="Session notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} style={{ resize: "vertical", minHeight: "70px" }} />
          {error && <p style={{ color: "#f87171", margin: 0, fontSize: "0.85rem" }}>{error}</p>}
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn-primary" onClick={handleSave} disabled={loading}>{loading ? "Saving…" : "Log Session"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
