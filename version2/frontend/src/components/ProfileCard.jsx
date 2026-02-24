import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Calendar,
  CheckCircle2,
  Clock3,
  Database,
  LogOut,
  Mail,
  MessageSquare,
  Settings,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useAuth } from "../store/authStore";
import useDatasetStore from "../store/datasetStore";
import useChatStore from "../store/chatStore";

const MotionDiv = motion.div;
const MotionButton = motion.button;

const formatMonthYear = (value) => {
  if (!value) return "No date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No date";
  return date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
};

const formatDateTime = (value) => {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const formatCount = (value) => Number(value || 0).toLocaleString();

const ProfileCard = ({ variant = "page", onAction }) => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const datasets = useDatasetStore((state) => state.datasets);
  const conversations = useChatStore((state) => state.conversations);
  const isPopover = variant === "popover";

  const identityName = user?.username || user?.full_name || "DataSage User";
  const identityEmail = user?.email || "No email";
  const initials = identityName.slice(0, 2).toUpperCase();

  const stats = useMemo(() => {
    const totalDatasets = datasets?.length || 0;
    const readyDatasets = (datasets || []).filter((dataset) => {
      const status = (dataset?.status || "").toLowerCase();
      return dataset?.is_processed || status === "completed";
    }).length;
    const conversationCount = Object.keys(conversations || {}).length;
    const messageCount = Object.values(conversations || {}).reduce(
      (sum, conversation) => sum + (conversation?.messages?.length || 0),
      0
    );
    return { totalDatasets, readyDatasets, conversationCount, messageCount };
  }, [datasets, conversations]);

  const profileDetails = [
    {
      label: "Email",
      value: identityEmail,
      icon: Mail,
    },
    {
      label: "Member Since",
      value: formatMonthYear(user?.created_at),
      icon: Calendar,
    },
    {
      label: "Last Login",
      value: formatDateTime(user?.last_login),
      icon: Clock3,
    },
    {
      label: "Security",
      value: user?.is_verified ? "Verified Account" : "Standard Account",
      icon: ShieldCheck,
    },
  ];

  const topStats = [
    {
      label: "Datasets",
      value: formatCount(stats.totalDatasets),
      icon: Database,
    },
    {
      label: "Ready",
      value: formatCount(stats.readyDatasets),
      icon: CheckCircle2,
    },
    {
      label: "Chats",
      value: formatCount(stats.conversationCount),
      icon: MessageSquare,
    },
    {
      label: "Messages",
      value: formatCount(stats.messageCount),
      icon: Sparkles,
    },
  ];

  const handleLogout = () => {
    onAction?.();
    logout();
    navigate("/login");
  };

  return (
    <MotionDiv
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className={isPopover ? "w-full" : "mx-auto w-full max-w-xl"}
    >
      {!isPopover && (
        <div className="mb-3 flex items-center justify-between">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
            <UserRound className="h-3.5 w-3.5 text-[#cad2fd]" />
            {identityName}
          </div>
          <div className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-400">
            {formatMonthYear(user?.created_at)}
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-[30px] border border-white/10 bg-[#0b1018] shadow-[0_28px_80px_-42px_rgba(0,0,0,0.95)]">
        <div className={`relative ${isPopover ? "h-32" : "h-40"} bg-[linear-gradient(125deg,#0fd9d0_0%,#11294e_46%,#eb3300_100%)]`}>
          <div className="absolute inset-0 opacity-55 [background:radial-gradient(circle_at_15%_20%,rgba(255,255,255,0.35),transparent_36%),radial-gradient(circle_at_75%_35%,rgba(255,255,255,0.22),transparent_40%)]" />
        </div>

        <div className={isPopover ? "px-4 pb-4" : "px-6 pb-6"}>
          <div className={`${isPopover ? "-mt-7" : "-mt-8"} flex items-end justify-between`}>
            <div className={`${isPopover ? "h-14 w-14" : "h-16 w-16"} rounded-full border-2 border-[#0b1018] bg-gradient-to-br from-[#cad2fd] to-[#c7bc92] p-[2px]`}>
              <div className="flex h-full w-full items-center justify-center rounded-full bg-[#05070d] text-lg font-bold text-[#cad2fd]">
                {initials}
              </div>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-200">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Active
            </div>
          </div>

          <div className={isPopover ? "mt-2" : "mt-3"}>
            <h2 className={`${isPopover ? "text-xl" : "text-2xl"} font-semibold tracking-tight text-white`}>{identityName}</h2>
            <p className={`${isPopover ? "mt-0.5 text-xs" : "mt-1 text-sm"} text-slate-400`}>Data Intelligence Operator</p>
          </div>

          <div className={`${isPopover ? "mt-3" : "mt-4"} grid grid-cols-4 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04]`}>
            {topStats.map((item, index) => (
              <div
                key={item.label}
                className={`${isPopover ? "px-2 py-2.5" : "px-3 py-3"} text-center ${index !== topStats.length - 1 ? "border-r border-white/10" : ""}`}
              >
                <item.icon className="mx-auto h-3.5 w-3.5 text-slate-400" />
                <p className={`${isPopover ? "text-base" : "text-lg"} mt-1 font-semibold leading-none text-slate-100`}>{item.value}</p>
                <p className="mt-1 text-[10px] uppercase tracking-widest text-slate-500">{item.label}</p>
              </div>
            ))}
          </div>

          <div className={`${isPopover ? "mt-3" : "mt-4"} grid gap-2 sm:grid-cols-2`}>
            {profileDetails.map((detail) => (
              <div
                key={detail.label}
                className={`rounded-xl border border-white/10 bg-black/25 ${isPopover ? "px-2.5 py-2" : "px-3 py-2.5"}`}
              >
                <p className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-slate-500">
                  <detail.icon className="h-3.5 w-3.5" />
                  {detail.label}
                </p>
                <p className={`mt-1 truncate ${isPopover ? "text-xs" : "text-sm"} text-slate-100`}>{detail.value}</p>
              </div>
            ))}
          </div>

          <div className={`${isPopover ? "mt-3" : "mt-4"} grid gap-2 sm:grid-cols-2`}>
            <MotionButton
              whileTap={{ scale: 0.98 }}
              onClick={() => {
                onAction?.();
                navigate("/app/settings");
              }}
              className={`inline-flex items-center justify-center gap-2 rounded-xl bg-[#cad2fd] px-4 ${isPopover ? "py-2.5 text-xs" : "py-3 text-sm"} font-semibold text-[#020203] transition hover:bg-[#d6dcff]`}
            >
              <Settings className="h-4 w-4" />
              Manage Profile
            </MotionButton>
            <MotionButton
              whileTap={{ scale: 0.98 }}
              onClick={handleLogout}
              className={`inline-flex items-center justify-center gap-2 rounded-xl border border-rose-400/35 bg-rose-500/12 px-4 ${isPopover ? "py-2.5 text-xs" : "py-3 text-sm"} font-semibold text-rose-100 transition hover:bg-rose-500/20`}
            >
              <LogOut className="h-4 w-4" />
              Sign Out
            </MotionButton>
          </div>
        </div>
      </div>
    </MotionDiv>
  );
};

export default ProfileCard;
