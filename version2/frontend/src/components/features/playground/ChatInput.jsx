import React, { useRef, useState, useEffect, useCallback, forwardRef } from 'react';
import { ArrowUp, Mic, Square, Plus, X } from 'lucide-react';
import { cn } from '@/lib/utils';

/* ─── Icons ─── */
function DynamicBarsIcon({ level }) {
  const isMid = level === 'Medium' || level === 'Max Effort';
  const isHigh = level === 'Max Effort';
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <rect x="1.5" y="8" width="2.5" height="4.5" rx="1" fill="currentColor" opacity={1} />
      <rect x="5.75" y="5" width="2.5" height="7.5" rx="1" fill="currentColor" opacity={isMid ? 1 : 0.3} />
      <rect x="10" y="2" width="2.5" height="10.5" rx="1" fill="currentColor" opacity={isHigh ? 1 : 0.3} />
    </svg>
  );
}

/* ─── Morphing Text ─── */
function MorphingText({ text }) {
  const [width, setWidth] = useState('auto');
  const spanRef = useRef(null);

  useEffect(() => {
    if (spanRef.current) setWidth(spanRef.current.offsetWidth);
  }, [text]);

  return (
    <span className="relative inline-flex items-center justify-center overflow-hidden transition-all duration-300" style={{ width, transitionTimingFunction: 'cubic-bezier(0.175,0.885,0.32,1.275)' }}>
      <span ref={spanRef} className="invisible whitespace-nowrap px-1">{text}</span>
      <span key={text} className="absolute inset-0 flex items-center justify-center whitespace-nowrap">{text}</span>
    </span>
  );
}

/* ─── Attachment Thumbnail ─── */
function AttachmentThumb({ attachment, index, onRemove, onOpen, registerRef }) {
  const btnRef = useRef(null);
  const [hovered, setHovered] = useState(false);

  return (
    <button
      ref={el => { btnRef.current = el; registerRef(attachment.id, el); }}
      type="button"
      onMouseDown={e => e.preventDefault()}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={e => { e.stopPropagation(); if (btnRef.current) onOpen(attachment, btnRef.current.getBoundingClientRect()); }}
      className={cn(
        'group relative size-12 shrink-0 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] outline-none',
        'transition-transform duration-200 hover:scale-[1.04] active:scale-[0.96]'
      )}
      style={{ animationDelay: `${index * 35}ms`, animationFillMode: 'backwards' }}
      aria-label={`Open preview of ${attachment.name}`}
    >
      <img src={attachment.url} alt={attachment.name} className="size-full object-cover" draggable={false} />
      <span className={cn('absolute inset-0 flex items-start justify-end bg-black/0 transition-colors duration-200', hovered && 'bg-black/25')}>
        <span
          role="button" tabIndex={-1}
          onMouseDown={e => { e.preventDefault(); e.stopPropagation(); }}
          onClick={e => { e.stopPropagation(); onRemove(attachment.id); }}
          className={cn(
            'm-1 flex size-4 items-center justify-center rounded-full bg-[var(--bg-surface)]/90 text-[var(--text-muted)] shadow-sm transition-all duration-200 hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)]',
            hovered ? 'opacity-100 scale-100' : 'opacity-0 scale-50 pointer-events-none'
          )}
          aria-label={`Remove ${attachment.name}`}
        >
          <X className="size-2.5" />
        </span>
      </span>
    </button>
  );
}

