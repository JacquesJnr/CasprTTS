// Adapted from Watermelon UI's select-ai-agent: agents became voices, Enter speaks, / opens a command menu.
import React, { useRef, useState } from 'react';
import { motion, AnimatePresence, LayoutGroup } from 'motion/react';
import { ArrowRight } from 'lucide-react';

export interface SlashOption {
  id: string; // inserted as /id
  label: string;
  detail?: string;
}

export interface AIAgent {
  id: string;
  name: string;
  icon: React.ReactNode;
}

interface SelectAIAgentProps {
  agents: AIAgent[];
  selectedId?: string;
  onSelectAgent?: (agentId: string) => void;
  onSendMessage?: (message: string, agentId: string) => void;
  onEscape?: () => void;
  footer?: React.ReactNode;
  /** Optional styled rendering of the typed text (e.g. highlighted /commands). */
  renderValue?: (value: string) => React.ReactNode;
  /** Typing "/" at the start of a word lists these above the input. */
  slashOptions?: SlashOption[];
  slashEmpty?: React.ReactNode;
  /** Up/Down outside the command menu: return the history entry to show. */
  onHistory?: (direction: 'previous' | 'next', current: string) => Promise<string>;
  className?: string;
}

export const SelectAIAgent: React.FC<SelectAIAgentProps> = ({
  agents,
  selectedId,
  onSelectAgent,
  onSendMessage,
  onEscape,
  footer,
  renderValue,
  slashOptions,
  slashEmpty,
  onHistory,
  className = '',
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const mirrorRef = useRef<HTMLDivElement>(null);
  // Keep the styled mirror scrolled with the input's text.
  const syncScroll = () => {
    if (mirrorRef.current && inputRef.current) mirrorRef.current.scrollLeft = inputRef.current.scrollLeft;
  };
  const selectedAgent = agents.find((a) => a.id === selectedId) ?? agents[0];
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [message, setMessage] = useState('');
  // Index of the "/" that opened the command menu; null when closed.
  const [slashStart, setSlashStart] = useState<number | null>(null);
  const [active, setActive] = useState(0);
  const query = slashStart === null ? '' : message.slice(slashStart + 1).split(/\s/)[0].toLowerCase();
  const matches = (slashOptions ?? []).filter((o) => o.id.startsWith(query));

  const insertCommand = (option: SlashOption) => {
    if (slashStart === null) return;
    const before = message.slice(0, slashStart) + '/' + option.id + ' ';
    setMessage(before + message.slice(slashStart + 1 + query.length).replace(/^ /, ''));
    setSlashStart(null);
    requestAnimationFrame(() => {
      inputRef.current?.setSelectionRange(before.length, before.length);
      syncScroll();
    });
  };

  const send = () => {
    if (!message.trim() || !selectedAgent) return;
    onSendMessage?.(message.trim(), selectedAgent.id);
    setMessage('');
    setSlashStart(null);
  };

  if (!selectedAgent) return null;

  return (
    <div className={`relative w-full antialiased select-none ${className}`}>
      <LayoutGroup>
        <AnimatePresence>
          {isMenuOpen && (
            <motion.div
              initial={{ opacity: 0, y: 10, filter: 'blur(8px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, y: 20, filter: 'blur(8px)' }}
              transition={{ type: 'spring', stiffness: 400, damping: 30, mass: 0.8 }}
              className="border-border bg-popover absolute bottom-full left-0 z-10 mb-2 flex w-fit origin-bottom-left gap-1 rounded-lg border p-1 shadow-lift"
            >
              {agents.map((agent) => (
                <button
                  key={agent.id}
                  title={agent.name}
                  onClick={() => {
                    onSelectAgent?.(agent.id);
                    setIsMenuOpen(false);
                  }}
                  className={`flex h-10 min-w-10 shrink-0 items-center justify-center rounded-md px-1.5 text-xl transition-all active:scale-95 ${
                    selectedAgent.id === agent.id
                      ? 'border-primary/70 bg-primary/[0.04] border shadow-glow'
                      : 'hover:bg-accent'
                  }`}
                >
                  {agent.icon}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <motion.div layout className="border-border bg-card rounded-xl border p-2.5 shadow-lift">
          <div className="flex items-center gap-3">
            <motion.button
              layoutId={`agent-${selectedAgent.id}`}
              title={`Voice: ${selectedAgent.name}`}
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="bg-muted border-border flex h-10 min-w-10 shrink-0 cursor-pointer items-center justify-center rounded-md border px-1.5 text-xl"
            >
              {selectedAgent.icon}
            </motion.button>

            <div className="relative min-w-0 flex-1">
            <input
              ref={inputRef}
              autoFocus
              type="text"
              placeholder={`Say something as ${selectedAgent.name}…`}
              value={message}
              onChange={(e) => {
                const value = e.target.value;
                const caret = e.target.selectionStart ?? value.length;
                setMessage(value);
                requestAnimationFrame(syncScroll);
                if (!slashOptions) return;
                if (value.length > message.length && value[caret - 1] === '/' && (caret === 1 || /\s/.test(value[caret - 2]))) {
                  setSlashStart(caret - 1);
                  setActive(0);
                  setIsMenuOpen(false);
                } else if (slashStart !== null && (value[slashStart] !== '/' || /\s/.test(value.slice(slashStart, caret)))) {
                  setSlashStart(null); // the command word ended or was deleted
                }
              }}
              onScroll={syncScroll}
              onSelect={(e) => {
                syncScroll();
                const caret = e.currentTarget.selectionStart ?? 0;
                if (slashStart !== null && caret <= slashStart) setSlashStart(null);
              }}
              onKeyUp={syncScroll}
              onBlur={() => setSlashStart(null)}
              onKeyDown={(e) => {
                if (slashStart !== null) {
                  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                    e.preventDefault();
                    const step = e.key === 'ArrowDown' ? 1 : -1;
                    setActive((i) => (i + step + matches.length) % Math.max(matches.length, 1));
                    return;
                  }
                  if ((e.key === 'Enter' || e.key === 'Tab') && matches.length) {
                    e.preventDefault();
                    return insertCommand(matches[Math.min(active, matches.length - 1)]);
                  }
                  if (e.key === 'Escape') {
                    e.preventDefault();
                    return setSlashStart(null);
                  }
                  if (e.key === 'Backspace' || e.key === 'Tab') setSlashStart(null);
                }
                if (onHistory && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
                  e.preventDefault();
                  onHistory(e.key === 'ArrowUp' ? 'previous' : 'next', message).then((text) => {
                    setMessage(text);
                    requestAnimationFrame(() => {
                      inputRef.current?.setSelectionRange(text.length, text.length);
                      syncScroll();
                    });
                  });
                  return;
                }
                if (e.key === 'Enter') send();
                if (e.key === 'Escape') {
                  if (isMenuOpen) return setIsMenuOpen(false);
                  setMessage('');
                  onEscape?.();
                }
              }}
              className={`${renderValue ? 'text-transparent caret-foreground' : 'text-foreground'} placeholder:text-muted-foreground bg-muted border-input w-full rounded-md border px-3 py-2 text-[14px] leading-5 outline-none transition focus:border-primary/70 focus:shadow-glow`}
            />
            <AnimatePresence>
              {slashStart !== null && (
                <motion.div
                  initial={{ opacity: 0, y: 6, filter: 'blur(6px)' }}
                  animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                  exit={{ opacity: 0, y: 6, filter: 'blur(6px)' }}
                  transition={{ type: 'spring', stiffness: 500, damping: 34, mass: 0.6 }}
                  role="listbox"
                  aria-label="Quick option commands"
                  className="border-border bg-popover absolute right-0 bottom-full left-0 z-20 mb-2 origin-bottom rounded-lg border p-1 shadow-lift"
                >
                  {matches.length ? (
                    matches.map((option, i) => (
                      <div
                        key={option.id}
                        role="option"
                        aria-selected={i === active}
                        onMouseDown={(e) => {
                          e.preventDefault(); // keep focus in the input
                          insertCommand(option);
                        }}
                        onMouseEnter={() => setActive(i)}
                        className={`flex cursor-pointer items-center justify-between gap-3 rounded-md px-2.5 py-1.5 text-[13px] ${
                          i === active ? 'bg-accent' : ''
                        }`}
                      >
                        <span className="text-primary font-mono text-[12px]">/{option.id}</span>
                        <span className="text-muted-foreground truncate text-[12px]">
                          {option.label}
                          {option.detail && <span className="text-fog"> · {option.detail}</span>}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="text-muted-foreground px-2.5 py-1.5 text-[12px]">
                      {slashOptions?.length ? `No category matches /${query}` : slashEmpty}
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
            {renderValue && (
              <div
                ref={mirrorRef}
                aria-hidden
                className="text-foreground pointer-events-none absolute inset-0 overflow-hidden rounded-md border border-transparent px-3 py-2 text-[14px] leading-5 whitespace-pre"
              >
                {renderValue(message)}
              </div>
            )}
            </div>

            <button
              title="Speak"
              onClick={send}
              className="bg-primary text-primary-foreground shadow-glow flex h-10 w-10 shrink-0 items-center justify-center rounded-md transition-all hover:brightness-110 active:scale-95"
            >
              <ArrowRight size={20} strokeWidth={2.5} />
            </button>
          </div>
          {footer}
        </motion.div>
      </LayoutGroup>
    </div>
  );
};
