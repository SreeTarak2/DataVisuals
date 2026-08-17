import React, { useEffect, useState, useCallback } from "react";
import {
  KeyRound,
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
  Loader2,
  Eye,
  EyeOff,
  RefreshCw,
  ExternalLink,
  AlertTriangle,
  Shield,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "react-hot-toast";
import { keysAPI } from "../../../services/api";
import { cn } from "../../../lib/utils";
import OpenAI from "@lobehub/icons/es/OpenAI";
import Anthropic from "@lobehub/icons/es/Anthropic";
import DeepSeek from "@lobehub/icons/es/DeepSeek";
import Gemini from "@lobehub/icons/es/Gemini";

void motion;

/* ─── CSS class constants (matching SettingsPage patterns) ─── */
const inputCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/50 px-3.5 text-[14px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none transition-all focus:border-[var(--accent-primary)] focus:bg-[var(--bg-elevated)] focus:ring-1 focus:ring-[var(--accent-primary)]";

const selectCls =
  "h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/50 px-3 text-[14px] text-[var(--text-primary)] outline-none transition-all focus:border-[var(--accent-primary)] focus:ring-1 focus:ring-[var(--accent-primary)] appearance-none cursor-pointer";

const btnPrimary =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--accent-primary)] px-4 py-2 text-[13px] font-medium text-white transition-all hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 h-9";

const btnSecondary =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] transition-all hover:bg-[var(--bg-active)] h-9";

const btnDanger =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-rose-500/25 bg-rose-500/10 px-4 py-2 text-[13px] font-medium text-rose-400 transition-all hover:bg-rose-500/20 hover:border-rose-500/40 disabled:opacity-50 disabled:cursor-not-allowed h-9";

/* ─── Provider config ─── */
const PROVIDERS = [
  { id: "openai", label: "OpenAI", color: "text-emerald-500", logo: "OpenAI" },
  { id: "anthropic", label: "Anthropic", color: "text-amber-500", logo: "Claude" },
  { id: "deepseek", label: "DeepSeek", color: "text-blue-500", logo: "DeepSeek" },
  { id: "google", label: "Google", color: "text-purple-500", logo: "Gemini" },
];

const PROVIDER_ICON_MAP = {
  openai: OpenAI,
  anthropic: Anthropic,
  deepseek: DeepSeek,
  google: Gemini,
};

/* ─── Framer motion variants ─── */
const fadeSlide = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: "easeOut" } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.14 } },
};

const staggerItem = {
  hidden: { opacity: 0, y: 8 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.04, duration: 0.2, ease: "easeOut" },
  }),
};

/* ─── Format date ─── */
const formatDate = (value) => {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

/* ─── Toggle component ─── */
const Toggle = ({ checked, onChange }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    onClick={onChange}
    className={cn(
      "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors duration-200",
      checked
        ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]"
        : "border-[var(--border)] bg-[var(--bg-secondary)]"
    )}
  >
    <span
      className={cn(
        "pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200",
        checked ? "translate-x-[22px]" : "translate-x-[4px]"
      )}
    />
  </button>
);

/* ─── Form Row ─── */
const FormRow = ({ label, description, children, noBorder }) => (
  <div className={cn("py-5", !noBorder && "border-b border-[var(--border)]/50")}>
    <h4 className="text-[14px] font-medium text-[var(--text-primary)]">{label}</h4>
    {description && (
      <p className="mt-1 text-[13px] text-[var(--text-secondary)] leading-relaxed">{description}</p>
    )}
    <div className="mt-3.5">{children}</div>
  </div>
);

/* ─── Provider Icon helper ─── */
const ProviderIcon = ({ provider, size = "md" }) => {
  const IconComp = PROVIDER_ICON_MAP[provider];
  if (!IconComp) return <span>🔑</span>;
  const sizeClass = size === "lg" ? "w-5 h-5" : "w-4.5 h-4.5";
  return <IconComp className={sizeClass} />;
};

