"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getStats, getDashboardFeed, type Stats, type DashboardFeed } from "@/lib/api";
import { Trophy, Clock, Gamepad2, BookHeart, TrendingUp, Star, Play, ChevronRight } from "lucide-react";
import GameCover from "@/components/GameCover";
import { StatCardSkeleton } from "@/components/Skeleton";

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

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [feed, setFeed] = useState<DashboardFeed | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getStats().then(setStats).catch(() => setError("Could not load stats — is the API running?"));
    getDashboardFeed().then(setFeed).catch(() => {});
  }, []);

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ margin: 0, fontSize: "2rem", fontWeight: 800 }}>
          <span className="gradient-text">Dashboard</span> 🎮
        </h1>
        <p style={{ margin: "0.4rem 0 0", color: "#8f98a0" }}>
          Your gaming activity at a glance
        </p>
      </div>

      {error && (
        <div
          className="glass"
          style={{
            padding: "1rem 1.5rem",
            borderColor: "rgba(196,58,58,0.5)",
            color: "#e88a8a",
            marginBottom: "1.5rem",
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {feed?.currently_playing && <CurrentlyPlayingHero cp={feed.currently_playing} />}

      {/* Stat tiles */}
      {stats && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
            gap: "0.75rem",
            marginBottom: "1.5rem",
          }}
        >
          <StatCard icon={<Gamepad2 size={20} color="#66c0f4" />} label="Total Games" value={stats.total_games} />
          <StatCard icon={<Trophy size={20} color="#fcd34d" />} label="Achievements" value={`${stats.unlocked_achievements} / ${stats.total_achievements}`} />
          <StatCard icon={<Clock size={20} color="#aedffd" />} label="Hours Played" value={`${Math.round(stats.total_hours)}h`} />
          <StatCard icon={<BookHeart size={20} color="#e88a8a" />} label="Wishlist" value={stats.wishlist_count} />
          <StatCard icon={<Star size={20} color="#aedffd" />} label="Top Genre" value={stats.top_genre} />
        </div>
      )}

      {/* Progress bar */}
      {stats && stats.total_achievements > 0 && (
        <div className="glass" style={{ padding: "1.1rem 1.25rem", marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.6rem", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <TrendingUp size={15} color="#66c0f4" />
              <span style={{ fontWeight: 600, fontSize: "0.92rem" }}>Achievement Progress</span>
            </div>
            <span style={{ color: "#66c0f4", fontWeight: 700 }}>
              {Math.round((stats.unlocked_achievements / stats.total_achievements) * 100)}%
            </span>
          </div>
          <div style={{ height: "8px", borderRadius: "99px", background: "rgba(0,0,0,0.3)", overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                background: "linear-gradient(90deg, #66c0f4, #1a9fff)",
                width: `${Math.round((stats.unlocked_achievements / stats.total_achievements) * 100)}%`,
                transition: "width 1s ease",
              }}
            />
          </div>
          <p style={{ margin: "0.6rem 0 0", color: "#8f98a0", fontSize: "0.82rem" }}>
            {stats.unlocked_achievements} of {stats.total_achievements} achievements unlocked
          </p>
        </div>
      )}

      {feed && feed.recent_unlocks.length > 0 && <RecentUnlocks unlocks={feed.recent_unlocks} />}

      {!stats && !error && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "0.75rem" }}>
          {Array.from({ length: 5 }).map((_, i) => <StatCardSkeleton key={i} />)}
        </div>
      )}
    </div>
  );
}

