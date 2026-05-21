"use client";

import { useEffect, useState, useCallback } from "react";
import { getGames, getAchievements, addAchievement, toggleAchievement, syncSteamAchievements, type Game, type Achievement } from "@/lib/api";
import { Trophy, Plus, CheckCircle2, Circle, RefreshCw } from "lucide-react";
import GameCover from "@/components/GameCover";

function formatUnlockDate(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function RarityBadge({ pct }: { pct: number | null }) {
  if (pct === null || pct === undefined) {
    return <span style={{ color: "#56707f", fontSize: "0.75rem" }}>—</span>;
  }
  // Steam-style tiers: < 5% ultra-rare gold, < 15% rare purple, < 50% uncommon blue, else common grey
  let color = "#8f98a0";
  let label = "common";
  if (pct < 5) { color = "#facc15"; label = "ultra rare"; }
  else if (pct < 15) { color = "#c084fc"; label = "rare"; }
  else if (pct < 50) { color = "#60a5fa"; label = "uncommon"; }
  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-end" }}>
      <span style={{ color, fontWeight: 700, fontSize: "0.85rem" }}>
        {pct.toFixed(1)}%
      </span>
      <span style={{ color: "#8f98a0", fontSize: "0.65rem", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </span>
    </div>
  );
}

function ProgressBar({ achievements }: { achievements: Achievement[] }) {
  const unlocked = achievements.filter((a) => a.is_unlocked).length;
  const total = achievements.length;
  const pct = total === 0 ? 0 : (unlocked / total) * 100;
  return (
    <div className="glass" style={{ padding: "1rem 1.25rem", marginBottom: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.5rem" }}>
        <span style={{ fontSize: "0.78rem", color: "#8f98a0", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
          Progress
        </span>
        <span style={{ fontSize: "0.85rem", color: "#c7d5e0" }}>
          <strong style={{ color: "#4ade80" }}>{unlocked}</strong> / {total} unlocked ·{" "}
          <strong>{pct.toFixed(1)}%</strong>
        </span>
      </div>
      <div style={{ height: "8px", background: "rgba(255,255,255,0.05)", borderRadius: "999px", overflow: "hidden" }}>
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: "linear-gradient(90deg, #4ade80, #22d3ee)",
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}

export default function AchievementsPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [selectedGame, setSelectedGame] = useState<Game | null>(null);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  useEffect(() => { getGames().then(setGames); }, []);

  const loadAchievements = useCallback((game: Game) => {
    setSelectedGame(game);
    setLoading(true);
    getAchievements(game.id).then(setAchievements).finally(() => setLoading(false));
  }, []);

  const handleToggle = async (ach: Achievement) => {
    const newStatus = !ach.is_unlocked;
    setAchievements(achievements.map((a) => a.id === ach.id ? { ...a, is_unlocked: newStatus } : a));
    await toggleAchievement(ach.id, newStatus).catch(() => {});
    // Reload dynamically to get the accurate timestamp
    if (selectedGame) loadAchievements(selectedGame);
  };

  const handleSync = async () => {
    if (!selectedGame) return;
    setSyncing(true);
    try {
      await syncSteamAchievements(selectedGame.id);
      loadAchievements(selectedGame);
    } catch (e: any) {
      alert("Error syncing: " + (e.message || "Steam API failed"));
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ margin: 0, fontSize: "2rem", fontWeight: 800 }}>
          <span className="gradient-text">Achievements</span> 🏆
        </h1>
        <p style={{ margin: "0.4rem 0 0", color: "#8f98a0" }}>Track your custom game milestones</p>
      </div>

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
                  onClick={() => loadAchievements(g)}
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
                    <div style={{ color: "#8f98a0", fontSize: "0.7rem" }}>{g.platform || "No Platform"}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Achievements panel */}
        <div>
          {selectedGame ? (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <div>
                  <h2 style={{ margin: 0, fontWeight: 700 }}>{selectedGame.title}</h2>
                  <p style={{ margin: "0.2rem 0 0", color: "#8f98a0", fontSize: "0.85rem" }}>
                    {achievements.filter(a => a.is_unlocked).length} / {achievements.length} Unlocked
                  </p>
                </div>
                <div style={{ display: "flex", gap: "0.75rem" }}>
                  {selectedGame.platform === "Steam" && (
                    <button className="btn-ghost" onClick={handleSync} disabled={syncing}>
                      <RefreshCw size={15} style={{ display: "inline", marginRight: "0.4rem", verticalAlign: "middle", animation: syncing ? "spin 1s linear infinite" : "none" }} />
                      {syncing ? "Syncing..." : "Sync Steam"}
                    </button>
                  )}
                  <button className="btn-primary" onClick={() => setShowAdd(true)}>
                    <Plus size={15} style={{ display: "inline", marginRight: "0.4rem", verticalAlign: "middle" }} />
                    Add Achievement
                  </button>
                </div>
              </div>

              {achievements.length > 0 && <ProgressBar achievements={achievements} />}

              <div className="glass" style={{ overflow: "auto" }}>
                {loading ? (
                  <div style={{ padding: "2rem", textAlign: "center", color: "#8f98a0" }}>Loading…</div>
                ) : achievements.length === 0 ? (
                  <div style={{ padding: "2rem", textAlign: "center", color: "#8f98a0" }}>
                    No achievements created yet. Hit "Add Achievement" to start tracking!
                  </div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th style={{ width: "64px" }}></th>
                        <th style={{ width: "40px" }}></th>
                        <th>Status</th>
                        <th>Achievement</th>
                        <th>Description</th>
                        <th style={{ textAlign: "right" }}>Rarity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {achievements.map((a) => {
                        const iconSrc = a.is_unlocked ? (a.icon_url || a.icon_gray_url) : (a.icon_gray_url || a.icon_url);
                        const hiddenLocked = a.is_hidden && !a.is_unlocked;
                        return (
                          <tr key={a.id} style={{ transition: "opacity 0.2s" }}>
                            <td>
                              {iconSrc ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                  src={iconSrc}
                                  alt=""
                                  width={48}
                                  height={48}
                                  style={{
                                    borderRadius: "8px",
                                    display: "block",
                                    filter: a.is_unlocked ? "none" : "grayscale(0.6) brightness(0.7)",
                                  }}
                                />
                              ) : (
                                <div
                                  style={{
                                    width: 48,
                                    height: 48,
                                    borderRadius: "8px",
                                    background: "rgba(102, 192, 244, 0.10)",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    color: "#8f98a0",
                                  }}
                                >
                                  <Trophy size={20} />
                                </div>
                              )}
                            </td>
                            <td>
                              <button
                                onClick={() => handleToggle(a)}
                                style={{ background: "none", border: "none", cursor: "pointer", color: a.is_unlocked ? "#4ade80" : "#8f98a0", padding: 0 }}
                              >
                                {a.is_unlocked ? <CheckCircle2 size={22} /> : <Circle size={22} />}
                              </button>
                            </td>
                            <td style={{ color: a.is_unlocked ? "#4ade80" : "#8f98a0", fontWeight: a.is_unlocked ? 600 : 400, whiteSpace: "nowrap" }}>
                              {a.is_unlocked ? (
                                <>
                                  <div>Unlocked</div>
                                  {a.unlocked_at && (
                                    <div style={{ color: "#8f98a0", fontSize: "0.7rem", fontWeight: 400, marginTop: "0.15rem" }}>
                                      {formatUnlockDate(a.unlocked_at)}
                                    </div>
                                  )}
                                </>
                              ) : "Locked"}
                            </td>
                            <td style={{ color: "#f5f9fc", fontWeight: 600 }}>
                              <div>{hiddenLocked ? <span style={{ color: "#8f98a0", fontStyle: "italic" }}>🔒 Hidden achievement</span> : a.title}</div>
                            </td>
                            <td style={{ color: "#8f98a0" }}>
                              {hiddenLocked ? "—" : (a.description || "—")}
                            </td>
                            <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                              <RarityBadge pct={a.global_pct} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          ) : (
            <div className="glass" style={{ padding: "3rem", textAlign: "center", color: "#8f98a0" }}>
              <Trophy size={36} style={{ marginBottom: "0.75rem", opacity: 0.4 }} />
              <p style={{ margin: 0 }}>Select a game to view or add achievements</p>
            </div>
          )}
        </div>
      </div>

      {showAdd && selectedGame && (
        <AddAchievementModal
          game={selectedGame}
          onClose={() => {
            setShowAdd(false);
            loadAchievements(selectedGame);
          }}
        />
      )}
    </div>
  );
}

function AddAchievementModal({ game, onClose }: { game: Game; onClose: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!title.trim()) { setError("Title is required"); return; }
    setLoading(true);
    try {
      await addAchievement(game.id, title, description);
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
        <h2 style={{ margin: "0 0 0.5rem", fontWeight: 700 }}>🏆 Add Achievement</h2>
        <p style={{ margin: "0 0 1.25rem", color: "#8f98a0", fontSize: "0.9rem" }}>{game.title}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
          <input className="form-input" placeholder="Achievement Title *" value={title} onChange={(e) => setTitle(e.target.value)} />
          <textarea className="form-input" placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} style={{ resize: "vertical", minHeight: "70px" }} />
          {error && <p style={{ color: "#f87171", margin: 0, fontSize: "0.85rem" }}>{error}</p>}
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn-primary" onClick={handleSave} disabled={loading}>{loading ? "Saving…" : "Save"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
