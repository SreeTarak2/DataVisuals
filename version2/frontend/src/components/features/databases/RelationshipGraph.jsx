import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Loader2, ZoomIn, ZoomOut, RefreshCw, Info, Table, ArrowRight } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { databaseAPI } from '../../../services/api';

// ─── Color palette for table nodes ──────────────────────────────────────────

const TABLE_COLORS = [
  { bg: 'rgba(249, 115, 22, 0.12)', border: 'rgba(249, 115, 22, 0.4)',  text: '#fb923c' },  // orange
  { bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.4)',  text: '#60a5fa' },  // blue
  { bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.4)',  text: '#34d399' },  // emerald
  { bg: 'rgba(168, 85, 247, 0.12)', border: 'rgba(168, 85, 247, 0.4)',  text: '#a78bfa' },  // purple
  { bg: 'rgba(236, 72, 153, 0.12)', border: 'rgba(236, 72, 153, 0.4)',  text: '#f472b6' },  // pink
  { bg: 'rgba(234, 179, 8, 0.12)',  border: 'rgba(234, 179, 8, 0.4)',   text: '#fbbf24' },  // yellow
  { bg: 'rgba(20, 184, 166, 0.12)', border: 'rgba(20, 184, 166, 0.4)',  text: '#2dd4bf' },  // teal
  { bg: 'rgba(239, 68, 68, 0.12)',  border: 'rgba(239, 68, 68, 0.4)',   text: '#f87171' },  // red
];

const DIM_COLORS = { bg: 'rgba(255,255,255,0.03)', border: 'rgba(255,255,255,0.06)', text: 'rgba(255,255,255,0.25)' };

// ─── Layout engine ──────────────────────────────────────────────────────────

function computeLayout(tables, foreignKeys) {
  // Simple radial layout: place tables in a circle
  const nodes = [];
  const centerX = 400, centerY = 300;
  const radius = Math.min(centerX, centerY) - 100;
  const count = tables.length;

  tables.forEach((table, i) => {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2;
    nodes.push({
      id: table,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    });
  });

  return nodes;
}

// ─── Main Component ─────────────────────────────────────────────────────────

