"use client";

/**
 * Login page.
 *
 * Converted to Client Component to support Demo Access Code interaction.
 *
 * The "Sign in with Google" button is an anchor tag pointing to the backend's
 * /auth/google endpoint. Clicking it redirects the browser to Google's consent
 * screen.
 *
 * The Demo Access Code input allows evaluators to bypass Google login by 
 * providing a pre-configured secret code.
 */

import { useState } from "react";
import { Ticket, KeyRound, Loader2 } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function LoginPage() {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDemoLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/auth/demo-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });

      const data = await res.json();

      if (res.ok && data.token) {
        // Use the existing callback route to set the cookie and redirect to /board
        window.location.href = `/api/auth/callback?token=${data.token}`;
      } else {
        setError(data.detail || "Código de acceso inválido.");
      }
    } catch {
      setError("Error al conectar con el servidor.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="bg-white rounded-2xl shadow-lg p-10 max-w-md w-full mx-4 text-center">
        {/* Logo / Brand */}
        <div className="flex items-center justify-center gap-2 mb-2">
          <Ticket className="h-8 w-8 text-slate-800" />
          <h1 className="text-2xl font-bold text-slate-800">D4-Ticket AI</h1>
        </div>
        <p className="text-slate-500 text-sm mb-8">
          Collaborative ticketing with AI-powered assistance
        </p>

        {/* Google OAuth button */}
        <a
          href={`${API_URL}/api/v1/auth/google`}
          aria-label="Iniciar sesión con Google"
          className="flex items-center justify-center gap-3 w-full py-3 px-6 border border-slate-200 rounded-lg text-slate-700 font-medium hover:bg-slate-50 transition-colors mb-6"
        >
          {/* Google SVG logo */}
          <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              fill="#EA4335"
            />
          </svg>
          Sign in with Google
        </a>

        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-slate-200"></span>
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-white px-2 text-slate-400">or use demo access</span>
          </div>
        </div>

        <form onSubmit={handleDemoLogin} className="space-y-4">
          <div className="relative">
            <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              id="demo-code"
              aria-label="Código de acceso demo"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Enter Access Code"
              className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-transparent transition-all"
            />
          </div>
          {error && <p className="text-xs text-rose-500 font-medium">{error}</p>}
          <button
            type="submit"
            disabled={loading || !code}
            className="w-full py-2 px-4 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-900 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Access System"}
          </button>
        </form>

        <p className="mt-8 text-xs text-slate-400">
          By signing in, you agree to our terms of service. <br />
          Your account is created automatically on first login.
        </p>
      </div>
    </main>
  );
}
