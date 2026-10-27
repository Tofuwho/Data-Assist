"use client";

import React, { useState, useRef, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import {
  Building2,
  ChevronDown,
  Plus,
  LogOut,
  Check,
  Shield,
  Sparkles,
} from "lucide-react";

interface HeaderProps {
  onOpenCreateWorkspace: () => void;
}

export function Header({ onOpenCreateWorkspace }: HeaderProps) {
  const { user, workspaces, currentWorkspace, setCurrentWorkspace, logout } = useAuth();
  const [wsMenuOpen, setWsMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const wsDropdownRef = useRef<HTMLDivElement>(null);
  const userDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wsDropdownRef.current && !wsDropdownRef.current.contains(event.target as Node)) {
        setWsMenuOpen(false);
      }
      if (userDropdownRef.current && !userDropdownRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const getRoleBadgeColor = (role?: string) => {
    switch (role) {
      case "admin":
        return "bg-purple-500/10 text-purple-400 border-purple-500/20";
      case "steward":
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
      case "stakeholder":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      default:
        return "bg-zinc-500/10 text-zinc-400 border-zinc-500/20";
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand & Workspace Switcher */}
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-violet-500 shadow-lg shadow-indigo-500/20 ring-1 ring-white/20">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="text-base font-bold tracking-tight text-white">ClearData</span>
              <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-400">Data Platform</span>
            </div>
          </div>

          <div className="h-5 w-[1px] bg-zinc-800" />

          {/* Workspace Switcher */}
          {currentWorkspace && (
            <div className="relative" ref={wsDropdownRef}>
              <button
                type="button"
                onClick={() => setWsMenuOpen(!wsMenuOpen)}
                className="flex items-center space-x-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-sm font-medium text-zinc-200 transition-all hover:border-zinc-700 hover:bg-zinc-800/80"
              >
                <Building2 className="h-4 w-4 text-indigo-400" />
                <span className="max-w-[160px] truncate">{currentWorkspace.name}</span>
                <span
                  className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${getRoleBadgeColor(
                    currentWorkspace.role
                  )}`}
                >
                  {currentWorkspace.role}
                </span>
                <ChevronDown className={`h-3.5 w-3.5 text-zinc-400 transition-transform ${wsMenuOpen ? "rotate-180" : ""}`} />
              </button>

              {wsMenuOpen && (
                <div className="absolute left-0 mt-2 w-72 origin-top-left rounded-xl border border-zinc-800 bg-zinc-900 p-1.5 shadow-2xl ring-1 ring-black/50 backdrop-blur-xl animate-in fade-in zoom-in-95 duration-100">
                  <div className="px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                    Switch Workspace
                  </div>
                  <div className="max-h-60 space-y-1 overflow-y-auto py-1">
                    {workspaces.map((ws) => {
                      const isSelected = ws.id === currentWorkspace.id;
                      return (
                        <button
                          key={ws.id}
                          onClick={() => {
                            setCurrentWorkspace(ws);
                            setWsMenuOpen(false);
                          }}
                          className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                            isSelected
                              ? "bg-indigo-600/10 text-indigo-300 font-medium border border-indigo-500/20"
                              : "text-zinc-300 hover:bg-zinc-800"
                          }`}
                        >
                          <div className="flex items-center space-x-2 truncate">
                            <Building2 className={`h-4 w-4 ${isSelected ? "text-indigo-400" : "text-zinc-500"}`} />
                            <span className="truncate">{ws.name}</span>
                          </div>
                          <div className="flex items-center space-x-2">
                            <span
                              className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${getRoleBadgeColor(
                                ws.role
                              )}`}
                            >
                              {ws.role}
                            </span>
                            {isSelected && <Check className="h-4 w-4 text-indigo-400" />}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-1 border-t border-zinc-800/80 pt-1">
                    <button
                      onClick={() => {
                        setWsMenuOpen(false);
                        onOpenCreateWorkspace();
                      }}
                      className="flex w-full items-center space-x-2 rounded-lg px-2.5 py-2 text-left text-sm font-medium text-indigo-400 transition-colors hover:bg-indigo-950/30"
                    >
                      <Plus className="h-4 w-4" />
                      <span>Create New Workspace</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* User Profile & Actions */}
        {user && (
          <div className="flex items-center space-x-4">
            <div className="relative" ref={userDropdownRef}>
              <button
                type="button"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center space-x-2.5 rounded-full border border-zinc-800 bg-zinc-900/60 py-1 pl-2 pr-3 text-sm font-medium text-zinc-200 transition-all hover:border-zinc-700 hover:bg-zinc-800"
              >
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 font-semibold text-white text-xs">
                  {user.name.charAt(0).toUpperCase()}
                </div>
                <span className="max-w-[120px] truncate">{user.name}</span>
                <ChevronDown className={`h-3.5 w-3.5 text-zinc-400 transition-transform ${userMenuOpen ? "rotate-180" : ""}`} />
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 mt-2 w-60 origin-top-right rounded-xl border border-zinc-800 bg-zinc-900 p-1.5 shadow-2xl ring-1 ring-black/50 backdrop-blur-xl animate-in fade-in zoom-in-95 duration-100">
                  <div className="border-b border-zinc-800 px-3 py-2.5">
                    <p className="text-sm font-semibold text-white truncate">{user.name}</p>
                    <p className="text-xs text-zinc-400 truncate">{user.email}</p>
                  </div>
                  <div className="py-1">
                    <div className="flex items-center space-x-2 px-3 py-2 text-xs text-zinc-400">
                      <Shield className="h-3.5 w-3.5 text-zinc-500" />
                      <span>Role in Workspace: <strong className="text-zinc-200 capitalize">{currentWorkspace?.role || "Member"}</strong></span>
                    </div>
                  </div>
                  <div className="border-t border-zinc-800 pt-1">
                    <button
                      onClick={logout}
                      className="flex w-full items-center space-x-2 rounded-lg px-3 py-2 text-left text-sm text-rose-400 transition-colors hover:bg-rose-950/20"
                    >
                      <LogOut className="h-4 w-4" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
