"use client";

import { useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase/client";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);
    const { data, error } = await supabase.auth.signUp({ email, password });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    // If email confirmation is on, there is no session yet — tell the user to check their inbox.
    if (data.session) {
      window.location.href = "/";
    } else {
      setInfo("Account created. Check your email to confirm, then sign in.");
    }
  };

  return (
    <div style={{ maxWidth: 380, margin: "4rem auto" }}>
      <h1 style={{ fontSize: "1.8rem", fontWeight: 800, marginBottom: "0.25rem" }}>
        <span className="gradient-text">Create account</span> 🎮
      </h1>
      <p style={{ color: "#8f98a0", marginBottom: "1.5rem" }}>Start tracking your library.</p>

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
          placeholder="Password (min. 6 characters)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          minLength={6}
          required
        />
        {error && <p style={{ color: "#fca5a5", margin: 0, fontSize: "0.9rem" }}>{error}</p>}
        {info && <p style={{ color: "#4ade80", margin: 0, fontSize: "0.9rem" }}>{info}</p>}
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Creating…" : "Create account"}
        </button>
      </form>

      <p style={{ color: "#8f98a0", marginTop: "1.25rem", fontSize: "0.9rem" }}>
        Already have an account?{" "}
        <Link href="/login" style={{ color: "#66c0f4" }}>
          Sign in
        </Link>
      </p>
    </div>
  );
}