/* ═══════════════════════════════════════════════ */
/*              API KEYS SECTION                   */
/* ═══════════════════════════════════════════════ */

const ApiKeysSection = () => {
  /* ── State ── */
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Add key form
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("openai");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [keyLabel, setKeyLabel] = useState("");
  const [showKeyText, setShowKeyText] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);
  const [selectedModels, setSelectedModels] = useState([]);
  const [keyValid, setKeyValid] = useState(null); // null | true | false
  const [keyError, setKeyError] = useState(null);
  const [saving, setSaving] = useState(false);

  // Expanded key details
  const [expandedKey, setExpandedKey] = useState(null);

  // Validation state per key
  const [validatingKey, setValidatingKey] = useState(null);
  const [deletingKey, setDeletingKey] = useState(null);

  /* ── Fetch keys on mount ── */
  const fetchKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await keysAPI.listKeys();
      setKeys(res.data?.keys || []);
    } catch (err) {
      const msg = err.response?.status === 403
        ? "BYOK is not enabled on this server."
        : err.response?.data?.detail || "Failed to load API keys.";
      setError(msg);
      setKeys([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  /* ── Reset add form ── */
  const resetForm = () => {
    setSelectedProvider("openai");
    setApiKeyInput("");
    setKeyLabel("");
    setShowKeyText(false);
    setDiscovering(false);
    setAvailableModels([]);
    setSelectedModels([]);
    setKeyValid(null);
    setKeyError(null);
  };

  const cancelAdd = () => {
    resetForm();
    setShowAddForm(false);
  };

  /* ── Discover models for the entered key ── */
  const handleDiscover = async () => {
    if (!apiKeyInput.trim()) {
      toast.error("Enter an API key first.");
      return;
    }
    setDiscovering(true);
    setKeyValid(null);
    setKeyError(null);
    setAvailableModels([]);

    try {
      const res = await keysAPI.discoverModels(selectedProvider, apiKeyInput.trim());
      const data = res.data;
      if (data.valid) {
        setKeyValid(true);
        setAvailableModels(data.available_models || []);
        setSelectedModels(data.available_models || []);
        toast.success(`Key validated — ${data.available_models?.length || 0} models available.`);
      } else {
        setKeyValid(false);
        setKeyError(data.error || "Key validation failed.");
        toast.error(data.error || "Invalid API key.");
      }
    } catch (err) {
      setKeyValid(false);
      const msg = err.response?.data?.detail || "Failed to validate key.";
      setKeyError(msg);
      toast.error(msg);
    } finally {
      setDiscovering(false);
    }
  };

  /* ── Toggle model selection ── */
  const toggleModel = (modelId) => {
    setSelectedModels((prev) =>
      prev.includes(modelId) ? prev.filter((m) => m !== modelId) : [...prev, modelId]
    );
  };

  /* ── Save the new key ── */
  const handleSaveKey = async () => {
    if (!apiKeyInput.trim()) {
      toast.error("Enter an API key.");
      return;
    }
    if (!keyValid) {
      toast.error("Validate the key first.");
      return;
    }
    setSaving(true);
    try {
      await keysAPI.createKey({
        provider: selectedProvider,
        api_key: apiKeyInput.trim(),
        label: keyLabel.trim() || `${PROVIDERS.find((p) => p.id === selectedProvider)?.label || selectedProvider} API Key`,
        selected_models: selectedModels,
      });
      toast.success("API key saved successfully.");
      cancelAdd();
      await fetchKeys();
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to save API key.";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  /* ── Delete a key ── */
  const handleDeleteKey = async (keyId) => {
    // Find the key to show a provider-specific prompt
    const key = keys.find((k) => k.id === keyId);
    const label = key?.label || key?.provider || "this key";
    if (!window.confirm(`Remove "${label}"? This cannot be undone.`)) {
      return;
    }
    setDeletingKey(keyId);
    try {
      await keysAPI.deleteKey(keyId);
      setKeys((prev) => prev.filter((k) => k.id !== keyId));
      if (expandedKey === keyId) setExpandedKey(null);
      toast.success("API key removed.");
    } catch (err) {
      toast.error("Failed to delete key.");
    } finally {
      setDeletingKey(null);
    }
  };

  /* ── Re-validate a stored key ── */
  const handleValidateKey = async (keyId) => {
    setValidatingKey(keyId);
    try {
      const res = await keysAPI.validateKey(keyId);
      if (res.data.valid) {
        toast.success("Key is valid.");
      } else {
        toast.error(res.data.error || "Key is no longer valid.");
      }
      // Update in local state
      setKeys((prev) =>
        prev.map((k) =>
          k.id === keyId
            ? { ...k, validated: res.data.valid, last_validated_at: res.data.last_validated_at }
            : k
        )
      );
    } catch (err) {
      toast.error("Failed to validate key.");
    } finally {
      setValidatingKey(null);
    }
  };

  /* ── Toggle key active state ── */
  const handleToggleActive = async (keyId, currentActive) => {
    // Optimistic update
    const newActive = !currentActive;
    setKeys((prev) =>
      prev.map((k) => (k.id === keyId ? { ...k, is_active: newActive } : k))
    );
    try {
      await keysAPI.updateKey(keyId, { is_active: newActive });
      toast.success(`Key ${newActive ? "activated" : "deactivated"}.`);
    } catch (err) {
      // Rollback on failure
      setKeys((prev) =>
        prev.map((k) => (k.id === keyId ? { ...k, is_active: currentActive } : k))
      );
      toast.error("Failed to update key.");
    }
  };

  /* ═══════════════════ RENDER ═══════════════════ */

  return (
    <motion.div variants={fadeSlide} initial="hidden" animate="visible" exit="exit">
      {/* Header */}
      <div className="mb-8">
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">
          API Keys (BYOK)
        </h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">
          Bring your own API key to use your preferred AI provider's models directly.
        </p>
      </div>

      {/* Explainer card */}
      <div className="mb-8 p-5 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/40">
        <div className="flex items-start gap-4">
          <div className="w-9 h-9 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] flex items-center justify-center shrink-0">
            <KeyRound className="w-4.5 h-4.5 text-[var(--text-secondary)]" />
          </div>
          <div>
            <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">
              How BYOK Works
            </h3>
            <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed mt-1">
              Add your API key from OpenAI, Anthropic, DeepSeek, or Google. The key is encrypted
              and stored securely. When you ask a question or run analysis, the best model from
              your selected set is automatically chosen for the task — chat uses a fast model,
              analysis uses a reasoning model. Your key is never exposed to other users.
            </p>
          </div>
        </div>
      </div>

      {/* Existing Keys */}
      <FormRow
        label="Your API Keys"
        description="Manage your registered API keys. Keys are encrypted at rest and never exposed."
      >
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-[var(--text-primary)] animate-spin" />
          </div>
        ) : error ? (
          <div className="flex items-center gap-3 p-4 rounded-lg border border-amber-500/20 bg-amber-500/5">
            <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
            <p className="text-[13px] text-[var(--text-secondary)]">{error}</p>
          </div>
        ) : keys.length === 0 ? (
          <div className="text-center py-10">
            <div className="w-12 h-12 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border)] flex items-center justify-center mx-auto mb-4">
              <KeyRound className="w-5 h-5 text-[var(--text-muted)]" />
            </div>
            <p className="text-[13px] text-[var(--text-secondary)] font-medium">
              No API keys added yet
            </p>
            <p className="text-[12px] text-[var(--text-muted)] mt-1 max-w-xs mx-auto">
              Add your first API key to use your preferred AI provider's models.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence>
              {keys.map((key, idx) => {
                const provider = PROVIDERS.find((p) => p.id === key.provider);
                const isExpanded = expandedKey === key.id;
                const isValidating = validatingKey === key.id;

                return (
                  <motion.div
                    key={key.id}
                    custom={idx}
                    variants={staggerItem}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                    className={cn(
                      "rounded-lg border transition-all",
                      key.is_active
                        ? "border-[var(--border)] bg-[var(--bg-elevated)]/40"
                        : "border-[var(--border)]/50 bg-[var(--bg-secondary)]/30 opacity-70"
                    )}
                  >
                    {/* Key row header */}
                    <div className="flex items-center justify-between p-4">
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        {/* Provider icon */}
                        <div
                          className={cn(
                            "w-9 h-9 rounded-lg flex items-center justify-center text-base shrink-0",
                            key.is_active
                              ? "bg-[var(--bg-secondary)] border border-[var(--border)]"
                              : "bg-[var(--bg-secondary)]/50 border border-[var(--border)]/50"
                          )}
                        >
                          <ProviderIcon provider={key.provider} />
                        </div>

                        {/* Key info */}
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[14px] font-medium text-[var(--text-primary)] truncate">
                              {key.label || provider?.label || key.provider}
                            </span>
                            {key.validated ? (
                              <span className="text-[11px] flex items-center gap-1 text-emerald-500 font-medium">
                                <CheckCircle className="w-3 h-3" /> Valid
                              </span>
                            ) : (
                              <span className="text-[11px] flex items-center gap-1 text-amber-500 font-medium">
                                <XCircle className="w-3 h-3" /> Untested
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[12px] text-[var(--text-secondary)]">
                              {key.provider.charAt(0).toUpperCase() + key.provider.slice(1)}
                            </span>
                            <span className="text-[10px] text-[var(--text-muted)]">·</span>
                            <span className="text-[12px] text-[var(--text-secondary)]">
                              {key.selected_models?.length || 0} models
                            </span>
                            <span className="text-[10px] text-[var(--text-muted)]">·</span>
                            <span className="text-[12px] text-[var(--text-secondary)]">
                              Added {formatDate(key.created_at)}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1.5 shrink-0">
                        <motion.button
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          onClick={() => handleValidateKey(key.id)}
                          disabled={isValidating}
                          className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-active)] transition-all"
                          title="Re-validate this key"
                        >
                          {isValidating ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <RefreshCw className="w-3.5 h-3.5" />
                          )}
                        </motion.button>

                        <motion.button
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          onClick={() => handleDeleteKey(key.id)}
                          disabled={deletingKey === key.id}
                          className="p-2 rounded-lg text-[var(--text-muted)] hover:text-rose-400 hover:bg-rose-500/10 transition-all"
                          title="Remove this key"
                        >
                          {deletingKey === key.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="w-3.5 h-3.5" />
                          )}
                        </motion.button>

                        <button
                          onClick={() => setExpandedKey(isExpanded ? null : key.id)}
                          className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-active)] transition-all"
                          title={isExpanded ? "Collapse" : "Expand details"}
                        >
                          {isExpanded ? (
                            <ChevronUp className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Expanded details */}
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="px-4 pb-4 pt-0 border-t border-[var(--border)]/50">
                            <div className="pt-4 space-y-3">
                              {/* Active toggle */}
                              <div className="flex items-center justify-between">
                                <div>
                                  <p className="text-[13px] font-medium text-[var(--text-primary)]">
                                    Active
                                  </p>
                                  <p className="text-[12px] text-[var(--text-secondary)]">
                                    When active, this key is used for matching tasks.
                                  </p>
                                </div>
                                <Toggle
                                  checked={key.is_active}
                                  onChange={() => handleToggleActive(key.id, key.is_active)}
                                />
                              </div>

                              {/* Models */}
                              <div>
                                <p className="text-[13px] font-medium text-[var(--text-primary)] mb-2">
                                  Enabled Models ({key.selected_models?.length || 0})
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                  {(key.selected_models || []).map((model) => (
                                    <span
                                      key={model}
                                      className={cn(
                                        "inline-flex items-center px-2.5 py-1 rounded-md text-[11px] font-medium border",
                                        key.is_active
                                          ? "bg-[var(--bg-secondary)] border-[var(--border)] text-[var(--text-primary)]"
                                          : "bg-[var(--bg-secondary)]/50 border-[var(--border)]/50 text-[var(--text-muted)]"
                                      )}
                                    >
                                      {model}
                                    </span>
                                  ))}
                                </div>
                              </div>

                              {/* Metadata */}
                              <div className="grid grid-cols-2 gap-3">
                                <div>
                                  <p className="text-[11px] text-[var(--text-muted)] font-medium uppercase tracking-wider">
                                    Last validated
                                  </p>
                                  <p className="text-[13px] text-[var(--text-primary)] mt-0.5">
                                    {formatDate(key.last_validated_at)}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-[11px] text-[var(--text-muted)] font-medium uppercase tracking-wider">
                                    Created
                                  </p>
                                  <p className="text-[13px] text-[var(--text-primary)] mt-0.5">
                                    {formatDate(key.created_at)}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </FormRow>

      {/* Add Key Button / Form */}
      {!showAddForm ? (
        <div className="pt-2">
          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setShowAddForm(true)}
            className="inline-flex items-center gap-2 rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-elevated)]/30 px-4 py-2.5 text-[13px] font-medium text-[var(--text-secondary)] transition-all hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/5 h-10"
          >
            <Plus className="w-4 h-4" />
            Add API Key
          </motion.button>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 p-5 rounded-lg border border-[var(--accent-primary)]/20 bg-[var(--accent-primary)]/5"
        >
          <h4 className="text-[15px] font-semibold text-[var(--text-primary)] mb-4">
            Add New API Key
          </h4>

          {/* Provider selector */}
          <div className="mb-4">
            <label className="text-[13px] font-medium text-[var(--text-primary)] mb-2 block">
              Provider
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {PROVIDERS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => {
                    setSelectedProvider(p.id);
                    setApiKeyInput("");
                    setKeyLabel("");
                    setShowKeyText(false);
                    setDiscovering(false);
                    setAvailableModels([]);
                    setSelectedModels([]);
                    setKeyValid(null);
                    setKeyError(null);
                  }}
                  className={cn(
                    "flex flex-col items-center gap-1.5 rounded-lg border px-3 py-3 transition-all text-center cursor-pointer",
                    selectedProvider === p.id
                      ? "border-[var(--text-primary)] bg-[var(--bg-active)] text-[var(--text-primary)] ring-[0.5px] ring-[var(--text-primary)]"
                      : "border-[var(--border)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-active)]/50 hover:text-[var(--text-primary)]"
                  )}
                >
                  <ProviderIcon provider={p.id} size="lg" />
                  <span className="text-[12px] font-medium">{p.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* API Key input */}
          <div className="mb-4">
            <label className="text-[13px] font-medium text-[var(--text-primary)] mb-2 block">
              API Key
            </label>
            <div className="relative max-w-lg">
              <input
                type={showKeyText ? "text" : "password"}
                value={apiKeyInput}
                onChange={(e) => {
                  setApiKeyInput(e.target.value);
                  setKeyValid(null);
                  setKeyError(null);
                  setAvailableModels([]);
                }}
                className={cn(inputCls, "pr-11 font-mono text-[13px]")}
                placeholder={`sk-... (${PROVIDERS.find((p) => p.id === selectedProvider)?.label || selectedProvider} API key)`}
              />
              <button
                type="button"
                onClick={() => setShowKeyText((p) => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1"
              >
                {showKeyText ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* Label */}
          <div className="mb-4">
            <label className="text-[13px] font-medium text-[var(--text-primary)] mb-2 block">
              Label <span className="text-[var(--text-muted)] font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={keyLabel}
              onChange={(e) => setKeyLabel(e.target.value)}
              className={cn(inputCls, "max-w-xs")}
              placeholder="My OpenAI key"
            />
          </div>

          {/* Validate button */}
          <div className="mb-4">
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleDiscover}
              disabled={discovering || !apiKeyInput.trim()}
              className={cn(btnSecondary, "text-[13px]")}
            >
              {discovering ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Validating...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" /> Validate &amp; Discover Models
                </>
              )}
            </motion.button>

            {/* Validation result */}
            {keyValid !== null && (
              <div
                className={cn(
                  "mt-3 p-3 rounded-lg border text-[13px] flex items-start gap-2.5",
                  keyValid
                    ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-500"
                    : "border-rose-500/20 bg-rose-500/5 text-rose-400"
                )}
              >
                {keyValid ? (
                  <>
                    <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                    <span>
                      Key is valid! {availableModels.length} model{availableModels.length !== 1 ? "s" : ""} available.
                    </span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
                    <span>{keyError || "Key validation failed."}</span>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Model selection (only shown after validation) */}
          {availableModels.length > 0 && (
            <div className="mb-6">
              <label className="text-[13px] font-medium text-[var(--text-primary)] mb-2 block">
                Select Models to Enable
                <span className="text-[var(--text-muted)] font-normal ml-1">
                  ({selectedModels.length} selected)
                </span>
              </label>
              <div className="flex flex-wrap gap-2 max-h-[180px] overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent p-1">
                {availableModels.map((model) => {
                  const isSelected = selectedModels.includes(model);
                  return (
                    <button
                      key={model}
                      type="button"
                      onClick={() => toggleModel(model)}
                      className={cn(
                        "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[12px] font-medium transition-all cursor-pointer",
                        isSelected
                          ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
                          : "border-[var(--border)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-active)] hover:text-[var(--text-primary)]"
                      )}
                    >
                      <span
                        className={cn(
                          "w-3.5 h-3.5 rounded border flex items-center justify-center transition-all",
                          isSelected
                            ? "bg-[var(--accent-primary)] border-[var(--accent-primary)]"
                            : "border-[var(--border)] bg-transparent"
                        )}
                      >
                        {isSelected && (
                          <CheckCircle className="w-3 h-3 text-white" />
                        )}
                      </span>
                      {model}
                    </button>
                  );
                })}
              </div>
              {selectedModels.length === 0 && (
                <p className="text-[12px] text-amber-500 mt-2 flex items-center gap-1.5">
                  <AlertTriangle className="w-3 h-3" />
                  Select at least one model to enable.
                </p>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2.5 pt-4 border-t border-[var(--border)]/50">
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleSaveKey}
              disabled={saving || !keyValid || selectedModels.length === 0}
              className={cn(btnPrimary, "h-9")}
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Saving...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" /> Save API Key
                </>
              )}
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={cancelAdd}
              disabled={saving}
              className={cn(btnSecondary, "h-9")}
            >
              Cancel
            </motion.button>
          </div>
        </motion.div>
      )}

      {/* Privacy note */}
      <div className="mt-6 p-4 rounded-lg border border-[var(--border)] border-l-2 border-l-amber-500/80 bg-[var(--bg-elevated)]/40 pl-4 pr-3 py-3.5">
        <div className="flex items-start gap-3">
          <Shield className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
          <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed">
            Your API keys are encrypted with Fernet (AES-128) at rest and decrypted only in
            memory during active requests. The decrypted key is never logged, cached, or exposed
            to other users. Each call through your key is tracked for analytics only — no charges
            are deducted from your platform daily budget for BYOK usage.
          </p>
        </div>
      </div>
    </motion.div>
  );
};

export default ApiKeysSection;
