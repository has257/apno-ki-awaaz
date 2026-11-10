import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AudioLines,
  BellRing,
  Check,
  CheckCheck,
  ChevronRight,
  CircleAlert,
  Clock3,
  Copy,
  HeartHandshake,
  Headphones,
  LoaderCircle,
  LogOut,
  Plus,
  RefreshCw,
  ShieldCheck,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";
import { ApiClient, ApiError } from "./api";
import { clearSession, readSession, saveSession } from "./session";
import type {
  AuthSession,
  FamilyLink,
  Reminder,
  ReminderAudioMetadata,
  Recurrence,
  User,
  UserRole,
} from "./types";

type Section = "overview" | "connections" | "reminders";

interface DashboardData {
  people: User[];
  reminders: Reminder[];
  links: FamilyLink[];
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function roleName(role: UserRole): string {
  return role === "FAMILY" ? "Family member" : "Elderly member";
}

function AuthScreen({ onAuthenticated, sessionMessage }: { onAuthenticated: (session: AuthSession) => void; sessionMessage: string }) {
  const [role, setRole] = useState<UserRole>("FAMILY");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const api = new ApiClient();
      const result =
        mode === "login"
          ? await api.login(phone, password)
          : await api.register({ full_name: fullName, phone_number: phone, password, role });
      if (result.user.role !== role) {
        setError(`That account is registered as ${roleName(result.user.role)}. Choose that role to sign in.`);
        return;
      }
      const session = { accessToken: result.access_token, user: result.user };
      saveSession(session);
      onAuthenticated(session);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-story" aria-label="Apno Ki Awaaz">
        <div className="brand-lockup brand-lockup-light">
          <span className="brand-mark"><AudioLines aria-hidden="true" /></span>
          <span>Apno Ki Awaaz</span>
        </div>
        <div className="story-copy">
          <p className="eyebrow">A little care, right on time</p>
          <h1>Reminders feel warmer when they come from family.</h1>
          <p>Simple, thoughtful reminders with a familiar Telugu voice.</p>
        </div>
        <div className="story-foot"><HeartHandshake size={18} /> Made for the people who care for you</div>
        <div className="sound-wave" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <p className="eyebrow">Welcome</p>
          <h2>{mode === "login" ? "Sign in to your account" : "Create your account"}</h2>
          <p className="muted">Choose the profile that matches how you use Apno Ki Awaaz.</p>
          {sessionMessage && <div className="notice notice-error" role="status"><ShieldCheck size={18} />{sessionMessage}</div>}

          <div className="role-switch" role="group" aria-label="Account type">
            <button type="button" className={role === "FAMILY" ? "selected" : ""} onClick={() => setRole("FAMILY")}>
              <UsersRound size={19} /> Family
            </button>
            <button type="button" className={role === "ELDERLY" ? "selected" : ""} onClick={() => setRole("ELDERLY")}>
              <UserRound size={19} /> Elderly member
            </button>
          </div>

          <form onSubmit={submit} className="form-stack">
            {mode === "register" && (
              <label>
                Full name
                <input autoComplete="name" required maxLength={120} value={fullName} onChange={(event) => setFullName(event.target.value)} />
              </label>
            )}
            <label>
              Phone number
              <input autoComplete="tel" type="tel" required minLength={7} maxLength={16} value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+91 98765 43210" />
            </label>
            <label>
              Password
              <input autoComplete={mode === "login" ? "current-password" : "new-password"} type="password" required minLength={mode === "register" ? 12 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />
              {mode === "register" && <small>Use at least 12 characters.</small>}
            </label>
            {error && <p className="inline-error" role="alert"><CircleAlert size={18} />{error}</p>}
            <button className="button button-primary button-wide" type="submit" disabled={busy}>
              {busy ? <LoaderCircle className="spin" size={19} /> : <ChevronRight size={19} />}
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <p className="auth-toggle">
            {mode === "login" ? "New to Apno Ki Awaaz?" : "Already have an account?"}{" "}
            <button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </p>
          <p className="secure-note"><ShieldCheck size={16} /> Your account is protected with secure sign-in.</p>
        </div>
      </section>
    </main>
  );
}

function StatusPill({ status }: { status: string }) {
  const className = status.toLowerCase().replaceAll("_", "-");
  return <span className={`status-pill status-${className}`}>{status.replaceAll("_", " ")}</span>;
}

function LoadingLine({ label = "Loading your information…" }: { label?: string }) {
  return <div className="loading-line"><LoaderCircle className="spin" size={20} />{label}</div>;
}

function EmptyState({ title, detail, icon: Icon = BellRing }: { title: string; detail: string; icon?: typeof BellRing }) {
  return <div className="empty-state"><span className="empty-icon"><Icon size={23} /></span><strong>{title}</strong><p>{detail}</p></div>;
}

function ReminderCard({
  reminder,
  user,
  api,
  onComplete,
  onError,
}: {
  reminder: Reminder;
  user: User;
  api: ApiClient;
  onComplete: (reminderId: number) => Promise<void>;
  onError: (error: unknown) => void;
}) {
  const [metadata, setMetadata] = useState<ReminderAudioMetadata | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [loadingAudio, setLoadingAudio] = useState(false);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [audioError, setAudioError] = useState("");
  const mayPlay = user.role === "ELDERLY" || reminder.created_by === user.id;
  const hasReadyAudio = Boolean(metadata?.occurrences.some((item) => item.audio_available && item.status === "AUDIO_READY"));

  useEffect(() => {
    let active = true;
    setLoadingMetadata(true);
    api.audioMetadata(reminder.id)
      .then((result) => { if (active) setMetadata(result); })
      .catch((error: unknown) => { if (active) onError(error); })
      .finally(() => { if (active) setLoadingMetadata(false); });
    return () => { active = false; };
  }, [api, onError, reminder.id]);

  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl); }, [audioUrl]);

  async function loadAudio() {
    setLoadingAudio(true);
    setAudioError("");
    try {
      const blob = await api.audioBlob(reminder.id);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      setAudioUrl(URL.createObjectURL(blob));
    } catch (error) {
      setAudioError(errorText(error));
      onError(error);
    } finally {
      setLoadingAudio(false);
    }
  }

  return (
    <article className="reminder-row">
      <div className="reminder-time"><span>{formatDate(reminder.scheduled_at)}</span><small>{reminder.recurrence.toLowerCase()}</small></div>
      <div className="reminder-copy"><h3>{reminder.title}</h3><p>{reminder.message}</p><small>Reminder #{reminder.id}</small></div>
      <div className="reminder-actions"><StatusPill status={reminder.status} />
        {mayPlay && hasReadyAudio && !audioUrl && <button className="button button-audio" type="button" onClick={loadAudio} disabled={loadingAudio}>
          {loadingAudio ? <LoaderCircle className="spin" size={17} /> : <Headphones size={17} />}{loadingAudio ? "Loading audio…" : "Load voice audio"}
        </button>}
        {mayPlay && loadingMetadata && <span className="tiny-muted">Checking audio…</span>}
        {user.role === "ELDERLY" && reminder.status === "AUDIO_READY" && <button className="button button-soft" type="button" onClick={() => void onComplete(reminder.id)}><CheckCheck size={17} />Mark complete</button>}
      </div>
      {audioUrl && <div className="audio-player"><div className="audio-label"><AudioLines size={17} /> Telugu voice reminder</div><audio controls autoPlay src={audioUrl}>Your browser does not support audio playback.</audio></div>}
      {audioError && <p className="inline-error audio-error" role="alert">{audioError}</p>}
    </article>
  );
}

