import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  BellRing,
  BrainCircuit,
  CalendarClock,
  Clock,
  Database,
  Download,
  Eye,
  EyeOff,
  Fingerprint,
  HardDrive,
  KeyRound,
  Laptop,
  LogOut,
  MailCheck,
  Moon,
  RotateCcw,
  Save,
  Shield,
  ShieldCheck,
  SlidersHorizontal,
  Sun,
  Trash2,
  User,
  UserCog,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "react-hot-toast";
import { useAuth } from "../../store/authStore";
import useThemeStore from "../../store/themeStore";
import useDatasetStore from "../../store/datasetStore";
import useChatStore from "../../store/chatStore";
import useChatHistoryStore from "../../store/chatHistoryStore";
import { cn } from "../../lib/utils";
import { agenticAPI } from "../../services/api";

/* ─── Constants ─── */
const SETTINGS_PREFS_KEY = "datasage-settings-preferences";

const TAB_ITEMS = [
  { id: "account", label: "Account", icon: UserCog },
  { id: "security", label: "Password", icon: ShieldCheck },
  { id: "notifications", label: "Notifications", icon: BellRing },
  { id: "workspace", label: "Appearance", icon: SlidersHorizontal },
  { id: "data", label: "Data & Session", icon: Database },
  { id: "ai-memory", label: "AI Memory", icon: BrainCircuit },
];

/* ─── Motion ─── */
const fadeSlide = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: "easeOut" } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.14 } },
};

/* ─── Preference helpers ─── */
const buildDefaultPreferences = (theme = "dark") => ({
  notifications: { productAnnouncements: true, aiInsightReady: true, securityAlerts: true },
  workspace: { theme, language: "en", autoRefreshDatasets: true, compactDensity: false, reduceAnimations: false },
});

const normalizePreferences = (raw, fallbackTheme = "dark") => {
  const d = buildDefaultPreferences(fallbackTheme);
  if (!raw || typeof raw !== "object") return d;
  return {
    notifications: { ...d.notifications, ...(raw.notifications || {}) },
    workspace: { ...d.workspace, ...(raw.workspace || {}) },
  };
};

const readStoredPreferences = (fallbackTheme = "dark") => {
  if (typeof window === "undefined") return buildDefaultPreferences(fallbackTheme);
  try {
    const raw = window.localStorage.getItem(SETTINGS_PREFS_KEY);
    if (!raw) return buildDefaultPreferences(fallbackTheme);
    return normalizePreferences(JSON.parse(raw), fallbackTheme);
  } catch { return buildDefaultPreferences(fallbackTheme); }
};

const persistPreferences = (prefs) => {
  if (typeof window !== "undefined") window.localStorage.setItem(SETTINGS_PREFS_KEY, JSON.stringify(prefs));
};

const formatDate = (value) => {
  if (!value) return "\u2014";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "\u2014";
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};

const getDisplayName = (u) => u?.username || u?.full_name || "User";

/* ─── Primitives ─── */
const inputCls =
  "h-12 w-full rounded-xl border border-white/[0.08] bg-noir/60 px-4 text-[15px] text-pearl/90 placeholder:text-granite/60 outline-none transition-all focus:border-pearl/25 focus:ring-2 focus:ring-pearl/10";

const Toggle = ({ checked, onChange }) => (
  <button type="button" role="switch" aria-checked={checked} onClick={onChange}
    className={cn("relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-colors duration-200",
      checked ? "border-pearl/30 bg-pearl/80" : "border-white/[0.1] bg-avocado/80")}>
    <span className={cn("pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-200",
      checked ? "translate-x-[24px]" : "translate-x-[3px]")} />
  </button>
);

/* ─── Horizontal form row (label left, content right) — stacks on mobile ─── */
const FormRow = ({ label, description, children, noBorder }) => (
  <div className={cn("flex flex-col sm:flex-row sm:items-start gap-1.5 sm:gap-8 py-5", !noBorder && "border-b border-white/[0.05]")}>
    <div className="sm:w-[280px] shrink-0">
      <p className="text-[15px] font-medium text-pearl">{label}</p>
      {description && <p className="mt-1 text-sm text-granite/90 leading-relaxed">{description}</p>}
    </div>
    <div className="flex-1 mt-2 sm:mt-0">{children}</div>
  </div>
);

