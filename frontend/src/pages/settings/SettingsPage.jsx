import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BellRing,
  CheckCircle2,
  Database,
  Download,
  Eye,
  EyeOff,
  KeyRound,
  Laptop,
  LogOut,
  Mail,
  MonitorCog,
  Moon,
  Palette,
  RefreshCcw,
  Save,
  ShieldCheck,
  Sun,
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

const SETTINGS_PREFS_KEY = "datasage-settings-preferences";

const MotionSection = motion.section;
const MotionDiv = motion.div;
const MotionButton = motion.button;

const TAB_ITEMS = [
  { id: "account", label: "Account", icon: UserCog },
  { id: "security", label: "Security", icon: ShieldCheck },
  { id: "notifications", label: "Notifications", icon: BellRing },
  { id: "workspace", label: "Workspace", icon: Palette },
  { id: "data", label: "Data & Session", icon: Database },
];

const buildDefaultPreferences = (theme = "dark") => ({
  notifications: {
    productAnnouncements: true,
    aiInsightReady: true,
    securityAlerts: true,
  },
  workspace: {
    theme,
    language: "en",
    autoRefreshDatasets: true,
    compactDensity: false,
    reduceAnimations: false,
  },
});

const normalizePreferences = (raw, fallbackTheme = "dark") => {
  const defaults = buildDefaultPreferences(fallbackTheme);
  if (!raw || typeof raw !== "object") return defaults;
  return {
    notifications: {
      ...defaults.notifications,
      ...(raw.notifications || {}),
    },
    workspace: {
      ...defaults.workspace,
      ...(raw.workspace || {}),
    },
  };
};

const readStoredPreferences = (fallbackTheme = "dark") => {
  if (typeof window === "undefined") {
    return buildDefaultPreferences(fallbackTheme);
  }
  try {
    const raw = window.localStorage.getItem(SETTINGS_PREFS_KEY);
    if (!raw) return buildDefaultPreferences(fallbackTheme);
    return normalizePreferences(JSON.parse(raw), fallbackTheme);
  } catch (error) {
    console.warn("Failed to read settings preferences:", error);
    return buildDefaultPreferences(fallbackTheme);
  }
};

const persistPreferences = (preferences) => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SETTINGS_PREFS_KEY, JSON.stringify(preferences));
};

const formatDate = (value) => {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const getDisplayName = (user) => user?.username || user?.full_name || "User";

const ToggleRow = ({ title, description, checked, onChange }) => (
  <div className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-black/25 px-4 py-3">
    <div className="min-w-0">
      <p className="text-sm font-medium text-slate-100">{title}</p>
      <p className="text-xs text-slate-400">{description}</p>
    </div>
    <button
      type="button"
      onClick={onChange}
      className={cn(
        "relative inline-flex h-6 w-11 items-center rounded-full border transition-colors",
        checked
          ? "border-[#cad2fd]/40 bg-[#cad2fd]"
          : "border-slate-500/30 bg-slate-700/70"
      )}
      aria-pressed={checked}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 transform rounded-full bg-white transition-transform",
          checked ? "translate-x-5" : "translate-x-0.5"
        )}
      />
    </button>
  </div>
);

