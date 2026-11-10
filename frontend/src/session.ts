import type { AuthSession } from "./types";

const SESSION_KEY = "apno-ki-awaaz.session";

export function tokenIsExpired(token: string, nowSeconds = Date.now() / 1000): boolean {
  try {
    const payloadPart = token.split(".")[1];
    if (!payloadPart) return true;
    const normalized = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(normalized)) as { exp?: unknown };
    return typeof payload.exp !== "number" || payload.exp <= nowSeconds;
  } catch {
    return true;
  }
}

export function readSession(): AuthSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as AuthSession;
    if (!session.accessToken || tokenIsExpired(session.accessToken)) {
      clearSession();
      return null;
    }
    return session;
  } catch {
    clearSession();
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}