/* ─── Toggle Row in horizontal layout ─── */
const ToggleFormRow = ({ label, description, checked, onChange }) => (
  <FormRow label={label} description={description}>
    <div className="flex sm:justify-end">
      <Toggle checked={checked} onChange={onChange} />
    </div>
  </FormRow>
);

/* ─── Action footer bar (Cancel + Save) ─── */
const ActionFooter = ({ onSave, saving, disabled, saveLabel = "Save changes", saveClassName }) => (
  <div className="flex items-center justify-end gap-3 pt-5 border-t border-white/[0.05] mt-2">
    <motion.button whileTap={{ scale: 0.97 }}
      className="rounded-xl border border-white/[0.08] bg-white/[0.03] px-6 py-2.5 text-[15px] font-medium text-pearl/70 transition-all hover:bg-white/[0.06] hover:text-pearl">
      Cancel
    </motion.button>
    <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.97 }} onClick={onSave} disabled={disabled}
      className={cn("inline-flex items-center gap-2 rounded-xl bg-pearl px-6 py-2.5 text-[15px] font-semibold text-noir transition-colors hover:bg-pearl/85 disabled:cursor-not-allowed disabled:opacity-50", saveClassName)}>
      <Save className="h-[18px] w-[18px]" />
      {saving ? "Saving\u2026" : saveLabel}
    </motion.button>
  </div>
);

