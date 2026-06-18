import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
    LayoutDashboard, BarChart3, Library, Settings,
    Sparkles, Upload, Plus, ChevronsLeft, ChevronsRight, Lightbulb, LogOut, History, Trash2, User, Database, Eye, FileSpreadsheet,
    PanelLeft, PanelLeftClose
} from 'lucide-react';
import useDatasetStore from '../../store/datasetStore';
import useChatStore from '../../store/chatStore';
import UploadModal from '../features/datasets/UploadModal';
import ChatHistoryModal from '../features/observatory/ChatHistoryModal';
import { cn } from '../../lib/utils';
import { useAuth } from '../../store/authStore';
import { AiBotIcon } from '../svg/icons';
import { ProfileDropdown } from '../ui/ProfileDropdown';
import { databaseAPI } from '../../services/api';

import useSidebarStore from '../../store/sidebarStore';

/* ─── Nav items ─── */
const NAV_ITEMS = [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/app/dashboard' },
    { icon: Lightbulb, label: 'Analysis', path: '/app/analysis' },
    { icon: AiBotIcon, label: 'AI Chat', path: '/app/chat' },
    { icon: BarChart3, label: 'Charts', path: '/app/charts' },
    { icon: Library, label: 'Assets', path: '/app/workspace', badge: 'datasets' },
    { icon: Database, label: 'Data Connectors', path: '/app/connectors' },
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

    const { expanded, toggle } = useSidebarStore();
    const [isHovered, setIsHovered] = useState(false);
    const [showUpload, setShowUpload] = useState(false);
    const [showHistoryModal, setShowHistoryModal] = useState(false);

    useEffect(() => {
        if (sessionStorage.getItem("logo_processed_v3")) return;

        const img = new Image();
        img.crossOrigin = "anonymous";
        img.src = "/logo.png?v=2";
        img.onload = () => {
            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);

            const imgData = ctx.getImageData(0, 0, img.width, img.height);
            const data = imgData.data;

            let xMin = img.width, xMax = 0, yMin = img.height, yMax = 0;
            let found = false;

            for (let y = 0; y < img.height; y++) {
                for (let x = 0; x < img.width; x++) {
                    const idx = (y * img.width + x) * 4;
                    const r = data[idx];
                    const g = data[idx+1];
                    const b = data[idx+2];
                    const a = data[idx+3];

                    const isOrange = r > 150 && g > 40 && b < 100 && (r - g > 30) && (g - b > 20) && a > 50;
                    if (isOrange) {
                        if (x < xMin) xMin = x;
                        if (x > xMax) xMax = x;
                        if (y < yMin) yMin = y;
                        if (y > yMax) yMax = y;
                        found = true;
                    }
                }
            }

            if (found) {
                const pad = 4;
                xMin = Math.max(0, xMin - pad);
                yMin = Math.max(0, yMin - pad);
                xMax = Math.min(img.width - 1, xMax + pad);
                yMax = Math.min(img.height - 1, yMax + pad);

                const cropW = xMax - xMin + 1;
                const cropH = yMax - yMin + 1;

                const tempCanvas = document.createElement("canvas");
                tempCanvas.width = cropW;
                tempCanvas.height = cropH;
                const tempCtx = tempCanvas.getContext("2d");
                tempCtx.drawImage(canvas, xMin, yMin, cropW, cropH, 0, 0, cropW, cropH);

                const tempImgData = tempCtx.getImageData(0, 0, cropW, cropH);
                const tempData = tempImgData.data;
                for (let i = 0; i < tempData.length; i += 4) {
                    const r = tempData[i];
                    const g = tempData[i+1];
                    const b = tempData[i+2];
                    const isOrange = r > 150 && g > 40 && b < 100 && (r - g > 30) && (g - b > 20);
                    if (!isOrange) {
                        tempData[i+3] = 0;
                    } else {
                        tempData[i+3] = 255;
                    }
                }
                tempCtx.putImageData(tempImgData, 0, 0);

                const finalCanvas = document.createElement("canvas");
                finalCanvas.width = 256;
                finalCanvas.height = 256;
                const finalCtx = finalCanvas.getContext("2d");

                const scale = Math.min(232 / cropW, 232 / cropH);
                const destW = cropW * scale;
                const destH = cropH * scale;
                const destX = (256 - destW) / 2;
                const destY = (256 - destH) / 2;

                finalCtx.drawImage(tempCanvas, 0, 0, cropW, cropH, destX, destY, destW, destH);

                const base64Data = finalCanvas.toDataURL("image/png");

                fetch("/local-api/save-logo", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ base64Data })
                })
                .then(res => res.json())
                .then(resData => {
                    if (resData.success) {
                        console.log("Logo successfully cropped and transparency set.");
                        sessionStorage.setItem("logo_processed_v3", "true");
                        window.location.reload();
                    }
                })
                .catch(err => console.error("Error saving logo:", err));
            } else {
                sessionStorage.setItem("logo_processed_v3", "true");
            }
        };
    }, []);

    useEffect(() => {
        if (expanded) {
            loadConversations();
        }
    }, [expanded, loadConversations]);

    const [dbConnections, setDbConnections] = useState([]);

    const fetchConnections = useCallback(() => {
        if (!expanded) return;
        databaseAPI.listConnections()
            .then((res) => setDbConnections(res.data || []))
            .catch(() => {});
    }, [expanded]);

    useEffect(() => {
        fetchConnections();
    }, [fetchConnections]);

    // Listen for db-connection-saved events from ConnectorSetupPage
    useEffect(() => {
        const handler = () => fetchConnections();
        window.addEventListener('db-connection-saved', handler);
        return () => window.removeEventListener('db-connection-saved', handler);
    }, [fetchConnections]);

    const googleSheetsDatasets = useMemo(() =>
        datasets.filter((d) => d.source_type === 'google_sheets'),
    [datasets]);

    const connectorItems = useMemo(() => {
        const items = [];
        dbConnections.forEach((conn) => {
            const typeMap = {
                postgresql: 'postgres',
                mysql: 'mysql',
                mongodb: 'mongodb',
                supabase: 'supabase',
            };
            items.push({
                id: `db-${conn.connection_id}`,
                name: conn.name || conn.database,
                type: 'database',
                icon: Database,
                path: `/app/connectors/${typeMap[conn.db_type] || conn.db_type}?connId=${conn.connection_id}`,
                status: conn.status || 'active',
            });
        });
        googleSheetsDatasets.forEach((ds) => {
            const dsId = ds.id || ds._id;
            items.push({
                id: `gs-${dsId}`,
                name: ds.name || ds.original_filename || 'Google Sheet',
                type: 'google_sheets',
                icon: FileSpreadsheet,
                path: '/app/workspace',
                status: ds.is_processed ? 'active' : 'syncing',
            });
        });
        return items;
    }, [dbConnections, googleSheetsDatasets]);

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

    const W_COLLAPSED = 68; // Adjusting slightly for better collapsed padding
    const W_EXPANDED = 240;

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
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
            >
                <div
                    className={cn(
                        "group relative flex flex-col shrink-0 w-full transition-all duration-300",
                        expanded ? "px-3 pt-4 pb-2" : "px-2 pt-4 pb-2 items-center"
                    )}
                >
                    <div className="flex items-center justify-between mb-4 px-1 w-full">
                        {expanded ? (
                            <>
                                <button
                                    onClick={() => navigate('/app/dashboard')}
                                    className="flex items-center gap-2.5 group transition-all duration-300"
                                    title="Go to Dashboard"
                                >
                                    <img src="/logo.png?v=2" alt="Signal Logo" className="h-6 w-6 object-contain shrink-0" />
                                    <span className="text-[16px] font-semibold tracking-tight text-blue-500 leading-none">
                                        Signal
                                    </span>
                                </button>
                                <button
                                    onClick={toggle}
                                    className="p-1.5 rounded-lg hover:bg-[var(--bg-active)]/50 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all shrink-0"
                                    title="Collapse Sidebar"
                                >
                                    <PanelLeftClose className="w-4 h-4" />
                                </button>
                            </>
                        ) : (
                            <div className="w-full flex justify-center items-center h-8 relative">
                                {isHovered ? (
                                    <button
                                        onClick={toggle}
                                        className="p-1.5 rounded-lg hover:bg-[var(--bg-active)]/50 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all"
                                        title="Expand Sidebar"
                                    >
                                        <PanelLeft className="w-5 h-5" />
                                    </button>
                                ) : (
                                    <button
                                        onClick={() => navigate('/app/dashboard')}
                                        className="flex items-center justify-center w-full transition-all duration-300 scale-90"
                                        title="Go to Dashboard"
                                    >
                                        <img src="/logo.png?v=2" alt="Signal Logo" className="h-6 w-6 object-contain shrink-0" />
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                <nav className={cn("flex-1 flex flex-col overflow-y-auto overflow-x-hidden pt-2 pb-6", expanded ? "px-3" : "px-2")}>

                    <div className="flex flex-col gap-0.5 mb-4">
                        {NAV_ITEMS.map((item) => {
                            const badge = getBadge(item.badge);
                            return (
                                <NavLink
                                    key={item.path}
                                    to={item.path}
                                    className={({ isActive }) =>
                                        cn(
                                            "relative flex items-center rounded-md transition-all duration-200 group border border-transparent",
                                            expanded ? "h-8 px-2.5 gap-2.5" : "h-10 w-10 mx-auto justify-center",
                                            isActive
                                                ? "bg-[var(--bg-active)] text-[var(--text-primary)]"
                                                : "text-[var(--text-secondary)] hover:bg-[var(--bg-active)]/50 hover:text-[var(--text-primary)]"
                                        )
                                    }
                                    title={expanded ? undefined : item.label}
                                >
                                    {({ isActive }) => (
                                        <>
                                            <item.icon className={cn("shrink-0 transition-colors", expanded ? "w-[15px] h-[15px]" : "w-5 h-5")} />
                                            {expanded && (
                                                <span className="text-[13px] font-normal truncate flex-1 transition-colors">{item.label}</span>
                                            )}
                                            {badge != null && (
                                                <span
                                                    className="flex items-center justify-center font-medium tabular-nums rounded-full absolute top-1.5 right-2"
                                                    style={{
                                                        backgroundColor: 'rgba(255, 255, 255, 0.1)',
                                                        color: '#A1A1AA',
                                                        fontSize: '10px',
                                                        padding: expanded ? '0 5px' : '0 4px',
                                                        height: expanded ? '18px' : '14px',
                                                        minWidth: expanded ? '18px' : '14px',
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
                    </div>

                    {expanded && (
                        <>
                            <div className="mb-1.5 px-2.5 mt-2 flex items-center justify-between">
                                <span className="text-[12px] font-medium text-[var(--text-secondary)]/70">
                                    Sources
                                </span>
                            </div>

                            {connectorItems.length === 0 ? (
                                <div
                                    className="px-2.5 py-2 text-[12px] text-[var(--text-secondary)]/70"
                                >
                                    No active sources
                                </div>
                            ) : (
                                <div className="flex flex-col gap-0.5 mb-4">
                                    {connectorItems.map((conn) => {
                                        const isActive = window.location.pathname + window.location.search === conn.path;
                                        
                                        return (
                                            <div
                                                key={conn.id}
                                                onClick={() => navigate(conn.path)}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter' || e.key === ' ') {
                                                        e.preventDefault();
                                                        navigate(conn.path);
                                                    }
                                                }}
                                                role="button"
                                                tabIndex={0}
                                                className={cn(
                                                    "relative flex items-center h-8 px-2.5 gap-2.5 w-full text-left rounded-md transition-all duration-200 cursor-pointer border border-transparent group",
                                                    isActive
                                                        ? "bg-[var(--bg-active)] text-[var(--text-primary)]"
                                                        : "text-[var(--text-secondary)] hover:bg-[var(--bg-active)]/50 hover:text-[var(--text-primary)]"
                                                )}
                                            >
                                                <conn.icon 
                                                    className="shrink-0 transition-colors"
                                                    size={15} 
                                                />

                                                <div className="flex-1 min-w-0 flex items-center justify-between gap-2">
                                                    <span 
                                                        className="text-[13px] font-normal truncate min-w-0 transition-colors"
                                                    >
                                                        {conn.name}
                                                    </span>
                                                    <div className="relative flex h-1.5 w-1.5 items-center justify-center shrink-0">
                                                        {conn.status === 'active' && (
                                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-40"></span>
                                                        )}
                                                        <span
                                                            className={cn(
                                                                "relative inline-flex rounded-full h-1.5 w-1.5 shrink-0",
                                                                conn.status === 'active'
                                                                    ? 'bg-emerald-500'
                                                                    : 'bg-amber-500'
                                                            )}
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}

                            <div className="mb-1.5 px-2.5 mt-2 flex items-center justify-between">
                                <span className="text-[12px] font-medium text-[var(--text-secondary)]/70">
                                    Recent Chats
                                </span>
                            </div>

                            {recentChats.length === 0 ? (
                                <div
                                    className="px-2.5 py-2 text-[12px] text-[var(--text-secondary)]/70"
                                >
                                    No recent chats
                                </div>
                            ) : (
                                <div className="flex flex-col gap-0.5">
                                    {recentChats.map((chat) => {
                                        const isActive = currentConversationId === chat.id;
                                        return (
                                            <div
                                                key={chat.id}
                                                onClick={() => openConversation(chat.id, chat.datasetId)}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter' || e.key === ' ') {
                                                        e.preventDefault();
                                                        openConversation(chat.id, chat.datasetId);
                                                    }
                                                }}
                                                role="button"
                                                tabIndex={0}
                                                className={cn(
                                                    "group w-full text-left rounded-md px-2.5 h-8 transition-all duration-200 flex items-center justify-between gap-2 border border-transparent",
                                                    isActive
                                                        ? "bg-[var(--bg-active)] text-[var(--text-primary)]"
                                                        : "text-[var(--text-secondary)] hover:bg-[var(--bg-active)]/50 hover:text-[var(--text-primary)]"
                                                )}
                                                style={{ cursor: 'pointer' }}
                                            >
                                                <div className="flex-1 min-w-0">
                                                    <div className="text-[13px] font-normal truncate transition-colors">
                                                        {chat.title}
                                                    </div>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        const { clearConversation } = useChatStore.getState();
                                                        clearConversation(chat.id);
                                                    }}
                                                    className="p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500/20 hover:text-red-400"
                                                    title="Delete task"
                                                    style={{ flexShrink: 0 }}
                                                >
                                                    <Trash2 size={12} />
                                                </button>
                                            </div>
                                        );
                                    })}

                                    <button
                                        type="button"
                                        onClick={() => setShowHistoryModal(true)}
                                        className="w-full flex items-center justify-start gap-2.5 rounded-md px-2.5 h-8 text-[13px] font-normal text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-active)]/50 hover:text-[var(--text-primary)]"
                                    >
                                        <History className="w-[15px] h-[15px]" />
                                        View All
                                    </button>
                                </div>
                            )}
                        </>
                    )}
                </nav>

                <div
                    className={cn(
                        "mt-auto flex flex-col transition-all duration-500",
                        expanded ? "p-3" : "p-2 items-center pb-6"
                    )}
                >
                    <ProfileDropdown
                        expanded={expanded}
                        data={{
                            name: user?.full_name || user?.username || 'User',
                            email: user?.email || 'user@signal.ai',
                            avatar: user?.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.full_name || user?.username || 'User')}&background=6366f1&color=fff`,
                            subscription: user?.subscription || 'GUEST',
                            model: 'Gemini 2.0 Flash'
                        }}
                        onLogout={() => {
                            logout();
                            navigate('/login');
                        }}
                    />
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
