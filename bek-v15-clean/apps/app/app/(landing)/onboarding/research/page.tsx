"use client";

import { useEffect, useState } from "react";

export default function SignInPage() {
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function checkSession() {
      try {
        const res = await fetch("/api/auth/session");
        if (!res.ok) throw new Error("Session unreachable");
        const data = await res.json();
        setSession(data);
      } catch (err) {
        console.error("[SignIn] Session check failed:", err);
        setError("Service d'authentification temporairement indisponible.");
      } finally {
        setLoading(false);
      }
    }
    checkSession();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p>Chargement...</p>
      </div>
    );
  }

  if (session?.user) {
    if (typeof window !== "undefined") {
      window.location.href = "/dashboard";
    }
    return null;
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-6">
      <h1 className="text-3xl font-bold mb-2">Welcome back</h1>
      <p className="text-gray-500 mb-8">Connectez-vous à votre compte</p>

      {error && (
        <div className="bg-red-100 border border-red-300 text-red-800 px-4 py-3 rounded mb-4 max-w-sm w-full">
          <p className="font-semibold">Erreur</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      <button
        onClick={() => {
          window.location.href = "/api/auth/signin/google?callbackUrl=/dashboard";
        }}
        className="flex items-center gap-2 px-6 py-3 bg-white border rounded shadow hover:bg-gray-50 transition"
      >
        <span>Se connecter avec Google</span>
      </button>
    </main>
  );
}
