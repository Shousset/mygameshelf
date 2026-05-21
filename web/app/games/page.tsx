"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getGames, addGame, updateStatus, rateGame, deleteGame,
  type Game,
} from "@/lib/api";
import { Plus, Trash2, Star, RefreshCw, Filter, LayoutGrid, List } from "lucide-react";
import GameCover from "@/components/GameCover";
import { CoverCardSkeleton } from "@/components/Skeleton";

const STATUSES = ["Backlog", "Playing", "Completed", "Abandoned"] as const;

function statusBadge(s: string) {
  const cls: Record<string, string> = {
    Backlog: "badge badge-backlog",
    Playing: "badge badge-playing",
    Completed: "badge badge-completed",
    Abandoned: "badge badge-abandoned",
  };
  return cls[s] || "badge badge-backlog";
}

export default function GamesPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [ratingModal, setRatingModal] = useState<Game | null>(null);
  const [viewMode, setViewMode] = useState<"list" | "grid">(() => {
    if (typeof window === "undefined") return "grid";
    return (window.localStorage.getItem("mgs.viewMode") as "list" | "grid") || "grid";
  });

  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem("mgs.viewMode", viewMode);
  }, [viewMode]);

  const load = useCallback((sf?: string) => {
    setLoading(true);
    getGames(sf || undefined)
      .then(setGames)
      .catch(() => setError("Could not load games"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this game? Sessions will also be removed.")) return;
    await deleteGame(id).catch(() => {});
    load(filter || undefined);
  };

  const handleStatusChange = async (id: number, newStatus: string) => {
    await updateStatus(id, newStatus).catch(() => {});
    load(filter || undefined);
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "2rem", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "2rem", fontWeight: 800 }}>
            <span className="gradient-text">Game Collection</span>
          </h1>
          <p style={{ margin: "0.4rem 0 0", color: "#8f98a0" }}>
            {games.length} games tracked
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>
          <Plus size={16} style={{ display: "inline", marginRight: "0.4rem", verticalAlign: "middle" }} />
          Add Game
        </button>
      </div>

      {/* Filter bar */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "#8f98a0", fontSize: "0.85rem" }}>
          <Filter size={14} /> Filter:
        </div>
        {["", ...STATUSES].map((s) => (
          <button
            key={s}
            onClick={() => { setFilter(s); load(s || undefined); }}
            style={{
              padding: "0.35rem 0.85rem",
              borderRadius: "99px",
              border: "1px solid",
              fontSize: "0.8rem",
              fontFamily: "Outfit, sans-serif",
              cursor: "pointer",
              transition: "all 0.2s",
              borderColor: filter === s ? "#66c0f4" : "rgba(143, 152, 160, 0.25)",
              background: filter === s ? "rgba(102, 192, 244, 0.22)" : "transparent",
              color: filter === s ? "#c7d5e0" : "#8f98a0",
            }}
          >
            {s || "All"}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", gap: "0.4rem", alignItems: "center" }}>
          <div style={{ display: "flex", border: "1px solid rgba(143, 152, 160, 0.25)", borderRadius: "4px", overflow: "hidden" }}>
            <button
              onClick={() => setViewMode("grid")}
              title="Grid view"
              style={{
                background: viewMode === "grid" ? "rgba(102, 192, 244, 0.22)" : "transparent",
                color: viewMode === "grid" ? "#c7d5e0" : "#8f98a0",
                border: "none",
                padding: "0.4rem 0.6rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
              }}
            >
              <LayoutGrid size={14} />
            </button>
            <button
              onClick={() => setViewMode("list")}
              title="List view"
              style={{
                background: viewMode === "list" ? "rgba(102, 192, 244, 0.22)" : "transparent",
                color: viewMode === "list" ? "#c7d5e0" : "#8f98a0",
                border: "none",
                padding: "0.4rem 0.6rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
              }}
            >
              <List size={14} />
            </button>
          </div>
          <button className="btn-ghost" style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem" }} onClick={() => load(filter || undefined)}>
            <RefreshCw size={13} style={{ display: "inline", marginRight: "0.3rem", verticalAlign: "middle" }} />
            Refresh
          </button>
        </div>
      </div>

      {error && <p style={{ color: "#f87171" }}>{error}</p>}

      {/* List or Grid */}
      {loading ? (
        viewMode === "grid" ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: "1rem" }}>
            {Array.from({ length: 8 }).map((_, i) => <CoverCardSkeleton key={i} />)}
          </div>
        ) : (
          <div className="glass" style={{ padding: "2rem", textAlign: "center", color: "#8f98a0" }}>Loading…</div>
        )
      ) : games.length === 0 ? (
        <div className="glass" style={{ padding: "2rem", textAlign: "center", color: "#8f98a0" }}>
          No games found. Add one above!
        </div>
      ) : viewMode === "grid" ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: "1rem" }}>
          {games.map((g) => (
            <div key={g.id} className="cover-card" style={{ position: "relative", display: "flex", flexDirection: "column" }}>
              <div style={{ position: "relative" }}>
                <GameCover appid={g.external_id} title={g.title} variant="library" width="100%" height={250} rounded={0} />
                <div style={{ position: "absolute", top: 8, left: 8 }}>
                  <span className={statusBadge(g.status)}>{g.status}</span>
                </div>
                {g.rating !== null && g.rating !== undefined && (
                  <div style={{ position: "absolute", top: 8, right: 8, background: "rgba(0,0,0,0.65)", color: "#fcd34d", padding: "0.15rem 0.4rem", borderRadius: 2, fontSize: "0.72rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "0.2rem" }}>
                    <Star size={11} fill="#fcd34d" /> {g.rating}
                  </div>
                )}
              </div>
              <div style={{ padding: "0.55rem 0.75rem 0.7rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                <div style={{ fontWeight: 600, fontSize: "0.85rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: "#f5f9fc" }}>{g.title}</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.72rem", color: "#8f98a0" }}>
                  <span>{g.platform || "—"}</span>
                  <span style={{ color: "#66c0f4", fontWeight: 600 }}>{g.hours_played}h</span>
                </div>
                <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.3rem" }}>
                  <select
                    value={g.status}
                    onChange={(e) => handleStatusChange(g.id, e.target.value)}
                    className="form-select"
                    style={{ padding: "0.2rem 0.4rem", fontSize: "0.72rem", flex: 1 }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <button
                    onClick={() => setRatingModal(g)}
                    title="Rate"
                    style={{ background: "rgba(252, 211, 77, 0.10)", border: "1px solid rgba(252, 211, 77, 0.3)", borderRadius: 3, cursor: "pointer", color: g.rating ? "#fcd34d" : "#8f98a0", padding: "0.2rem 0.4rem", display: "flex", alignItems: "center" }}
                  >
                    <Star size={12} fill={g.rating ? "#fcd34d" : "none"} />
                  </button>
                  <button
                    onClick={() => handleDelete(g.id)}
                    title="Delete"
                    style={{ background: "rgba(196, 58, 58, 0.10)", border: "1px solid rgba(196, 58, 58, 0.3)", borderRadius: 3, cursor: "pointer", color: "#e88a8a", padding: "0.2rem 0.4rem", display: "flex", alignItems: "center" }}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="glass" style={{ overflow: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th></th>
                <th>Title</th>
                <th>Platform</th>
                <th>Genre</th>
                <th>Year</th>
                <th>Status</th>
                <th>Rating</th>
                <th>Hours</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {games.map((g) => (
                <tr key={g.id}>
                  <td style={{ width: "78px" }}>
                    <GameCover appid={g.external_id} title={g.title} variant="capsule" width={62} height={29} rounded={3} />
                  </td>
                  <td style={{ fontWeight: 600 }}>{g.title}</td>
                  <td style={{ color: "#8f98a0" }}>{g.platform || "—"}</td>
                  <td style={{ color: "#8f98a0" }}>{g.genre || "—"}</td>
                  <td style={{ color: "#8f98a0" }}>{g.year || "—"}</td>
                  <td>
                    <select
                      value={g.status}
                      onChange={(e) => handleStatusChange(g.id, e.target.value)}
                      className="form-select"
                      style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem", width: "auto" }}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button
                      onClick={() => setRatingModal(g)}
                      style={{ background: "none", border: "none", cursor: "pointer", color: g.rating ? "#fcd34d" : "#8f98a0", display: "flex", alignItems: "center", gap: "0.3rem", fontFamily: "Outfit, sans-serif", fontSize: "0.875rem" }}
                    >
                      <Star size={14} fill={g.rating ? "#fcd34d" : "none"} />
                      {g.rating ?? "Rate"}
                    </button>
                  </td>
                  <td style={{ color: "#66c0f4" }}>{g.hours_played}h</td>
                  <td>
                    <button className="btn-danger" style={{ padding: "0.3rem 0.65rem", fontSize: "0.78rem" }} onClick={() => handleDelete(g.id)}>
                      <Trash2 size={13} style={{ display: "inline", marginRight: "0.3rem", verticalAlign: "middle" }} />
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && <AddGameModal onClose={() => { setShowAdd(false); load(filter || undefined); }} />}
      {ratingModal && (
        <RatingModal
          game={ratingModal}
          onClose={() => { setRatingModal(null); load(filter || undefined); }}
        />
      )}
    </div>
  );
}

function AddGameModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ title: "", platform: "", genre: "", year: "", status: "Backlog", notes: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async () => {
    if (!form.title.trim()) { setError("Title is required"); return; }
    setLoading(true);
    try {
      await addGame({
        title: form.title,
        platform: form.platform,
        genre: form.genre,
        year: form.year ? parseInt(form.year) : null,
        status: form.status as Game["status"],
        notes: form.notes,
      });
      onClose();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="glass" style={{ width: "100%", maxWidth: "460px", padding: "2rem" }} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: "0 0 1.5rem", fontWeight: 700 }}>➕ Add Game</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
          <input className="form-input" placeholder="Title *" value={form.title} onChange={(e) => set("title", e.target.value)} />
          <input className="form-input" placeholder="Platform (e.g. PC, PS5)" value={form.platform} onChange={(e) => set("platform", e.target.value)} />
          <input className="form-input" placeholder="Genre (e.g. RPG, FPS)" value={form.genre} onChange={(e) => set("genre", e.target.value)} />
          <input className="form-input" placeholder="Release Year" type="number" value={form.year} onChange={(e) => set("year", e.target.value)} />
          <select className="form-select" value={form.status} onChange={(e) => set("status", e.target.value)}>
            {["Backlog", "Playing", "Completed", "Abandoned"].map((s) => <option key={s}>{s}</option>)}
          </select>
          <textarea className="form-input" placeholder="Notes (optional)" value={form.notes} onChange={(e) => set("notes", e.target.value)} style={{ resize: "vertical", minHeight: "80px" }} />
          {error && <p style={{ color: "#f87171", margin: 0, fontSize: "0.85rem" }}>{error}</p>}
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn-primary" onClick={handleSubmit} disabled={loading}>
              {loading ? "Saving…" : "Add Game"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function RatingModal({ game, onClose }: { game: Game; onClose: () => void }) {
  const [rating, setRating] = useState(game.rating?.toString() || "");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    setLoading(true);
    await rateGame(game.id, parseFloat(rating), notes).catch(() => {});
    setLoading(false);
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="glass" style={{ width: "100%", maxWidth: "380px", padding: "2rem" }} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: "0 0 0.5rem", fontWeight: 700 }}>⭐ Rate Game</h2>
        <p style={{ margin: "0 0 1.25rem", color: "#8f98a0", fontSize: "0.9rem" }}>{game.title}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
          <input className="form-input" placeholder="Rating (0 – 10)" type="number" min={0} max={10} step={0.5} value={rating} onChange={(e) => setRating(e.target.value)} />
          <textarea className="form-input" placeholder="Review notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} style={{ resize: "vertical", minHeight: "70px" }} />
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn-primary" onClick={handleSave} disabled={loading || !rating}>
              {loading ? "Saving…" : "Save Rating"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