/* ─── Attachment Gallery Modal ─── */
function AttachmentGalleryModal({ attachment, originRect, onClose }) {
  const [phase, setPhase] = useState('opening');
  const [targetRect, setTargetRect] = useState(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const maxW = Math.min(window.innerWidth * 0.86, 560);
    const maxH = Math.min(window.innerHeight * 0.78, 720);
    const naturalW = attachment.width || 800;
    const naturalH = attachment.height || 600;
    const scale = Math.min(maxW / naturalW, maxH / naturalH, 1.6);
    setTargetRect({
      top: (window.innerHeight - naturalH * scale) / 2,
      left: (window.innerWidth - naturalW * scale) / 2,
      width: naturalW * scale,
      height: naturalH * scale,
    });
    requestAnimationFrame(() => { setPhase('open'); setIsOpen(true); });
  }, [attachment]);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    setPhase('closing');
  }, []);

  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') handleClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [handleClose]);

  const animState = phase === 'open' && targetRect ? targetRect : { top: originRect.top, left: originRect.left, width: originRect.width, height: originRect.height };

  return (
    <div className="fixed inset-0 z-[100]" onClick={handleClose} role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-[var(--bg-primary)]/70 backdrop-blur-md transition-opacity duration-400" style={{ opacity: isOpen ? 1 : 0 }} />
      <div
        style={{
          position: 'fixed', ...animState,
            borderRadius: phase === 'open' ? 16 : 10,
          transition: `${phase === 'closing' ? '0.3s ease-out' : '0.45s cubic-bezier(0.175,0.885,0.32,1.275)'}`,
          overflow: 'hidden',
          boxShadow: isOpen ? '0 24px 60px -12px rgba(0,0,0,0.35)' : 'none',
        }}
        className="bg-[var(--bg-elevated)]"
        onClick={e => e.stopPropagation()}
        onTransitionEnd={() => { if (phase === 'closing') onClose(); }}
      >
        <img src={attachment.url} alt={attachment.name} className="size-full object-cover" draggable={false} />
      </div>
      <button
        type="button"
        onClick={handleClose}
        className={cn(
          'fixed right-4 top-4 flex size-9 items-center justify-center rounded-full bg-[var(--bg-surface)]/90 text-[var(--text-muted)] shadow-md backdrop-blur-sm transition-all duration-300 hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)]',
          !isOpen && 'pointer-events-none opacity-0 scale-75'
        )}
      >
        <span className="scale-150"><X className="size-3" /></span>
      </button>
    </div>
  );
}

/* ─── Main Component ─── */