function CurrentlyPlayingHero({ cp }: { cp: NonNullable<DashboardFeed["currently_playing"]> }) {
  return (
    <Link
      href="/sessions"
      className="glass fade-in lift-on-hover"
      style={{
        display: "flex",
        gap: "1.25rem",
        padding: "0",
        marginBottom: "1.5rem",
        textDecoration: "none",
        color: "inherit",
        overflow: "hidden",
        cursor: "pointer",
      }}
    >
      <GameCover appid={cp.external_id} title={cp.title} variant="header" width={368} height={172} rounded={0} />
      <div style={{ flex: 1, padding: "1rem 1.25rem", display: "flex", flexDirection: "column", justifyContent: "space-between", minWidth: 0 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "#66c0f4", fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase" }}>
            <Play size={11} /> Most recently played
          </div>
          <div style={{ margin: "0.35rem 0 0.2rem", fontSize: "1.5rem", fontWeight: 700, color: "#f5f9fc", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {cp.title}
          </div>
          <div style={{ fontSize: "0.82rem", color: "#8f98a0" }}>
            {cp.hours_played.toFixed(1)}h played · last played {formatRelative(cp.last_played_at)}
          </div>
        </div>
        {cp.recent_unlocks_for_this_game.length > 0 ? (
          <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginTop: "0.6rem" }}>
            {cp.recent_unlocks_for_this_game.slice(0, 5).map((a, i) =>
              a.icon_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={i}
                  src={a.icon_url}
                  alt={a.title}
                  title={a.title}
                  width={32}
                  height={32}
                  style={{ borderRadius: 3, border: "1px solid rgba(102, 192, 244, 0.35)" }}
                />
              ) : null
            )}
            <span style={{ color: "#8f98a0", fontSize: "0.78rem", marginLeft: "0.25rem" }}>recent unlocks</span>
            <ChevronRight size={14} color="#66c0f4" style={{ marginLeft: "auto" }} />
          </div>
        ) : (
          <div style={{ color: "#56707f", fontSize: "0.78rem", marginTop: "0.6rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
            Open session log <ChevronRight size={14} color="#66c0f4" style={{ marginLeft: "auto" }} />
          </div>
        )}
      </div>
    </Link>
  );
}

function RecentUnlocks({ unlocks }: { unlocks: DashboardFeed["recent_unlocks"] }) {
  return (
    <div className="glass" style={{ padding: "1rem 1.25rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.85rem" }}>
        <Trophy size={15} color="#fcd34d" />
        <span style={{ fontSize: "0.78rem", color: "#8f98a0", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 700 }}>
          Recent Unlocks
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {unlocks.map((u, i) => {
          let rarityColor = "#8f98a0";
          if (u.global_pct !== null && u.global_pct !== undefined) {
            if (u.global_pct < 5) rarityColor = "#fcd34d";
            else if (u.global_pct < 15) rarityColor = "#c084fc";
            else if (u.global_pct < 50) rarityColor = "#66c0f4";
          }
          return (
            <Link
              key={i}
              href="/achievements"
              className="row-hover"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.7rem",
                padding: "0.55rem 0.65rem",
                background: "rgba(0,0,0,0.18)",
                border: "1px solid rgba(143, 152, 160, 0.15)",
                borderRadius: 3,
                textDecoration: "none",
                color: "inherit",
              }}
            >
              {u.icon_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={u.icon_url} alt="" width={36} height={36} style={{ borderRadius: 3, flexShrink: 0 }} />
              ) : (
                <div style={{ width: 36, height: 36, borderRadius: 3, background: "#2a475e", flexShrink: 0 }} />
              )}
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: "0.88rem", fontWeight: 600, color: "#f5f9fc", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {u.title}
                </div>
                <div style={{ fontSize: "0.7rem", color: "#8f98a0", display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.game_title}</span>
                  <span style={{ color: "#56707f" }}>·</span>
                  <span>{formatRelative(u.unlocked_at)}</span>
                </div>
              </div>
              {u.global_pct !== null && u.global_pct !== undefined && (
                <div style={{ flexShrink: 0, fontSize: "0.78rem", fontWeight: 700, color: rarityColor }}>
                  {u.global_pct.toFixed(1)}%
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <div className="glass" style={{ padding: "0.95rem 1.1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
        {icon}
        <span style={{ color: "#8f98a0", fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>
          {label}
        </span>
      </div>
      <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "#f5f9fc" }}>{value}</div>
    </div>
  );
}
