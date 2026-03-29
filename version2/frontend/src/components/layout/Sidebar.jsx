import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard, BarChart3, Library, Settings,
  Sparkles, Upload, Plus, ChevronsLeft, ChevronsRight, Lightbulb, LogOut, History, Trash2, User,
} from 'lucide-react';
import useDatasetStore from '../../store/datasetStore';
import useChatStore from '../../store/chatStore';
import UploadModal from '../features/datasets/UploadModal';
import ChatHistoryModal from '../features/observatory/ChatHistoryModal';
import { cn } from '../../lib/utils';
import { useAuth } from '../../store/authStore';
import { AiBotIcon } from '../svg/icons';
import { ProfileDropdown } from '../ui/ProfileDropdown';

import useSidebarStore from '../../store/sidebarStore';

/* ─── Nav items ─── */
const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/app/dashboard' },
  { icon: Lightbulb, label: 'Analysis', path: '/app/analysis' },
  { icon: AiBotIcon, label: 'AI Chat', path: '/app/chat' },
  { icon: BarChart3, label: 'Charts', path: '/app/charts' },
  { icon: Library, label: 'Workspace', path: '/app/workspace', badge: 'datasets' },
  { icon: Settings, label: 'Settings', path: '/app/settings' },
];


/* ─── Sidebar ─── */
const Sidebar = () => {
  const navigate = useNavigate();
  const datasets = useDatasetStore((s) => s.datasets);
  const selectedDataset = useDatasetStore((s) => s.selectedDataset);
  const setSelectedDataset = useDatasetStore((s) => s.setSelectedDataset);
  const startNewConversation = useChatStore((s) => s.startNewConversation);
  const conversations = useChatStore((s) => s.conversations);
  const currentConversationId = useChatStore((s) => s.currentConversationId);
  const setCurrentConversation = useChatStore((s) => s.setCurrentConversation);
  const loadConversations = useChatStore((s) => s.loadConversations);
  const { logout, user } = useAuth();

  const { expanded } = useSidebarStore();
  const [showUpload, setShowUpload] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  useEffect(() => {
    if (expanded) {
      loadConversations();
    }
  }, [expanded, loadConversations]);

  const recentChats = useMemo(() => {
    const generateTitle = (messages = [], datasetName = 'New Chat') => {
      const firstUserMessage = messages.find((m) => m.role === 'user');
      if (firstUserMessage?.content && typeof firstUserMessage.content === 'string') {
        // Strip injected [Context: ...] prefix — user never typed it
        let title = firstUserMessage.content.replace(/^\[Context:[^\]]*\]\s*/i, '').trim();
        title = title.replace(/^(show me|can you|please|i want to|help me|what is|what are|how do|tell me)/i, '').trim();
        title = title.charAt(0).toUpperCase() + title.slice(1);
        if (title.length > 42) title = `${title.slice(0, 39)}...`;
        return title || datasetName;
      }
      return datasetName;
    };

    const stripMarkdown = (text) => text
      .replace(/^>\s*/gm, '')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/\*([^*]+)\*/g, '$1')
      .replace(/`[^`]+`/g, '')
      .replace(/#+\s*/g, '')
      .replace(/\s+/g, ' ')
      .trim();

    return Object.values(conversations)
      .map((conv) => {
        const messages = conv.messages || [];
        const lastMessage = messages[messages.length - 1];
        const rawSnippet = typeof lastMessage?.content === 'string' ? lastMessage.content : '';
        const snippet = rawSnippet ? stripMarkdown(rawSnippet) : 'No messages yet';
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

  const getBadge = (key) => {
    if (key === 'datasets' && datasets.length > 0) return datasets.length;
    return null;
  };

  const W_COLLAPSED = 60;
  const W_EXPANDED = 220;

  return (
    <>
      <motion.aside
        className="h-full flex flex-col shrink-0 overflow-hidden select-none"
        initial={false}
        animate={{ width: expanded ? W_EXPANDED : W_COLLAPSED }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderRight: '1px solid var(--border)',
        }}
      >
        <div
          className={cn(
            "group relative flex items-center shrink-0 h-14 w-full transition-all duration-300",
            expanded ? "px-4" : "px-3 justify-center"
          )}
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <button
            onClick={() => navigate('/app/dashboard')}
            className={cn(
              "flex items-center gap-2.5 group transition-all duration-300",
              !expanded && "scale-90"
            )}
            title={expanded ? 'Go to Dashboard' : undefined}
          >
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 shadow-md transform group-hover:scale-105 transition-transform"
              style={{
                background: 'linear-gradient(135deg, var(--accent-primary), #6366f1)',
              }}
            >
              <Sparkles className="w-4 h-4" style={{ color: '#FFFFFF' }} />
            </div>
            {expanded && (
              <span className="text-[15px] font-bold tracking-tight text-header">
                DataSage
              </span>
            )}
          </button>
        </div>

        <nav className="flex-1 flex flex-col gap-0.5 px-2 pt-3 overflow-y-auto overflow-x-hidden">
          {expanded && (
            <div
              className="text-xs uppercase tracking-[0.08em] font-semibold px-2 mb-1"
              style={{ color: 'var(--text-muted)' }}
            >
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
                      ? "text-[var(--text-header)]"
                      : "hover:opacity-80"
                  )
                }
                style={({ isActive }) => ({
                  color: isActive ? 'var(--text-header)' : 'var(--text-secondary)',
                  backgroundColor: 'transparent',
                })}
                title={expanded ? undefined : item.label}
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <div
                        className={cn(
                          "absolute rounded-full",
                          expanded
                            ? "left-0 top-1 bottom-1 w-[4px]"
                            : "left-[-4px] top-1.5 bottom-1.5 w-[5px]"
                        )}
                        style={{
                          backgroundColor: 'var(--accent-primary)',
                          boxShadow: '0 0 8px var(--accent-primary)'
                        }}
                      />
                    )}
                    {isActive && (
                      <motion.div
                        layoutId="nav-bg"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-x-1 inset-y-0.5 rounded-xl -z-10 bg-accent-primary/10 border border-accent-primary/20"
                      />
                    )}
                    <item.icon className={cn("shrink-0", expanded ? "w-[18px] h-[18px]" : "w-5 h-5")} />
                    {expanded && (
                      <span className="text-sm font-medium truncate flex-1">{item.label}</span>
                    )}
                    {badge != null && (
                      <span
                        className="flex items-center justify-center font-bold tabular-nums rounded-full absolute top-0 right-0"
                        style={{
                          backgroundColor: 'var(--accent-primary-light)',
                          color: 'var(--accent-primary)',
                          fontSize: '11px',
                          padding: expanded ? '0 6px' : '0 4px',
                          height: expanded ? '20px' : '16px',
                          minWidth: expanded ? '20px' : '16px',
                        }}
                      >
                        {badge}
                      </span>
                    )}
                    {!expanded && (
                      <span
                        className="absolute left-full ml-3 px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50"
                        style={{
                          backgroundColor: 'var(--bg-surface)',
                          color: 'var(--text-header)',
                          border: '1px solid var(--border)',
                          boxShadow: 'var(--shadow-lg)',
                        }}
                      >
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
              <div className="h-px my-3 mx-1" style={{ backgroundColor: 'var(--border)' }} />
              <div className="px-2 mb-1 flex items-center justify-between">
                <span
                  className="text-xs uppercase tracking-[0.08em] font-semibold"
                  style={{ color: 'var(--text-muted)' }}
                >
                  Recent Chats
                </span>
                {recentChats.length > 0 && (
                  <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{recentChats.length}</span>
                )}
              </div>

              {recentChats.length === 0 ? (
                <div
                  className="px-2 py-2 text-[13px]"
                  style={{ color: 'var(--text-muted)' }}
                >
                  No recent chats
                </div>
              ) : (
                <>
                  {recentChats.map((chat) => (
                    <button
                      key={chat.id}
                      type="button"
                      onClick={() => openConversation(chat.id, chat.datasetId)}
                      className="group w-full text-left rounded-lg px-2.5 py-2 transition-all hover:bg-opacity-80 flex items-start justify-between gap-2"
                      style={{
                        color: currentConversationId === chat.id ? 'var(--text-header)' : 'var(--text-secondary)',
                        backgroundColor: currentConversationId === chat.id ? 'var(--accent-primary-light)' : 'transparent',
                        cursor: 'pointer',
                      }}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-[13px] font-semibold truncate">{chat.title}</div>
                        <div className="text-xs truncate mt-0.5" style={{ opacity: 0.7 }}>
                          {chat.snippet}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const { clearConversation } = useChatStore.getState();
                          clearConversation(chat.id);
                        }}
                        className="p-1.5 rounded-md opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500/20 hover:text-red-400"
                        title="Delete chat"
                        style={{ flexShrink: 0 }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </button>
                  ))}

                  <button
                    type="button"
                    onClick={() => setShowHistoryModal(true)}
                    className="mt-1 w-full flex items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-all"
                    style={{
                      color: 'var(--text-secondary)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    <History className="w-3.5 h-3.5" />
                    View More
                  </button>
                </>
              )}
            </>
          )}
        </nav>


        <div
          className={cn(
            "mt-auto flex flex-col transition-all duration-300",
            expanded ? "p-4 gap-2" : "p-2 items-center gap-1.5 pb-4"
          )}
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <ProfileDropdown
            expanded={expanded}
            data={{
              name: user?.full_name || user?.username || 'User',
              email: user?.email || 'user@datasage.ai',
              avatar: user?.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.full_name || user?.username || 'User')}&background=6366f1&color=fff`,
              subscription: user?.subscription || 'GUEST',
              model: 'Gemini 2.0 Flash'
            }}
          />
          <button
            onClick={() => {
              logout();
              navigate('/login');
            }}
            className={cn(
              "flex items-center text-red-500/80 hover:text-red-500 rounded-xl transition-all duration-300 border border-transparent hover:bg-red-500/10 hover:border-red-500/20 group cursor-pointer",
              expanded ? "w-full px-3 py-2.5 gap-3" : "w-10 h-10 justify-center"
            )}
            title={expanded ? undefined : "Sign Out"}
          >
            <LogOut size={expanded ? 16 : 19} className="shrink-0 group-hover:scale-110 group-hover:rotate-[-5deg] transition-all" />
            {expanded && <span className="text-[13px] font-bold tracking-tight">Sign Out</span>}
          </button>
        </div>
      </motion.aside>

      <UploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
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
