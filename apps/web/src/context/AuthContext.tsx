"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { api, User, Workspace } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  workspaces: Workspace[];
  currentWorkspace: Workspace | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, workspaceName?: string) => Promise<void>;
  logout: () => void;
  setCurrentWorkspace: (ws: Workspace) => void;
  refreshWorkspaces: () => Promise<void>;
  createWorkspace: (name: string) => Promise<Workspace>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function initialize() {
      const token = typeof window !== "undefined" ? localStorage.getItem("cleardata_token") : null;
      if (!token) {
        if (isMounted) setLoading(false);
        return;
      }

      try {
        const me = await api.getMe();
        if (!isMounted) return;
        setUser(me);

        const wsList = await api.getWorkspaces();
        if (!isMounted) return;
        setWorkspaces(wsList);

        if (wsList.length > 0) {
          const savedWsId = typeof window !== "undefined" ? localStorage.getItem("cleardata_active_ws") : null;
          const found = wsList.find((w) => w.id === savedWsId) || wsList[0];
          setCurrentWorkspace(found);
        }
      } catch {
        if (isMounted) {
          api.logout();
          setUser(null);
          setWorkspaces([]);
          setCurrentWorkspace(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    initialize();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSelectWorkspace = (ws: Workspace) => {
    setCurrentWorkspace(ws);
    if (typeof window !== "undefined") {
      localStorage.setItem("cleardata_active_ws", ws.id);
    }
  };

  const login = async (email: string, password: string) => {
    setLoading(true);
    try {
      const res = await api.login({ email, password });
      setUser(res.user);
      const wsList = await api.getWorkspaces();
      setWorkspaces(wsList);
      if (wsList.length > 0) {
        handleSelectWorkspace(wsList[0]);
      }
    } finally {
      setLoading(false);
    }
  };

  const register = async (email: string, password: string, name: string, workspaceName?: string) => {
    setLoading(true);
    try {
      const res = await api.register({ email, password, name, workspace_name: workspaceName });
      setUser(res.user);
      const wsList = await api.getWorkspaces();
      setWorkspaces(wsList);
      if (wsList.length > 0) {
        handleSelectWorkspace(wsList[0]);
      }
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    api.logout();
    setUser(null);
    setWorkspaces([]);
    setCurrentWorkspace(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("cleardata_active_ws");
    }
  };

  const refreshWorkspaces = async () => {
    const wsList = await api.getWorkspaces();
    setWorkspaces(wsList);
    if (currentWorkspace) {
      const updated = wsList.find((w) => w.id === currentWorkspace.id);
      if (updated) setCurrentWorkspace(updated);
    } else if (wsList.length > 0) {
      handleSelectWorkspace(wsList[0]);
    }
  };

  const createWorkspace = async (name: string): Promise<Workspace> => {
    const newWs = await api.createWorkspace(name);
    await refreshWorkspaces();
    handleSelectWorkspace(newWs);
    return newWs;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        workspaces,
        currentWorkspace,
        loading,
        login,
        register,
        logout,
        setCurrentWorkspace: handleSelectWorkspace,
        refreshWorkspaces,
        createWorkspace,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