function ReminderList({
  reminders,
  user,
  api,
  loading,
  onComplete,
  onError,
}: {
  reminders: Reminder[];
  user: User;
  api: ApiClient;
  loading: boolean;
  onComplete: (reminderId: number) => Promise<void>;
  onError: (error: unknown) => void;
}) {
  if (loading) return <LoadingLine label="Loading reminders…" />;
  if (reminders.length === 0) return <EmptyState title="No reminders yet" detail={user.role === "FAMILY" ? "Create one for an approved family connection." : "Your family reminders will appear here."} />;
  return <div className="reminder-list">{reminders.map((reminder) => <ReminderCard key={reminder.id} reminder={reminder} user={user} api={api} onComplete={onComplete} onError={onError} />)}</div>;
}

function FamilyConnections({
  people,
  links,
  loading,
  api,
  onChanged,
  onError,
}: {
  people: User[];
  links: FamilyLink[];
  loading: boolean;
  api: ApiClient;
  onChanged: () => void;
  onError: (error: unknown) => void;
}) {
  const [elderlyId, setElderlyId] = useState("");
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState("");
  const [formError, setFormError] = useState("");
  const linkedPeople = people.filter((person) => person.role === "ELDERLY");

  async function requestAccess(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setSuccess("");
    setFormError("");
    try {
      const link = await api.requestLink(Number(elderlyId));
      setSuccess(`Request sent for elderly account #${link.elderly_user_id}.`);
      setElderlyId("");
      onChanged();
    } catch (error) {
      setFormError(errorText(error));
      onError(error);
    } finally {
      setBusy(false);
    }
  }

  return <div className="connections-grid">
    <section className="section-block">
      <SectionHeading eyebrow="Your people" title="Connected members" detail="Only approved connections can receive reminders." />
      {loading ? <LoadingLine label="Loading connections…" /> : linkedPeople.length === 0 ? <EmptyState title="No approved connections" detail="Send a request to an elderly member using their account ID." icon={UsersRound} /> :
        <div className="people-list">{linkedPeople.map((person) => <div className="person-row" key={person.id}><span className="person-avatar"><UserRound size={20} /></span><span><strong>{person.full_name}</strong><small>Account #{person.id}</small></span><StatusPill status="APPROVED" /></div>)}</div>}
    </section>
    <section className="section-block request-panel">
      <SectionHeading eyebrow="Ask to connect" title="Send a family request" detail="The elderly member must approve before you can manage reminders." />
      <form className="form-stack compact-form" onSubmit={requestAccess}>
        <label>Elderly account ID<input inputMode="numeric" type="number" min="1" required value={elderlyId} onChange={(event) => setElderlyId(event.target.value)} placeholder="For example, 12" /></label>
        {formError && <p className="inline-error" role="alert"><CircleAlert size={17} />{formError}</p>}
        {success && <p className="inline-success" role="status"><Check size={17} />{success}</p>}
        <button className="button button-primary" type="submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={18} /> : <Plus size={18} />}{busy ? "Sending…" : "Send request"}</button>
      </form>
      <div className="sent-list"><h3>Requests you’ve sent</h3>{loading ? <LoadingLine label="Loading requests…" /> : links.length === 0 ? <p className="muted">No requests yet.</p> : links.map((link) => <div className="sent-row" key={link.id}><span>Account #{link.elderly_user_id}</span><StatusPill status={link.status} /></div>)}</div>
    </section>
  </div>;
}

function ElderlyRequests({
  links,
  loading,
  api,
  onChanged,
  onError,
}: {
  links: FamilyLink[];
  loading: boolean;
  api: ApiClient;
  onChanged: () => void;
  onError: (error: unknown) => void;
}) {
  const [busyId, setBusyId] = useState<number | null>(null);

  async function decide(linkId: number, decision: "approve" | "reject") {
    setBusyId(linkId);
    try {
      await api.decideLink(linkId, decision);
      onChanged();
    } catch (error) {
      onError(error);
    } finally {
      setBusyId(null);
    }
  }

  if (loading) return <LoadingLine label="Loading family requests…" />;
  if (links.length === 0) return <EmptyState title="No family requests" detail="New requests will appear here for you to review." icon={HeartHandshake} />;
  return <div className="request-list">{links.map((link) => <article className="request-row" key={link.id}>
    <div className="request-icon"><HeartHandshake size={23} /></div>
    <div className="request-description"><strong>Family account #{link.family_user_id}</strong><p>Would like to help manage your reminders.</p><small>Sent {formatDate(link.requested_at)}</small></div>
    {link.status === "PENDING" ? <div className="request-actions"><button className="button button-primary" type="button" disabled={busyId === link.id} onClick={() => void decide(link.id, "approve")}>{busyId === link.id ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />}Approve</button><button className="button button-outline" type="button" disabled={busyId === link.id} onClick={() => void decide(link.id, "reject")}><X size={17} />Decline</button></div> : <StatusPill status={link.status} />}
  </article>)}</div>;
}

function ReminderForm({
  people,
  api,
  onCreated,
  onError,
}: {
  people: User[];
  api: ApiClient;
  onCreated: () => void;
  onError: (error: unknown) => void;
}) {
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [elderlyId, setElderlyId] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [recurrence, setRecurrence] = useState<Recurrence>("ONCE");
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setSuccess("");
    setError("");
    try {
      const created = await api.createReminder({
        title: title.trim(),
        message: message.trim(),
        elderly_user_id: Number(elderlyId),
        scheduled_at: new Date(scheduledAt).toISOString(),
        recurrence,
      });
      setSuccess(`Reminder “${created.title}” was saved.`);
      setTitle("");
      setMessage("");
      setScheduledAt("");
      onCreated();
    } catch (submitError) {
      setError(errorText(submitError));
      onError(submitError);
    } finally {
      setBusy(false);
    }
  }

  if (people.length === 0) return <div className="callout"><UsersRound size={20} /><p>Approve a family connection before creating a reminder.</p></div>;
  return <form className="reminder-form" onSubmit={submit}>
    <label>Send to<select required value={elderlyId} onChange={(event) => setElderlyId(event.target.value)}><option value="">Choose a family member</option>{people.map((person) => <option value={person.id} key={person.id}>{person.full_name}</option>)}</select></label>
    <label>Reminder title<input required maxLength={150} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Medicine time" /></label>
    <label className="form-span">Message<textarea required maxLength={2000} rows={3} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="A short, kind message to include in the voice reminder" /></label>
    <label>Date and time<input required type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} /></label>
    <label>Repeat<select value={recurrence} onChange={(event) => setRecurrence(event.target.value as Recurrence)}><option value="ONCE">One time</option><option value="DAILY">Every day</option><option value="WEEKLY">Every week</option></select></label>
    {error && <p className="inline-error form-span" role="alert"><CircleAlert size={17} />{error}</p>}
    {success && <p className="inline-success form-span" role="status"><Check size={17} />{success}</p>}
    <div className="form-span form-footer"><span className="muted"><AudioLines size={17} /> Telugu voice will be generated at reminder time.</span><button className="button button-primary" type="submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={18} /> : <Plus size={18} />}{busy ? "Saving…" : "Create reminder"}</button></div>
  </form>;
}

function SectionHeading({ eyebrow, title, detail }: { eyebrow: string; title: string; detail: string }) {
  return <div className="section-heading"><p className="eyebrow">{eyebrow}</p><h2>{title}</h2><p className="muted">{detail}</p></div>;
}

function App() {
  const [session, setSession] = useState<AuthSession | null>(() => readSession());
  const [checkingSession, setCheckingSession] = useState(Boolean(session));
  const [section, setSection] = useState<Section>("overview");
  const [data, setData] = useState<DashboardData>({ people: [], reminders: [], links: [] });
  const [loading, setLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState("");
  const [notice, setNotice] = useState("");
  const [copiedAccountId, setCopiedAccountId] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const api = useMemo(() => new ApiClient(session?.accessToken), [session?.accessToken]);

  const signOut = useCallback((message = "") => {
    clearSession();
    setSession(null);
    setData({ people: [], reminders: [], links: [] });
    setDashboardError("");
    setNotice(message);
    setSection("overview");
  }, []);

  const handleApiError = useCallback((error: unknown) => {
    if (isUnauthorized(error)) signOut("Your secure session ended. Please sign in again.");
  }, [signOut]);

  useEffect(() => {
    if (!session) {
      setCheckingSession(false);
      return;
    }
    let active = true;
    api.me()
      .then((user) => {
        if (!active) return;
        const updated = { ...session, user };
        saveSession(updated);
        setSession(updated);
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (isUnauthorized(error)) signOut("Your secure session ended. Please sign in again.");
      })
      .finally(() => { if (active) setCheckingSession(false); });
    return () => { active = false; };
    // Validate the stored identity once when the application opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!session) return;
    let active = true;
    setLoading(true);
    setDashboardError("");
    const requests = session.user.role === "FAMILY"
      ? Promise.all([api.users(), api.reminders(), api.sentLinks()])
      : Promise.all([api.users(), api.reminders(), api.receivedLinks()]);
    requests
      .then(([people, reminders, links]) => {
        if (active) setData({ people, reminders, links });
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (isUnauthorized(error)) handleApiError(error);
        else setDashboardError(errorText(error));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api, refreshKey, session]);

  const refresh = useCallback(() => {
    setRefreshKey((value) => value + 1);
  }, []);

  const completeReminder = useCallback(async (reminderId: number) => {
    try {
      await api.completeReminder(reminderId);
      setNotice("Reminder marked as complete.");
      refresh();
    } catch (error) {
      if (isUnauthorized(error)) handleApiError(error);
      else setDashboardError(errorText(error));
    }
  }, [api, handleApiError, refresh]);

  async function copyAccountId() {
    const accountId = String(session!.user.id);
    try {
      await navigator.clipboard.writeText(accountId);
      setCopiedAccountId(true);
      setNotice(`Account ID ${accountId} copied. Your family still needs your approval to connect.`);
      window.setTimeout(() => setCopiedAccountId(false), 2500);
    } catch {
      setNotice(`Your account ID is ${accountId}. Share it with family; you will still approve any request.`);
    }
  }

  if (checkingSession) return <main className="boot-screen"><AudioLines size={28} /><LoadingLine label="Checking your secure session…" /></main>;
  if (!session) return <AuthScreen sessionMessage={notice} onAuthenticated={(authenticated) => { setNotice(""); setSession(authenticated); }} />;

  const isFamily = session.user.role === "FAMILY";
  const linkedPeople = data.people.filter((person) => person.role === "ELDERLY");
  const pendingReminders = data.reminders.filter((reminder) => reminder.status === "PENDING").length;
  const navItems: { key: Section; label: string; icon: typeof Activity }[] = isFamily
    ? [{ key: "overview", label: "Overview", icon: Activity }, { key: "connections", label: "Family connections", icon: UsersRound }, { key: "reminders", label: "Reminders", icon: BellRing }]
    : [{ key: "overview", label: "My reminders", icon: BellRing }, { key: "connections", label: "Family requests", icon: HeartHandshake }, { key: "reminders", label: "All reminders", icon: Clock3 }];

  return <div className={`app-shell ${isFamily ? "family-shell" : "elderly-shell"}`}>
    <aside className="sidebar">
      <a className="brand-lockup" href="#home" onClick={(event) => { event.preventDefault(); setSection("overview"); }}><span className="brand-mark"><AudioLines aria-hidden="true" /></span><span>Apno Ki Awaaz</span></a>
      <div className="side-profile"><span className="profile-orb">{isFamily ? <UsersRound /> : <UserRound />}</span><div><strong>{session.user.full_name}</strong><span>{roleName(session.user.role)} · ID {session.user.id}</span></div></div>
      <nav className="main-nav" aria-label="Main navigation">{navItems.map(({ key, label, icon: Icon }) => <button key={key} type="button" className={section === key ? "active" : ""} onClick={() => setSection(key)}><Icon size={19} />{label}{key === "connections" && !isFamily && data.links.filter((link) => link.status === "PENDING").length > 0 && <span className="nav-count">{data.links.filter((link) => link.status === "PENDING").length}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="privacy-mark"><ShieldCheck size={18} /><span>Private family space</span></div><button className="signout-button" type="button" onClick={() => signOut()}><LogOut size={18} />Sign out</button></div>
    </aside>

    <main className="main-panel">
      <header className="topbar"><div><span className="today-label">{new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date())}</span><span className="topbar-role">{roleName(session.user.role)}</span></div><button className="icon-button" type="button" onClick={refresh} aria-label="Refresh information" title="Refresh"><RefreshCw size={19} /></button></header>
      <div className="content-wrap">
        {notice && <div className="notice notice-success" role="status"><Check size={18} />{notice}<button type="button" aria-label="Dismiss message" onClick={() => setNotice("")}><X size={17} /></button></div>}
        {dashboardError && <div className="notice notice-error" role="alert"><CircleAlert size={18} /><span>{dashboardError}</span><button type="button" onClick={refresh}><RefreshCw size={16} />Try again</button></div>}

        {section === "overview" && <>
          <div className="welcome-row"><div><p className="eyebrow">{isFamily ? "Your care circle" : "Your day, gently organized"}</p><h1>{isFamily ? `Good to see you, ${session.user.full_name.split(" ")[0]}.` : `Namaste, ${session.user.full_name.split(" ")[0]}.`}</h1><p className="welcome-detail">{isFamily ? "A thoughtful reminder can make someone’s day feel a little easier." : "Your family’s reminders are here whenever you need them."}</p></div><div className="welcome-art" aria-hidden="true"><span className="art-sun"/><span className="art-line art-line-one"/><span className="art-line art-line-two"/><AudioLines size={48}/></div></div>
          {!isFamily && <section className="account-id-card" aria-label="Your account ID"><span className="account-id-icon"><UserRound size={20}/></span><div><strong>Your account ID: {session.user.id}</strong><small>Share this with family to receive a connection request. You approve every request.</small></div><button className="button button-outline" type="button" onClick={() => void copyAccountId()}><Copy size={17}/>{copiedAccountId ? "Copied" : "Copy ID"}</button></section>}
          <div className="metric-strip"><div className="metric"><span className="metric-icon green"><UsersRound size={20}/></span><span><strong>{isFamily ? linkedPeople.length : data.links.filter((link) => link.status === "PENDING").length}</strong><small>{isFamily ? "connected members" : "requests to review"}</small></span></div><div className="metric"><span className="metric-icon yellow"><BellRing size={20}/></span><span><strong>{pendingReminders}</strong><small>upcoming reminders</small></span></div><div className="metric"><span className="metric-icon coral"><AudioLines size={20}/></span><span><strong>{data.reminders.filter((reminder) => reminder.status === "AUDIO_READY").length}</strong><small>voice reminders ready</small></span></div></div>
          {isFamily ? <>
            <div className="overview-heading"><SectionHeading eyebrow="Your schedule" title="Upcoming reminders" detail="Voice audio appears when the reminder is due."/><button className="text-button" type="button" onClick={() => setSection("reminders")}>View all <ChevronRight size={17}/></button></div>
            <ReminderList reminders={data.reminders.slice(0, 4)} user={session.user} api={api} loading={loading} onComplete={completeReminder} onError={handleApiError}/>
            <div className="overview-footer"><div><HeartHandshake size={22}/><span><strong>Care works both ways</strong><small>Every connection is approved by the elderly member.</small></span></div><button className="button button-outline" type="button" onClick={() => setSection("connections")}>Manage connections <ChevronRight size={17}/></button></div>
          </> : <>
            <div className="overview-heading"><SectionHeading eyebrow="Coming up" title="Your reminders" detail="Listen to each voice reminder whenever you’re ready."/><button className="text-button" type="button" onClick={() => setSection("reminders")}>View all <ChevronRight size={17}/></button></div>
            <ReminderList reminders={data.reminders.slice(0, 5)} user={session.user} api={api} loading={loading} onComplete={completeReminder} onError={handleApiError}/>
            {data.links.some((link) => link.status === "PENDING") && <button className="consent-nudge" type="button" onClick={() => setSection("connections")}><HeartHandshake size={20}/><span><strong>You have family requests to review</strong><small>Choose who may help manage your reminders.</small></span><ChevronRight size={19}/></button>}
          </>}
        </>}

        {section === "connections" && <>
          <SectionHeading eyebrow={isFamily ? "Your care circle" : "Your choice"} title={isFamily ? "Family connections" : "Family requests"} detail={isFamily ? "Request a connection, then wait for the elderly member’s approval." : "Only people you approve can help manage your reminders."}/>
          {isFamily ? <FamilyConnections people={data.people} links={data.links} loading={loading} api={api} onChanged={refresh} onError={handleApiError}/> : <ElderlyRequests links={data.links} loading={loading} api={api} onChanged={refresh} onError={handleApiError}/>}
        </>}

        {section === "reminders" && <>
          <SectionHeading eyebrow={isFamily ? "Plan a kind reminder" : "Your reminder list"} title={isFamily ? "Reminders" : "All reminders"} detail={isFamily ? "Set a time and a familiar Telugu voice will speak your message." : "Your family’s reminders, in one easy-to-read place."}/>
          {isFamily && <section className="create-panel"><div className="panel-topline"><span className="panel-icon"><Plus size={21}/></span><div><h2>Create a reminder</h2><p>Only approved family connections are available.</p></div></div><ReminderForm people={linkedPeople} api={api} onCreated={refresh} onError={handleApiError}/></section>}
          <section className="reminders-section"><div className="section-subheading"><h2>{isFamily ? "Scheduled reminders" : "Your reminders"}</h2><span>{data.reminders.length} total</span></div><ReminderList reminders={data.reminders} user={session.user} api={api} loading={loading} onComplete={completeReminder} onError={handleApiError}/></section>
        </>}
      </div>
    </main>
  </div>;
}

export default App;