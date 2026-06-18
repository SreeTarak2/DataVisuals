import React, { useState, useRef, useEffect, useCallback, forwardRef, createContext, useContext, useId } from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ArrowUp, Paperclip, Square, X, Loader2, Sparkles, Command, Search, Brain, Zap } from "lucide-react";
import { motion, AnimatePresence, useMotionTemplate, useMotionValue } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * 🌠 Celestial Observer Design System
 * ---------------------------------
 * Principles:
 * 1. Smart Surface: Every interface element is a "lens" or "surface" with depth.
 * 2. Ambient Intelligence: Subtle glows and shadows indicate activity and state.
 * 3. Editorial Grade: Sharp edges, premium typography, and intentional spacing.
 */

// Premium motion presets
const premiumMotion = {
  spring: { type: 'spring', stiffness: 200, damping: 20, mass: 1 },
  springGentle: { type: 'spring', stiffness: 100, damping: 15, mass: 1 },
  easing: [0.32, 0.72, 0, 1],
  easingBounce: [0.34, 1.56, 0.64, 1],
};

// Tooltip Components
const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;
const TooltipContent = forwardRef(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] backdrop-blur-md px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-[var(--text-primary)] shadow-xl animate-in fade-in-0 zoom-in-95",
        className
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

// Dialog Components
const Dialog = DialogPrimitive.Root;
const DialogPortal = DialogPrimitive.Portal;
const DialogOverlay = forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/60 backdrop-blur-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = forwardRef(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-[95vw] md:max-w-200 translate-x-[-50%] translate-y-[-50%] gap-0 border border-[var(--border)] bg-[var(--bg-surface)] backdrop-blur-2xl p-0 duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out rounded-2xl shadow-2xl",
        className
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 z-10 rounded-full bg-white/5 p-2 hover:bg-white/10 transition-all border border-[var(--border)]">
        <X className="h-4 w-4 text-[var(--text-primary)]" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogTitle = forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight text-[var(--text-primary)]", className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

// --- Redesigned Components ---

/**
 * 🛸 Smart Input Lens
 * A production-grade contenteditable with zero-jitter auto-sizing and rich placeholder logic.
 */
const SmartInputLens = forwardRef(({ className, placeholder, value, onInput, onKeyDown, onPaste, disabled, ...props }, ref) => {
  const innerRef = useRef(null);
  const [isFocused, setIsFocused] = useState(false);
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  useEffect(() => {
    if (ref) {
      if (typeof ref === 'function') ref(innerRef.current);
      else ref.current = innerRef.current;
    }
  }, [ref]);

  useEffect(() => {
    if (!innerRef.current) return;
    if (innerRef.current.innerText !== (value ?? '')) {
      innerRef.current.innerText = value ?? '';
    }
  }, [value]);

  const handleInput = (e) => {
    onInput?.({ target: { value: e.currentTarget.innerText } });
  };

  const handleMouseMove = ({ currentTarget, clientX, clientY }) => {
    const { left, top } = currentTarget.getBoundingClientRect();
    mouseX.set(clientX - left);
    mouseY.set(clientY - top);
  };

  return (
    <div 
      className="relative group/input"
      onMouseMove={handleMouseMove}
    >
      {/* Dynamic Glow Spotlight */}
      <motion.div
        className="pointer-events-none absolute -inset-px rounded-xl opacity-0 transition duration-300 group-focus-within/input:opacity-100"
        style={{
          background: useMotionTemplate`
            radial-gradient(
              350px circle at ${mouseX}px ${mouseY}px,
              rgba(255, 107, 0, 0.08),
              transparent 80%
            )
          `,
        }}
      />

      <div
        ref={innerRef}
        contentEditable={!disabled}
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        aria-label="Message composer"
        onInput={handleInput}
        onKeyDown={onKeyDown}
        onPaste={onPaste}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        className={cn(
          "relative w-full min-h-[44px] max-h-[300px] overflow-y-auto outline-none py-2 px-1",
          "text-[15px] leading-[26px] text-[var(--text-primary)] selection:bg-orange-500/30",
          "whitespace-pre-wrap break-words",
          "[&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:bg-white/10 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-white/20",
          disabled && "cursor-not-allowed opacity-50",
          className
        )}

        {...props}
      />

      <AnimatePresence>
        {(!value || value.trim() === "") && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute left-1 top-2 pointer-events-none text-[var(--text-muted)] text-[15px]"
          >
            {placeholder || "Type a message..."}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

/**
 * 🛠️ Mode Selector (Smart Surface Indicators)
 */
const ModeIndicator = ({ active, icon: Icon, label, color = "p2-cyan" }) => (
  <motion.div
    initial={false}
    animate={{ 
      opacity: active ? 1 : 0.3,
      scale: active ? 1 : 0.95,
      color: active ? `var(--${color})` : 'var(--p2-slate)'
    }}
    className={cn(
      "flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest transition-all duration-300",
      active ? `bg-${color}/10 border border-${color}/20 shadow-[0_0_10px_rgba(0,240,255,0.1)]` : "bg-transparent border border-transparent"
    )}
  >
    <Icon className="w-3 h-3" />
    <span>{label}</span>
  </motion.div>
);

/**
 * 🎨 Command Menu Stub
 */
const CommandMenu = ({ visible }) => (
  <AnimatePresence>
    {visible && (
      <motion.div
        initial={{ opacity: 0, y: 10, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.95 }}
        className="absolute bottom-full left-0 mb-4 w-64 bg-[var(--bg-surface)] backdrop-blur-xl border border-[var(--border)] rounded-xl shadow-2xl overflow-hidden z-50"
      >
        <div className="p-2 border-b border-[var(--border)] bg-white/5 flex items-center gap-2">
          <Command className="w-3.5 h-3.5 text-orange-500 dark:text-p2-amber" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-secondary)]">Quick Commands</span>
        </div>
        <div className="p-1">
          {[
            { icon: Search, label: "Search Datasets", cmd: "/search" },
            { icon: Brain, label: "Analyze Patterns", cmd: "/analyze" },
            { icon: Zap, label: "Generate SQL", cmd: "/sql" }
          ].map((item, i) => (
            <button 
              key={i}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-orange-500/10 group transition-all text-left"
            >
              <item.icon className="w-4 h-4 text-[var(--text-secondary)] group-hover:text-orange-500 transition-colors" />
              <div className="flex flex-col items-start">
                <span className="text-[12px] font-medium text-[var(--text-primary)]">{item.label}</span>
                <span className="text-[9px] text-[var(--text-muted)] font-mono">{item.cmd}</span>
              </div>
            </button>
          ))}
        </div>
      </motion.div>
    )}
  </AnimatePresence>
);

// PromptInput Context
const PromptInputContext = createContext({
  isLoading: false,
  value: "",
  setValue: () => { },
  onSubmit: undefined,
  disabled: false,
});

const usePromptInput = () => useContext(PromptInputContext);

/**
 * 🚀 Main PromptInputBox Export
 */
export const PromptInputBox = forwardRef((props, ref) => {
  const {
    onSend,
    onStop,
    isLoading = false,
    placeholder = "Ask Signal anything...",
    className,
    value: input,
    onChange: setInput,
    pendingImages = [],
    onRemoveImage,
    onAttachClick,
    onPaste,
  } = props;

  const [selectedImage, setSelectedImage] = useState(null);
  const [showCommands, setShowCommands] = useState(false);
  const containerRef = useRef(null);

  // Handle slash commands
  useEffect(() => {
    if (input.startsWith('/')) setShowCommands(true);
    else setShowCommands(false);
  }, [input]);

  const handleSubmit = () => {
    if (input.trim() || pendingImages.length > 0) {
      onSend(input);
      setShowCommands(false);
    }
  };

  const hasContent = input.trim() !== "" || pendingImages.length > 0;

  // Image Paste Handler
  const handlePasteWrapper = (e) => {
    const items = Array.from(e.clipboardData?.items ?? []);
    const imageItems = items.filter((item) => item.type.startsWith('image/'));

    if (imageItems.length > 0) {
      e.preventDefault();
      imageItems.forEach((item) => {
        const file = item.getAsFile();
        if (file) onPaste?.({ file });
      });
      return;
    }

    // Standard text paste
    e.preventDefault();
    const text = e.clipboardData?.getData('text/plain') || '';
    document.execCommand('insertText', false, text);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
      return;
    }
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
      return;
    }
  };

  return (
    <TooltipProvider>
      <div className={cn("relative w-full max-w-4xl mx-auto px-2 sm:px-4", className)}>
        <CommandMenu visible={showCommands} />

        {/* 🛸 Celestial Surface Container */}
        <motion.div
          ref={containerRef}
          layout
          className={cn(
            "relative flex flex-col w-full rounded-[20px] overflow-hidden",
            "bg-[var(--bg-surface)] backdrop-blur-xl border border-[var(--border)] shadow-lg",
            "transition-all duration-500 ease-out",
            isLoading && "border-orange-500/30 ring-1 ring-orange-500/10"
          )}
        >
          {/* Ambient Background Glow (Top Left) */}
          <div className="absolute -top-24 -left-24 w-48 h-48 bg-orange-500/5 blur-[100px] pointer-events-none" />
          
          {/* Attachment Strip */}
          <AnimatePresence>
            {pendingImages.length > 0 && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="flex flex-wrap gap-3 px-4 pt-4 pb-1"
              >
                {pendingImages.map((img, idx) => (
                  <motion.div
                    key={img.id}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: idx * 0.05 }}
                    className="relative group h-16 w-16"
                  >
                    <img src={img.previewUrl || img.url} alt="upload" className="w-full h-full object-cover rounded-lg border border-[var(--border)] bg-white/5" />
                    <button 
                      onClick={() => onRemoveImage?.(img.id)}
                      className="absolute -top-2 -right-2 p-1 bg-black/80 backdrop-blur-md rounded-full shadow-lg border border-white/20 opacity-0 scale-90 group-hover:opacity-100 group-hover:scale-100 hover:bg-black hover:border-white/40 transition-all duration-200 z-10"
                    >
                      <X className="w-3 h-3 text-white drop-shadow-md" />
                    </button>
                    {img.uploading && (
                      <div className="absolute inset-0 bg-black/40 rounded-lg flex items-center justify-center">
                        <Loader2 className="w-4 h-4 text-orange-500 animate-spin" />
                      </div>
                    )}
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Main Input Area */}
          <div className="px-4 pt-3 pb-1">
            <SmartInputLens
              ref={ref}
              value={input}
              onInput={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePasteWrapper}
              placeholder={placeholder}
              disabled={isLoading}
            />
          </div>

          {/* 🛠️ Unified Action Bar */}
          <div className="flex items-center justify-between px-4 pb-3 pt-2">
            <div className="flex items-center gap-3">
              {/* Action: Attach */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <motion.button
                    whileHover={{ scale: 1.1, backgroundColor: 'rgba(234, 88, 12, 0.1)' }}
                    whileTap={{ scale: 0.95 }}
                    onClick={onAttachClick}
                    className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full border border-[var(--border)] bg-white/5 text-[var(--text-secondary)] hover:text-orange-500 transition-colors"
                  >
                    <Paperclip className="w-4 h-4" />
                  </motion.button>
                </TooltipTrigger>
                <TooltipContent side="top">Attach File</TooltipContent>
              </Tooltip>

            </div>

            <div className="flex items-center gap-4">
              {/* Action Orb: Send/Stop */}
              <div className="flex-shrink-0">
                <AnimatePresence mode="wait">
                  {isLoading ? (
                    <motion.button
                      key="stop"
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.8, opacity: 0 }}
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      onClick={onStop}
                      className="w-9 h-9 flex items-center justify-center rounded-full bg-red-500/20 border border-red-500/30 text-red-400"
                    >
                      <Square className="w-3 h-3 fill-current" />
                    </motion.button>
                  ) : (
                    <motion.button
                      key="send"
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.8, opacity: 0 }}
                      whileHover={hasContent ? { scale: 1.1, y: -2, backgroundColor: '#ea580c' } : {}}
                      whileTap={hasContent ? { scale: 0.95 } : {}}
                      onClick={handleSubmit}
                      disabled={!hasContent}
                      className={cn(
                        "w-9 h-9 flex items-center justify-center rounded-full transition-all duration-300",
                        hasContent 
                          ? "bg-orange-500 text-white shadow-md shadow-orange-500/20" 
                          : "bg-white/5 text-[var(--text-secondary)] border border-[var(--border)] cursor-not-allowed"
                      )}
                    >
                      <ArrowUp className="w-5 h-5" />
                    </motion.button>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Image View Dialog */}
      <ImageViewDialog imageUrl={selectedImage} onClose={() => setSelectedImage(null)} />
    </TooltipProvider>
  );
});

PromptInputBox.displayName = "PromptInputBox";

/**
 * 🖼️ Image Preview Component
 */
const ImageViewDialog = ({ imageUrl, onClose }) => {
  if (!imageUrl) return null;
  return (
    <Dialog open={!!imageUrl} onOpenChange={onClose}>
      <DialogContent className="p-0 border-none bg-transparent shadow-none max-w-[90vw] md:max-w-200">
        <DialogTitle className="sr-only">Image Preview</DialogTitle>
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative bg-[var(--bg-surface)] backdrop-blur-2xl rounded-2xl overflow-hidden border border-[var(--border)] shadow-2xl"
        >
          <img src={imageUrl} alt="Full preview" className="w-full max-h-[80vh] object-contain" />
          <div className="absolute top-4 right-4 flex gap-2">
             <button onClick={onClose} className="p-2 bg-black/50 rounded-full hover:bg-black/70 transition-colors border border-white/10">
               <X className="w-5 h-5 text-white" />
             </button>
          </div>
        </motion.div>
      </DialogContent>
    </Dialog>
  );
};
