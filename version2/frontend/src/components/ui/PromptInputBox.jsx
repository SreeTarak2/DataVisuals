import React, { useState, useRef, useEffect, useCallback, forwardRef, createContext, useContext } from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ArrowUp, Paperclip, Square, X, StopCircle, Mic, Globe, BrainCog, FolderCode, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

// Embedded CSS for minimal custom styles
const styles = `
  *:focus-visible {
    outline-offset: 0 !important;
    --ring-offset: 0 !important;
  }
  textarea::-webkit-scrollbar {
    width: 6px;
  }
  textarea::-webkit-scrollbar-track {
    background: transparent;
  }
  textarea::-webkit-scrollbar-thumb {
    background-color: var(--scrollbar-thumb);
    border-radius: 3px;
  }
  textarea::-webkit-scrollbar-thumb:hover {
    background-color: var(--border-strong);
  }
`;

// Inject styles into document (if not already present)
if (typeof document !== 'undefined') {
    const styleId = "ai-prompt-box-styles";
    if (!document.getElementById(styleId)) {
        const styleSheet = document.createElement("style");
        styleSheet.id = styleId;
        styleSheet.innerText = styles;
        document.head.appendChild(styleSheet);
    }
}

// Textarea Component
const Textarea = forwardRef(({ className, ...props }, ref) => (
    <textarea
        className={cn(
            "flex w-full rounded-md border-none bg-transparent px-3 py-2.5 text-base text-header placeholder:text-muted focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-50 min-h-[44px] resize-none",
            className
        )}
        ref={ref}
        rows={1}
        {...props}
    />
));
Textarea.displayName = "Textarea";

// Tooltip Components
const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;
const TooltipContent = forwardRef(({ className, sideOffset = 4, ...props }, ref) => (
    <TooltipPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
            "z-50 overflow-hidden rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-header shadow-md animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
            className
        )}
        {...props}
    />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

