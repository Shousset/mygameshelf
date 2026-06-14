"use client";

import { useEffect, useState, useCallback } from "react";
import { getWishlist, addWishlistItem, removeWishlistItem, type WishlistItem } from "@/lib/api";
import { Plus, Trash2 } from "lucide-react";

const PRIORITIES = ["High", "Medium", "Low"] as const;

export default function WishlistPage() {
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    getWishlist().then(setItems).catch(() => setItems([])).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRemove = async (id: number) => {
    if (!confirm("Remove from wishlist?")) return;
    await removeWishlistItem(id).catch(() => {});
    load();
  };

  const priorityBadge = (p: string) => {
    const cls: Record<string, string> = { High: "badge badge-high", Medium: "badge badge-medium", Low: "badge badge-low" };
    return cls[p] || "badge badge-low";
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "2rem", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "2rem", fontWeight: 800 }}>
            <span className="gradient-text">Wishlist</span> 📋
          </h1>
          <p style={{ margin: "0.4rem 0 0", color: "#8f98a0" }}>{items.length} games on your wishlist</p>
        </div>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>
          <Plus size={16} style={{ display: "inline", marginRight: "0.4rem", verticalAlign: "middle" }} />
          Add to Wishlist
        </button>
      </div>

      <div className="glass" style={{ overflow: "auto" }}>
        {loading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "#8f98a0" }}>Loading…</div>
        ) : items.length === 0 ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "#8f98a0" }}>
            Your wishlist is empty. Start adding games!
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Game</th>
                <th>Platform</th>
                <th>Priority</th>
                <th>Notes</th>
                <th>Remove</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td style={{ fontWeight: 600 }}>{item.title}</td>
                  <td style={{ color: "#8f98a0" }}>{item.platform || "—"}</td>
                  <td><span className={priorityBadge(item.priority)}>{item.priority}</span></td>
                  <td style={{ color: "#8f98a0", maxWidth: "200px" }}>{item.notes || "—"}</td>
                  <td>
                    <button className="btn-danger" style={{ padding: "0.3rem 0.65rem", fontSize: "0.78rem" }} onClick={() => handleRemove(item.id)}>
                      <Trash2 size={13} style={{ display: "inline", marginRight: "0.3rem", verticalAlign: "middle" }} />
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showAdd && <AddWishlistModal onClose={() => { setShowAdd(false); load(); }} />}
    </div>
  );
}

function AddWishlistModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ title: "", platform: "", priority: "Medium", notes: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async () => {
    if (!form.title.trim()) { setError("Title is required"); return; }
    setLoading(true);
    try {
      await addWishlistItem({ title: form.title, platform: form.platform, priority: form.priority as WishlistItem["priority"], notes: form.notes });
      onClose();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="glass" style={{ width: "100%", maxWidth: "420px", padding: "2rem" }} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: "0 0 1.5rem", fontWeight: 700 }}>📋 Add to Wishlist</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
          <input className="form-input" placeholder="Game title *" value={form.title} onChange={(e) => set("title", e.target.value)} />
          <input className="form-input" placeholder="Platform" value={form.platform} onChange={(e) => set("platform", e.target.value)} />
          <select className="form-select" value={form.priority} onChange={(e) => set("priority", e.target.value)}>
            {PRIORITIES.map((p) => <option key={p}>{p}</option>)}
          </select>
          <textarea className="form-input" placeholder="Notes (optional)" value={form.notes} onChange={(e) => set("notes", e.target.value)} style={{ resize: "vertical", minHeight: "70px" }} />
          {error && <p style={{ color: "#f87171", margin: 0, fontSize: "0.85rem" }}>{error}</p>}
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn-primary" onClick={handleSubmit} disabled={loading}>{loading ? "Saving…" : "Add"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
