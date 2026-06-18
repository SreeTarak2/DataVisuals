"use client";
import { useToaster, toast } from "react-hot-toast";
import { X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

function DefaultIcon({ type }) {
  switch (type) {
    case "success":
      return <CheckCircle2 size={18} color="#10b981" strokeWidth={2} />;
    case "error":
      return <AlertCircle size={18} color="#ef4444" strokeWidth={2} />;
    case "loading":
      return (
        <Loader2
          size={18}
          color="var(--accent-primary, #3b82f6)"
          strokeWidth={2}
          style={{
            animation: "loadingSpin 1s linear infinite",
          }}
        />
      );
    default:
      return null;
  }
}

export function CustomToaster() {
  const { toasts, handlers } = useToaster();
  const { startPause, endPause } = handlers;

  return (
    <>
      <style>{`
        @keyframes loadingSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    <div
      style={{
        position: "fixed",
        zIndex: 9999,
        bottom: 32,
        right: 32,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        maxWidth: 400,
        pointerEvents: "none",
      }}
      onMouseEnter={startPause}
      onMouseLeave={endPause}
    >
      {toasts.map((t) => {
        const isVisible = t.visible;

        return (
          <div
            key={t.id}
            ref={(el) => {
              if (el && t.height !== el.offsetHeight) {
                handlers.updateHeight(t.id, el.offsetHeight);
              }
            }}
            style={{
              position: "relative",
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              background: "var(--bg-elevated, var(--bg-surface, #18181b))",
              color: "var(--text-header, #fafafa)",
              border: "1px solid var(--border, #27272a)",
              boxShadow:
                "0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3)",
              borderRadius: 12,
              padding: "12px 14px",
              fontSize: 14,
              fontWeight: 500,
              letterSpacing: "0.01em",
              lineHeight: 1.4,
              pointerEvents: "auto",
              transition: "all 0.2s ease",
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? "translateY(0)" : "translateY(8px)",
              width: "100%",
            }}
          >
            {/* Icon */}
            <span
              style={{
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                marginTop: 1,
              }}
            >
              {t.icon || <DefaultIcon type={t.type} />}
            </span>

            {/* Message */}
            <span style={{ flex: 1, minWidth: 0 }}>{t.message}</span>

            {/* Close button */}
            <button
              onClick={() => {
                toast.dismiss(t.id);
              }}
              style={{
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 22,
                height: 22,
                border: "none",
                background: "transparent",
                color: "var(--text-muted, #a1a1aa)",
                borderRadius: 6,
                cursor: "pointer",
                transition: "all 0.15s ease",
                marginTop: -1,
                marginRight: -4,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.1)";
                e.currentTarget.style.color = "#fafafa";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = "var(--text-muted, #a1a1aa)";
              }}
              aria-label="Dismiss notification"
            >
              <X size={14} strokeWidth={2} />
            </button>
          </div>
        );
      })}
    </div>
    </>
  );
}
