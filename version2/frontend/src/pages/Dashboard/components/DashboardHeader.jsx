import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../../store/authStore';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { 
    Database, 
    ShieldCheck,
    Clock,
    Activity,
    Camera,
    History,
    RotateCcw,
    Trash2,
} from 'lucide-react';
import useDashboardActionStore from '../../../store/dashboardActionStore';

const MotionDiv = motion.div;

const DashboardHeader = ({
    selectedDataset,
    domainInfo,
    qualityMetrics,
    dashboardLoading,
    artifactPreparing,
    dashboardArtifactStatus,
    MAX_REDESIGNS,
    lastUpdatedAt,
    insightsSummary,
}) => {
    const { user } = useAuth();

    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 18) return 'Good afternoon';
        return 'Good evening';
    };

    const userName = user?.username || user?.full_name || 'there';
    
    // Clean up dataset name (remove common repeats and extensions)
    const cleanName = selectedDataset?.name 
        ? selectedDataset.name.split(' - ')[0].replace(/\.[^/.]+$/, "")
        : 'Dataset';

    const formattedUpdatedAt = lastUpdatedAt
        ? new Date(lastUpdatedAt).toLocaleString([], { hour: '2-digit', minute: '2-digit' })
        : '—';

    const datasetId = selectedDataset?.id || selectedDataset?._id;
    const {
        snapshots,
        showSnapshots,
        setShowSnapshots,
        loadSnapshots,
        saveSnapshot,
        restoreSnapshot,
        deleteSnapshot,
    } = useDashboardActionStore();
    const [snapshotName, setSnapshotName] = useState('');
    const [savingSnapshot, setSavingSnapshot] = useState(false);
    const snapshotInputRef = useRef(null);

    useEffect(() => {
        if (showSnapshots && datasetId) {
            loadSnapshots(datasetId);
        }
    }, [showSnapshots, datasetId, loadSnapshots]);

    const handleSaveSnapshot = async () => {
        if (!snapshotName.trim() || !datasetId) return;
        setSavingSnapshot(true);
        const success = await saveSnapshot(datasetId, snapshotName);
        setSavingSnapshot(false);
        if (success) {
            setSnapshotName('');
            toast.success('📸 Layout snapshot saved!', {
                duration: 2500,
                style: { background: '#1e293b', color: '#e2e8f0', border: '1px solid rgba(16, 185, 129, 0.3)' },
            });
        } else {
            toast.error('Failed to save snapshot');
        }
    };

    const handleRestoreSnapshot = async (snapshotId) => {
        if (!datasetId) return;
        const layout = await restoreSnapshot(datasetId, snapshotId);
        if (layout) {
            toast.success('Layout restored from snapshot');
            setShowSnapshots(false);
            // Trigger page reload to re-render with restored layout
            window.location.reload();
        }
    };

    const handleDeleteSnapshot = async (snapshotId) => {
        if (!datasetId) return;
        const success = await deleteSnapshot(datasetId, snapshotId);
        if (success) {
            toast.success('Snapshot deleted');
        }
    };

    return (
        <MotionDiv
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col md:flex-row md:items-center justify-between gap-6"
        >
            <div className="space-y-4">
                {/* Greeting Section */}
                <div className="space-y-2">
                    <h1 className="text-5xl font-black tracking-tight text-header">
                        {getGreeting()}, <span className="text-muted">{userName}.</span>
                    </h1>
                </div>

                {/* Meta Strip - Clean & Editorial */}
                <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] font-medium">
                    <div className="flex items-center gap-2 text-header">
                        <span className="opacity-40">Dataset:</span>
                        <span className="font-bold">{cleanName}</span>
                    </div>

                    <div className="flex items-center gap-2 text-muted border-l border-white/10 pl-5">
                        <Database className="w-3.5 h-3.5 opacity-50" />
                        <span className="tabular-nums">
                            {(selectedDataset?.row_count || 0).toLocaleString()} 
                            <span className="ml-1 opacity-60">Rows</span>
                        </span>
                    </div>

                    {selectedDataset?.metadata?.data_quality?.data_cleaning_applied && (
                        <div className="flex items-center gap-2 text-emerald-400/90 border-l border-white/10 pl-5">
                            <ShieldCheck className="w-3.5 h-3.5" />
                            <span>Verified Schema</span>
                        </div>
                    )}

                    {domainInfo?.domain && (
                        <div className="flex items-center gap-2 text-muted border-l border-white/10 pl-5">
                            <span className="opacity-40">Domain:</span>
                            <span className="text-header/80">{domainInfo.domain}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Right Side: Status + Snapshot Controls */}
            <div className="flex items-center gap-6 pb-1">
                {/* Snapshots Button & Dropdown */}
                <div className="relative">
                    <button
                        onClick={() => setShowSnapshots(!showSnapshots)}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all"
                        style={{
                            color: showSnapshots ? 'var(--accent-primary)' : 'var(--text-secondary)',
                            border: `1px solid ${showSnapshots ? 'var(--accent-primary)' : 'var(--border)'}`,
                            background: showSnapshots ? 'var(--accent-primary-light)' : 'transparent',
                        }}
                        title="Layout snapshots"
                    >
                        <Camera className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Snapshots</span>
                        {snapshots.length > 0 && (
                            <span className="ml-1 px-1 py-0.5 rounded text-[10px] font-bold tabular-nums"
                                style={{ background: 'var(--accent-primary-light)', color: 'var(--accent-primary)' }}>
                                {snapshots.length}
                            </span>
                        )}
                    </button>

                    <AnimatePresence>
                        {showSnapshots && (
                            <motion.div
                                initial={{ opacity: 0, y: 8, scale: 0.96 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: 8, scale: 0.96 }}
                                transition={{ duration: 0.15, ease: 'easeOut' }}
                                className="absolute right-0 mt-2 w-72 rounded-xl overflow-hidden z-50 shadow-2xl"
                                style={{
                                    background: 'var(--bg-elevated)',
                                    border: '1px solid var(--border)',
                                }}
                            >
                                {/* Save new snapshot */}
                                <div className="p-3 border-b" style={{ borderColor: 'var(--border)' }}>
                                    <p className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-secondary)' }}>
                                        Save Current Layout
                                    </p>
                                    <div className="flex items-center gap-2">
                                        <input
                                            ref={snapshotInputRef}
                                            type="text"
                                            value={snapshotName}
                                            onChange={(e) => setSnapshotName(e.target.value)}
                                            placeholder="Snapshot name..."
                                            className="flex-1 px-2.5 py-1.5 rounded-lg text-xs font-medium outline-none transition-all"
                                            style={{
                                                background: 'var(--bg-primary)',
                                                color: 'var(--text-primary)',
                                                border: '1px solid var(--border)',
                                            }}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') handleSaveSnapshot();
                                            }}
                                        />
                                        <button
                                            onClick={handleSaveSnapshot}
                                            disabled={savingSnapshot || !snapshotName.trim()}
                                            className="p-1.5 rounded-lg transition-all"
                                            style={{
                                                background: 'var(--accent-primary)',
                                                color: '#fff',
                                                opacity: savingSnapshot || !snapshotName.trim() ? 0.5 : 1,
                                            }}
                                        >
                                            {savingSnapshot ? (
                                                <Activity className="w-3.5 h-3.5 animate-spin" />
                                            ) : (
                                                <Camera className="w-3.5 h-3.5" />
                                            )}
                                        </button>
                                    </div>
                                </div>

                                {/* Snapshot list */}
                                <div className="max-h-60 overflow-y-auto">
                                    {snapshots.length === 0 ? (
                                        <div className="p-4 text-center">
                                            <History className="w-5 h-5 mx-auto mb-2" style={{ color: 'var(--text-secondary)', opacity: 0.4 }} />
                                            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                                No snapshots yet. Save your first layout to bookmark it.
                                            </p>
                                        </div>
                                    ) : (
                                        snapshots.map((snap) => (
                                            <div
                                                key={snap.id}
                                                className="flex items-center justify-between px-3 py-2.5 transition-colors hover:bg-white/5"
                                                style={{ borderBottom: '1px solid var(--border)' }}
                                            >
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-xs font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                                                        {snap.name}
                                                        {snap.is_auto && (
                                                            <span className="ml-1.5 text-[10px] font-normal" style={{ color: 'var(--text-secondary)' }}>
                                                                (auto)
                                                            </span>
                                                        )}
                                                    </p>
                                                    <p className="text-[10px] mt-0.5 font-mono" style={{ color: 'var(--text-secondary)' }}>
                                                        {new Date(snap.created_at).toLocaleString()}
                                                    </p>
                                                </div>
                                                <div className="flex items-center gap-1 ml-2">
                                                    <button
                                                        onClick={() => handleRestoreSnapshot(snap.id)}
                                                        className="p-1.5 rounded-lg transition-all hover:bg-white/10"
                                                        title="Restore this snapshot"
                                                    >
                                                        <RotateCcw className="w-3 h-3" style={{ color: 'var(--accent-primary)' }} />
                                                    </button>
                                                    <button
                                                        onClick={() => handleDeleteSnapshot(snap.id)}
                                                        className="p-1.5 rounded-lg transition-all hover:bg-white/10"
                                                        title="Delete snapshot"
                                                    >
                                                        <Trash2 className="w-3 h-3" style={{ color: '#ef4444' }} />
                                                    </button>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                <div className="flex flex-col items-end">
                    <span className="text-[10px] uppercase tracking-[0.2em] text-muted font-black">Sync Status</span>
                    <div className="flex items-center gap-2 mt-0.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse" />
                        <span className="text-xs font-bold text-header uppercase tracking-wider">Ready</span>
                    </div>
                </div>

                <div className="w-px h-8 bg-white/10" />

                <div className="flex flex-col items-end">
                    <span className="text-[10px] uppercase tracking-[0.2em] text-muted font-black">Refreshed</span>
                    <div className="flex items-center gap-2 mt-0.5">
                        <Clock className="w-3 h-3 text-muted" />
                        <span className="text-xs font-mono font-bold text-header">{formattedUpdatedAt}</span>
                    </div>
                </div>
            </div>
        </MotionDiv>
    );
};

export default DashboardHeader;
