import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, BarChart3, Layers3, Settings,
  Sparkles, Upload, Plus, ChevronsLeft, ChevronsRight, Lightbulb, LogOut, History,
} from 'lucide-react';
import useDatasetStore from '../../store/datasetStore';
import useChatStore from '../../store/chatStore';
import UploadModal from '../features/datasets/UploadModal';
import ChatHistoryModal from '../features/observatory/ChatHistoryModal';
import { cn } from '../../lib/utils';
import { useAuth } from '../../store/authStore';
import { AiBotIcon } from '../svg/icons';

/* ─── Storage key ─── */
const SIDEBAR_KEY = 'datasage-sidebar-expanded';

/* ─── Nav items ─── */
const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/app/dashboard' },
  { icon: Lightbulb, label: 'Insights', path: '/app/insights' },
  { icon: AiBotIcon, label: 'AI Chat', path: '/app/chat' },
  { icon: BarChart3, label: 'Charts', path: '/app/charts' },
  { icon: Layers3, label: 'Datasets', path: '/app/datasets', badge: 'datasets' },
  { icon: Settings, label: 'Settings', path: '/app/settings' },
];

/* ─── Sidebar ─── */
const Sidebar = () => {
  const navigate = useNavigate();
  const datasets = useDatasetStore((s) => s.datasets);
  const fetchDatasets = useDatasetStore((s) => s.fetchDatasets);
  const selectedDataset = useDatasetStore((s) => s.selectedDataset);
  const setSelectedDataset = useDatasetStore((s) => s.setSelectedDataset);
  const startNewConversation = useChatStore((s) => s.startNewConversation);
  const conversations = useChatStore((s) => s.conversations);
  const currentConversationId = useChatStore((s) => s.currentConversationId);
  const setCurrentConversation = useChatStore((s) => s.setCurrentConversation);
  const loadConversations = useChatStore((s) => s.loadConversations);
  const { logout } = useAuth();

  const [expanded, setExpanded] = useState(() => {
    try { return JSON.parse(localStorage.getItem(SIDEBAR_KEY)) ?? false; }
    catch { return false; }
  });
  const [showUpload, setShowUpload] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  // Persist expand state
  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, JSON.stringify(expanded));
  }, [expanded]);

  const toggle = useCallback(() => setExpanded((p) => !p), []);

  useEffect(() => {
    if (expanded) {
      loadConversations();
    }
  }, [expanded, loadConversations]);

  const recentChats = useMemo(() => {
    const generateTitle = (messages = [], datasetName = 'New Chat') => {
      const firstUserMessage = messages.find((m) => m.role === 'user');
      if (firstUserMessage?.content && typeof firstUserMessage.content === 'string') {
        let title = firstUserMessage.content.trim();
        title = title.replace(/^(show me|can you|please|i want to|help me|what is|what are|how do|tell me)/i, '').trim();
        title = title.charAt(0).toUpperCase() + title.slice(1);
        if (title.length > 42) title = `${title.slice(0, 39)}...`;
        return title || datasetName;
      }
      return datasetName;
    };

    return Object.values(conversations)
      .map((conv) => {
        const messages = conv.messages || [];
        const lastMessage = messages[messages.length - 1];
        const snippet = typeof lastMessage?.content === 'string'
          ? lastMessage.content.replace(/\s+/g, ' ').trim()
          : 'No messages yet';
        return {
          id: conv.id,
          datasetId: conv.datasetId,
          title: generateTitle(messages, conv.datasetName || 'New Chat'),
          snippet: snippet || 'No messages yet',
          ts: new Date(conv.updatedAt || conv.createdAt || Date.now()).getTime(),
        };
      })
      .sort((a, b) => b.ts - a.ts)
      .slice(0, 6);
  }, [conversations]);

  const openConversation = useCallback((conversationId, datasetId = null) => {
    if (!conversationId) return;
    setCurrentConversation(conversationId);

    if (datasetId) {
      const matchedDataset = datasets.find((d) => (d.id || d._id) === datasetId);
      if (matchedDataset) setSelectedDataset(matchedDataset);
    }

    const params = new URLSearchParams();
    params.set('chatId', conversationId);
    if (datasetId) params.set('dataset', datasetId);
    navigate(`/app/chat?${params.toString()}`);
  }, [datasets, navigate, setCurrentConversation, setSelectedDataset]);

  const handleNewChat = () => {
    const dsId = selectedDataset?.id || selectedDataset?._id || null;
    startNewConversation(dsId);
    navigate('/app/chat');
  };

  const handleUploadSuccess = () => {
    fetchDatasets();
    setShowUpload(false);
  };

  // Badge values
  const getBadge = (key) => {
    if (key === 'datasets' && datasets.length > 0) return datasets.length;
    return null;
  };

  const W_COLLAPSED = 60;
  const W_EXPANDED = 220;

  return (
    <>
      <aside
        className="h-full flex flex-col border-r border-white/[0.04] bg-noir shrink-0 overflow-hidden select-none"
        style={{ width: expanded ? W_EXPANDED : W_COLLAPSED }}
      >
        {/* ═══ Zone 1: Brand ═══ */}
        <div className={cn(
          "relative flex items-center shrink-0 h-14 border-b border-white/[0.04]",
          expanded ? "px-3 justify-between" : "justify-center"
        )}>
          {/* Logo */}
          <button
            onClick={expanded ? () => navigate('/app/dashboard') : toggle}
            className="flex items-center gap-2.5 group"
            title={expanded ? 'Go to Dashboard' : 'Expand sidebar'}
          >
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-ocean to-pearl/60 flex items-center justify-center shrink-0 group-hover:shadow-md group-hover:shadow-ocean/20 transition-shadow">
              <Sparkles className="w-4 h-4 text-noir" />
            </div>
            {expanded && (
              <span className="text-[15px] font-bold text-pearl tracking-tight">
                DataSage
              </span>
            )}
          </button>

          {/* Collapse toggle */}
          {expanded && (
            <button
              onClick={toggle}
              className="w-6 h-6 rounded-md flex items-center justify-center text-granite/50 hover:text-pearl/70 hover:bg-white/[0.05] transition-all"
              title="Collapse sidebar"
            >
              <ChevronsLeft className="w-4 h-4" />
            </button>
          )}

          {!expanded && (
            <button
              onClick={toggle}
              className="absolute right-1 top-1/2 -translate-y-1/2 w-6 h-6 rounded-md flex items-center justify-center text-granite/60 hover:text-pearl/80 hover:bg-white/[0.05] transition-all"
              title="Expand sidebar"
              aria-label="Expand sidebar"
            >
              <ChevronsRight className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* ═══ Zone 2: Navigation ═══ */}
        <nav className="flex-1 flex flex-col gap-0.5 px-2 pt-3 overflow-y-auto overflow-x-hidden">
          {expanded && (
            <div className="text-xs uppercase tracking-[0.08em] text-pearl/40 font-semibold px-2 mb-1">
              Main
            </div>
          )}

          {NAV_ITEMS.map((item) => {
            const badge = getBadge(item.badge);
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  cn(
                    "relative flex items-center rounded-lg transition-all duration-150 group",
                    expanded ? "h-9 px-2.5 gap-2.5" : "h-10 w-10 mx-auto justify-center",
                    isActive
                      ? "bg-white/[0.06] text-pearl"
                      : "text-pearl/50 hover:text-pearl/80 hover:bg-white/[0.04]"
                  )
                }
                title={expanded ? undefined : item.label}
              >
                {/* Left accent bar for active state */}
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <div
                        className={cn(
                          "absolute bg-ocean rounded-full",
                          expanded
                            ? "left-0 top-1.5 bottom-1.5 w-[3px]"
                            : "left-0 top-2 bottom-2 w-[3px]"
                        )}
                      />
                    )}
                    <item.icon className={cn("shrink-0", expanded ? "w-[18px] h-[18px]" : "w-5 h-5")} />
                    {expanded && (
                      <span className="text-sm font-medium truncate flex-1">{item.label}</span>
                    )}
                    {/* Badge */}
                    {badge != null && (
                      <span className={cn(
                        "flex items-center justify-center font-bold tabular-nums rounded-full bg-ocean/15 text-ocean",
                        expanded ? "min-w-[20px] h-5 px-1.5 text-xs" : "absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 text-[11px]"
                      )}>
                        {badge}
                      </span>
                    )}
                    {/* Tooltip — collapsed only */}
                    {!expanded && (
                      <span className="absolute left-full ml-3 px-2.5 py-1 rounded-md bg-[#141419] text-pearl text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity shadow-xl border border-white/[0.08] z-50">
                        {item.label}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}

          {expanded && (
            <>
              <div className="h-px bg-white/[0.05] my-3 mx-1" />
              <div className="px-2 mb-1 flex items-center justify-between">
                <span className="text-xs uppercase tracking-[0.08em] text-pearl/40 font-semibold">
                  Recent Chats
                </span>
                {recentChats.length > 0 && (
                  <span className="text-xs text-pearl/40 tabular-nums">{recentChats.length}</span>
                )}
              </div>

              {recentChats.length === 0 ? (
                <div className="px-2 py-2 text-[13px] text-pearl/40">
                  No recent chats
                </div>
              ) : (
                <>
                  {recentChats.map((chat) => (
                    <button
                      key={chat.id}
                      type="button"
                      onClick={() => openConversation(chat.id, chat.datasetId)}
                      className={cn(
                        "w-full text-left rounded-lg px-2.5 py-2 transition-all",
                        currentConversationId === chat.id
                          ? "bg-white/[0.06] text-pearl"
                          : "text-pearl/60 hover:text-pearl/80 hover:bg-white/[0.04]"
                      )}
                    >
                      <div className="text-[13px] font-semibold truncate">{chat.title}</div>
                      <div className="text-xs opacity-70 truncate mt-0.5">
                        {chat.snippet}
                      </div>
                    </button>
                  ))}

                  <button
                    type="button"
                    onClick={() => setShowHistoryModal(true)}
                    className="mt-1 w-full flex items-center justify-center gap-1.5 rounded-lg border border-white/[0.08] px-2.5 py-1.5 text-[13px] text-granite hover:text-pearl/80 hover:bg-white/[0.04] transition-all"
                  >
                    <History className="w-3.5 h-3.5" />
                    View More
                  </button>
                </>
              )}
            </>
          )}
        </nav>

        {/* ─── Zone 3: Bottom Actions ─── */}
        <div className="p-2 border-t border-white/[0.04]">
          <button
            onClick={handleNewChat}
            className={cn(
              "relative w-full flex items-center rounded-lg transition-all duration-150 group mb-1",
              expanded ? "h-9 px-2.5 gap-2.5" : "h-10 justify-center",
              "text-pearl/60 hover:text-pearl/80 hover:bg-white/[0.04]"
            )}
            title={expanded ? undefined : "New Chat"}
            aria-label="New Chat"
          >
            <Plus className={cn("shrink-0", expanded ? "w-4 h-4" : "w-5 h-5")} />
            {expanded && (
              <span className="text-sm font-medium truncate flex-1 text-left">New Chat</span>
            )}
            {!expanded && (
              <span className="absolute left-full ml-3 px-2.5 py-1 rounded-md bg-[#141419] text-pearl text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity shadow-xl border border-white/[0.08] z-50">
                New Chat
              </span>
            )}
          </button>

          <button
            onClick={() => setShowUpload(true)}
            className={cn(
              "relative w-full flex items-center rounded-lg transition-all duration-150 group mb-1",
              expanded ? "h-9 px-2.5 gap-2.5" : "h-10 justify-center",
              "text-pearl/60 hover:text-pearl/80 hover:bg-white/[0.04]"
            )}
            title={expanded ? undefined : "Upload Dataset"}
            aria-label="Upload Dataset"
          >
            <Upload className={cn("shrink-0", expanded ? "w-4 h-4" : "w-5 h-5")} />
            {expanded && (
              <span className="text-sm font-medium truncate flex-1 text-left">Upload Dataset</span>
            )}
            {!expanded && (
              <span className="absolute left-full ml-3 px-2.5 py-1 rounded-md bg-[#141419] text-pearl text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity shadow-xl border border-white/[0.08] z-50">
                Upload Dataset
              </span>
            )}
          </button>

          <button
            onClick={() => {
              logout();
              navigate('/login');
            }}
            className={cn(
              "relative w-full flex items-center rounded-lg transition-all duration-150 group",
              expanded ? "h-9 px-2.5 gap-2.5" : "h-10 justify-center",
              "text-pearl/60 hover:text-red-400 hover:bg-white/[0.04]"
            )}
            title={expanded ? undefined : "Sign Out"}
            aria-label="Sign Out"
          >
            <LogOut className={cn("shrink-0", expanded ? "w-4 h-4" : "w-5 h-5")} />
            {expanded && (
              <span className="text-sm font-medium truncate flex-1 text-left">Sign Out</span>
            )}
            {!expanded && (
              <span className="absolute left-full ml-3 px-2.5 py-1 rounded-md bg-[#141419] text-pearl text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity shadow-xl border border-white/[0.08] z-50">
                Sign Out
              </span>
            )}
          </button>
        </div>
      </aside>

      {/* Upload Modal */}
      <UploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        onUploadSuccess={handleUploadSuccess}
      />

      <ChatHistoryModal
        isOpen={showHistoryModal}
        onClose={() => setShowHistoryModal(false)}
        currentConversationId={currentConversationId}
        onSelectConversation={(id) => {
          const selected = conversations[id];
          openConversation(id, selected?.datasetId || null);
          setShowHistoryModal(false);
        }}
      />
    </>
  );
};

export default Sidebar;
