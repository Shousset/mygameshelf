"use client";

import { useState } from "react";
import { steamImport, epicImport, psnImport } from "@/lib/api";
import { Download, AlertCircle, CheckCircle2 } from "lucide-react";

export default function ImportPage() {
  const [activeTab, setActiveTab] = useState<"steam" | "epic" | "psn">("steam");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>("");

  // Steam State
  const [steamId, setSteamId] = useState("");

  // Bulk Import State (Epic / PSN)
  const [bulkText, setBulkText] = useState("");

  const handleSteamSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!steamId) {
      setError("Please enter your Steam ID");
      return;
    }
    setError("");
    setResult(null);
    setLoading(true);

    try {
      const data = await steamImport(steamId, false);
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Failed to fetch from Steam");
    } finally {
      setLoading(false);
    }
  };

  const handleBulkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const titles = bulkText
      .split("\n")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    if (titles.length === 0) {
      setError("Please enter at least one game title.");
      return;
    }
    setError("");
    setResult(null);
    setLoading(true);

    try {
      const data = activeTab === "epic" ? await epicImport(titles) : await psnImport(titles);
      setResult({
        message: `Processed ${titles.length} titles.`,
        imported: data.imported,
        skipped: data.skipped?.length || 0,
      });
      if (data.imported > 0) setBulkText("");
    } catch (err: any) {
      setError(err.message || "Bulk import failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto" }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ margin: 0, fontSize: "2rem", fontWeight: 800 }}>
          <span className="gradient-text">Sync Platforms</span> 🔄
        </h1>
        <p style={{ margin: "0.4rem 0 0", color: "#8f98a0" }}>
          Import your game libraries into your offline database.
        </p>
      </div>

      <div style={{ display: "flex", gap: "1rem", marginBottom: "1.5rem" }}>
        <button
          className={activeTab === "steam" ? "btn-primary" : "btn-ghost"}
          onClick={() => { setActiveTab("steam"); setResult(null); setError(""); }}
        >
          Steam
        </button>
        <button
          className={activeTab === "epic" ? "btn-primary" : "btn-ghost"}
          onClick={() => { setActiveTab("epic"); setResult(null); setError(""); }}
        >
          Epic Games
        </button>
        <button
          className={activeTab === "psn" ? "btn-primary" : "btn-ghost"}
          onClick={() => { setActiveTab("psn"); setResult(null); setError(""); }}
        >
          PlayStation (PSN)
        </button>
      </div>

      <div className="glass" style={{ padding: "2rem" }}>
        {activeTab === "steam" && (
          <form onSubmit={handleSteamSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            <p style={{ margin: 0, color: "#8f98a0", fontSize: "0.9rem", lineHeight: 1.5 }}>
              Enter your SteamID64. Your Steam profile must be set to <b>Public</b>.
              We use the app&apos;s own Steam key on the server — you don&apos;t need your own API key.
              Your SteamID is saved to your account so future syncs are automatic.
            </p>
            <input
              className="form-input"
              type="text"
              placeholder="SteamID64 (e.g., 7656119...)"
              value={steamId}
              onChange={(e) => setSteamId(e.target.value)}
            />
            <button type="submit" className="btn-primary" disabled={loading} style={{ alignSelf: "flex-start" }}>
              {loading ? "Syncing..." : "Start Steam Sync"}
              <Download size={16} style={{ marginLeft: "0.5rem", display: "inline" }} />
            </button>
          </form>
        )}

        {(activeTab === "epic" || activeTab === "psn") && (
          <form onSubmit={handleBulkSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            <p style={{ margin: 0, color: "#8f98a0", fontSize: "0.9rem", lineHeight: 1.5 }}>
              Since {activeTab === "epic" ? "Epic Games" : "PlayStation Network"} doesn't provide a public API, you can bulk import games 
              by pasting your library list here. Put one game title per line.
            </p>
            <textarea
              className="form-input"
              placeholder="Game Title 1&#10;Game Title 2&#10;..."
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              rows={8}
            />
            <button type="submit" className="btn-primary" disabled={loading} style={{ alignSelf: "flex-start" }}>
              {loading ? "Importing..." : `Import ${activeTab === "epic" ? "Epic" : "PSN"} Games`}
              <Download size={16} style={{ marginLeft: "0.5rem", display: "inline" }} />
            </button>
          </form>
        )}
      </div>

      {error && (
        <div style={{ marginTop: "1.5rem", padding: "1rem", background: "rgba(102, 192, 244, 0.12)", border: "1px solid rgba(102, 192, 244, 0.35)", borderRadius: "10px", display: "flex", alignItems: "center", gap: "0.75rem", color: "#fca5a5" }}>
          <AlertCircle size={20} />
          <p style={{ margin: 0 }}>{error}</p>
        </div>
      )}

      {result && (
        <div style={{ marginTop: "1.5rem", padding: "1.5rem", background: "rgba(74, 222, 128, 0.05)", border: "1px solid rgba(74, 222, 128, 0.2)", borderRadius: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#4ade80", marginBottom: "0.75rem" }}>
            <CheckCircle2 size={24} />
            <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Import Complete</h3>
          </div>
          <p style={{ margin: "0 0 0.5rem", color: "#c7d5e0" }}>{result.message}</p>
          <ul style={{ margin: 0, paddingLeft: "1.25rem", color: "#8f98a0", fontSize: "0.9rem" }}>
            <li><b>{result.imported}</b> new games added to backlog.</li>
            {result.skipped !== undefined && <li><b>{result.skipped}</b> games skipped (already exist).</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
