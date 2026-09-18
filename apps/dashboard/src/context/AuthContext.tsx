"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import type { UserProfile, UserPreferences } from "@nexus/types";

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  updatePreferences: (updates: {
    timezone?: string;
    model_preferences?: Record<string, unknown>;
    permission_preferences?: Record<string, unknown>;
    privacy_settings?: Record<string, unknown>;
  }) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "nexus_auth_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Restore existing session on mount
  useEffect(() => {
    const restoreSession = async () => {
      try {
        const storedToken = localStorage.getItem(TOKEN_KEY);
        if (!storedToken) {
          setIsLoading(false);
          return;
        }

        setToken(storedToken);
        const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
          headers: {
            Authorization: `Bearer ${storedToken}`,
          },
        });

        if (res.ok) {
          const profile: UserProfile = await res.json();
          setUser(profile);
        } else {
          // Token expired or invalid
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
          setUser(null);
        }
      } catch (err) {
        console.error("Failed to restore NEXUS auth session:", err);
      } finally {
        setIsLoading(false);
      }
    };

    restoreSession();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      let res: Response;
      try {
        res = await fetch(`${API_BASE}/api/v1/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
      } catch {
        throw new Error(
          `Unable to reach NEXUS Core API at ${API_BASE}. Please verify the API service is online.`
        );
      }

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "Login failed" }));
        throw new Error(errorData.detail || "Invalid email or password");
      }

      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      setUser(data.user);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, password: string, fullName?: string) => {
    setIsLoading(true);
    try {
      let res: Response;
      try {
        res = await fetch(`${API_BASE}/api/v1/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email,
            password,
            full_name: fullName || null,
          }),
        });
      } catch {
        throw new Error(
          `Unable to reach NEXUS Core API at ${API_BASE}. Please verify the API service is online.`
        );
      }

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "Registration failed" }));
        throw new Error(errorData.detail || "Registration failed");
      }

      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      setUser(data.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    if (token) {
      try {
        await fetch(`${API_BASE}/api/v1/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
      } catch (err) {
        console.warn("Logout audit notification failed:", err);
      }
    }

    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  const updatePreferences = async (updates: {
    timezone?: string;
    model_preferences?: Record<string, unknown>;
    permission_preferences?: Record<string, unknown>;
    privacy_settings?: Record<string, unknown>;
  }) => {
    if (!token) throw new Error("Authentication required");

    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/v1/auth/preferences`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(updates),
      });
    } catch {
      throw new Error(
        `Unable to reach NEXUS Core API at ${API_BASE}. Preferences could not be updated.`
      );
    }

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: "Preferences update failed" }));
      throw new Error(errorData.detail || "Preferences update failed");
    }

    const updatedPrefs: UserPreferences = await res.json();
    setUser((prev) => (prev ? { ...prev, preferences: updatedPrefs } : null));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user && !!token,
        login,
        register,
        logout,
        updatePreferences,
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