// Dialog Components
const Dialog = DialogPrimitive.Root;
const DialogPortal = DialogPrimitive.Portal;
const DialogOverlay = forwardRef(({ className, ...props }, ref) => (
    <DialogPrimitive.Overlay
        ref={ref}
        className={cn(
            "fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
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
                "fixed left-[50%] top-[50%] z-50 grid w-full max-w-[90vw] md:max-w-[800px] translate-x-[-50%] translate-y-[-50%] gap-4 border border-border bg-surface p-0 shadow-xl duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 rounded-2xl",
                className
            )}
            {...props}
        >
            {children}
            <DialogPrimitive.Close className="absolute right-4 top-4 z-10 rounded-full bg-elevated/80 p-2 hover:bg-elevated transition-all">
                <X className="h-5 w-5 text-header hover:text-primary" />
                <span className="sr-only">Close</span>
            </DialogPrimitive.Close>
        </DialogPrimitive.Content>
    </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogTitle = forwardRef(({ className, ...props }, ref) => (
    <DialogPrimitive.Title
        ref={ref}
        className={cn("text-lg font-semibold leading-none tracking-tight text-header", className)}
        {...props}
    />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

// Button Component
const Button = forwardRef(({ className, variant = "default", size = "default", ...props }, ref) => {
    const variantClasses = {
        default: "bg-accent-primary hover:bg-accent-primary-hover text-white",
        outline: "border border-border bg-transparent hover:bg-elevated",
        ghost: "bg-transparent hover:bg-elevated",
    };
    const sizeClasses = {
        default: "h-10 px-4 py-2",
        sm: "h-8 px-3 text-sm",
        lg: "h-12 px-6",
        icon: "h-8 w-8 rounded-full aspect-[1/1]",
    };
    return (
        <button
            className={cn(
                "inline-flex items-center justify-center font-medium transition-all focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50 rounded-lg cursor-pointer",
                variantClasses[variant],
                sizeClasses[size],
                className
            )}
            ref={ref}
            {...props}
        />
    );
});
Button.displayName = "Button";

// VoiceRecorder Component
const VoiceRecorder = ({
    isRecording,
    onStartRecording,
    onStopRecording,
    visualizerBars = 32,
}) => {
    const [time, setTime] = useState(0);
    const timerRef = useRef(null);

    useEffect(() => {
        if (isRecording) {
            onStartRecording?.();
            timerRef.current = setInterval(() => setTime((t) => t + 1), 1000);
        } else {
            if (timerRef.current) {
                clearInterval(timerRef.current);
                timerRef.current = null;
            }
            onStopRecording?.(time);
            setTime(0);
        }
        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [isRecording, onStartRecording, onStopRecording]); // eslint-disable-line react-hooks/exhaustive-deps

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    return (
        <div
            className={cn(
                "flex flex-col items-center justify-center w-full transition-all duration-300 py-3",
                isRecording ? "opacity-100" : "opacity-0 h-0 invisible"
            )}
        >
            <div className="flex items-center gap-2 mb-3">
                <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                <span className="font-mono text-sm text-secondary">{formatTime(time)}</span>
            </div>
            <div className="w-full h-10 flex items-center justify-center gap-0.5 px-4">
                {[...Array(visualizerBars)].map((_, i) => (
                    <div
                        key={i}
                        className="w-1 rounded-full bg-accent-primary/40 animate-pulse"
                        style={{
                            height: `${Math.max(20, Math.random() * 100)}%`,
                            animationDelay: `${i * 0.05}s`,
                            animationDuration: `${0.5 + Math.random() * 0.5}s`,
                        }}
                    />
                ))}
            </div>
        </div>
    );
};

// ImageViewDialog Component
const ImageViewDialog = ({ imageUrl, onClose }) => {
    if (!imageUrl) return null;
    return (
        <Dialog open={!!imageUrl} onOpenChange={onClose}>
            <DialogContent className="p-0 border-none bg-transparent shadow-none max-w-[90vw] md:max-w-[800px]">
                <DialogTitle className="sr-only">Image Preview</DialogTitle>
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ duration: 0.2, ease: "easeOut" }}
                    className="relative bg-surface rounded-2xl overflow-hidden shadow-2xl"
                >
                    <img
                        src={imageUrl}
                        alt="Full preview"
                        className="w-full max-h-[80vh] object-contain rounded-2xl"
                    />
                </motion.div>
            </DialogContent>
        </Dialog>
    );
};

// PromptInput Context and Components
const PromptInputContext = createContext({
    isLoading: false,
    value: "",
    setValue: () => { },
    maxHeight: 240,
    onSubmit: undefined,
    disabled: false,
});

function usePromptInput() {
    const context = useContext(PromptInputContext);
    if (!context) throw new Error("usePromptInput must be used within a PromptInput");
    return context;
}

const PromptInput = forwardRef(
    (
        {
            className,
            isLoading = false,
            maxHeight = 240,
            value,
            onValueChange,
            onSubmit,
            children,
            disabled = false,
            onDragOver,
            onDragLeave,
            onDrop,
        },
        ref
    ) => {
        return (
            <TooltipProvider>
                <PromptInputContext.Provider
                    value={{
                        isLoading,
                        value,
                        setValue: onValueChange,
                        maxHeight,
                        onSubmit,
                        disabled,
                    }}
                >
                    <div
                        ref={ref}
                        className={cn(
                            "rounded-3xl border border-border bg-surface p-2 shadow-lg transition-all duration-300",
                            isLoading && "border-accent-primary/70",
                            className
                        )}
                        onDragOver={onDragOver}
                        onDragLeave={onDragLeave}
                        onDrop={onDrop}
                    >
                        {children}
                    </div>
                </PromptInputContext.Provider>
            </TooltipProvider>
        );
    }
);
PromptInput.displayName = "PromptInput";

const PromptInputTextarea = ({
    className,
    onKeyDown,
    disableAutosize = false,
    placeholder,
    ...props
}) => {
    const { value, setValue, maxHeight, onSubmit, disabled } = usePromptInput();
    const textareaRef = useRef(null);

    useEffect(() => {
        if (disableAutosize || !textareaRef.current) return;
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height =
            typeof maxHeight === "number"
                ? `${Math.min(textareaRef.current.scrollHeight, maxHeight)}px`
                : `min(${textareaRef.current.scrollHeight}px, ${maxHeight})`;
    }, [value, maxHeight, disableAutosize]);

    const handleKeyDown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit?.();
        }
        onKeyDown?.(e);
    };

    return (
        <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className={cn("text-base", className)}
            disabled={disabled}
            placeholder={placeholder}
            {...props}
        />
    );
};

const PromptInputActions = ({ children, className, ...props }) => (
    <div className={cn("flex items-center gap-2", className)} {...props}>
        {children}
    </div>
);

const PromptInputAction = ({
    tooltip,
    children,
    className,
    side = "top",
    ...props
}) => {
    const { disabled } = usePromptInput();
    return (
        <Tooltip {...props}>
            <TooltipTrigger asChild disabled={disabled}>
                {children}
            </TooltipTrigger>
            <TooltipContent side={side} className={className}>
                {tooltip}
            </TooltipContent>
        </Tooltip>
    );
};

// Custom Divider Component
const CustomDivider = () => (
    <div className="relative h-6 w-[1px] mx-1 bg-border/40" />
);

// Main PromptInputBox Component
export const PromptInputBox = forwardRef((props, ref) => {
    const {
        onSend,
        onStop,
        isLoading = false,
        placeholder = "Ask me anything about your data...",
        className,
        value: input,
        onChange: setInput,
        pendingImages = [],
        onRemoveImage,
        onAttachClick,
    } = props;

    const [selectedImage, setSelectedImage] = useState(null);
    const [isRecording, setIsRecording] = useState(false);
    const [showSearch, setShowSearch] = useState(false);
    const [showThink, setShowThink] = useState(false);
    const [showCanvas, setShowCanvas] = useState(false);

    const promptBoxRef = useRef(null);

    const handleToggleChange = (item) => {
        if (item === "search") {
            setShowSearch((prev) => !prev);
            setShowThink(false);
        } else if (item === "think") {
            setShowThink((prev) => !prev);
            setShowSearch(false);
        }
    };

    const handleCanvasToggle = () => setShowCanvas((prev) => !prev);

    const handleSubmit = () => {
        if (input.trim() || pendingImages.length > 0) {
            let messagePrefix = "";
            if (showSearch) messagePrefix = "[Search] ";
            else if (showThink) messagePrefix = "[Think] ";
            else if (showCanvas) messagePrefix = "[Canvas] ";

            const formattedInput = messagePrefix ? `${messagePrefix}${input}` : input;
            onSend(formattedInput);
        }
    };

    const handleStartRecording = () => console.log("Started recording");

    const handleStopRecording = (duration) => {
        console.log(`Stopped recording after ${duration} seconds`);
        setIsRecording(false);
        if (duration > 0.5) {
            onSend(`[Voice message - ${duration} seconds]`);
        }
    };

    const hasContent = input.trim() !== "" || pendingImages.length > 0;

    return (
        <>
            <PromptInput
                value={input}
                onValueChange={setInput}
                isLoading={isLoading}
                onSubmit={handleSubmit}
                className={cn(
                    "w-full bg-surface border-border shadow-2xl transition-all duration-300 ease-in-out",
                    isRecording && "border-red-500/70",
                    className
                )}
                disabled={isLoading || isRecording}
                ref={ref || promptBoxRef}
            >
                {pendingImages.length > 0 && !isRecording && (
                    <div className="flex flex-wrap gap-2 p-1 pb-2 transition-all duration-300">
                        {pendingImages.map((img) => (
                            <div key={img.id} className="relative group/thumb">
                                <div
                                    className="w-16 h-16 rounded-xl overflow-hidden cursor-pointer border border-border/50 transition-all hover:border-accent-primary/50"
                                    onClick={() => setSelectedImage(img.previewUrl || img.url)}
                                >
                                    <img
                                        src={img.previewUrl || img.url}
                                        alt="attachment"
                                        className="h-full w-full object-cover"
                                    />
                                    {img.uploading && (
                                        <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                                            <Loader2 size={16} className="text-white animate-spin" />
                                        </div>
                                    )}
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onRemoveImage?.(img.id);
                                        }}
                                        className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-red-500 text-white flex items-center justify-center text-[10px] opacity-0 group-hover/thumb:opacity-100 transition-opacity shadow-lg"
                                    >
                                        <X size={12} />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                <div
                    className={cn(
                        "transition-all duration-300",
                        isRecording ? "h-0 overflow-hidden opacity-0" : "opacity-100"
                    )}
                >
                    <PromptInputTextarea
                        placeholder={
                            showSearch
                                ? "Search your data & web..."
                                : showThink
                                    ? "Analyzing deeply..."
                                    : showCanvas
                                        ? "Generating on canvas..."
                                        : placeholder
                        }
                        className="text-[16px]"
                    />
                </div>

                {isRecording && (
                    <VoiceRecorder
                        isRecording={isRecording}
                        onStartRecording={handleStartRecording}
                        onStopRecording={handleStopRecording}
                    />
                )}

                <PromptInputActions className="flex items-center justify-between gap-2 p-0 pt-2">
                    <div
                        className={cn(
                            "flex items-center gap-1 transition-opacity duration-300",
                            isRecording ? "opacity-0 invisible h-0" : "opacity-100 visible"
                        )}
                    >
                        <PromptInputAction tooltip="Upload image">
                            <button
                                onClick={onAttachClick}
                                className="flex h-9 w-9 text-muted cursor-pointer items-center justify-center rounded-full transition-colors hover:bg-elevated hover:text-header"
                                disabled={isRecording}
                            // disabled={isRecording} // Commented out
                            >
                                <Paperclip className="h-5 w-5" />
                            </button>
                        </PromptInputAction>

                        {/* 
            <div className="flex items-center ml-1 space-x-0.5">
              <button
                type="button"
                onClick={() => handleToggleChange("search")}
                className={cn(
                  "rounded-full transition-all flex items-center gap-1.5 px-3 py-1 border h-9",
                  showSearch
                    ? "bg-accent-primary/15 border-accent-primary text-accent-primary"
                    : "bg-transparent border-transparent text-muted hover:bg-elevated hover:text-header"
                )}
              >
                <Globe className={cn("w-4 h-4", showSearch ? "text-accent-primary" : "text-inherit")} />
                <AnimatePresence>
                  {showSearch && (
                    <motion.span
                      initial={{ width: 0, opacity: 0 }}
                      animate={{ width: "auto", opacity: 1 }}
                      exit={{ width: 0, opacity: 0 }}
                      className="text-xs font-medium"
                    >
                      Search
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>

              <CustomDivider />

              <button
                type="button"
                onClick={() => handleToggleChange("think")}
                className={cn(
                  "rounded-full transition-all flex items-center gap-1.5 px-3 py-1 border h-9",
                  showThink
                    ? "bg-violet-500/15 border-violet-500 text-violet-500"
                    : "bg-transparent border-transparent text-muted hover:bg-elevated hover:text-header"
                )}
              >
                <BrainCog className={cn("w-4 h-4", showThink ? "text-violet-500" : "text-inherit")} />
                <AnimatePresence>
                  {showThink && (
                    <motion.span
                      initial={{ width: 0, opacity: 0 }}
                      animate={{ width: "auto", opacity: 1 }}
                      exit={{ width: 0, opacity: 0 }}
                      className="text-xs font-medium"
                    >
                      Think
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>

              <CustomDivider />

              <button
                type="button"
                onClick={handleCanvasToggle}
                className={cn(
                  "rounded-full transition-all flex items-center gap-1.5 px-3 py-1 border h-9",
                  showCanvas
                    ? "bg-orange-500/15 border-orange-500 text-orange-500"
                    : "bg-transparent border-transparent text-muted hover:bg-elevated hover:text-header"
                )}
              >
                <FolderCode className={cn("w-4 h-4", showCanvas ? "text-orange-500" : "text-inherit")} />
                <AnimatePresence>
                  {showCanvas && (
                    <motion.span
                      initial={{ width: 0, opacity: 0 }}
                      animate={{ width: "auto", opacity: 1 }}
                      exit={{ width: 0, opacity: 0 }}
                      className="text-xs font-medium"
                    >
                      Canvas
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
            </div>
            */}
                    </div>

                    <PromptInputAction
                        tooltip={
                            isLoading
                                ? "Stop generation"
                                : hasContent
                                    ? "Send message"
                                    : "Send message" // Changed from "Voice message"
                        }
                    >
                        <Button
                            variant={isLoading || hasContent ? "default" : "ghost"}
                            size="icon"
                            className={cn(
                                "h-9 w-9 rounded-full transition-all duration-300",
                                isLoading
                                    ? "bg-red-500/80 hover:bg-red-500 shadow-lg"
                                    : hasContent
                                        ? "bg-accent-primary shadow-lg"
                                        : "text-muted hover:bg-elevated hover:text-header"
                            )}
                            onClick={() => {
                                if (isLoading) {
                                    onStop?.();
                                } else if (hasContent) {
                                    handleSubmit();
                                }
                            }}
                            disabled={!isLoading && !hasContent}
                        >
                            {isLoading ? (
                                <Square className="h-3.5 w-3.5 fill-current" />
                            ) : (
                                <ArrowUp className="h-5 w-5" />
                            )}
                        </Button>
                    </PromptInputAction>
                </PromptInputActions>
            </PromptInput>

            <ImageViewDialog imageUrl={selectedImage} onClose={() => setSelectedImage(null)} />
        </>
    );
});
PromptInputBox.displayName = "PromptInputBox";
