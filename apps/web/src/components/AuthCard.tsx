"use client";

import React, { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Sparkles, ArrowRight, Loader2, Lock, Mail, User, Building } from "lucide-react";

export function AuthCard() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password, name, workspaceName || undefined);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An authentication error occurred. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (role: "admin" | "steward") => {
    if (role === "admin") {
      setEmail("admin@cleardata.io");
      setPassword("Password123!");
      setName("Alice Admin");
      setWorkspaceName("Acme Operations");
    } else {
      setEmail("steward@cleardata.io");
      setPassword("Password123!");
      setName("Sam Steward");
      setWorkspaceName("Global Data Office");
    }
  };

  return (
    <div className="w-full max-w-md overflow-hidden rounded-3xl border border-zinc-800 bg-zinc-900/90 p-8 shadow-2xl backdrop-blur-xl ring-1 ring-white/10">
      {/* Brand header */}
      <div className="flex flex-col items-center text-center mb-8">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-500 via-indigo-600 to-violet-500 shadow-xl shadow-indigo-500/20 ring-1 ring-white/20 mb-4">
          <Sparkles className="h-6 w-6 text-white" />
        </div>
        <h2 className="text-2xl font-black tracking-tight text-white">
          {mode === "login" ? "Welcome Back to ClearData" : "Get Started with ClearData"}
        </h2>
        <p className="mt-1.5 text-xs text-zinc-400 max-w-xs">
          {mode === "login"
            ? "Sign in to inspect datasets, apply cleaning rules, and publish reports."
            : "Create your workspace to transform ambiguous company data into clean, trusted reports."}
        </p>
      </div>

      {/* Tabs */}
      <div className="grid grid-cols-2 gap-1 rounded-xl bg-zinc-950 p-1 mb-6 border border-zinc-800">
        <button
          type="button"
          onClick={() => {
            setMode("login");
            setError(null);
          }}
          className={`rounded-lg py-2 text-xs font-semibold transition-all ${
            mode === "login"
              ? "bg-zinc-800 text-white shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Sign In
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("register");
            setError(null);
          }}
          className={`rounded-lg py-2 text-xs font-semibold transition-all ${
            mode === "register"
              ? "bg-zinc-800 text-white shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Create Account
        </button>
      </div>

      {error && (
        <div className="mb-5 rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-400">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "register" && (
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">Full Name</label>
            <div className="relative">
              <User className="absolute left-3.5 top-3 h-4 w-4 text-zinc-500" />
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-zinc-300 mb-1.5">Work Email</label>
          <div className="relative">
            <Mail className="absolute left-3.5 top-3 h-4 w-4 text-zinc-500" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-300 mb-1.5">Password</label>
          <div className="relative">
            <Lock className="absolute left-3.5 top-3 h-4 w-4 text-zinc-500" />
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        {mode === "register" && (
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">
              Workspace Name <span className="text-zinc-500">(Optional)</span>
            </label>
            <div className="relative">
              <Building className="absolute left-3.5 top-3 h-4 w-4 text-zinc-500" />
              <input
                type="text"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="e.g. Acme Analytics"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center space-x-2 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-violet-600 py-3 text-sm font-semibold text-white shadow-xl shadow-indigo-600/25 transition-all hover:opacity-95 hover:shadow-indigo-600/35 disabled:opacity-50 mt-2"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <span>{mode === "login" ? "Sign In" : "Create Account & Workspace"}</span>
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </form>

      {/* Quick Demo Pre-fill helper */}
      <div className="mt-6 border-t border-zinc-800/80 pt-5">
        <p className="text-center text-[11px] font-medium text-zinc-500 mb-2.5">
          Need quick test credentials?
        </p>
        <div className="flex justify-center space-x-2">
          <button
            type="button"
            onClick={() => fillDemo("admin")}
            className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-1 text-[11px] font-medium text-zinc-400 hover:border-zinc-700 hover:text-white transition-colors"
          >
            Quickfill Admin
          </button>
          <button
            type="button"
            onClick={() => fillDemo("steward")}
            className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-1 text-[11px] font-medium text-zinc-400 hover:border-zinc-700 hover:text-white transition-colors"
          >
            Quickfill Steward
          </button>
        </div>
      </div>
    </div>
  );
}
