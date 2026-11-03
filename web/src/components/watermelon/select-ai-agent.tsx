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
              className="border-border bg-popover absolute bottom-full left-0 z-10 mb-2 flex w-fit origin-bottom-left gap-1.5 rounded-xl border p-1.5"
            >
              {agents.map((agent) => (
                <button
                  key={agent.id}
                  title={agent.name}
                  onClick={() => {
                    onSelectAgent?.(agent.id);
                    setIsMenuOpen(false);
                  }}
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-2xl transition-all active:scale-95 ${
                    selectedAgent.id === agent.id
                      ? 'border-primary bg-secondary border'
                      : 'hover:bg-accent'
                  }`}
                >
                  {agent.icon}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <motion.div layout className="border-border bg-card rounded-[22px] border p-3.5">
          <div className="flex items-center gap-3">
            <motion.button
              layoutId={`agent-${selectedAgent.id}`}
              title={`Voice: ${selectedAgent.name}`}
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="bg-secondary flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-xl text-2xl"
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
              className="text-foreground placeholder:text-muted-foreground bg-input min-w-0 flex-1 rounded-xl px-3 py-2.5 text-[15px] outline-none focus:ring-2 focus:ring-ring"
            />

            <button
              title="Speak"
              onClick={send}
              className="bg-primary text-primary-foreground flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-all hover:scale-105 active:scale-90"
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
