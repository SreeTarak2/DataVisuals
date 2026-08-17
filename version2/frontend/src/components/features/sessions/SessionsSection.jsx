import React, { useEffect, useState } from "react";
import { Laptop, Smartphone, Monitor, Loader2, ShieldCheck, LogOut, RefreshCw, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "react-hot-toast";
import { useAuth } from "../../../store/authStore";
import { cn } from "../../../lib/utils";

const timeAgo = (iso) => {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const diffMs = Date.now() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "yesterday" : `${days}d ago`;
};

const deviceIcon = (name = "") => {
  const n = name.toLowerCase();
  if (/iphone|ipad|android|ios|mobile/i.test(n)) return Smartphone;
  if (/mac|windows|linux|desktop|chrome|firefox|safari|edge|browser/i.test(n)) return Monitor;
  return Laptop;
};

/**
 * SessionsSection — manage active devices for the account.
 *
 * Lists every active session (one per logged-in device). The current device
 * is marked and can't be revoked from here (use logout instead). "Log out
 * everywhere else" revokes every other session server-side — those devices
 * are denied on their next request/refresh, and any open WebSocket on this
 * account gets a `session_revoked` push on full logout.
 */
const SessionsSection = () => {
  const { sessions, sessionsLoading, fetchSessions, revokeSession, logoutAll } = useAuth();
  const [revokingId, setRevokingId] = useState(null);
  const [loggingOutAll, setLoggingOutAll] = useState(false);

  useEffect(() => {
    fetchSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRevoke = async (session) => {
    setRevokingId(session.jti);
    const r = await revokeSession(session.jti);
    setRevokingId(null);
    if (r.success) {
      toast.success(`Signed out "${session.device_name || 'device'}"`);
    } else {
      toast.error(r.error || "Failed to revoke session");
    }
  };

  const handleLogoutAll = async () => {
    if (window.confirm("Log out of every other device? This device stays signed in.")) {
      setLoggingOutAll(true);
      await logoutAll();
      setLoggingOutAll(false);
      toast.success("Signed out everywhere else");
      fetchSessions();
    }
  };

  const otherCount = sessions.filter((s) => !s.is_current).length;

  return (
    <motion.div variants={{ hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0 } }} initial="hidden" animate="visible">
      <div className="mb-8">
        <h3 className="text-xl font-semibold text-[var(--text-primary)]">Devices & Sessions</h3>
        <p className="text-[15px] text-[var(--text-secondary)] mt-1">
          Review where you're signed in. Revoke any device you don't recognize.
        </p>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)]/30 overflow-hidden">
        {sessionsLoading && sessions.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-12 text-[var(--text-secondary)]">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-[13px]">Loading sessions…</span>
          </div>
        ) : sessions.length === 0 ? (
          <div className="py-12 text-center">
            <ShieldCheck className="w-6 h-6 mx-auto mb-2 text-[var(--text-muted)] opacity-50" />
            <p className="text-[13px] text-[var(--text-secondary)]">No active sessions found.</p>
          </div>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {sessions.map((s) => {
              const Icon = deviceIcon(s.device_name);
              const isCurrent = s.is_current;
              const isRevoking = revokingId === s.jti;
              return (
                <li key={s.jti} className="flex items-center gap-3.5 px-4 py-3.5">
                  <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 bg-[var(--bg-secondary)] border border-[var(--border)]">
                    <Icon className="w-4 h-4 text-[var(--text-secondary)]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[13.5px] font-medium text-[var(--text-primary)] truncate">
                        {s.device_name || "Web browser"}
                      </span>
                      {isCurrent && (
                        <span className="text-[10.5px] font-bold px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                          This device
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5 text-[12px] text-[var(--text-secondary)]">
                      <span>Active {timeAgo(s.last_used_at)}</span>
                      {s.ip && (
                        <>
                          <span className="opacity-40">·</span>
                          <span className="font-mono">{s.ip}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleRevoke(s)}
                    disabled={isCurrent || isRevoking}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-1.5 text-[12.5px] font-medium text-[var(--text-primary)] transition-all hover:bg-[var(--bg-active)] disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                    title={isCurrent ? "Use Log out to end this session" : "Revoke this session"}
                  >
                    {isRevoking ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <LogOut className="w-3.5 h-3.5" />
                    )}
                    {isCurrent ? "Current" : "Revoke"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 text-[12.5px] text-[var(--text-secondary)]">
          {otherCount > 0 ? (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              <span>{otherCount} other device{otherCount === 1 ? "" : "s"} signed in</span>
            </>
          ) : (
            <span>You're only signed in on this device.</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchSessions()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-1.5 text-[12.5px] font-medium text-[var(--text-primary)] transition-all hover:bg-[var(--bg-active)]"
            title="Refresh session list"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", sessionsLoading && "animate-spin")} />
            Refresh
          </button>
          <button
            onClick={handleLogoutAll}
            disabled={otherCount === 0 || loggingOutAll}
            className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-1.5 text-[12.5px] font-medium text-amber-500 transition-all hover:bg-amber-500/20 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Revoke every other session — this device stays signed in"
          >
            {loggingOutAll ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <LogOut className="w-3.5 h-3.5" />
            )}
            Log out everywhere else
          </button>
        </div>
      </div>
    </motion.div>
  );
};

export default SessionsSection;