const RelationshipGraph = ({ connId, isDark }) => {
  const [foreignKeys, setForeignKeys] = useState([]);
  const [inferred, setInferred] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [hoveredEdge, setHoveredEdge] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [cached, setCached] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [showInferred, setShowInferred] = useState(true);
  const svgRef = useRef(null);
  const dragStart = useRef(null);

  const fetchForeignKeys = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await databaseAPI.getForeignKeys(connId, refresh);
      const fks = data.foreign_keys || [];
      const infra = data.inferred || [];
      setForeignKeys(fks);
      setInferred(infra);
      setCached(data.cached || false);

      // Collect unique table names from both declared FKs and inferred
      const tableSet = new Set();
      fks.forEach(fk => {
        tableSet.add(fk.table_name);
        tableSet.add(fk.referenced_table);
      });
      infra.forEach(ir => {
        tableSet.add(ir.source_table);
        tableSet.add(ir.target_table);
      });
      const tables = Array.from(tableSet).sort();
      setNodes(computeLayout(tables, fks));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load foreign keys');
    } finally {
      setLoading(false);
    }
  }, [connId]);

  useEffect(() => {
    if (connId) fetchForeignKeys();
  }, [connId, fetchForeignKeys]);

  // ── Drag handling ─────────────────────────────────────────────────────────

  const handleMouseDown = useCallback((nodeId, e) => {
    e.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    setDragging(nodeId);
    dragStart.current = {
      nodeId,
      offsetX: e.clientX - rect.left,
      offsetY: e.clientY - rect.top,
      nodeX: nodes.find(n => n.id === nodeId)?.x || 0,
      nodeY: nodes.find(n => n.id === nodeId)?.y || 0,
    };
  }, [nodes]);

  const handleMouseMove = useCallback((e) => {
    if (!dragging || !dragStart.current) return;
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const dx = (e.clientX - rect.left - dragStart.current.offsetX) / zoom;
    const dy = (e.clientY - rect.top - dragStart.current.offsetY) / zoom;

    setNodes(prev => prev.map(n =>
      n.id === dragging
        ? { ...n, x: dragStart.current.nodeX + dx, y: dragStart.current.nodeY + dy }
        : n
    ));
  }, [dragging, zoom]);

  const handleMouseUp = useCallback(() => {
    setDragging(null);
    dragStart.current = null;
  }, []);

  // ── Zoom handlers ─────────────────────────────────────────────────────────

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 3));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.3));
  const handleReset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  // ── Derived data ──────────────────────────────────────────────────────────

  const nodeWidth = 140;
  const nodeHeight = 44;
  const tableColorMap = {};
  nodes.forEach((n, i) => {
    tableColorMap[n.id] = TABLE_COLORS[i % TABLE_COLORS.length];
  });

  // Helper: compute edge endpoint positions from node centers
  const computeEdge = (sourceId, targetId, label, isInferred, i) => {
    const source = nodes.find(n => n.id === sourceId);
    const target = nodes.find(n => n.id === targetId);
    if (!source || !target) return null;

    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const nx = dx / dist;
    const ny = dy / dist;

    const hw = nodeWidth / 2 + 12;
    const hh = nodeHeight / 2 + 12;
    const startX = source.x + nx * Math.min(hw, hh / Math.abs(ny || 0.01) * Math.abs(nx || 0.01));
    const startY = source.y + ny * Math.min(hh, hw / Math.abs(nx || 0.01) * Math.abs(ny || 0.01));
    const endX = target.x - nx * Math.min(hw, hh / Math.abs(ny || 0.01) * Math.abs(nx || 0.01));
    const endY = target.y - ny * Math.min(hh, hw / Math.abs(nx || 0.01) * Math.abs(ny || 0.01));

    const midX = (startX + endX) / 2;
    const midY = (startY + endY) / 2;

    return {
      key: isInferred ? `inferred-edge-${i}` : `fk-edge-${i}`,
      sourceId,
      targetId,
      label,
      startX, startY, endX, endY, midX, midY,
      isInferred,
    };
  };

  // Build FK edges (declared foreign keys, solid lines)
  const fkEdges = foreignKeys.map((fk, i) =>
    computeEdge(fk.table_name, fk.referenced_table, `${fk.column_name} → ${fk.referenced_column}`, false, i)
  ).filter(Boolean);

  // Build inferred edges (cross-dataset, dashed lines)
  const inferredEdges = (showInferred ? inferred : []).map((ir, i) =>
    computeEdge(ir.source_table, ir.target_table, `${ir.source_column} → ${ir.target_column}`, true, i)
  ).filter(Boolean);

  const edges = [...fkEdges, ...inferredEdges];

  const edgeMarkerId = 'fk-arrowhead';

  // ── Render State ──────────────────────────────────────────────────────────

  if (!connId) return null;

  if (loading) {
    return (
      <div className={cn(
        "flex flex-col items-center justify-center py-16 gap-4 rounded-2xl border",
        isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
      )}>
        <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
        <p className={cn("text-xs font-semibold", isDark ? "text-gray-500" : "text-gray-400")}>
          Discovering relationships...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn(
        "flex flex-col items-center justify-center py-12 gap-3 rounded-2xl border",
        isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
      )}>
        <p className={cn("text-xs text-center px-8", isDark ? "text-red-400" : "text-red-500")}>
          {error}
        </p>
        <button
          type="button"
          onClick={() => fetchForeignKeys(true)}
          className="flex items-center gap-1.5 text-[11px] font-semibold text-orange-500 hover:text-orange-400 transition-colors cursor-pointer"
        >
          <RefreshCw size={12} />
          Retry
        </button>
      </div>
    );
  }

  if (foreignKeys.length === 0 && inferred.length === 0) {
    return (
      <div className={cn(
        "rounded-2xl border p-6",
        isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
      )}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-orange-500" />
            <h3 className={cn("text-xs font-bold uppercase tracking-wider", isDark ? "text-gray-300" : "text-gray-700")}>
              Table Relationships
            </h3>
          </div>
          <button
            type="button"
            onClick={() => fetchForeignKeys(true)}
            className="flex items-center gap-1.5 text-[10px] font-semibold text-orange-500 hover:text-orange-400 transition-colors cursor-pointer"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>
        <div className="flex flex-col items-center justify-center py-10 gap-3">
          <Table size={28} className={isDark ? "text-gray-600" : "text-gray-300"} />
          <p className={cn("text-xs text-center", isDark ? "text-gray-500" : "text-gray-400")}>
            No foreign key constraints detected.
          </p>
          <p className={cn("text-[10px] text-center max-w-sm", isDark ? "text-gray-600" : "text-gray-400")}>
        No foreign key constraints or inferred relationships found. Foreign keys must be declared at the
        database level, or extract multiple tables from this connection for cross-dataset inference.
      </p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      "rounded-2xl border overflow-hidden",
      isDark ? "bg-[#131316] border-white/[0.04]" : "bg-white border-gray-200"
    )}>
      {/* Header */}
      <div className={cn(
        "flex items-center justify-between px-5 py-3 border-b",
        isDark ? "border-white/[0.04]" : "border-gray-100"
      )}>
        <div className="flex items-center gap-2.5">
          <div className="w-1.5 h-1.5 rounded-full bg-orange-500" />
          <h3 className={cn("text-xs font-bold uppercase tracking-wider", isDark ? "text-gray-300" : "text-gray-700")}>
            Table Relationships
          </h3>
          <span className={cn(
            "text-[10px] font-semibold px-1.5 py-0.5 rounded",
            isDark ? "bg-white/[0.04] text-gray-500" : "bg-gray-100 text-gray-500"
          )}>
            {foreignKeys.length} FK{foreignKeys.length !== 1 ? 's' : ''}
          </span>
          {inferred.length > 0 && (
            <span className={cn(
              "text-[10px] font-semibold px-1.5 py-0.5 rounded",
              isDark ? "bg-purple-500/10 text-purple-400" : "bg-purple-100 text-purple-600"
            )}>
              {inferred.length} inferred
            </span>
          )}
          {cached && (
            <span className="flex items-center gap-1 text-[9px] text-orange-500/60 font-semibold">
              <Info size={10} />
              Cached
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {inferred.length > 0 && (
            <button
              type="button"
              onClick={() => setShowInferred(prev => !prev)}
              className={cn(
                "text-[10px] font-semibold px-2 py-1 rounded-lg transition-colors cursor-pointer",
                showInferred
                  ? (isDark ? "bg-purple-500/15 text-purple-400" : "bg-purple-100 text-purple-600")
                  : (isDark ? "bg-white/[0.04] text-gray-500" : "bg-gray-100 text-gray-500")
              )}
              title="Toggle inferred relationships"
            >
              {showInferred ? 'Hide inferred' : 'Show inferred'}
            </button>
          )}
          <button
            type="button"
            onClick={() => fetchForeignKeys(true)}
            className={cn(
              "p-1.5 rounded-lg transition-colors cursor-pointer",
              isDark ? "hover:bg-white/[0.06] text-gray-500 hover:text-gray-300" : "hover:bg-gray-100 text-gray-400 hover:text-gray-600"
            )}
            title="Re-query live database"
          >
            <RefreshCw size={14} />
          </button>
          <button
            type="button"
            onClick={handleZoomIn}
            className={cn(
              "p-1.5 rounded-lg transition-colors cursor-pointer",
              isDark ? "hover:bg-white/[0.06] text-gray-500 hover:text-gray-300" : "hover:bg-gray-100 text-gray-400 hover:text-gray-600"
            )}
            title="Zoom in"
          >
            <ZoomIn size={14} />
          </button>
          <button
            type="button"
            onClick={handleZoomOut}
            className={cn(
              "p-1.5 rounded-lg transition-colors cursor-pointer",
              isDark ? "hover:bg-white/[0.06] text-gray-500 hover:text-gray-300" : "hover:bg-gray-100 text-gray-400 hover:text-gray-600"
            )}
            title="Zoom out"
          >
            <ZoomOut size={14} />
          </button>
          <span className={cn(
            "text-[10px] font-mono min-w-[36px] text-center",
            isDark ? "text-gray-600" : "text-gray-400"
          )}>
            {Math.round(zoom * 100)}%
          </span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div
        className="relative"
        style={{ width: '100%', height: 420, overflow: 'hidden' }}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          viewBox={`${-pan.x} ${-pan.y} ${800 / zoom} ${600 / zoom}`}
          className="w-full h-full"
          style={{ cursor: dragging ? 'grabbing' : 'grab' }}
        >
          {/* Arrow marker */}
          <defs>
            <marker
              id={edgeMarkerId}
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill={isDark ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)'} />
            </marker>
            <marker
              id={`${edgeMarkerId}-hover`}
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#f97316" />
            </marker>
            <marker
              id={`${edgeMarkerId}-inferred`}
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill={isDark ? 'rgba(168, 85, 247, 0.4)' : 'rgba(168, 85, 247, 0.4)'} />
            </marker>
            <marker
              id={`${edgeMarkerId}-inferred-hover`}
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#a78bfa" />
            </marker>
          </defs>

          {/* Background grid */}
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke={isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.03)'} strokeWidth="0.5" />
          </pattern>
          <rect width="800" height="600" fill="url(#grid)" />

          {/* Edges */}
          {edges.map(edge => {
            const isHighlighted = hoveredEdge === edge.key || hoveredNode === edge.sourceId || hoveredNode === edge.targetId;
            const strokeColor = isHighlighted
              ? (edge.isInferred ? '#a78bfa' : '#f97316')
              : (edge.isInferred
                  ? (isDark ? 'rgba(168, 85, 247, 0.3)' : 'rgba(168, 85, 247, 0.3)')
                  : (isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)'))
            const strokeW = isHighlighted ? 2.5 : (edge.isInferred ? 1.8 : 1.5);
            const dashArray = edge.isInferred ? '6,4' : 'none';
            const markerId = edge.isInferred
              ? (isHighlighted ? `${edgeMarkerId}-inferred-hover` : `${edgeMarkerId}-inferred`)
              : (isHighlighted ? `${edgeMarkerId}-hover` : `${edgeMarkerId}`);
            const labelColor = edge.isInferred ? '#a78bfa' : '#f97316';

            return (
              <g key={edge.key}>
                {/* Edge line */}
                <line
                  x1={edge.startX}
                  y1={edge.startY}
                  x2={edge.endX}
                  y2={edge.endY}
                  stroke={strokeColor}
                  strokeWidth={strokeW}
                  strokeDasharray={dashArray}
                  markerEnd={`url(#${markerId})`}
                  style={{ transition: 'stroke 0.15s, stroke-width 0.15s' }}
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredEdge(edge.key)}
                  onMouseLeave={() => setHoveredEdge(null)}
                />
                {/* Edge label (visible on hover) */}
                {isHighlighted && (
                  <g>
                    <rect
                      x={edge.midX - 65}
                      y={edge.midY - 12}
                      width={130}
                      height={24}
                      rx={4}
                      fill={isDark ? '#1c1c1f' : '#fff'}
                      stroke={labelColor}
                      strokeWidth={1}
                      opacity={0.95}
                    />
                    <text
                      x={edge.midX}
                      y={edge.midY + 4}
                      textAnchor="middle"
                      fill={labelColor}
                      fontSize={9}
                      fontWeight={600}
                      fontFamily="monospace"
                    >
                      {edge.label}
                    </text>
                    {edge.isInferred && (
                      <text
                        x={edge.midX}
                        y={edge.midY - 4}
                        textAnchor="middle"
                        fill={labelColor}
                        fontSize={7}
                        fontWeight={700}
                        fontFamily="system-ui, sans-serif"
                        opacity={0.7}
                      >
                        INFERRED
                      </text>
                    )}
                  </g>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map(node => {
            const color = tableColorMap[node.id] || DIM_COLORS;
            const isHighlighted = hoveredNode === node.id;
            const hasEdges = edges.some(e => e.sourceId === node.id || e.targetId === node.id);

            return (
              <g
                key={node.id}
                transform={`translate(${node.x - nodeWidth / 2}, ${node.y - nodeHeight / 2})`}
                onMouseDown={(e) => handleMouseDown(node.id, e)}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                style={{ cursor: 'move' }}
              >
                {/* Node shadow */}
                {isHighlighted && (
                  <rect
                    x={-3}
                    y={-3}
                    width={nodeWidth + 6}
                    height={nodeHeight + 6}
                    rx={10}
                    fill="none"
                    stroke="rgba(249, 115, 22, 0.3)"
                    strokeWidth={2}
                    opacity={0.6}
                  />
                )}
                {/* Node background */}
                <rect
                  width={nodeWidth}
                  height={nodeHeight}
                  rx={8}
                  fill={isHighlighted ? 'rgba(249, 115, 22, 0.15)' : color.bg}
                  stroke={isHighlighted ? '#f97316' : color.border}
                  strokeWidth={isHighlighted ? 2 : 1}
                  style={{ transition: 'fill 0.15s, stroke 0.15s' }}
                />
                {/* Node icon + label */}
                <g transform={`translate(12, ${nodeHeight / 2})`}>
                  <Table
                    size={14}
                    color={color.text}
                    style={{ display: 'block' }}
                  />
                </g>
                <text
                  x={34}
                  y={nodeHeight / 2 + 4}
                  fill={isHighlighted ? '#f97316' : color.text}
                  fontSize={11}
                  fontWeight={600}
                  fontFamily="system-ui, sans-serif"
                  style={{ transition: 'fill 0.15s' }}
                >
                  {node.id.length > 22 ? node.id.substring(0, 20) + '…' : node.id}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Empty state overlay for no edges */}
        {edges.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <p className={cn("text-[11px] font-semibold", isDark ? "text-gray-600" : "text-gray-400")}>
              No relationships between {nodes.length} tables
            </p>
          </div>
        )}
      </div>

      {/* Footer: Legend */}
      <div className={cn(
        "flex items-center justify-between px-5 py-2.5 border-t text-[10px]",
        isDark ? "border-white/[0.04] text-gray-500" : "border-gray-100 text-gray-400"
      )}>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-px inline-block bg-current opacity-40" />
            Foreign Key
          </span>
          {inferred.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-px inline-block" style={{ background: isDark ? 'rgba(168, 85, 247, 0.4)' : 'rgba(168, 85, 247, 0.5)', borderTop: 'dashed 1px' }} />
              <span className="ml-0.5">Inferred</span>
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded inline-block" style={{ background: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.06)', border: isDark ? '1px solid rgba(255,255,255,0.15)' : '1px solid rgba(0,0,0,0.1)' }} />
            Table
          </span>
        </div>
        <p className="opacity-60">
          Hover to highlight · Drag to rearrange
        </p>
      </div>
    </div>
  );
};

export default RelationshipGraph;