const ChatInput = forwardRef(({
  value: controlledValue,
  onChange,
  onSend,
  onSubmit,
  onStop,
  isLoading: _isLoading,
  placeholder = 'Ask anything',
  className,
  efforts: _efforts,
  defaultValue = '',
  maxAttachments = 6,
}, ref) => {
  const efforts = _efforts || ['Low', 'Medium', 'Max Effort'];
  const isLoading = _isLoading || false;

  const [localValue, setLocalValue] = useState(defaultValue);
  const [effortIndex, setEffortIndex] = useState(1);
  const [attachments, setAttachments] = useState([]);
  const [activeAttachment, setActiveAttachment] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [audioData, setAudioData] = useState(new Array(5).fill(0));
  const [inputHeight, setInputHeight] = useState(68);
  const [isScrolling, setIsScrolling] = useState(false);

  const isControlled = controlledValue !== undefined;
  const value = isControlled ? controlledValue : localValue;
  const hasValue = value.trim() !== '' || attachments.length > 0;
  const hasAttachments = attachments.length > 0;

  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const topFadeRef = useRef(null);
  const bottomFadeRef = useRef(null);
  const fileInputRef = useRef(null);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const rafRef = useRef(null);
  const recognitionRef = useRef(null);
  const demoIntervalRef = useRef(null);
  const valueRef = useRef(value);
  const thumbRefs = useRef(new Map());
  const suppressSyncRef = useRef(false);

  useEffect(() => { valueRef.current = value; }, [value]);

  // Sync value to contentEditable div (one-way: prop → DOM)
  useEffect(() => {
    if (inputRef.current && !suppressSyncRef.current) {
      const text = inputRef.current.innerText;
      if (text !== value) {
        inputRef.current.innerText = value;
      }
    }
  }, [value]);

  const handleValueChange = useCallback(val => {
    if (!isControlled) setLocalValue(val);
    onChange?.(val);
  }, [isControlled, onChange]);

  const addAttachment = (file, url, w, h) => {
    const id = `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`;
    setAttachments(prev => [...prev, { id, file, url, name: file.name, width: w, height: h }]);
  };

  const handleInput = useCallback(e => {
    suppressSyncRef.current = true;
    requestAnimationFrame(() => { suppressSyncRef.current = false; });
    handleValueChange(e.currentTarget.innerText);
  }, [handleValueChange]);

  const handlePaste = useCallback(e => {
    const items = Array.from(e.clipboardData?.items ?? []);
    const imageItems = items.filter(item => item.type.startsWith('image/'));
    if (imageItems.length > 0) {
      e.preventDefault();
      imageItems.forEach(item => {
        const file = item.getAsFile();
        if (file) {
          const url = URL.createObjectURL(file);
          const img = new Image();
          img.onload = () => addAttachment(file, url, img.naturalWidth, img.naturalHeight);
          img.onerror = () => addAttachment(file, url, 800, 600);
          img.src = url;
        }
      });
      return;
    }
    e.preventDefault();
    const text = e.clipboardData?.getData('text/plain') || '';
    document.execCommand('insertText', false, text);
  }, []);

  const updateFades = () => {
    const el = inputRef.current;
    if (!el) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    if (topFadeRef.current) topFadeRef.current.style.opacity = Math.min(scrollTop / 20, 1);
    if (bottomFadeRef.current) {
      const bs = scrollHeight - clientHeight - scrollTop;
      bottomFadeRef.current.style.opacity = Math.min(Math.max(bs - 16, 0) / 10, 1);
    }
  };

  const stopRecording = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    if (demoIntervalRef.current) clearInterval(demoIntervalRef.current);
    setIsRecording(false);
    setAudioData(new Array(5).fill(0));
  }, []);

  const startRecording = useCallback(async () => {
    let stream = null;
    try {
      if (navigator.mediaDevices?.getUserMedia) {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
    } catch { console.warn('Microphone denied, using simulated voice.'); }

    setIsRecording(true);

    const simulateText = () => {
      const words = "Can you build a high fidelity Framer Motion layout animation for a dark mode dashboard?".split(' ');
      let i = 0;
      let base = valueRef.current;
      const simText = setInterval(() => {
        if (i < words.length) {
          base = (base ? base + ' ' : '') + words[i];
          handleValueChange(base);
          i++;
        } else { stopRecording(); clearInterval(simText); }
      }, 300);
    };

    if (stream) {
      streamRef.current = stream;
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      audioCtxRef.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      const source = ctx.createMediaStreamSource(stream);
      source.connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);

      const viz = () => {
        analyser.getByteFrequencyData(buf);
        const step = Math.floor(buf.length / 5);
        const bands = Array.from({ length: 5 }, (_, i) => {
          let sum = 0;
          for (let j = 0; j < step; j++) sum += buf[i * step + j];
          return sum / step / 255;
        });
        setAudioData(bands);
        rafRef.current = requestAnimationFrame(viz);
      };
      viz();

      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SR) {
        const rec = new SR();
        rec.continuous = true;
        rec.interimResults = true;
        let baseline = valueRef.current;
        rec.onresult = ev => {
          let final = '', interim = '';
          for (let i = ev.resultIndex; i < ev.results.length; i++) {
            if (ev.results[i].isFinal) final += ev.results[i][0].transcript;
            else interim += ev.results[i][0].transcript;
          }
          if (final) baseline += (baseline ? ' ' : '') + final;
          handleValueChange((baseline + (interim ? ' ' + interim : '')).trim());
        };
        rec.onerror = () => stopRecording();
        rec.onend = () => stopRecording();
        recognitionRef.current = rec;
        rec.start();
      } else {
        simulateText();
      }
    } else {
      demoIntervalRef.current = setInterval(() => {
        setAudioData(Array.from({ length: 5 }, () => Math.random() * 0.8 + 0.1));
      }, 100);
      simulateText();
    }
  }, [handleValueChange, stopRecording]);

  useEffect(() => {
    return () => {
      stopRecording();
      attachments.forEach(a => URL.revokeObjectURL(a.url));
    };
  }, [stopRecording]);

  // Auto-resize based on scrollHeight
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = '0px';
    const sh = el.scrollHeight;
    const nh = Math.max(68, Math.min(sh, 160));
    el.style.height = `${nh}px`;
    setInputHeight(nh);
    setIsScrolling(sh > 160);
    setTimeout(updateFades, 0);
  }, [value]);

  const handleSubmit = () => {
    if (value.trim() === '' && !hasAttachments) return;
    const files = attachments.map(a => a.file);
    if (onSubmit) {
      onSubmit(value, { effort: efforts[effortIndex], attachments: files });
    } else if (onSend) {
      onSend(value);
    }
    handleValueChange('');
    attachments.forEach(a => URL.revokeObjectURL(a.url));
    setAttachments([]);
  };

  const openFileChooser = e => { e.stopPropagation(); fileInputRef.current?.click(); };

  const handleFiles = e => {
    const files = Array.from(e.target.files || []).filter(f => f.type.startsWith('image/'));
    e.target.value = '';
    if (!files.length) return;
    const room = Math.max(0, maxAttachments - attachments.length);
    const accepted = files.slice(0, room);
    accepted.forEach(file => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => addAttachment(file, url, img.naturalWidth, img.naturalHeight);
      img.onerror = () => addAttachment(file, url, 800, 600);
      img.src = url;
    });
  };

  const removeAttachment = id => {
    setAttachments(prev => {
      const t = prev.find(a => a.id === id);
      if (t) URL.revokeObjectURL(t.url);
      return prev.filter(a => a.id !== id);
    });
    thumbRefs.current.delete(id);
  };

  const showArrow = hasValue && !isRecording && !isLoading;
  const showStop = isRecording || isLoading;
  const showMic = !hasValue && !isRecording && !isLoading;

  return (
    <>
      <div
        ref={node => {
          if (typeof ref === 'function') ref(node);
          else if (ref) ref.current = node;
          containerRef.current = node;
        }}
        className={cn('w-full', className)}
      >
        <input ref={fileInputRef} type="file" accept="image/*" multiple onChange={handleFiles} className="hidden" tabIndex={-1} aria-hidden="true" />

        {/* Attachment Tab */}
        <div
          aria-hidden={!hasAttachments}
          style={{ height: hasAttachments ? 68 : 0 }}
          className="w-full relative z-0 overflow-hidden transition-all duration-300"
        >
          <div
            style={{
              position: 'absolute', bottom: 0, left: 20, right: 20, height: 68,
              transform: hasAttachments ? 'translateY(0)' : 'translateY(100%)',
              opacity: hasAttachments ? 1 : 0,
            }}
            className="border border-[var(--border)] border-b-0 bg-[var(--bg-elevated)] rounded-t-xl px-2 pt-2 pb-1 flex items-start gap-2 overflow-x-auto transition-all duration-300"
          >
            {attachments.map((att, i) => (
              <AttachmentThumb
                key={att.id} attachment={att} index={i}
                onRemove={removeAttachment}
                onOpen={(a, rect) => setActiveAttachment({ attachment: a, rect })}
                registerRef={(id, el) => thumbRefs.current.set(id, el)}
              />
            ))}
          </div>
        </div>

        {/* Main Card */}
        <div
          className="relative w-full border border-[var(--border)] bg-[var(--bg-surface)] shadow-sm z-10 cursor-text"
          style={{ borderRadius: 16, height: Math.max(116, inputHeight + 48) }}
        >
          {/* Content Editable Input */}
          <div
            ref={inputRef}
            contentEditable={!isRecording}
            suppressContentEditableWarning
            role="textbox"
            aria-multiline="true"
            aria-label="Prompt"
            onInput={handleInput}
            onPaste={handlePaste}
            onScroll={updateFades}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                e.stopPropagation();
                handleSubmit();
              }
            }}
            className={cn(
              'absolute top-0 inset-x-0 z-[1] w-full bg-transparent pl-4 pr-12 py-3.5 text-sm leading-[22px] text-[var(--text-primary)] outline-none overflow-y-auto whitespace-pre-wrap break-words',
              isRecording && 'pointer-events-none'
            )}
            style={{
              minHeight: 68, maxHeight: 160,
              scrollbarWidth: 'thin', scrollbarColor: 'var(--border) transparent',
            }}
          />

          {/* Placeholder */}
          {(!value || value.trim() === '') && (
            <div className="absolute top-0 inset-x-0 z-[1] pl-4 pr-12 py-3.5 text-sm leading-[22px] text-[var(--text-muted)] pointer-events-none select-none">
              {placeholder}
            </div>
          )}

          {/* Fade overlays */}
          <div ref={topFadeRef} className="absolute left-4 right-12 top-0 z-[2] h-8 bg-gradient-to-b from-[var(--bg-surface)] via-[var(--bg-surface)]/90 to-transparent pointer-events-none" />
          <div
            ref={bottomFadeRef}
            className="absolute left-4 right-12 z-[2] h-8 bg-gradient-to-t from-[var(--bg-surface)] via-[var(--bg-surface)]/90 to-transparent pointer-events-none"
            style={{ opacity: 0, top: `${inputHeight - 32}px` }}
          />

          {/* Bottom actions */}
          <div
            className={cn(
              'absolute bottom-2 left-3 right-12 z-[10] flex items-center gap-0 transition-all duration-300',
              !isRecording && !isLoading ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
            )}
          >
            <button
              type="button"
              onMouseDown={e => e.preventDefault()}
              onClick={e => { e.stopPropagation(); setEffortIndex(p => (p + 1) % efforts.length); }}
              className="group flex items-center gap-1 rounded-full px-2 py-1 text-[var(--text-muted)] transition-all duration-200 hover:bg-white/5 hover:text-[var(--text-primary)] outline-none"
            >
              <DynamicBarsIcon level={efforts[effortIndex]} />
              <span className="text-xs font-semibold select-none"><MorphingText text={efforts[effortIndex]} /></span>
            </button>

            <button
              type="button"
              onMouseDown={e => e.preventDefault()}
              onClick={openFileChooser}
              disabled={attachments.length >= maxAttachments}
              className="ml-auto flex size-7 items-center justify-center rounded-full text-[var(--text-muted)] transition-all duration-200 hover:bg-white/5 hover:text-[var(--text-primary)] outline-none disabled:opacity-40 disabled:pointer-events-none"
            >
              <Plus className="size-3.5" />
            </button>
          </div>

          {/* Audio visualizer */}
          <div
            className={cn(
              'absolute right-12 bottom-2 z-[10] flex h-8 items-center justify-end gap-[3px] transition-all duration-400',
              isRecording ? 'w-16 opacity-100 translate-x-0' : 'w-0 opacity-0 translate-x-4 pointer-events-none'
            )}
          >
            {audioData.map((val, i) => (
              <div key={i} className="w-1 rounded-full bg-[var(--accent-primary)] transition-[height] duration-75" style={{ height: `${Math.max(4, val * 24)}px` }} />
            ))}
          </div>

          {/* Action button */}
          <button
            type="button"
            onMouseDown={e => { e.preventDefault(); e.stopPropagation(); }}
            onClick={e => {
              e.preventDefault();
              if (isRecording) stopRecording();
              else if (isLoading) onStop?.();
              else if (hasValue) handleSubmit();
              else startRecording();
            }}
            className="absolute right-2 bottom-2 z-[10] flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent-primary)] text-white transition-all duration-300 hover:opacity-90 outline-none"
          >
            <span className="relative flex h-full w-full items-center justify-center">
              <span className={cn('absolute inset-0 flex items-center justify-center transition-all duration-300', showArrow ? 'opacity-100 scale-100 rotate-0' : 'opacity-0 scale-50 rotate-45 pointer-events-none')}>
                <ArrowUp className="size-3" />
              </span>
              <span className={cn('absolute inset-0 flex items-center justify-center transition-all duration-300', showMic ? 'opacity-100 scale-100 rotate-0' : 'opacity-0 scale-50 -rotate-45 pointer-events-none')}>
                <Mic className="size-3.5" />
              </span>
              <span className={cn('absolute inset-0 flex items-center justify-center transition-all duration-300', showStop ? 'opacity-100 scale-100 rotate-0' : 'opacity-0 scale-50 rotate-45 pointer-events-none')}>
                <Square className="size-3 fill-current" />
              </span>
            </span>
          </button>
        </div>
      </div>

      {activeAttachment && (
        <AttachmentGalleryModal
          attachment={activeAttachment.attachment}
          originRect={activeAttachment.rect}
          onClose={() => setActiveAttachment(null)}
        />
      )}
    </>
  );
});

ChatInput.displayName = 'ChatInput';

export default ChatInput;
