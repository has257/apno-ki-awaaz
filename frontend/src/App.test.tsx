import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const family = {
  id: 21,
  full_name: "Asha Rao",
  phone_number: "+919876500021",
  role: "FAMILY",
  created_at: "2026-01-01T10:00:00Z",
};
const elderly = {
  id: 34,
  full_name: "Lakshmi Rao",
  phone_number: "+919876500034",
  role: "ELDERLY",
  created_at: "2026-01-02T10:00:00Z",
};
const token = "header.payload.signature";

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function authResponse(user: typeof family | typeof elderly) {
  return { access_token: token, token_type: "bearer", user };
}

function requestParts(input: RequestInfo | URL, init?: RequestInit) {
  return {
    url: String(input),
    method: init?.method || "GET",
    headers: new Headers(init?.headers),
    body: typeof init?.body === "string" ? JSON.parse(init.body) as Record<string, unknown> : undefined,
  };
}

function setBaseFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = requestParts(input, init);
    if (request.url.endsWith("/api/auth/login")) return jsonResponse(authResponse(family));
    if (request.url.endsWith("/api/users")) return jsonResponse([family, elderly]);
    if (request.url.endsWith("/api/reminders?limit=100")) return jsonResponse([]);
    if (request.url.endsWith("/api/links/sent")) return jsonResponse([]);
    if (request.url.endsWith("/api/links/received")) return jsonResponse([]);
    return jsonResponse({ detail: "Not found" }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function signInAs(role: "FAMILY" | "ELDERLY" = "FAMILY") {
  const user = userEvent.setup();
  render(<App />);
  if (role === "ELDERLY") await user.click(screen.getByRole("button", { name: /elderly member/i }));
  await user.type(screen.getByLabelText("Phone number"), "+919876500021");
  await user.type(screen.getByLabelText("Password"), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  return user;
}

describe("Apno Ki Awaaz frontend API integration", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("authenticates FAMILY, loads real connection data, and sends a link request", async () => {
    const calls: ReturnType<typeof requestParts>[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestParts(input, init);
      calls.push(request);
      if (request.url.endsWith("/api/auth/login")) return jsonResponse(authResponse(family));
      if (request.url.endsWith("/api/users")) return jsonResponse([family, elderly]);
      if (request.url.endsWith("/api/reminders?limit=100")) return jsonResponse([]);
      if (request.url.endsWith("/api/links/sent")) return jsonResponse([]);
      if (request.url.endsWith("/api/links/request")) {
        return jsonResponse({
          id: 9,
          family_user_id: family.id,
          elderly_user_id: elderly.id,
          status: "PENDING",
          requested_at: "2026-11-10T10:00:00Z",
          responded_at: null,
          created_at: "2026-11-10T10:00:00Z",
        }, 201);
      }
      return jsonResponse({ detail: "Not found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = await signInAs();
    expect(await screen.findByText("Good to see you, Asha.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /family connections/i }));
    expect(await screen.findByText("Lakshmi Rao")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Elderly account ID"), String(elderly.id));
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Request sent for elderly account #34");
    const requestCall = calls.find((call) => call.url.endsWith("/api/links/request"));
    expect(requestCall?.headers.get("authorization")).toBe(`Bearer ${token}`);
    expect(requestCall?.body).toEqual({ elderly_user_id: elderly.id });
    expect(requestCall?.body).not.toHaveProperty("family_user_id");
  });

  it("creates a reminder with the selected recipient, schedule, and recurrence", async () => {
    const calls: ReturnType<typeof requestParts>[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestParts(input, init);
      calls.push(request);
      if (request.url.endsWith("/api/auth/login")) return jsonResponse(authResponse(family));
      if (request.url.endsWith("/api/users")) return jsonResponse([family, elderly]);
      if (request.url.endsWith("/api/reminders?limit=100")) return jsonResponse([]);
      if (request.url.endsWith("/api/links/sent")) return jsonResponse([]);
      if (request.url.endsWith("/api/reminders")) {
        return jsonResponse({
          id: 51,
          title: "Evening tablet",
          message: "Please take your medicine",
          elderly_user_id: elderly.id,
          created_by: family.id,
          scheduled_at: "2026-11-11T13:30:00Z",
          recurrence: "DAILY",
          status: "PENDING",
          created_at: "2026-11-10T10:00:00Z",
          updated_at: "2026-11-10T10:00:00Z",
          logs: [],
        }, 201);
      }
      return jsonResponse({ detail: "Not found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = await signInAs();
    await user.click(screen.getByRole("button", { name: /^reminders$/i }));
    await user.selectOptions(await screen.findByLabelText("Send to"), String(elderly.id));
    await user.type(screen.getByLabelText("Reminder title"), "Evening tablet");
    await user.type(screen.getByLabelText("Message"), "Please take your medicine");
    fireEvent.change(screen.getByLabelText("Date and time"), { target: { value: "2026-11-11T19:00" } });
    await user.selectOptions(screen.getByLabelText("Repeat"), "DAILY");
    await user.click(screen.getByRole("button", { name: "Create reminder" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Reminder “Evening tablet” was saved.");
    const createCall = calls.find((call) => call.method === "POST" && call.url.endsWith("/api/reminders"));
    expect(createCall?.headers.get("authorization")).toBe(`Bearer ${token}`);
    expect(createCall?.body).toMatchObject({
      elderly_user_id: elderly.id,
      title: "Evening tablet",
      message: "Please take your medicine",
      recurrence: "DAILY",
    });
    expect(createCall?.body?.scheduled_at).toMatch(/Z$/);
    expect(createCall?.body).not.toHaveProperty("created_by");
  });

  it("lets ELDERLY approve a request and loads protected audio with the bearer token", async () => {
    const request = {
      id: 77,
      family_user_id: 21,
      elderly_user_id: 34,
      status: "PENDING",
      requested_at: "2026-11-10T10:00:00Z",
      responded_at: null,
      created_at: "2026-11-10T10:00:00Z",
    };
    const reminder = {
      id: 81,
      title: "Morning medicine",
      message: "Take your medicine now",
      elderly_user_id: elderly.id,
      created_by: family.id,
      scheduled_at: "2026-11-11T03:00:00Z",
      recurrence: "ONCE",
      status: "AUDIO_READY",
      created_at: "2026-11-10T10:00:00Z",
      updated_at: "2026-11-10T10:00:00Z",
      logs: [],
    };
    const calls: ReturnType<typeof requestParts>[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const requestCall = requestParts(input, init);
      calls.push(requestCall);
      if (requestCall.url.endsWith("/api/auth/login")) return jsonResponse(authResponse(elderly));
      if (requestCall.url.endsWith("/api/users")) return jsonResponse([elderly]);
      if (requestCall.url.endsWith("/api/reminders?limit=100")) return jsonResponse([reminder]);
      if (requestCall.url.endsWith("/api/links/received")) return jsonResponse([request]);
      if (requestCall.url.endsWith("/api/links/77/approve")) return jsonResponse({ ...request, status: "APPROVED" });
      if (requestCall.url.endsWith("/api/reminders/81/audio")) return jsonResponse({
        reminder_id: 81,
        occurrences: [{ occurrence_at: reminder.scheduled_at, status: "AUDIO_READY", audio_available: true, generated_at: reminder.created_at, attempt_count: 1 }],
      });
      if (requestCall.url.endsWith("/api/reminders/81/audio/content")) {
        return new Response(new Blob(["RIFF-test-wave"]), { status: 200, headers: { "content-type": "audio/wav" } });
      }
      return jsonResponse({ detail: "Not found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:reminder-audio"), revokeObjectURL: vi.fn() });

    const user = await signInAs("ELDERLY");
    await user.click(within(screen.getByRole("navigation")).getByRole("button", { name: /family requests/i }));
    expect(await screen.findByText("Family account #21")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByText("Your choice")).toBeInTheDocument();
    const approvalCall = calls.find((call) => call.url.endsWith("/api/links/77/approve"));
    expect(approvalCall?.headers.get("authorization")).toBe(`Bearer ${token}`);

    await user.click(screen.getByRole("button", { name: /my reminders/i }));
    await user.click(await screen.findByRole("button", { name: "Load voice audio" }));
    expect(await screen.findByLabelText("Audio playback").catch(() => document.querySelector("audio"))).toBeTruthy();
    await waitFor(() => expect(calls.some((call) => call.url.endsWith("/api/reminders/81/audio/content"))).toBe(true));
    const audioCall = calls.find((call) => call.url.endsWith("/api/reminders/81/audio/content"));
    expect(audioCall?.headers.get("authorization")).toBe(`Bearer ${token}`);
    expect(document.querySelector("audio")).toHaveAttribute("src", "blob:reminder-audio");
  });

  it("shows ELDERLY users their account ID and consent reminder", async () => {
    setBaseFetch().mockImplementation(async (input, init) => {
      const request = requestParts(input, init);
      if (request.url.endsWith("/api/auth/login")) return jsonResponse(authResponse(elderly));
      if (request.url.endsWith("/api/users")) return jsonResponse([elderly]);
      if (request.url.endsWith("/api/reminders?limit=100")) return jsonResponse([]);
      if (request.url.endsWith("/api/links/received")) return jsonResponse([]);
      return jsonResponse({ detail: "Not found" }, 404);
    });

    await signInAs("ELDERLY");

    expect(await screen.findByText("Your account ID: 34")).toBeInTheDocument();
    expect(screen.getByText(/you approve every request/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy id/i })).toBeInTheDocument();
  });

  it("clears a session and returns to sign in on an expired-token API response", async () => {
    const fetchMock = setBaseFetch();
    fetchMock.mockImplementation(async (input, init) => {
      const request = requestParts(input, init);
      if (request.url.endsWith("/api/auth/login")) return jsonResponse(authResponse(family));
      if (request.url.endsWith("/api/users")) return jsonResponse({ detail: "Invalid or expired credentials" }, 401);
      return jsonResponse([]);
    });

    await signInAs();
    expect(await screen.findByText(/secure session ended/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(sessionStorage.getItem("apno-ki-awaaz.session")).toBeNull();
  });
});