const SettingsPage = () => {
  const { user, updateProfile, changePassword, logout } = useAuth();
  const theme = useThemeStore((state) => state.theme);
  const resolvedTheme = useThemeStore((state) => state.resolvedTheme);
  const setTheme = useThemeStore((state) => state.setTheme);

  const datasets = useDatasetStore((state) => state.datasets);
  const fetchDatasets = useDatasetStore((state) => state.fetchDatasets);
  const setDatasets = useDatasetStore((state) => state.setDatasets);
  const setSelectedDataset = useDatasetStore((state) => state.setSelectedDataset);

  const clearAllConversations = useChatStore(
    (state) => state.clearAllConversations
  );
  const clearAllChats = useChatHistoryStore((state) => state.clearAllChats);

  const [activeTab, setActiveTab] = useState("account");
  const [savingProfile, setSavingProfile] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [clearingLocalData, setClearingLocalData] = useState(false);
  const [prefsDirty, setPrefsDirty] = useState(false);

  const [profileForm, setProfileForm] = useState({
    username: getDisplayName(user),
    email: user?.email || "",
  });

  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });

  const [showPassword, setShowPassword] = useState({
    current: false,
    next: false,
    confirm: false,
  });

  const [preferences, setPreferences] = useState(() =>
    readStoredPreferences(theme)
  );

  useEffect(() => {
    setProfileForm({
      username: getDisplayName(user),
      email: user?.email || "",
    });
  }, [user]);

  useEffect(() => {
    setPreferences((previous) => {
      if (previous.workspace.theme === theme) return previous;
      return {
        ...previous,
        workspace: {
          ...previous.workspace,
          theme,
        },
      };
    });
  }, [theme]);

  const datasetStats = useMemo(() => {
    const total = datasets.length;
    const ready = datasets.filter((dataset) => {
      const status = (dataset?.status || "").toLowerCase();
      return dataset?.is_processed || status === "completed";
    }).length;
    return { total, ready };
  }, [datasets]);

  const handleSaveProfile = async () => {
    const username = profileForm.username.trim();
    if (username.length < 2) {
      toast.error("Username must be at least 2 characters.");
      return;
    }

    setSavingProfile(true);
    const result = await updateProfile({ username });
    setSavingProfile(false);

    if (!result.success) {
      toast.error(result.error || "Unable to update profile.");
      return;
    }
    toast.success("Profile updated.");
  };

  const handleChangePassword = async () => {
    const { currentPassword, newPassword, confirmPassword } = passwordForm;
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast.error("Fill in all password fields.");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("New password must be at least 6 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error("New password and confirmation do not match.");
      return;
    }
    if (newPassword === currentPassword) {
      toast.error("New password must be different from current password.");
      return;
    }

    setChangingPassword(true);
    const result = await changePassword(currentPassword, newPassword);
    setChangingPassword(false);

    if (!result.success) {
      toast.error(result.error || "Failed to change password.");
      return;
    }

    setPasswordForm({
      currentPassword: "",
      newPassword: "",
      confirmPassword: "",
    });
    toast.success("Password changed successfully.");
  };

  const updatePreference = (section, key, value) => {
    setPreferences((previous) => ({
      ...previous,
      [section]: {
        ...previous[section],
        [key]: value,
      },
    }));
    setPrefsDirty(true);
  };

  const handleThemeSelection = (nextTheme) => {
    updatePreference("workspace", "theme", nextTheme);
    setTheme(nextTheme);
  };

  const handleSavePreferences = async () => {
    setSavingPrefs(true);
    persistPreferences(preferences);
    await new Promise((resolve) => setTimeout(resolve, 220));
    setSavingPrefs(false);
    setPrefsDirty(false);
    toast.success("Preferences saved.");
  };

  const handleExportWorkspace = () => {
    const snapshot = {
      exported_at: new Date().toISOString(),
      account: {
        id: user?.id,
        username: getDisplayName(user),
        email: user?.email,
        created_at: user?.created_at,
        last_login: user?.last_login,
      },
      preferences,
      datasets: datasets.map((dataset) => ({
        id: dataset?.id || dataset?._id,
        name: dataset?.name || dataset?.filename || "Untitled Dataset",
        row_count: dataset?.row_count || 0,
        column_count: dataset?.column_count || 0,
        status: dataset?.status || "unknown",
        created_at: dataset?.created_at || dataset?.uploaded_at || null,
      })),
    };

    const blob = new Blob([JSON.stringify(snapshot, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `datasage-workspace-${new Date()
      .toISOString()
      .slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);

    toast.success("Workspace snapshot exported.");
  };

  const handleClearLocalData = async () => {
    setClearingLocalData(true);
    clearAllConversations();
    clearAllChats();
    setDatasets([]);
    setSelectedDataset(null);

    localStorage.removeItem("dataset-storage");
    localStorage.removeItem("datasage-chat-store");
    localStorage.removeItem("chat-history-storage");
    localStorage.removeItem(SETTINGS_PREFS_KEY);

    sessionStorage.removeItem("dataset-storage");
    sessionStorage.removeItem("datasage-chat-store");
    sessionStorage.removeItem("chat-history-storage");

    const defaults = buildDefaultPreferences(theme);
    setPreferences(defaults);
    persistPreferences(defaults);
    setPrefsDirty(false);

    await fetchDatasets(true);
    setClearingLocalData(false);
    toast.success("Local cache reset and datasets reloaded.");
  };

  const sectionShell =
    "rounded-2xl border border-white/10 bg-[#080d15]/88 p-5 shadow-[0_18px_50px_-36px_rgba(0,0,0,0.95)]";

  const renderAccountTab = () => (
    <div className="space-y-4">
      <div className={sectionShell}>
        <h3 className="text-lg font-semibold text-white">Account Profile</h3>
        <p className="mt-1 text-sm text-slate-400">
          Keep your account identity up to date.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="space-y-1.5">
            <span className="text-xs uppercase tracking-wider text-slate-500">
              Username
            </span>
            <input
              value={profileForm.username}
              onChange={(event) =>
                setProfileForm((previous) => ({
                  ...previous,
                  username: event.target.value,
                }))
              }
              className="h-11 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-sm text-slate-100 outline-none focus:border-[#cad2fd]/50 focus:ring-2 focus:ring-[#cad2fd]/20"
            />
          </label>
          <label className="space-y-1.5">
            <span className="text-xs uppercase tracking-wider text-slate-500">
              Email
            </span>
            <input
              value={profileForm.email}
              disabled
              className="h-11 w-full cursor-not-allowed rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-500"
            />
          </label>
        </div>
        <div className="mt-5">
          <MotionButton
            whileTap={{ scale: 0.98 }}
            onClick={handleSaveProfile}
            disabled={savingProfile}
            className="inline-flex items-center gap-2 rounded-xl bg-[#cad2fd] px-4 py-2.5 text-sm font-semibold text-[#020203] transition hover:bg-[#d6dcff] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Save className="h-4 w-4" />
            {savingProfile ? "Saving..." : "Save Profile"}
          </MotionButton>
        </div>
      </div>

      <div className={sectionShell}>
        <h4 className="text-sm font-semibold text-slate-200">Account Metadata</h4>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-3">
            <p className="text-[11px] uppercase tracking-wider text-slate-500">
              Member Since
            </p>
            <p className="mt-1 text-sm text-slate-100">{formatDate(user?.created_at)}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-3">
            <p className="text-[11px] uppercase tracking-wider text-slate-500">
              Last Login
            </p>
            <p className="mt-1 text-sm text-slate-100">{formatDate(user?.last_login)}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-3">
            <p className="text-[11px] uppercase tracking-wider text-slate-500">
              User ID
            </p>
            <p className="mt-1 truncate text-sm text-slate-100">{user?.id || "Unknown"}</p>
          </div>
        </div>
      </div>
    </div>
  );

  const passwordInputClass =
    "h-11 w-full rounded-xl border border-white/10 bg-black/30 px-3 pr-10 text-sm text-slate-100 outline-none focus:border-[#cad2fd]/50 focus:ring-2 focus:ring-[#cad2fd]/20";

  const renderSecurityTab = () => (
    <div className={sectionShell}>
      <h3 className="text-lg font-semibold text-white">Password & Security</h3>
      <p className="mt-1 text-sm text-slate-400">
        Protect account access with a strong password.
      </p>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {[
          {
            key: "currentPassword",
            label: "Current Password",
            visibleKey: "current",
            value: passwordForm.currentPassword,
          },
          {
            key: "newPassword",
            label: "New Password",
            visibleKey: "next",
            value: passwordForm.newPassword,
          },
          {
            key: "confirmPassword",
            label: "Confirm Password",
            visibleKey: "confirm",
            value: passwordForm.confirmPassword,
          },
        ].map((field) => (
          <label key={field.key} className="space-y-1.5 md:col-span-2">
            <span className="text-xs uppercase tracking-wider text-slate-500">
              {field.label}
            </span>
            <div className="relative">
              <input
                type={showPassword[field.visibleKey] ? "text" : "password"}
                value={field.value}
                onChange={(event) =>
                  setPasswordForm((previous) => ({
                    ...previous,
                    [field.key]: event.target.value,
                  }))
                }
                className={passwordInputClass}
              />
              <button
                type="button"
                onClick={() =>
                  setShowPassword((previous) => ({
                    ...previous,
                    [field.visibleKey]: !previous[field.visibleKey],
                  }))
                }
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-200"
              >
                {showPassword[field.visibleKey] ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </label>
        ))}
      </div>

      <div className="mt-5">
        <MotionButton
          whileTap={{ scale: 0.98 }}
          onClick={handleChangePassword}
          disabled={changingPassword}
          className="inline-flex items-center gap-2 rounded-xl bg-[#c7bc92] px-4 py-2.5 text-sm font-semibold text-[#020203] transition hover:bg-[#d4c9a2] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <KeyRound className="h-4 w-4" />
          {changingPassword ? "Updating..." : "Update Password"}
        </MotionButton>
      </div>
    </div>
  );

  const renderNotificationsTab = () => (
    <div className="space-y-4">
      <div className={sectionShell}>
        <h3 className="text-lg font-semibold text-white">Notification Channels</h3>
        <p className="mt-1 text-sm text-slate-400">
          Choose what reaches your inbox and activity stream.
        </p>
        <div className="mt-4 space-y-3">
          <ToggleRow
            title="Product Announcements"
            description="Release notes and major platform updates."
            checked={preferences.notifications.productAnnouncements}
            onChange={() =>
              updatePreference(
                "notifications",
                "productAnnouncements",
                !preferences.notifications.productAnnouncements
              )
            }
          />
          <ToggleRow
            title="AI Insight Ready"
            description="Alerts when long-running analyses finish."
            checked={preferences.notifications.aiInsightReady}
            onChange={() =>
              updatePreference(
                "notifications",
                "aiInsightReady",
                !preferences.notifications.aiInsightReady
              )
            }
          />
          <ToggleRow
            title="Security Alerts"
            description="Suspicious activity and authentication alerts."
            checked={preferences.notifications.securityAlerts}
            onChange={() =>
              updatePreference(
                "notifications",
                "securityAlerts",
                !preferences.notifications.securityAlerts
              )
            }
          />
        </div>
      </div>
      <div className={sectionShell}>
        <button
          onClick={handleSavePreferences}
          disabled={!prefsDirty || savingPrefs}
          className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/8 px-4 py-2.5 text-sm font-medium text-slate-100 transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Save className="h-4 w-4" />
          {savingPrefs ? "Saving..." : "Save Notification Preferences"}
        </button>
      </div>
    </div>
  );

  const renderWorkspaceTab = () => (
    <div className="space-y-4">
      <div className={sectionShell}>
        <h3 className="text-lg font-semibold text-white">Workspace Preferences</h3>
        <p className="mt-1 text-sm text-slate-400">
          Configure visual and behavioral defaults.
        </p>

        <div className="mt-4">
          <p className="mb-2 text-xs uppercase tracking-wider text-slate-500">
            Theme
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            {[
              { id: "light", label: "Light", icon: Sun },
              { id: "dark", label: "Dark", icon: Moon },
              { id: "system", label: "System", icon: Laptop },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => handleThemeSelection(item.id)}
                className={cn(
                  "flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition",
                  preferences.workspace.theme === item.id
                    ? "border-[#cad2fd]/40 bg-[#cad2fd]/20 text-[#eef1ff]"
                    : "border-white/10 bg-black/20 text-slate-300 hover:bg-black/30"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Active theme: {preferences.workspace.theme} ({resolvedTheme} rendered)
          </p>
        </div>

        <div className="mt-4 space-y-3">
          <ToggleRow
            title="Auto Refresh Datasets"
            description="Refresh dataset metadata after cache resets."
            checked={preferences.workspace.autoRefreshDatasets}
            onChange={() =>
              updatePreference(
                "workspace",
                "autoRefreshDatasets",
                !preferences.workspace.autoRefreshDatasets
              )
            }
          />
          <ToggleRow
            title="Compact Density"
            description="Tighter spacing in data-heavy screens."
            checked={preferences.workspace.compactDensity}
            onChange={() =>
              updatePreference(
                "workspace",
                "compactDensity",
                !preferences.workspace.compactDensity
              )
            }
          />
          <ToggleRow
            title="Reduce Animations"
            description="Simplify motion for less visual noise."
            checked={preferences.workspace.reduceAnimations}
            onChange={() =>
              updatePreference(
                "workspace",
                "reduceAnimations",
                !preferences.workspace.reduceAnimations
              )
            }
          />
        </div>
      </div>

      <div className={sectionShell}>
        <button
          onClick={handleSavePreferences}
          disabled={!prefsDirty || savingPrefs}
          className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/8 px-4 py-2.5 text-sm font-medium text-slate-100 transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Save className="h-4 w-4" />
          {savingPrefs ? "Saving..." : "Save Workspace Preferences"}
        </button>
      </div>
    </div>
  );

  const renderDataTab = () => (
    <div className="space-y-4">
      <div className={sectionShell}>
        <h3 className="text-lg font-semibold text-white">Data Controls</h3>
        <p className="mt-1 text-sm text-slate-400">
          Export operational state and manage local cache safely.
        </p>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <button
            onClick={handleExportWorkspace}
            className="flex items-start gap-3 rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-left text-emerald-100 transition hover:bg-emerald-500/15"
          >
            <Download className="mt-0.5 h-4 w-4" />
            <span>
              <span className="block text-sm font-semibold">Export Workspace Snapshot</span>
              <span className="block text-xs text-emerald-200/80">
                JSON export of account, settings, and dataset metadata.
              </span>
            </span>
          </button>

          <button
            onClick={handleClearLocalData}
            disabled={clearingLocalData}
            className="flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-left text-amber-100 transition hover:bg-amber-500/15 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCcw className="mt-0.5 h-4 w-4" />
            <span>
              <span className="block text-sm font-semibold">
                {clearingLocalData ? "Resetting..." : "Reset Local Cache"}
              </span>
              <span className="block text-xs text-amber-200/80">
                Clears persisted dataset/chat caches and reloads datasets.
              </span>
            </span>
          </button>
        </div>
      </div>

      <div className={sectionShell}>
        <h4 className="text-sm font-semibold text-slate-200">Session</h4>
        <div className="mt-3 space-y-3">
          <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
            <p className="text-sm text-slate-200">Signed in as {user?.email || "unknown"}</p>
            <p className="text-xs text-slate-500">
              Use logout to terminate the current browser session.
            </p>
          </div>
          <button
            onClick={logout}
            className="inline-flex items-center gap-2 rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-100 transition hover:bg-rose-500/20"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </div>
    </div>
  );

  const renderActiveTab = () => {
    switch (activeTab) {
      case "account":
        return renderAccountTab();
      case "security":
        return renderSecurityTab();
      case "notifications":
        return renderNotificationsTab();
      case "workspace":
        return renderWorkspaceTab();
      case "data":
        return renderDataTab();
      default:
        return renderAccountTab();
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#05070d] text-slate-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-24 -top-24 h-80 w-80 rounded-full bg-[#cad2fd]/10 blur-[120px]" />
        <div className="absolute bottom-[-120px] right-[-80px] h-96 w-96 rounded-full bg-[#c7bc92]/12 blur-[130px]" />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-[1400px] space-y-6 p-4 md:p-6 lg:p-8">
        <MotionSection
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-3xl border border-white/10 bg-[linear-gradient(125deg,rgba(202,210,253,0.24),rgba(5,7,13,0.82)_45%,rgba(199,188,146,0.24))] p-6 shadow-[0_24px_70px_-42px_rgba(0,0,0,0.95)] md:p-8"
        >
          <p className="text-xs uppercase tracking-[0.28em] text-slate-300">Control Center</p>
          <h1 className="mt-3 text-3xl font-semibold text-white md:text-5xl">
            Settings that operate like production software
          </h1>
          <p className="mt-3 max-w-2xl text-sm text-slate-300 md:text-base">
            Manage account security, workspace preferences, data cache, and session state
            from one structured surface.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3 text-xs">
            <span className="inline-flex items-center gap-1 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-slate-100">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
              {datasetStats.ready}/{datasetStats.total} datasets ready
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-slate-100">
              <Mail className="h-3.5 w-3.5 text-sky-300" />
              {user?.email || "No email"}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-slate-100">
              <MonitorCog className="h-3.5 w-3.5 text-amber-300" />
              Theme: {theme}
            </span>
          </div>
        </MotionSection>

        <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
          <MotionSection
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            className="h-fit rounded-2xl border border-white/10 bg-[#070c14]/88 p-3 xl:sticky xl:top-6"
          >
            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#cad2fd] text-sm font-bold text-[#020203]">
                  {getDisplayName(user).slice(0, 1).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">
                    {getDisplayName(user)}
                  </p>
                  <p className="truncate text-xs text-slate-400">{user?.email}</p>
                </div>
              </div>
            </div>

            <nav className="mt-3 space-y-1">
              {TAB_ITEMS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm transition",
                    activeTab === tab.id
                      ? "border border-[#cad2fd]/30 bg-[#cad2fd]/20 text-[#eef1ff]"
                      : "border border-transparent text-slate-300 hover:border-white/10 hover:bg-white/5 hover:text-white"
                  )}
                >
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                </button>
              ))}
            </nav>

            <div className="mt-3 rounded-xl border border-amber-400/25 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
              <p className="inline-flex items-center gap-1 font-medium">
                <AlertTriangle className="h-3.5 w-3.5" />
                Security best practice
              </p>
              <p className="mt-1 text-amber-100/80">
                Rotate your password regularly and keep security alerts enabled.
              </p>
            </div>
          </MotionSection>

          <MotionSection
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            className="rounded-2xl border border-white/10 bg-[#070c14]/88 p-4 md:p-6"
          >
            <AnimatePresence mode="wait">
              <MotionDiv
                key={activeTab}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.16 }}
              >
                {renderActiveTab()}
              </MotionDiv>
            </AnimatePresence>
          </MotionSection>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
