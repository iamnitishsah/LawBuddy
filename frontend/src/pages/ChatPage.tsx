import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useChat } from '../hooks/useChat';
import { downloadDraft } from '../services/api';
import { useSettings } from '../services/settings';
import { Composer } from '../components/chat/Composer';
import { ReplyCard } from '../components/chat/ReplyCard';
import { SidePanel } from '../components/chat/SidePanel';
import type { PanelTab } from '../components/chat/SidePanel';
import { MicIcon, PlusIcon } from '../components/common/Icons';

const EXAMPLES = [
  'My landlord in Bengaluru is not returning my deposit of ₹1.5 lakh. I moved out on 31 October.',
  'Amazon delivered a phone with a cracked screen and keeps rejecting my return request.',
  'bhai mera owner deposit wapas nahi kar raha, maine flat chhod diya',
  'कंपनी ने तीन महीने से तनख्वाह नहीं दी, मैंने अगस्त में इस्तीफा दे दिया था',
  'ನನ್ನ ಕಂಪನಿ ಮೂರು ತಿಂಗಳಿಂದ ಸಂಬಳ ಕೊಟ್ಟಿಲ್ಲ. ನಾನು ಏನು ಮಾಡಬೇಕು?',
];

export const ChatPage: React.FC = () => {
  const chat = useChat();
  const { showSteps } = useSettings();
  const [tab, setTab] = useState<PanelTab>('case');
  const [selected, setSelected] = useState<{ turn: string; n: number | null } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [chat.turns]);

  // Sources: of the turn whose citation was clicked, else of the latest reply that had any.
  const sourceTurn = useMemo(() => {
    if (selected) return chat.turns.find((t) => t.id === selected.turn);
    return [...chat.turns].reverse().find((t) => t.reply?.sources.length);
  }, [chat.turns, selected]);

  const cite = (turnId: string, n: number) => {
    setSelected({ turn: turnId, n });
    setTab('sources');
    setTimeout(() => document.getElementById(`source-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50);
  };

  const canDraft = !!chat.caseInfo?.category && ['deposit', 'consumer', 'salary'].includes(chat.caseInfo.category);
  const onDownload = (n: number) => (chat.sessionId ? downloadDraft(chat.sessionId, n) : Promise.resolve());

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px] items-start">
      <section className="flex flex-col min-h-[70vh]">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-ink">Talk to LawBuddy</h1>
            <p className="text-sm text-muted">Deposits, refunds and unpaid salary · Karnataka · type or speak</p>
          </div>
          {chat.turns.length > 0 && (
            <button
              type="button"
              onClick={() => {
                chat.reset();
                setSelected(null);
                setTab('case');
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-rule-strong text-sm text-ink-2 hover:bg-surface"
            >
              <PlusIcon className="w-4 h-4" /> New conversation
            </button>
          )}
        </div>

        <div className="flex-1 space-y-5 pb-4" aria-live="polite">
          {chat.turns.length === 0 && (
            <div className="rounded-xl border border-dashed border-rule-strong px-5 py-6">
              <p className="text-ink-2">
                Tell me what happened, the way you would tell a friend. I'll ask for anything I need, explain where you
                stand using only verified law, and can draft a legal notice for you.
              </p>
              <p className="mt-2 text-sm text-muted inline-flex items-center gap-1.5">
                <MicIcon className="w-3.5 h-3.5" /> You can also speak, in English, Hindi or Kannada.
              </p>
              <div className="mt-4 grid gap-2">
                {EXAMPLES.map((e) => (
                  <button
                    key={e}
                    type="button"
                    onClick={() => chat.send(e)}
                    className="text-left text-sm px-3 py-2 rounded-lg border border-rule bg-surface text-ink-2 hover:border-accent hover:text-ink"
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>
          )}

          {chat.turns.map((t) => (
            <div key={t.id} className="space-y-3">
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-ink text-bg px-4 py-2.5 text-[0.97rem] whitespace-pre-wrap">
                  {t.viaVoice && (
                    <span className="flex items-center gap-1 text-xs opacity-70 mb-0.5">
                      <MicIcon className="w-3 h-3" /> {t.reply ? 'heard' : 'sending voice…'}
                    </span>
                  )}
                  {t.user}
                </div>
              </div>
              {t.reply ? (
                <ReplyCard
                  reply={t.reply}
                  showSteps={showSteps}
                  onCite={(n) => cite(t.id, n)}
                  onOpenDraft={() => setTab('draft')}
                />
              ) : t.failed ? (
                <div className="rounded-xl border border-danger bg-danger-soft px-4 py-3 text-sm text-danger">
                  {t.failed}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-muted px-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                  {t.viaVoice ? 'Listening and thinking…' : 'Thinking… (checking the law can take a few seconds)'}
                </div>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>

        <div className="sticky bottom-3">
          <Composer busy={chat.busy} canDraft={canDraft} onSend={chat.send} onAudio={chat.sendAudio} onDraft={chat.draft} />
          <p className="mt-2 text-center text-xs text-muted">
            Legal information, not legal advice. In an emergency call 112. Free legal aid: NALSA 15100.
          </p>
        </div>
      </section>

      <SidePanel
        tab={tab}
        onTab={setTab}
        caseInfo={chat.caseInfo}
        sources={sourceTurn?.reply?.sources || []}
        highlight={selected?.n ?? null}
        drafts={chat.drafts}
        onDownload={onDownload}
      />
    </div>
  );
};
