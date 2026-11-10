import type {
  AuthResponse,
  FamilyLink,
  Reminder,
  ReminderAudioMetadata,
  Recurrence,
  User,
  UserRole,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class ApiClient {
  constructor(private readonly accessToken?: string) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body && !(init.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (this.accessToken) headers.set("Authorization", `Bearer ${this.accessToken}`);

    const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
    if (response.status === 204) return undefined as T;

    const contentType = response.headers.get("content-type") || "";
    const payload: unknown = contentType.includes("application/json")
      ? await response.json()
      : await response.text();
    if (!response.ok) {
      const detail =
        typeof payload === "object" && payload !== null && "detail" in payload
          ? String((payload as { detail: unknown }).detail)
          : `Request failed (${response.status})`;
      throw new ApiError(response.status, detail);
    }
    return payload as T;
  }

  private json(method: string, body?: unknown): RequestInit {
    return { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) };
  }

  login(phone_number: string, password: string): Promise<AuthResponse> {
    return this.request("/api/auth/login", this.json("POST", { phone_number, password }));
  }

  register(data: {
    full_name: string;
    phone_number: string;
    password: string;
    role: UserRole;
  }): Promise<AuthResponse> {
    return this.request("/api/auth/register", this.json("POST", data));
  }

  me(): Promise<User> {
    return this.request("/api/auth/me");
  }

  users(): Promise<User[]> {
    return this.request("/api/users");
  }

  reminders(): Promise<Reminder[]> {
    return this.request("/api/reminders?limit=100");
  }

  sentLinks(): Promise<FamilyLink[]> {
    return this.request("/api/links/sent");
  }

  receivedLinks(): Promise<FamilyLink[]> {
    return this.request("/api/links/received");
  }

  requestLink(elderly_user_id: number): Promise<FamilyLink> {
    return this.request("/api/links/request", this.json("POST", { elderly_user_id }));
  }

  decideLink(linkId: number, action: "approve" | "reject" | "revoke"): Promise<FamilyLink> {
    return this.request(`/api/links/${linkId}/${action}`, this.json("PATCH"));
  }

  createReminder(input: {
    title: string;
    message: string;
    elderly_user_id: number;
    scheduled_at: string;
    recurrence: Recurrence;
  }): Promise<Reminder> {
    return this.request("/api/reminders", this.json("POST", input));
  }

  completeReminder(reminderId: number): Promise<Reminder> {
    return this.request(`/api/reminders/${reminderId}/complete`, this.json("PATCH"));
  }

  audioMetadata(reminderId: number): Promise<ReminderAudioMetadata> {
    return this.request(`/api/reminders/${reminderId}/audio`);
  }

  async audioBlob(reminderId: number): Promise<Blob> {
    const headers = new Headers({ Accept: "audio/wav" });
    if (this.accessToken) headers.set("Authorization", `Bearer ${this.accessToken}`);
    const response = await fetch(
      `${API_BASE_URL}/api/reminders/${reminderId}/audio/content`,
      { headers },
    );
    if (response.status === 401) throw new ApiError(401, "Your session has expired. Sign in again.");
    if (!response.ok) {
      let detail = `Audio unavailable (${response.status})`;
      if ((response.headers.get("content-type") || "").includes("application/json")) {
        const payload = (await response.json()) as { detail?: string };
        detail = payload.detail || detail;
      }
      throw new ApiError(response.status, detail);
    }
    return response.blob();
  }
}