/* ═══════════════════════════════════════════════ */
/*                  MAIN COMPONENT                 */
/* ═══════════════════════════════════════════════ */
const SettingsPage = () => {
  const { user, updateProfile, changePassword, logout } = useAuth();
  const theme = useThemeStore((s) => s.theme);
  const resolvedTheme = useThemeStore((s) => s.resolvedTheme);
  const setTheme = useThemeStore((s) => s.setTheme);

  const datasets = useDatasetStore((s) => s.datasets);
  const fetchDatasets = useDatasetStore((s) => s.fetchDatasets);
  const setDatasets = useDatasetStore((s) => s.setDatasets);
  const setSelectedDataset = useDatasetStore((s) => s.setSelectedDataset);

  const clearAllConversations = useChatStore((s) => s.clearAllConversations);
  const clearAllChats = useChatHistoryStore((s) => s.clearAllChats);

  const tabsRef = useRef(null);

  /* ── State ── */
  const [activeTab, setActiveTab] = useState("account");
  const [savingProfile, setSavingProfile] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [clearingLocalData, setClearingLocalData] = useState(false);
  const [prefsDirty, setPrefsDirty] = useState(false);

  /* ── Belief Store (AI Memory) state ── */
  const [beliefs, setBeliefs] = useState([]);
  const [beliefsCount, setBeliefsCount] = useState(0);
  const [loadingBeliefs, setLoadingBeliefs] = useState(false);
  const [clearingBeliefs, setClearingBeliefs] = useState(false);
  const [deletingBeliefId, setDeletingBeliefId] = useState(null);

  const [profileForm, setProfileForm] = useState({ username: getDisplayName(user), email: user?.email || "" });
  const [passwordForm, setPasswordForm] = useState({ currentPassword: "", newPassword: "", confirmPassword: "" });
  const [showPassword, setShowPassword] = useState({ current: false, next: false, confirm: false });
  const [preferences, setPreferences] = useState(() => readStoredPreferences(theme));

  useEffect(() => { setProfileForm({ username: getDisplayName(user), email: user?.email || "" }); }, [user]);

  /* ── Fetch beliefs when AI Memory tab is active ── */
  useEffect(() => {
    if (activeTab !== "ai-memory") return;
    let cancelled = false;
    const fetchBeliefs = async () => {
      setLoadingBeliefs(true);
      try {
        const res = await agenticAPI.listBeliefs(100);
        if (!cancelled) {
          setBeliefs(res.data?.beliefs || []);
          setBeliefsCount(res.data?.total_count || 0);
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Failed to fetch beliefs:", err);
          setBeliefs([]);
          setBeliefsCount(0);
        }
      } finally {
        if (!cancelled) setLoadingBeliefs(false);
      }
    };
    fetchBeliefs();
    return () => { cancelled = true; };
  }, [activeTab]);
  useEffect(() => {
    setPreferences((p) => p.workspace.theme === theme ? p : { ...p, workspace: { ...p.workspace, theme } });
  }, [theme]);

  const datasetStats = useMemo(() => {
    const total = datasets.length;
    const ready = datasets.filter((d) => d?.is_processed || (d?.status || "").toLowerCase() === "completed").length;
    return { total, ready };
  }, [datasets]);

  /* ── Handlers ── */
  const handleSaveProfile = async () => {
    const username = profileForm.username.trim();
    if (username.length < 2) { toast.error("Username must be at least 2 characters."); return; }
    setSavingProfile(true);
    const r = await updateProfile({ username });
    setSavingProfile(false);
    if (!r.success) { toast.error(r.error || "Unable to update profile."); return; }
    toast.success("Profile updated.");
  };

  const handleChangePassword = async () => {
    const { currentPassword, newPassword, confirmPassword } = passwordForm;
    if (!currentPassword || !newPassword || !confirmPassword) { toast.error("Fill in all password fields."); return; }
    if (newPassword.length < 6) { toast.error("New password must be at least 6 characters."); return; }
    if (newPassword !== confirmPassword) { toast.error("Passwords do not match."); return; }
    if (newPassword === currentPassword) { toast.error("New password must differ from current."); return; }
    setChangingPassword(true);
    const r = await changePassword(currentPassword, newPassword);
    setChangingPassword(false);
    if (!r.success) { toast.error(r.error || "Failed to change password."); return; }
    setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
    toast.success("Password changed.");
  };

  const updatePref = (section, key, value) => {
    setPreferences((p) => ({ ...p, [section]: { ...p[section], [key]: value } }));
    setPrefsDirty(true);
  };

  const handleTheme = (next) => { updatePref("workspace", "theme", next); setTheme(next); };

  const handleSavePrefs = async () => {
    setSavingPrefs(true);
    persistPreferences(preferences);
    await new Promise((r) => setTimeout(r, 200));
    setSavingPrefs(false);
    setPrefsDirty(false);
    toast.success("Preferences saved.");
  };

  const handleExport = () => {
    const snapshot = {
      exported_at: new Date().toISOString(),
      account: { id: user?.id, username: getDisplayName(user), email: user?.email, created_at: user?.created_at, last_login: user?.last_login },
      preferences,
      datasets: datasets.map((d) => ({ id: d?.id || d?._id, name: d?.name || d?.filename || "Untitled", row_count: d?.row_count || 0, column_count: d?.column_count || 0, status: d?.status || "unknown", created_at: d?.created_at || d?.uploaded_at || null })),
    };
    const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: `datasage-workspace-${new Date().toISOString().slice(0, 10)}.json` });
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast.success("Workspace exported.");
  };

  const handleClearLocal = async () => {
    setClearingLocalData(true);
    clearAllConversations(); clearAllChats();
    setDatasets([]); setSelectedDataset(null);
    ["dataset-storage", "datasage-chat-store", "chat-history-storage", SETTINGS_PREFS_KEY].forEach((k) => { localStorage.removeItem(k); sessionStorage.removeItem(k); });
    const d = buildDefaultPreferences(theme);
    setPreferences(d); persistPreferences(d); setPrefsDirty(false);
    await fetchDatasets(true);
    setClearingLocalData(false);
    toast.success("Local cache reset.");
  };

  /* ═══════════════════ TAB RENDERERS ═══════════════════ */

  const renderAccountTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <FormRow label="Username" description="This is your display name across DataSage.">
        <input value={profileForm.username} onChange={(e) => setProfileForm((p) => ({ ...p, username: e.target.value }))}
          className={cn(inputCls, "max-w-md")} placeholder="Enter your username" />
      </FormRow>
      <FormRow label="Email address" description="Your account email. Cannot be changed.">
        <input value={profileForm.email} disabled className={cn(inputCls, "max-w-md cursor-not-allowed opacity-50")} />
      </FormRow>
      <FormRow label="Member since" description="When your account was created.">
        <p className="text-[15px] text-pearl/80 pt-2.5">{formatDate(user?.created_at)}</p>
      </FormRow>
      <FormRow label="Last login" description="Your most recent sign-in." noBorder>
        <p className="text-[15px] text-pearl/80 pt-2.5">{formatDate(user?.last_login)}</p>
      </FormRow>
      <ActionFooter onSave={handleSaveProfile} saving={savingProfile} saveLabel="Save profile" />
    </motion.div>
  );

  const renderSecurityTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-2">
        <h3 className="text-lg font-semibold text-pearl">Password</h3>
        <p className="text-sm text-granite/90 mt-1">Please enter your current password to change your password.</p>
      </div>
      {[
        { key: "currentPassword", label: "Current password", vis: "current", value: passwordForm.currentPassword, hint: null },
        { key: "newPassword", label: "New password", vis: "next", value: passwordForm.newPassword, hint: "Your new password must be at least 6 characters." },
        { key: "confirmPassword", label: "Confirm new password", vis: "confirm", value: passwordForm.confirmPassword, hint: null },
      ].map((f, i, arr) => (
        <FormRow key={f.key} label={f.label} noBorder={i === arr.length - 1}>
          <div className="max-w-md">
            <div className="relative">
              <input type={showPassword[f.vis] ? "text" : "password"} value={f.value}
                onChange={(e) => setPasswordForm((p) => ({ ...p, [f.key]: e.target.value }))}
                className={cn(inputCls, "pr-11")} placeholder={f.label} />
              <button type="button" onClick={() => setShowPassword((p) => ({ ...p, [f.vis]: !p[f.vis] }))}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-granite hover:text-pearl/70 transition-colors p-1">
                {showPassword[f.vis] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {f.hint && <p className="mt-1.5 text-sm text-granite/90 leading-relaxed">{f.hint}</p>}
          </div>
        </FormRow>
      ))}
      <ActionFooter onSave={handleChangePassword} saving={changingPassword} saveLabel="Update password"
        saveClassName="bg-gold hover:bg-gold/85" />
    </motion.div>
  );

  const renderNotificationsTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-2">
        <h3 className="text-lg font-semibold text-pearl">Notification preferences</h3>
        <p className="text-sm text-granite/90 mt-1">Choose what reaches your inbox and activity stream.</p>
      </div>
      <ToggleFormRow label="Product announcements" description="Release notes, feature updates, and major platform changes."
        checked={preferences.notifications.productAnnouncements}
        onChange={() => updatePref("notifications", "productAnnouncements", !preferences.notifications.productAnnouncements)} />
      <ToggleFormRow label="AI insight ready" description="Get notified when long-running analyses and AI pipelines finish."
        checked={preferences.notifications.aiInsightReady}
        onChange={() => updatePref("notifications", "aiInsightReady", !preferences.notifications.aiInsightReady)} />
      <ToggleFormRow label="Security alerts" description="Authentication warnings, suspicious activity, and session alerts."
        checked={preferences.notifications.securityAlerts}
        onChange={() => updatePref("notifications", "securityAlerts", !preferences.notifications.securityAlerts)} />
      <ActionFooter onSave={handleSavePrefs} saving={savingPrefs} disabled={!prefsDirty} saveLabel="Save preferences" />
    </motion.div>
  );

  const renderWorkspaceTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-2">
        <h3 className="text-lg font-semibold text-pearl">Appearance & Behavior</h3>
        <p className="text-sm text-granite/90 mt-1">Configure how the application looks and behaves.</p>
      </div>
      <FormRow label="Color theme" description="Select your preferred color scheme.">
        <div className="grid grid-cols-3 gap-3 max-w-sm">
          {[
            { id: "light", label: "Light", icon: Sun },
            { id: "dark", label: "Dark", icon: Moon },
            { id: "system", label: "System", icon: Laptop },
          ].map((t) => (
            <button key={t.id} onClick={() => handleTheme(t.id)}
              className={cn("flex flex-col items-center gap-1.5 rounded-xl border px-3 py-4 transition-all text-center",
                preferences.workspace.theme === t.id
                  ? "border-pearl/30 bg-pearl/10 text-pearl ring-1 ring-pearl/20"
                  : "border-white/[0.06] bg-noir/30 text-granite hover:bg-white/[0.04] hover:text-pearl/70")}>
              <t.icon className="h-6 w-6" />
              <span className="text-sm font-medium">{t.label}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-sm text-granite/90">
          Active: <span className="text-pearl/70 font-medium">{preferences.workspace.theme}</span> &middot; Rendered as <span className="text-pearl/70 font-medium">{resolvedTheme}</span>
        </p>
      </FormRow>
      <ToggleFormRow label="Auto refresh datasets" description="Automatically refresh dataset metadata when cache is cleared or data changes."
        checked={preferences.workspace.autoRefreshDatasets}
        onChange={() => updatePref("workspace", "autoRefreshDatasets", !preferences.workspace.autoRefreshDatasets)} />
      <ToggleFormRow label="Compact density" description="Use tighter spacing and smaller elements on data-heavy screens."
        checked={preferences.workspace.compactDensity}
        onChange={() => updatePref("workspace", "compactDensity", !preferences.workspace.compactDensity)} />
      <ToggleFormRow label="Reduce animations" description="Simplify transitions and reduce motion throughout the interface."
        checked={preferences.workspace.reduceAnimations}
        onChange={() => updatePref("workspace", "reduceAnimations", !preferences.workspace.reduceAnimations)} />
      <ActionFooter onSave={handleSavePrefs} saving={savingPrefs} disabled={!prefsDirty} saveLabel="Save preferences" />
    </motion.div>
  );

  const renderDataTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-2">
        <h3 className="text-lg font-semibold text-pearl">Data & Session</h3>
        <p className="text-sm text-granite/90 mt-1">Export your workspace or manage local browser cache.</p>
      </div>

      {/* Export & Reset row */}
      <FormRow label="Workspace data" description="Export or reset your stored workspace data.">
        <div className="flex flex-col sm:flex-row gap-3">
          <motion.button whileTap={{ scale: 0.97 }} onClick={handleExport}
            className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/[0.06] px-5 py-2.5 text-[15px] font-medium text-emerald-300 transition-all hover:bg-emerald-500/[0.12] hover:border-emerald-500/40">
            <Download className="h-[18px] w-[18px]" /> Export snapshot
          </motion.button>
          <motion.button whileTap={{ scale: 0.97 }} onClick={handleClearLocal} disabled={clearingLocalData}
            className="inline-flex items-center gap-2 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] px-5 py-2.5 text-[15px] font-medium text-amber-300 transition-all hover:bg-amber-500/[0.12] hover:border-amber-500/40 disabled:opacity-50 disabled:cursor-not-allowed">
            <RotateCcw className="h-[18px] w-[18px]" /> {clearingLocalData ? "Resetting\u2026" : "Reset cache"}
          </motion.button>
        </div>
      </FormRow>

      {/* Storage stats */}
      <FormRow label="Storage overview" description="Current dataset state in your workspace.">
        <div className="grid grid-cols-3 gap-3 max-w-sm">
          <div className="rounded-xl border border-white/[0.05] bg-noir/30 px-4 py-3 text-center">
            <p className="text-2xl font-bold text-pearl/90">{datasetStats.total}</p>
            <p className="text-sm text-granite mt-0.5">Total</p>
          </div>
          <div className="rounded-xl border border-white/[0.05] bg-noir/30 px-4 py-3 text-center">
            <p className="text-2xl font-bold text-emerald-400">{datasetStats.ready}</p>
            <p className="text-sm text-granite mt-0.5">Ready</p>
          </div>
          <div className="rounded-xl border border-white/[0.05] bg-noir/30 px-4 py-3 text-center">
            <p className="text-2xl font-bold text-amber-400">{datasetStats.total - datasetStats.ready}</p>
            <p className="text-sm text-granite mt-0.5">Pending</p>
          </div>
        </div>
      </FormRow>

      {/* Active session */}
      <FormRow label="Active session" description="Your current browser session." noBorder>
        <div className="rounded-xl border border-white/[0.05] bg-noir/30 p-4 max-w-md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-pearl/10 shrink-0">
              <Activity className="h-4.5 w-4.5 text-pearl/60" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-medium text-pearl/90 truncate">{user?.email || "unknown"}</p>
              <p className="text-sm text-granite">Active &middot; {getDisplayName(user)}</p>
            </div>
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-400 shrink-0" title="Active" />
          </div>
        </div>
        <div className="mt-4">
          <button onClick={logout}
            className="inline-flex items-center gap-2 rounded-xl border border-rose-500/25 bg-rose-500/[0.06] px-5 py-2.5 text-[15px] font-medium text-rose-300 transition-all hover:bg-rose-500/[0.12] hover:border-rose-500/40">
            <LogOut className="h-[18px] w-[18px]" /> Sign out
          </button>
        </div>
      </FormRow>
    </motion.div>
  );

  /* ── Belief Store handlers ── */
  const handleDeleteBelief = async (beliefId) => {
    setDeletingBeliefId(beliefId);
    try {
      await agenticAPI.deleteBelief(beliefId);
      setBeliefs((prev) => prev.filter((b) => b.id !== beliefId));
      setBeliefsCount((c) => Math.max(0, c - 1));
      toast.success("Belief removed — similar insights will appear again.");
    } catch {
      toast.error("Failed to remove belief.");
    } finally {
      setDeletingBeliefId(null);
    }
  };

  const handleClearAllBeliefs = async () => {
    setClearingBeliefs(true);
    try {
      await agenticAPI.clearBeliefs();
      setBeliefs([]);
      setBeliefsCount(0);
      toast.success("AI Memory cleared. Novelty filtering reset.");
    } catch {
      toast.error("Failed to clear AI Memory.");
    } finally {
      setClearingBeliefs(false);
    }
  };

  const SOURCE_LABELS = {
    user_confirmed: { label: "Confirmed", color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
    user_accepted: { label: "Useful", color: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
    user_dismissed: { label: "Already Knew", color: "text-amber-400 bg-amber-500/10 border-amber-500/20" },
    document_ingested: { label: "Document", color: "text-purple-400 bg-purple-500/10 border-purple-500/20" },
    auto_generated: { label: "Auto", color: "text-slate-400 bg-slate-500/10 border-slate-500/20" },
  };

  const renderAiMemoryTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      {/* Explainer */}
      <div className="mb-6 p-5 rounded-xl border border-white/[0.06] bg-white/[0.02]">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center shrink-0">
            <BrainCircuit className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h3 className="text-[15px] font-semibold text-pearl">Belief Store — Your AI Memory</h3>
            <p className="text-sm text-granite/90 leading-relaxed mt-1">
              When you mark insights as <span className="text-emerald-400 font-medium">"Useful"</span> or{" "}
              <span className="text-amber-400 font-medium">"Already Knew"</span>, they are stored here as embeddings.
              Future analyses use these beliefs to compute <span className="text-pearl font-medium">Semantic Surprisal</span> — 
              suppressing insights you've already seen. Removing a belief will allow similar insights to surface again.
            </p>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <FormRow label="Stored beliefs" description="Total knowledge entries the system has learned from your feedback.">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl font-mono font-bold text-pearl">{beliefsCount}</span>
            <span className="text-sm text-granite">entries</span>
          </div>
          {beliefsCount > 0 && (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleClearAllBeliefs}
              disabled={clearingBeliefs}
              className="inline-flex items-center gap-2 rounded-xl border border-rose-500/25 bg-rose-500/[0.06] px-4 py-2 text-[13px] font-medium text-rose-300 transition-all hover:bg-rose-500/[0.12] hover:border-rose-500/40 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RotateCcw className={cn("h-3.5 w-3.5", clearingBeliefs && "animate-spin")} />
              {clearingBeliefs ? "Clearing…" : "Reset All"}
            </motion.button>
          )}
        </div>
      </FormRow>

      {/* Belief List */}
      <FormRow label="Knowledge entries" description="Insights stored from your feedback sessions. Click the trash icon to forget an entry." noBorder>
        <div className="space-y-2 max-h-[420px] overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent pr-1">
          {loadingBeliefs ? (
            // Loading skeleton
            Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="animate-pulse flex items-start gap-3 p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                <div className="w-6 h-6 rounded-lg bg-white/[0.06] shrink-0 mt-0.5" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 bg-white/[0.06] rounded w-3/4" />
                  <div className="h-2.5 bg-white/[0.04] rounded w-1/2" />
                </div>
              </div>
            ))
          ) : beliefs.length === 0 ? (
            <div className="text-center py-10">
              <div className="w-14 h-14 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mx-auto mb-4">
                <BrainCircuit className="w-6 h-6 text-granite/60" />
              </div>
              <p className="text-[14px] text-granite font-medium">No beliefs stored yet</p>
              <p className="text-[12px] text-granite/60 mt-1 max-w-xs mx-auto">
                Start by rating insights on your dashboard or analysis pages. Your feedback will appear here.
              </p>
            </div>
          ) : (
            <AnimatePresence>
              {beliefs.map((belief, idx) => {
                const src = SOURCE_LABELS[belief.metadata?.source] || SOURCE_LABELS.auto_generated;
                const confidence = belief.confidence != null ? (belief.confidence * 100).toFixed(0) : null;
                const isDeleting = deletingBeliefId === belief.id;

                return (
                  <motion.div
                    key={belief.id || idx}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: isDeleting ? 0.4 : 1, y: 0 }}
                    exit={{ opacity: 0, x: -20, height: 0 }}
                    transition={{ delay: idx * 0.03 }}
                    className="flex items-start gap-3 p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:border-white/[0.08] transition-colors group"
                  >
                    {/* Source badge */}
                    <div className={cn("mt-0.5 px-2 py-0.5 rounded-md text-[9px] font-semibold uppercase tracking-wider border shrink-0", src.color)}>
                      {src.label}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] text-pearl/80 leading-relaxed line-clamp-2">
                        {belief.document || "—"}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5 text-[10px] text-granite/50">
                        {confidence != null && <span>Confidence: {confidence}%</span>}
                        {belief.metadata?.created_at && (
                          <span>{formatDate(belief.metadata.created_at)}</span>
                        )}
                        {belief.similarity != null && (
                          <span>Similarity: {(belief.similarity * 100).toFixed(0)}%</span>
                        )}
                      </div>
                    </div>

                    {/* Delete button */}
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      onClick={() => handleDeleteBelief(belief.id)}
                      disabled={isDeleting}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg border border-transparent hover:border-rose-500/20 hover:bg-rose-500/10 text-granite/50 hover:text-rose-400 disabled:opacity-30"
                      title="Remove this belief"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </motion.button>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          )}
        </div>
      </FormRow>
    </motion.div>
  );

  const TAB_RENDERERS = {
    account: renderAccountTab,
    security: renderSecurityTab,
    notifications: renderNotificationsTab,
    workspace: renderWorkspaceTab,
    data: renderDataTab,
    "ai-memory": renderAiMemoryTab,
  };

  /* ═══════════════════ RENDER ═══════════════════ */
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* ───── Gradient Banner ───── */}
      <div className="relative shrink-0">
        <div className="h-32 sm:h-40 w-full overflow-hidden"
          style={{
            background: "linear-gradient(135deg, #1a1040 0%, #3b1d6e 25%, #7c3aed 45%, #c084fc 60%, #f59e0b 80%, #ec4899 100%)",
          }}
        >
          {/* Subtle noise overlay */}
          <div className="absolute inset-0 bg-noir/20" />
        </div>

        {/* Avatar overlapping the banner */}
        <div className="absolute -bottom-10 left-6 sm:left-10">
          <div className="relative">
            <div className="flex h-20 w-20 sm:h-24 sm:w-24 items-center justify-center rounded-full bg-midnight border-4 border-noir text-2xl sm:text-3xl font-bold text-pearl shadow-xl">
              {getDisplayName(user).charAt(0).toUpperCase()}
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-pearl border-2 border-noir">
              <BadgeCheck className="h-3.5 w-3.5 text-noir" />
            </div>
          </div>
        </div>

        {/* Right side: name + email on banner */}
        <div className="absolute bottom-3 right-6 sm:right-10 text-right hidden sm:block">
          <p className="text-base font-medium text-white/90 drop-shadow-sm">{user?.email}</p>
        </div>
      </div>

      {/* ───── Profile Header Row (below banner) ───── */}
      <div className="shrink-0 px-6 sm:px-10 pt-14 sm:pt-14 pb-0 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-pearl">{getDisplayName(user)}&apos;s Settings</h1>
          <p className="text-sm sm:text-base text-granite mt-1">{user?.email} &middot; {datasetStats.ready}/{datasetStats.total} datasets ready</p>
        </div>
      </div>

      {/* ───── Horizontal Tab Bar ───── */}
      <div className="shrink-0 px-6 sm:px-10 mt-5">
        <div ref={tabsRef} className="flex gap-0 overflow-x-auto scrollbar-hide border-b border-white/[0.06]">
          {TAB_ITEMS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "relative flex items-center gap-2.5 whitespace-nowrap px-5 py-3.5 text-[15px] font-medium transition-colors shrink-0",
                  isActive
                    ? "text-pearl"
                    : "text-granite hover:text-pearl/70",
                )}>
                <tab.icon className="h-[18px] w-[18px]" />
                {tab.label}
                {/* Active underline */}
                {isActive && (
                  <motion.div layoutId="settings-tab-underline"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-pearl rounded-full"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ───── Scrollable Content ───── */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-6 sm:px-10 py-6 max-w-4xl">
          <AnimatePresence mode="wait">
            <motion.div key={activeTab} variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
              {TAB_RENDERERS[activeTab]?.()}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
