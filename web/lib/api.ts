import { supabase } from "@/lib/supabase/client";

const isBrowser = typeof window !== "undefined";
const defaultApiUrl = isBrowser ? `http://${window.location.hostname}:8000` : "http://localhost:8000";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApiUrl;

export interface Game {
  id: number;
  title: string;
  platform: string;
  genre: string;
  year: number | null;
  status: "Backlog" | "Playing" | "Completed" | "Abandoned";
  rating: number | null;
  hours_played: number;
  notes?: string;
  external_id?: string | null;
}

export interface Session {
  date: string;
  hours: number;
  notes: string;
}

export interface WishlistItem {
  id: number;
  title: string;
  platform: string;
  priority: "High" | "Medium" | "Low";
  notes: string;
}

export interface Achievement {
  id: number;
  game_id: number;
  title: string;
  description: string;
  is_unlocked: boolean;
  unlocked_at: string | null;
  icon_url: string | null;
  icon_gray_url: string | null;
  is_hidden: boolean;
  global_pct: number | null;
}

export interface Stats {
  total_games: number;
  completed: number;
  completion_pct: number;
  total_hours: number;
  top_genre: string;
  wishlist_count: number;
  total_achievements: number;
  unlocked_achievements: number;
}

export class OfflineError extends Error {
  constructor(message = "Backend unreachable — you appear to be offline.") {
    super(message);
    this.name = "OfflineError";
  }
}

async function apiFetch(path: string, options?: RequestInit) {
  // Attach the Supabase access token so the backend can identify the user.
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options?.headers || {}),
      },
    });
  } catch (e) {
    // Network failure (DNS, refused, offline) — distinguishable from API errors below.
    throw new OfflineError();
  }
  if (res.status === 401 && isBrowser) {
    // Session expired or missing — bounce to login.
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API error");
  }
  return res.json();
}

// Games
export const getGames = (status?: string) =>
  apiFetch(`/api/games${status ? `?status=${status}` : ""}`);
export const addGame = (data: Omit<Game, "id" | "rating" | "hours_played">) =>
  apiFetch("/api/games", { method: "POST", body: JSON.stringify(data) });
export const updateStatus = (id: number, status: string) =>
  apiFetch(`/api/games/${id}/status`, { method: "PUT", body: JSON.stringify({ status }) });
export const rateGame = (id: number, rating: number, notes: string) =>
  apiFetch(`/api/games/${id}/rating`, { method: "PUT", body: JSON.stringify({ rating, notes }) });
export const deleteGame = (id: number) =>
  apiFetch(`/api/games/${id}`, { method: "DELETE" });

// Sessions
export const getSessions = (gameId: number) =>
  apiFetch(`/api/games/${gameId}/sessions`);
export const logSession = (gameId: number, hours: number, notes: string) =>
  apiFetch(`/api/games/${gameId}/sessions`, {
    method: "POST",
    body: JSON.stringify({ hours, notes }),
  });

// Wishlist
export const getWishlist = () => apiFetch("/api/wishlist");
export const addWishlistItem = (data: Omit<WishlistItem, "id">) =>
  apiFetch("/api/wishlist", { method: "POST", body: JSON.stringify(data) });
export const removeWishlistItem = (id: number) =>
  apiFetch(`/api/wishlist/${id}`, { method: "DELETE" });

// Stats
export const getStats = () => apiFetch("/api/stats");

// Achievements
export const getAchievements = (gameId: number) =>
  apiFetch(`/api/games/${gameId}/achievements`);

export const addAchievement = (gameId: number, title: string, description: string) =>
  apiFetch(`/api/games/${gameId}/achievements`, {
    method: "POST",
    body: JSON.stringify({ title, description }),
  });

export const toggleAchievement = (achId: number, isUnlocked: boolean) =>
  apiFetch(`/api/achievements/${achId}/toggle`, {
    method: "PUT",
    body: JSON.stringify({ is_unlocked: isUnlocked }),
  });

export const syncSteamAchievements = (gameId: number) =>
  apiFetch(`/api/games/${gameId}/sync_steam`, { method: "POST" });

// Imports
export const steamImport = (steamId: string, dryRun = false) =>
  apiFetch("/api/import/steam", {
    method: "POST",
    body: JSON.stringify({ steam_id: steamId, dry_run: dryRun }),
  });

export const epicImport = (titles: string[]) =>
  apiFetch("/api/import/epic", {
    method: "POST",
    body: JSON.stringify({ titles, platform: "Epic Games" }),
  });

export const psnImport = (titles: string[]) =>
  apiFetch("/api/import/psn", {
    method: "POST",
    body: JSON.stringify({ titles, platform: "PSN" }),
  });

// Health + Sync
export interface SyncStatus {
  in_progress: boolean;
  last_run: {
    started_at: string | null;
    finished_at: string | null;
    games_synced: number;
    errors: number;
    trigger: string | null;
  } | null;
  next_run_at: string | null;
  steam_configured: boolean;
}

export const getHealth = (): Promise<{ ok: boolean; db: boolean; steam_configured: boolean }> =>
  apiFetch("/api/health");

export const syncAll = () => apiFetch("/api/sync/all", { method: "POST" });

export const getSyncStatus = (): Promise<SyncStatus> => apiFetch("/api/sync/status");

// Steam recently played (last 2 weeks)
export interface RecentlyPlayedGame {
  appid: string;
  name: string;
  playtime_2weeks_hours: number;
  playtime_forever_hours: number;
  img_icon_url: string | null;
  local_game_id: number | null;
  local_title: string | null;
}

export const getRecentlyPlayed = (): Promise<{ games: RecentlyPlayedGame[]; count: number }> =>
  apiFetch("/api/steam/recently-played");

// Steam profile
export interface SteamProfile {
  steam_id: string;
  name: string | null;
  avatar: string | null;
  profile_url: string | null;
}
export const getSteamProfile = (): Promise<SteamProfile> => apiFetch("/api/steam/profile");

// Dashboard feed
export interface DashboardCurrentlyPlaying {
  id: number;
  title: string;
  platform: string;
  external_id: string | null;
  hours_played: number;
  last_played_at: string | null;
  recent_unlocks_for_this_game: Array<{ title: string; icon_url: string | null; global_pct: number | null; unlocked_at: string | null }>;
}
export interface DashboardUnlock {
  title: string;
  icon_url: string | null;
  global_pct: number | null;
  unlocked_at: string | null;
  game_id: number;
  game_title: string;
  game_external_id: string | null;
}
export interface DashboardFeed {
  currently_playing: DashboardCurrentlyPlaying | null;
  recent_unlocks: DashboardUnlock[];
}
export const getDashboardFeed = (): Promise<DashboardFeed> => apiFetch("/api/dashboard/feed");

// Per-game Steam stats
export interface SteamStats {
  game_id: number;
  title: string;
  platform: string;
  external_id: string | null;
  total_hours: number;
  hours_2weeks: number;
  last_played_at: string | null;
  last_session_date: string | null;
  is_steam_linked: boolean;
}

export const getSteamStats = (gameId: number): Promise<SteamStats> =>
  apiFetch(`/api/games/${gameId}/steam-stats`);

export const refreshGame = (gameId: number): Promise<SteamStats> =>
  apiFetch(`/api/games/${gameId}/refresh`, { method: "POST" });


