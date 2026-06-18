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
  Lock,
  FileSearch,
  CheckCircle,
  Loader2,
  CreditCard,
  Users,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "react-hot-toast";
import { useAuth } from "../../store/authStore";
import useThemeStore from "../../store/themeStore";
import useDatasetStore from "../../store/datasetStore";
import useChatStore from "../../store/chatStore";
import useChatHistoryStore from "../../store/chatHistoryStore";
import { cn } from "../../lib/utils";
import { useSearchParams } from "react-router-dom";
import { agenticAPI, privacyAPI, datasetAPI } from "../../services/api";

/* ─── Constants ─── */
const SETTINGS_PREFS_KEY = "signal-settings-preferences";

const ACCOUNT_TABS = [
  { id: "general", label: "Profile", icon: User },
  { id: "notifications", label: "Notifications", icon: BellRing },
  { id: "security", label: "Security & Privacy", icon: Shield },
];

const WORKSPACE_TABS = [
  { id: "workspace", label: "General", icon: Laptop },
  { id: "team", label: "Members", icon: Users },
  { id: "sources", label: "Data Sources", icon: Database },
  { id: "ai-preferences", label: "AI Preferences", icon: BrainCircuit },
  { id: "billing", label: "Billing & Plans", icon: CreditCard },
  { id: "advanced", label: "Advanced", icon: SlidersHorizontal },
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
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/50 px-3.5 text-[14px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none transition-all focus:border-[var(--accent-primary)] focus:bg-[var(--bg-elevated)] focus:ring-1 focus:ring-[var(--accent-primary)]";

const Toggle = ({ checked, onChange }) => (
  <button type="button" role="switch" aria-checked={checked} onClick={onChange}
    className={cn("relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors duration-200",
      checked ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]" : "border-[var(--border)] bg-[var(--bg-secondary)]")}>
    <span className={cn("pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200",
      checked ? "translate-x-[22px]" : "translate-x-[4px]")} />
  </button>
);

/* ─── Vertical form row (label top, content bottom) ─── */
const FormRow = ({ label, description, children, noBorder }) => (
  <div className={cn("py-5", !noBorder && "border-b border-[var(--border)]/50")}>
    <h4 className="text-[14px] font-medium text-[var(--text-primary)]">{label}</h4>
    {description && <p className="mt-1 text-[13px] text-[var(--text-secondary)] leading-relaxed">{description}</p>}
    <div className="mt-3.5">{children}</div>
  </div>
);

/* ─── Toggle Row in vertical layout ─── */
const ToggleFormRow = ({ label, description, checked, onChange, noBorder }) => (
  <div className={cn("flex items-center justify-between py-5", !noBorder && "border-b border-[var(--border)]/50")}>
    <div className="pr-8">
      <h4 className="text-[14px] font-medium text-[var(--text-primary)]">{label}</h4>
      {description && <p className="mt-1 text-[13px] text-[var(--text-secondary)] leading-relaxed">{description}</p>}
    </div>
    <div className="shrink-0">
      <Toggle checked={checked} onChange={onChange} />
    </div>
  </div>
);

/* ─── Action footer bar (Cancel + Save) ─── */
const ActionFooter = ({ onSave, onCancel, saving, disabled, saveLabel = "Save changes", saveClassName }) => (
  <div className="flex items-center justify-start gap-2.5 pt-5 border-t border-[var(--border)]/50 mt-4 max-w-md">
    <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.97 }} onClick={onSave} disabled={disabled}
      className={cn("inline-flex items-center gap-2 rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-[13px] font-medium text-white transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 h-9", saveClassName)}>
      <Save className="h-4 w-4" />
      {saving ? "Saving\u2026" : saveLabel}
    </motion.button>
    <motion.button
      whileTap={{ scale: 0.97 }}
      onClick={onCancel}
      className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition-all hover:bg-[var(--bg-active)] hover:text-[var(--text-primary)] h-9">
      Cancel
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTabState] = useState(() => {
    const initialTab = searchParams.get("tab");
    const allTabIds = [
      ...ACCOUNT_TABS.map((t) => t.id),
      ...WORKSPACE_TABS.map((t) => t.id),
    ];
    return allTabIds.includes(initialTab) ? initialTab : "general";
  });

  const setActiveTab = (tabId) => {
    setActiveTabState(tabId);
    setSearchParams({ tab: tabId }, { replace: true });
  };

  useEffect(() => {
    const currentTab = searchParams.get("tab");
    if (currentTab && currentTab !== activeTab) {
      const allTabIds = [
        ...ACCOUNT_TABS.map((t) => t.id),
        ...WORKSPACE_TABS.map((t) => t.id),
      ];
      if (allTabIds.includes(currentTab)) {
        setActiveTabState(currentTab);
      }
    }
  }, [searchParams, activeTab]);
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

  /* ── Privacy state ── */
  const [privacySettings, setPrivacySettings] = useState(null);
  const [privacyDatasets, setPrivacyDatasets] = useState([]);
  const [privacyAuditStats, setPrivacyAuditStats] = useState(null);
  const [loadingPrivacy, setLoadingPrivacy] = useState(false);
  const [savingPrivacy, setSavingPrivacy] = useState(false);
  const [scanningPii, setScanningPii] = useState(null);
  const [piiScanResults, setPiiScanResults] = useState({});

  const RETENTION_OPTIONS = [
    { value: 30, label: "30 days" },
    { value: 60, label: "60 days" },
    { value: 90, label: "90 days" },
    { value: 365, label: "1 year" },
    { value: -1, label: "Forever" },
  ];

  const [profileForm, setProfileForm] = useState({ username: getDisplayName(user), email: user?.email || "" });
  const [passwordForm, setPasswordForm] = useState({ currentPassword: "", newPassword: "", confirmPassword: "" });
  const [showPassword, setShowPassword] = useState({ current: false, next: false, confirm: false });
  const [preferences, setPreferences] = useState(() => readStoredPreferences(theme));

  useEffect(() => { setProfileForm({ username: getDisplayName(user), email: user?.email || "" }); }, [user]);

  /* ── Fetch beliefs when AI Preferences tab is active ── */
  useEffect(() => {
    if (activeTab !== "ai-preferences") return;
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

  /* ── Fetch privacy settings when Security & Privacy tab is active ── */
  useEffect(() => {
    if (activeTab !== "security") return;
    let cancelled = false;
    const loadPrivacyData = async () => {
      setLoadingPrivacy(true);
      try {
        const [settingsRes, datasetsRes, statsRes] = await Promise.all([
          privacyAPI.getGlobalSettings(),
          datasetAPI.getDatasets(),
          privacyAPI.getAuditStats(30),
        ]);
        if (!cancelled) {
          setPrivacySettings(settingsRes.data?.global_defaults || {});
          setPrivacyDatasets(datasetsRes.data?.datasets || []);
          setPrivacyAuditStats(statsRes.data || {});
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Failed to load privacy settings:", err);
        }
      } finally {
        if (!cancelled) setLoadingPrivacy(false);
      }
    };
    loadPrivacyData();
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

  /* ─── Handlers ─── */
  const handleSaveProfile = async () => {
    const username = profileForm.username.trim();
    if (username.length < 2) { toast.error("Username must be at least 2 characters."); return; }
    setSavingProfile(true);
    const r = await updateProfile({ username });
    setSavingProfile(false);
    if (!r.success) { toast.error(r.error || "Unable to update profile."); return; }
    toast.success("Profile updated.");
  };

  const handleResetProfile = () => {
    setProfileForm({ username: getDisplayName(user), email: user?.email || "" });
    toast.dismiss();
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

  const handleResetPassword = () => {
    setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
    toast.dismiss();
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

  const handleResetPrefs = () => {
    const d = readStoredPreferences(theme);
    setPreferences(d);
    setPrefsDirty(false);
    toast.dismiss();
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
    const a = Object.assign(document.createElement("a"), { href: url, download: `signal-workspace-${new Date().toISOString().slice(0, 10)}.json` });
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast.success("Workspace exported.");
  };

  const handleClearLocal = async () => {
    setClearingLocalData(true);
    clearAllConversations(); clearAllChats();
    setDatasets([]); setSelectedDataset(null);
    ["dataset-storage", "signal-chat-store", "chat-history-storage", SETTINGS_PREFS_KEY].forEach((k) => { localStorage.removeItem(k); sessionStorage.removeItem(k); });
    const d = buildDefaultPreferences(theme);
    setPreferences(d); persistPreferences(d); setPrefsDirty(false);
    await fetchDatasets(true);
    setClearingLocalData(false);
    toast.success("Local cache reset.");
  };

  /* ═══════════════════ TAB RENDERERS ═══════════════════ */

  const renderAccountTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-8">
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">Profile Settings</h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">Manage your basic account details and personal information.</p>
      </div>
      <FormRow label="Username" description="This is your display name across Signal.">
        <input value={profileForm.username} onChange={(e) => setProfileForm((p) => ({ ...p, username: e.target.value }))}
          className={cn(inputCls, "max-w-md")} placeholder="Enter your username" />
      </FormRow>
      <FormRow label="Email address" description="Your account email. Cannot be changed.">
        <input value={profileForm.email} disabled className={cn(inputCls, "max-w-md cursor-not-allowed opacity-50")} />
      </FormRow>
      <FormRow label="Member since" description="When your account was created.">
        <div className="text-[13px] text-[var(--text-primary)] font-mono py-1.5">
          {formatDate(user?.created_at)}
        </div>
      </FormRow>
      <FormRow label="Last login" description="Your most recent sign-in." noBorder>
        <div className="text-[13px] text-[var(--text-primary)] font-mono py-1.5">
          {formatDate(user?.last_login)}
        </div>
      </FormRow>
      <ActionFooter onSave={handleSaveProfile} onCancel={handleResetProfile} saving={savingProfile} saveLabel="Save profile" />
    </motion.div>
  );

  const renderSecurityTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-8">
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">Password</h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">Update your password to keep your account secure.</p>
      </div>
      {[
        { key: "currentPassword", label: "Current password", vis: "current", value: passwordForm.currentPassword, hint: null },
        { key: "newPassword", label: "New password", vis: "next", value: passwordForm.newPassword, hint: "Your new password must be at least 6 characters." },
        { key: "confirmPassword", label: "Confirm new password", vis: "confirm", value: passwordForm.confirmPassword, hint: null },
      ].map((f, i, arr) => (
        <FormRow key={f.key} label={f.label} description={f.hint} noBorder={i === arr.length - 1}>
          <div className="max-w-md relative">
            <input type={showPassword[f.vis] ? "text" : "password"} value={f.value}
              onChange={(e) => setPasswordForm((p) => ({ ...p, [f.key]: e.target.value }))}
              className={cn(inputCls, "pr-11")} placeholder={f.label} />
            <button type="button" onClick={() => setShowPassword((p) => ({ ...p, [f.vis]: !p[f.vis] }))}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1">
              {showPassword[f.vis] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </FormRow>
      ))}
      <ActionFooter onSave={handleChangePassword} onCancel={handleResetPassword} saving={changingPassword} saveLabel="Update password" />
    </motion.div>
  );

  const renderNotificationsTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-8">
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">Notification Preferences</h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">Choose what reaches your inbox and activity stream.</p>
      </div>
      <ToggleFormRow label="Product announcements" description="Release notes, feature updates, and major platform changes."
        checked={preferences.notifications.productAnnouncements}
        onChange={() => updatePref("notifications", "productAnnouncements", !preferences.notifications.productAnnouncements)} />
      <ToggleFormRow label="AI insight ready" description="Get notified when long-running analyses and AI pipelines finish."
        checked={preferences.notifications.aiInsightReady}
        onChange={() => updatePref("notifications", "aiInsightReady", !preferences.notifications.aiInsightReady)} />
      <ToggleFormRow label="Security alerts" description="Authentication warnings, suspicious activity, and session alerts."
        checked={preferences.notifications.securityAlerts}
        onChange={() => updatePref("notifications", "securityAlerts", !preferences.notifications.securityAlerts)}
        noBorder />
      <div className="pt-4">
        <ActionFooter onSave={handleSavePrefs} onCancel={handleResetPrefs} saving={savingPrefs} disabled={!prefsDirty} saveLabel="Save preferences" />
      </div>
    </motion.div>
  );

  const renderWorkspaceTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-8">
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">Workspace Appearance</h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">Configure how the application looks and behaves.</p>
      </div>
      <FormRow label="Color theme" description="Select your preferred color scheme for the interface.">
        <div className="grid grid-cols-3 gap-3 max-w-md">
          {[
            { id: "light", label: "Light", icon: Sun },
            { id: "dark", label: "Dark", icon: Moon },
            { id: "system", label: "System", icon: Laptop },
          ].map((t) => (
            <button key={t.id} onClick={() => handleTheme(t.id)}
              className={cn("flex flex-col items-center gap-1.5 rounded-lg border px-3 py-3 transition-all text-center cursor-pointer",
                preferences.workspace.theme === t.id
                  ? "border-[var(--text-primary)] bg-[var(--bg-active)] text-[var(--text-primary)] ring-[0.5px] ring-[var(--text-primary)]"
                  : "border-[var(--border)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-active)]/50 hover:text-[var(--text-primary)]")}>
              <t.icon className="h-4.5 w-4.5" />
              <span className="text-[13px] font-medium">{t.label}</span>
            </button>
          ))}
        </div>
      </FormRow>
      <ToggleFormRow label="Auto refresh datasets" description="Automatically refresh dataset metadata when cache is cleared or data changes."
        checked={preferences.workspace.autoRefreshDatasets}
        onChange={() => updatePref("workspace", "autoRefreshDatasets", !preferences.workspace.autoRefreshDatasets)} />
      <ToggleFormRow label="Compact density" description="Use tighter spacing and smaller elements on data-heavy screens."
        checked={preferences.workspace.compactDensity}
        onChange={() => updatePref("workspace", "compactDensity", !preferences.workspace.compactDensity)} />
      <ToggleFormRow label="Reduce animations" description="Simplify transitions and reduce motion throughout the interface."
        checked={preferences.workspace.reduceAnimations}
        onChange={() => updatePref("workspace", "reduceAnimations", !preferences.workspace.reduceAnimations)}
        noBorder />
      <div className="pt-4">
        <ActionFooter onSave={handleSavePrefs} onCancel={handleResetPrefs} saving={savingPrefs} disabled={!prefsDirty} saveLabel="Save preferences" />
      </div>
    </motion.div>
  );

  const renderDataTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-8">
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">Data Sources & Session</h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">Export your workspace data or manage your local browser session.</p>
      </div>

      {/* Export & Reset row */}
      <FormRow label="Workspace data" description="Export or reset your stored workspace data.">
        <div className="flex flex-col sm:flex-row gap-2.5">
          <motion.button whileTap={{ scale: 0.97 }} onClick={handleExport}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] transition-all hover:bg-[var(--bg-active)] h-9">
            <Download className="h-4 w-4" /> Export snapshot
          </motion.button>
          <motion.button whileTap={{ scale: 0.97 }} onClick={handleClearLocal} disabled={clearingLocalData}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-rose-500/25 bg-rose-500/10 px-4 py-2 text-[13px] font-medium text-rose-400 transition-all hover:bg-rose-500/20 hover:border-rose-500/40 disabled:opacity-50 disabled:cursor-not-allowed h-9">
            <RotateCcw className="h-4 w-4" /> {clearingLocalData ? "Resetting\u2026" : "Reset cache"}
          </motion.button>
        </div>
      </FormRow>

      {/* Storage stats */}
      <FormRow label="Storage overview" description="Current dataset state in your workspace.">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-[14px]">
          <div className="flex items-center gap-2">
            <span className="text-[var(--text-primary)] font-semibold font-mono text-base">{datasetStats.total}</span>
            <span className="text-[var(--text-secondary)] text-[13px]">datasets total</span>
          </div>
          <div className="hidden sm:block h-4 w-px bg-[var(--border)]/50" />
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-[var(--text-primary)] font-semibold font-mono text-base">{datasetStats.ready}</span>
            <span className="text-[var(--text-secondary)] text-[13px]">ready</span>
          </div>
          <div className="hidden sm:block h-4 w-px bg-[var(--border)]/50" />
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            <span className="text-[var(--text-primary)] font-semibold font-mono text-base">{datasetStats.total - datasetStats.ready}</span>
            <span className="text-[var(--text-secondary)] text-[13px]">pending</span>
          </div>
        </div>
      </FormRow>

      {/* Active session */}
      <FormRow label="Active session" description="Your current browser session." noBorder>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/40 p-4 max-w-md">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--bg-secondary)] shrink-0">
                <Activity className="h-4 w-4 text-[var(--text-secondary)]" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <p className="text-[14px] font-medium text-[var(--text-primary)] truncate">{user?.email || "unknown"}</p>
                  <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" title="Active" />
                </div>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">Active &middot; {getDisplayName(user)}</p>
              </div>
            </div>
            <button onClick={logout}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-1.5 text-[13px] font-medium text-[var(--text-primary)] transition-all hover:bg-[var(--bg-active)] h-9 shrink-0 cursor-pointer">
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          </div>
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

  /* ── Privacy handlers ── */
  const updatePrivacySetting = async (key, value) => {
    setSavingPrivacy(true);
    try {
      const res = await privacyAPI.updateGlobalSettings({ [key]: value });
      setPrivacySettings(res.data?.global_defaults || {});
      toast.success("Privacy setting updated.");
    } catch (err) {
      console.error("Failed to update privacy setting:", err);
      toast.error("Failed to update setting.");
    } finally {
      setSavingPrivacy(false);
    }
  };

  const handleScanPII = async (datasetId) => {
    setScanningPii(datasetId);
    try {
      const res = await privacyAPI.scanForPII(datasetId);
      setPiiScanResults((prev) => ({ ...prev, [datasetId]: res.data }));
      toast.success("PII scan complete.");
    } catch (err) {
      console.error("PII scan failed:", err);
      toast.error("PII scan failed.");
    } finally {
      setScanningPii(null);
    }
  };

  const handleRedactColumn = async (datasetId, columnName) => {
    try {
      await privacyAPI.managePrivateColumn(datasetId, "add", columnName);
      toast.success(`Column marked as private.`);
      handleScanPII(datasetId);
    } catch (err) {
      console.error("Failed to redact column:", err);
      toast.error("Failed to redact column.");
    }
  };

  const handleExportPrivacyData = () => {
    const exportData = {
      exported_at: new Date().toISOString(),
      privacy_settings: privacySettings,
      datasets: privacyDatasets,
      audit_stats: privacyAuditStats,
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: `signal-privacy-${new Date().toISOString().slice(0, 10)}.json` });
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast.success("Privacy data exported.");
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
    user_confirmed: { label: "Confirmed", color: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20" },
    user_accepted: { label: "Useful", color: "text-blue-500 bg-blue-500/10 border-blue-500/20" },
    user_dismissed: { label: "Already Knew", color: "text-amber-500 bg-amber-500/10 border-amber-500/20" },
    document_ingested: { label: "Document", color: "text-orange-500 bg-orange-500/10 border-orange-500/20" },
    auto_generated: { label: "Auto", color: "text-slate-500 bg-slate-500/10 border-slate-500/20" },
  };

  const renderAiMemoryTab = () => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-8">
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">AI Preferences</h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">Manage what the AI has learned from your feedback.</p>
      </div>

      {/* Explainer */}
      <div className="mb-8 p-5 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/40">
        <div className="flex items-start gap-4">
          <div className="w-9 h-9 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] flex items-center justify-center shrink-0">
            <BrainCircuit className="w-4.5 h-4.5 text-[var(--text-secondary)]" />
          </div>
          <div>
            <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">Belief Store — Your AI Memory</h3>
            <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed mt-1">
              When you mark insights as "Useful" or "Already Knew", they are stored here as embeddings.
              Future analyses use these beliefs to compute Semantic Surprisal —
              suppressing insights you've already seen. Removing a belief will allow similar insights to surface again.
            </p>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <FormRow label="Stored beliefs" description="Total knowledge entries the system has learned from your feedback.">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold font-mono text-[var(--text-primary)]">{beliefsCount}</span>
            <span className="text-[13px] text-[var(--text-secondary)]">entries</span>
          </div>
          {beliefsCount > 0 && (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleClearAllBeliefs}
              disabled={clearingBeliefs}
              className="inline-flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3.5 py-1.5 text-[13px] font-medium text-rose-500 transition-all hover:bg-rose-500/20 hover:border-rose-500/30 disabled:opacity-50 disabled:cursor-not-allowed h-9"
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
              <div key={i} className="animate-pulse flex items-start gap-3 p-3.5 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border)]">
                <div className="w-6 h-6 rounded-lg bg-[var(--bg-secondary)] shrink-0 mt-0.5" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 bg-[var(--bg-secondary)] rounded w-3/4" />
                  <div className="h-2.5 bg-[var(--bg-secondary)] rounded w-1/2" />
                </div>
              </div>
            ))
          ) : beliefs.length === 0 ? (
            <div className="text-center py-10">
              <div className="w-12 h-12 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border)] flex items-center justify-center mx-auto mb-4">
                <BrainCircuit className="w-5 h-5 text-[var(--text-muted)]" />
              </div>
              <p className="text-[13px] text-[var(--text-secondary)] font-medium">No beliefs stored yet</p>
              <p className="text-[12px] text-[var(--text-muted)] mt-1 max-w-xs mx-auto">
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
                    className="flex items-start gap-3 p-3.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] hover:border-[var(--text-muted)] transition-colors group"
                  >
                    {/* Source badge */}
                    <div className={cn("mt-0.5 px-2 py-0.5 rounded-md text-[9px] font-semibold uppercase tracking-wider border shrink-0", src.color)}>
                      {src.label}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] text-[var(--text-primary)]/80 leading-relaxed line-clamp-2">
                        {belief.document || "—"}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5 text-[10px] text-[var(--text-muted)]">
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
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg border border-transparent hover:border-rose-500/20 hover:bg-rose-500/10 text-[var(--text-muted)] hover:text-rose-400 disabled:opacity-30"
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

  /* ── Privacy Tab ── */
  const renderPrivacyTab = () => {
    if (loadingPrivacy) {
      return (
        <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit" className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-[var(--text-primary)] animate-spin" />
        </motion.div>
      );
    }

    return (
      <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
        <div className="mb-8">
          <h3 className="text-xl font-semibold text-[var(--text-primary)]">Data Privacy</h3>
          <p className="text-[15px] text-[var(--text-secondary)] mt-1">Control how your data is processed by AI models and manage PII.</p>
        </div>

        {/* Explainer */}
        <div className="mb-8 p-5 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/40">
          <div className="flex items-start gap-4">
            <div className="w-9 h-9 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] flex items-center justify-center shrink-0">
              <Shield className="w-4.5 h-4.5 text-[var(--text-secondary)]" />
            </div>
            <div>
              <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">Privacy & Security</h3>
              <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed mt-1">
                Sensitive information like emails, phone numbers, and other PII can be automatically detected and redacted for your protection before data is sent to AI models.
              </p>
            </div>
          </div>
        </div>

        {/* Privacy Stats */}
        <FormRow label="Privacy overview" description="Current privacy status across your workspace.">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-[14px]">
            <div className="flex items-center gap-2">
              <span className="text-[var(--text-primary)] font-semibold font-mono text-base">{privacyDatasets.length}</span>
              <span className="text-[var(--text-secondary)] text-[13px]">datasets total</span>
            </div>
            <div className="hidden sm:block h-4 w-px bg-[var(--border)]/50" />
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span className="text-[var(--text-primary)] font-semibold font-mono text-base">{privacyAuditStats?.pii_scan || 0}</span>
              <span className="text-[var(--text-secondary)] text-[13px]">PII scans</span>
            </div>
            <div className="hidden sm:block h-4 w-px bg-[var(--border)]/50" />
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-orange-500" />
              <span className="text-[var(--text-primary)] font-semibold font-mono text-base">{privacyAuditStats?.data_accessed || 0}</span>
              <span className="text-[var(--text-secondary)] text-[13px]">access events</span>
            </div>
          </div>
        </FormRow>

        {/* AI Data Processing */}
        <div className="mt-8 mb-2">
          <h3 className="text-lg font-medium text-[var(--text-primary)]">AI Data Processing</h3>
          <p className="text-sm text-[var(--text-secondary)] mt-1">Configure how data is shared with AI models.</p>
        </div>

        <ToggleFormRow
          label="Auto-detect PII"
          description="Automatically scan datasets for sensitive information like emails, phone numbers, etc."
          checked={privacySettings?.pii_auto_detect ?? true}
          onChange={() => updatePrivacySetting("pii_auto_detect", !(privacySettings?.pii_auto_detect ?? true))}
        />
        <ToggleFormRow
          label="Auto-redact PII"
          description="Automatically redact sensitive columns before sending to AI models."
          checked={privacySettings?.pii_auto_redact ?? true}
          onChange={() => updatePrivacySetting("pii_auto_redact", !(privacySettings?.pii_auto_redact ?? true))}
        />
        <ToggleFormRow
          label="Share column names"
          description="Include column names when processing data (required for analysis)."
          checked={privacySettings?.share_column_names ?? true}
          onChange={() => updatePrivacySetting("share_column_names", !(privacySettings?.share_column_names ?? true))}
        />
        <ToggleFormRow
          label="Share sample rows"
          description="Include sample data rows for context (helps AI understand your data)."
          checked={privacySettings?.share_sample_rows ?? true}
          onChange={() => updatePrivacySetting("share_sample_rows", !(privacySettings?.share_sample_rows ?? true))}
        />

        {/* Data Retention */}
        <div className="mt-8 mb-2">
          <h3 className="text-lg font-medium text-[var(--text-primary)]">Data Retention</h3>
          <p className="text-sm text-[var(--text-secondary)] mt-1">Manage how long your data is stored.</p>
        </div>

        <FormRow label="Auto-delete after" description="Automatically delete datasets after this period.">
          <select
            value={privacySettings?.data_retention_days ?? 90}
            onChange={(e) => updatePrivacySetting("data_retention_days", parseInt(e.target.value))}
            className={cn(inputCls, "max-w-xs")}
          >
            {RETENTION_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </FormRow>

        <ToggleFormRow
          label="Retention warnings"
          description="Receive an email notification 7 days before datasets are automatically deleted."
          checked={privacySettings?.send_retention_warnings ?? true}
          onChange={() => updatePrivacySetting("send_retention_warnings", !(privacySettings?.send_retention_warnings ?? true))}
        />

        {/* Dataset Privacy */}
        <div className="mt-8 mb-2">
          <h3 className="text-lg font-medium text-[var(--text-primary)]">Dataset Privacy</h3>
          <p className="text-sm text-[var(--text-secondary)] mt-1">Scan datasets for PII and configure per-dataset settings.</p>
        </div>

        {privacyDatasets.length === 0 ? (
          <FormRow label="No datasets" description="Upload a dataset to configure privacy settings." noBorder>
            <p className="text-[14px] text-[var(--text-secondary)]">No datasets found.</p>
          </FormRow>
        ) : (
          <div className="space-y-4 mb-6 pt-4">
            {privacyDatasets.map((dataset) => {
              const dsId = dataset.id || dataset._id;
              const scanResult = piiScanResults[dsId];
              const isScanning = scanningPii === dsId;

              return (
                <div key={dsId} className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/40 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[14px] font-medium text-[var(--text-primary)]">{dataset.name || "Unnamed Dataset"}</p>
                      <p className="text-[12px] text-[var(--text-secondary)] mt-1">
                        {dataset.row_count ? `${dataset.row_count.toLocaleString()} rows` : ""} · {dataset.column_count ? `${dataset.column_count} columns` : ""}
                      </p>
                    </div>
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => handleScanPII(dsId)}
                      disabled={isScanning}
                      className="inline-flex items-center gap-2 rounded-lg border border-orange-500/20 bg-orange-500/10 px-3.5 py-1.5 text-[13px] font-medium text-orange-500 transition-all hover:bg-orange-500/20 hover:border-orange-500/30 disabled:opacity-50 h-9"
                    >
                      {isScanning ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileSearch className="w-3.5 h-3.5" />
                      )}
                      {isScanning ? "Scanning…" : "Scan PII"}
                    </motion.button>
                  </div>

                  {/* PII Scan Results */}
                  {scanResult && (
                    <div className="mt-4 pt-4 border-t border-[var(--border)]">
                      <p className="text-[13px] text-[var(--text-secondary)] mb-3">
                        Found {scanResult.columns_with_pii?.length || 0} columns with potential PII
                      </p>
                      {scanResult.columns_with_pii?.length > 0 ? (
                        <div className="space-y-2">
                          {scanResult.columns_with_pii.slice(0, 5).map((col) => (
                            <div key={col.column_name} className="flex items-center justify-between py-2 px-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                              <div className="flex items-center gap-3">
                                <span className="text-[14px] text-[var(--text-primary)] font-medium">{col.column_name}</span>
                                <span className="text-[11px] px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-500 font-semibold">{col.pii_type}</span>
                                <span className="text-[12px] text-[var(--text-secondary)]">{Math.round(col.confidence * 100)}%</span>
                              </div>
                              <button
                                onClick={() => handleRedactColumn(dsId, col.column_name)}
                                className="text-[12px] px-3 py-1.5 rounded-lg border border-amber-500/20 bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 transition-colors font-medium"
                              >
                                Redact
                              </button>
                            </div>
                          ))}
                          {scanResult.columns_with_pii.length > 5 && (
                            <p className="text-[13px] text-[var(--text-secondary)] text-center pt-2">+{scanResult.columns_with_pii.length - 5} more</p>
                          )}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-emerald-500 text-[14px] font-medium bg-emerald-500/10 px-3 py-2 rounded-lg w-fit">
                          <CheckCircle className="w-4 h-4" />
                          <span>No PII detected</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Warning notice */}
        <div className="mb-6 p-4 rounded-lg border border-[var(--border)] border-l-2 border-l-amber-500/80 bg-[var(--bg-elevated)]/40 pl-4 pr-3 py-3.5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
            <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed">
              Data is processed by AI models through OpenRouter. Column names and sample data may be shared
              for analysis purposes. Configure your privacy settings above to control what is shared.
            </p>
          </div>
        </div>

        {/* Export Button */}
        <FormRow label="Export privacy data" description="Download your privacy settings and audit logs for compliance." noBorder>
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleExportPrivacyData}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] transition-all hover:bg-[var(--bg-active)] h-9"
          >
            <Download className="w-4 h-4" />
            Export Privacy Data
          </motion.button>
        </FormRow>
      </motion.div>
    );
  };

  const PlaceholderTab = ({ title, desc }) => (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      <div className="mb-8">
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">{title}</h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">{desc}</p>
      </div>
      <div className="py-12 text-center border border-dashed border-[var(--border)] rounded-lg bg-[var(--bg-secondary)]">
        <p className="text-[14px] font-medium text-[var(--text-primary)]">Coming Soon</p>
        <p className="text-[13px] text-[var(--text-secondary)] mt-1">This section is currently under construction.</p>
      </div>
    </motion.div>
  );

  const renderCombinedSecurityTab = () => (
    <div className="space-y-12">
      {renderSecurityTab()}
      <div className="pt-8 border-t border-[var(--border)]">
        {renderPrivacyTab()}
      </div>
    </div>
  );

  const TAB_RENDERERS = {
    general: renderAccountTab,
    workspace: renderWorkspaceTab,
    sources: renderDataTab,
    "ai-preferences": renderAiMemoryTab,
    notifications: renderNotificationsTab,
    security: renderCombinedSecurityTab,
    billing: () => <PlaceholderTab title="Billing" desc="Manage your subscription and billing details." />,
    team: () => <PlaceholderTab title="Team" desc="Manage your team members and roles." />,
    advanced: () => <PlaceholderTab title="Advanced Settings" desc="Configure advanced workspace settings." />,
  };

  /* ═══════════════════ RENDER ═══════════════════ */
  const isAccountTab = ACCOUNT_TABS.some((tab) => tab.id === activeTab);
  const headerTitle = isAccountTab ? "Account Settings" : "Workspace Settings";
  const headerSubtitle = isAccountTab
    ? "Manage your personal profile, credentials, security, and notification alerts."
    : "Manage workspace details, data sources, members, and AI configurations.";

  return (
    <div className="h-full flex bg-[var(--bg-primary)] overflow-hidden">
      {/* Left Sidebar Navigation */}
      <div className="w-[240px] shrink-0 border-r border-[var(--border)] bg-[var(--bg-elevated)]/20 overflow-y-auto py-7 px-4.5 hidden md:block">
        <nav className="flex flex-col gap-6">
          {/* Account Settings Section */}
          <div className="flex flex-col gap-0.5">
            <div className="px-3 mb-1.5 text-[10px] font-bold text-[var(--text-secondary)]/50 uppercase tracking-[0.08em]">
              Account Settings
            </div>
            {ACCOUNT_TABS.map((tab) => {
              const isActive = activeTab === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center w-full px-3 py-2 text-[13px] font-medium rounded-lg transition-all text-left gap-2.5",
                    isActive
                      ? "bg-[var(--bg-active)] text-[var(--text-primary)] shadow-sm"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]/40 hover:text-[var(--text-primary)]"
                  )}
                >
                  <Icon className={cn("w-4 h-4 shrink-0 transition-colors", isActive ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]/70")} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Workspace Settings Section */}
          <div className="flex flex-col gap-0.5">
            <div className="px-3 mb-1.5 text-[10px] font-bold text-[var(--text-secondary)]/50 uppercase tracking-[0.08em]">
              Workspace Settings
            </div>
            {WORKSPACE_TABS.map((tab) => {
              const isActive = activeTab === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center w-full px-3 py-2 text-[13px] font-medium rounded-lg transition-all text-left gap-2.5",
                    isActive
                      ? "bg-[var(--bg-active)] text-[var(--text-primary)] shadow-sm"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]/40 hover:text-[var(--text-primary)]"
                  )}
                >
                  <Icon className={cn("w-4 h-4 shrink-0 transition-colors", isActive ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]/70")} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </nav>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto bg-[var(--bg-primary)]">
        {/* Mobile Tab Select - Optional fallback for small screens */}
        <div className="md:hidden px-6 py-4 border-b border-[var(--border)]">
          <select
            value={activeTab}
            onChange={(e) => setActiveTab(e.target.value)}
            className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-3 text-[14px] text-[var(--text-primary)] outline-none"
          >
            <optgroup label="Account Settings">
              {ACCOUNT_TABS.map(tab => <option key={tab.id} value={tab.id}>{tab.label}</option>)}
            </optgroup>
            <optgroup label="Workspace Settings">
              {WORKSPACE_TABS.map(tab => <option key={tab.id} value={tab.id}>{tab.label}</option>)}
            </optgroup>
          </select>
        </div>

        <div className="px-6 py-10 sm:px-12 md:px-16 lg:px-20">
          <div className="max-w-[800px] mx-auto pb-24">
            {/* Settings Page Header inside Main Content */}
            <div className="mb-8 pb-6 border-b border-[var(--border)]/50">
              <h1 className="text-2xl font-semibold text-[var(--text-primary)] tracking-tight">{headerTitle}</h1>
              <p className="mt-1.5 text-[14px] text-[var(--text-secondary)]">
                {headerSubtitle}
              </p>
            </div>

            <AnimatePresence mode="wait">
              <motion.div key={activeTab} variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
                {TAB_RENDERERS[activeTab]?.()}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
