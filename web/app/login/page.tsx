"use client";

import { useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    // Full reload so the middleware sees the fresh session cookie.
    window.location.href = "/";
  };

  return (
    <div style={{ maxWidth: 380, margin: "4rem auto" }}>
      <h1 style={{ fontSize: "1.8rem", fontWeight: 800, marginBottom: "0.25rem" }}>
        <span className="gradient-text">MyGameShelf</span> 🎮
      </h1>
      <p style={{ color: "#8f98a0", marginBottom: "1.5rem" }}>Sign in to your shelf.</p>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <input
          className="form-input"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <input
          className="form-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        {error && <p style={{ color: "#fca5a5", margin: 0, fontSize: "0.9rem" }}>{error}</p>}
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p style={{ color: "#8f98a0", marginTop: "1.25rem", fontSize: "0.9rem" }}>
        No account?{" "}
        <Link href="/signup" style={{ color: "#66c0f4" }}>
          Create one
        </Link>
      </p>
    </div>
  );
}
