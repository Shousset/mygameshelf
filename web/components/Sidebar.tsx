"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Gamepad2,
  BookHeart,
  Timer,
  Trophy,
  Download,
  Settings,
  User,
  LogOut,
} from "lucide-react";
import { getSteamProfile, getStats, type SteamProfile, type Stats } from "@/lib/api";
import { supabase } from "@/lib/supabase/client";

const HIDDEN_ON = ["/login", "/signup"];

const navItems = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/games", icon: Gamepad2, label: "Collection" },
  { href: "/sessions", icon: Timer, label: "Sessions" },
  { href: "/achievements", icon: Trophy, label: "Achievements" },
  { href: "/wishlist", icon: BookHeart, label: "Wishlist" },
  { href: "/import", icon: Download, label: "Import" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [profile, setProfile] = useState<SteamProfile | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);

  const hidden = HIDDEN_ON.some((p) => pathname === p || pathname.startsWith(p + "/"));

  useEffect(() => {
    if (hidden) return;
    getSteamProfile().then(setProfile).catch(() => setProfile(null));
    getStats().then(setStats).catch(() => setStats(null));
  }, [hidden]);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    window.location.href = "/login";
  };

  if (hidden) return null;

  return (
    <aside
      style={{
        width: "220px",
        minHeight: "100vh",
        background: "linear-gradient(180deg, #171a21 0%, #1b2838 100%)",
        backdropFilter: "blur(16px)",
        borderRight: "1px solid rgba(102, 192, 244, 0.18)",
        display: "flex",
        flexDirection: "column",
        padding: "1.5rem 0",
        position: "sticky",
        top: 0,
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div style={{ padding: "0 1.25rem 1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ fontSize: "1.3rem" }}>🎮</span>
          <span
            style={{
              fontWeight: 800,
              fontSize: "1.05rem",
              background: "linear-gradient(135deg, #66c0f4, #aedffd)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            MyGameShelf
          </span>
        </div>
      </div>

      {/* Identity panel */}
      <div style={{ padding: "0 0.85rem 1rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.6rem",
            padding: "0.55rem 0.6rem",
            background: "rgba(0, 0, 0, 0.25)",
            border: "1px solid rgba(102, 192, 244, 0.18)",
            borderRadius: "4px",
          }}
        >
          {profile?.avatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={profile.avatar}
              alt={profile.name || "Avatar"}
              width={36}
              height={36}
              style={{ borderRadius: "3px", display: "block", border: "1px solid rgba(102, 192, 244, 0.35)" }}
            />
          ) : (
            <div style={{ width: 36, height: 36, borderRadius: "3px", background: "#2a475e", display: "flex", alignItems: "center", justifyContent: "center", color: "#8f98a0" }}>
              <User size={18} />
            </div>
          )}
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: "0.82rem", color: "#f5f9fc", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {profile?.name || "Steam user"}
            </div>
            <div style={{ fontSize: "0.68rem", color: "#8f98a0" }}>
              {stats ? `${stats.total_games} games · ${Math.round(stats.total_hours)}h` : "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div
        style={{
          height: "1px",
          background: "rgba(102, 192, 244, 0.18)",
          marginBottom: "1rem",
        }}
      />

      {/* Nav */}
      <nav style={{ flex: 1, padding: "0 0.75rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
        {navItems.map(({ href, icon: Icon, label }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.65rem 0.85rem",
                borderRadius: "10px",
                textDecoration: "none",
                color: active ? "#f5f9fc" : "#8f98a0",
                background: active
                  ? "rgba(102, 192, 244, 0.18)"
                  : "transparent",
                border: active
                  ? "1px solid rgba(102, 192, 244, 0.4)"
                  : "1px solid transparent",
                fontWeight: active ? 600 : 400,
                fontSize: "0.875rem",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  (e.currentTarget as HTMLAnchorElement).style.background =
                    "rgba(102, 192, 244, 0.10)";
                  (e.currentTarget as HTMLAnchorElement).style.color = "#f5f9fc";
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  (e.currentTarget as HTMLAnchorElement).style.background =
                    "transparent";
                  (e.currentTarget as HTMLAnchorElement).style.color = "#8f98a0";
                }
              }}
            >
              <Icon size={17} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div
        style={{
          padding: "1rem 0.75rem 0",
          borderTop: "1px solid rgba(102, 192, 244, 0.15)",
          marginTop: "auto",
        }}
      >
        <button
          onClick={handleSignOut}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.6rem",
            width: "100%",
            padding: "0.55rem 0.85rem",
            borderRadius: "10px",
            border: "1px solid transparent",
            background: "transparent",
            color: "#8f98a0",
            fontSize: "0.85rem",
            cursor: "pointer",
            transition: "all 0.2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(239, 68, 68, 0.12)";
            e.currentTarget.style.color = "#fca5a5";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "#8f98a0";
          }}
        >
          <LogOut size={16} />
          Sign out
        </button>
        <div style={{ padding: "0.75rem 0.5rem 0", fontSize: "0.7rem", color: "#56707f" }}>
          v2.0 · Next.js + FastAPI
        </div>
      </div>
    </aside>
  );
}
