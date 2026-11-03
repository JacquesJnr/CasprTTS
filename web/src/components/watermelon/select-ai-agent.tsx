// Adapted from Watermelon UI's select-ai-agent: agents became voices, Enter speaks.
import React, { useState } from 'react';
import { motion, AnimatePresence, LayoutGroup } from 'motion/react';
import { ArrowRight } from 'lucide-react';

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
  className?: string;
}

export const SelectAIAgent: React.FC<SelectAIAgentProps> = ({
  agents,
  selectedId,
  onSelectAgent,
  onSendMessage,
  onEscape,
  footer,
  className = '',
}) => {
  const selectedAgent = agents.find((a) => a.id === selectedId) ?? agents[0];
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [message, setMessage] = useState('');

  const send = () => {
    if (!message.trim() || !selectedAgent) return;
    onSendMessage?.(message.trim(), selectedAgent.id);
    setMessage('');
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
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-xl transition-all active:scale-95 ${
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
              className="bg-muted border-border flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-md border text-xl"
            >
              {selectedAgent.icon}
            </motion.button>

            <input
              autoFocus
              type="text"
              placeholder={`Say something as ${selectedAgent.name}…`}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') send();
                if (e.key === 'Escape') (isMenuOpen ? setIsMenuOpen(false) : onEscape?.());
              }}
              className="text-foreground placeholder:text-muted-foreground bg-muted border-input min-w-0 flex-1 rounded-md border px-3 py-2 text-[14px] outline-none transition focus:border-primary/70 focus:shadow-glow"
            />

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
