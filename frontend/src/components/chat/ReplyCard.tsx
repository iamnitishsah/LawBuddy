import React, { useState } from 'react';
import type { ChatResponse } from '../../types/api';
import { Markdown } from '../common/Markdown';
import { AlertTriangleIcon, ChevronRightIcon, FileTextIcon, PhoneIcon, ShieldCheckIcon } from '../common/Icons';

// One LawBuddy reply. The kind decides the frame: emergency and referral replies look different from advice, so a
// person in danger or out of scope sees that at once.

const FRAME: Record<string, { box: string; label: string | null }> = {
  emergency: { box: 'border-danger bg-danger-soft', label: 'Your safety first' },
  escalate: { box: 'border-warn bg-warn-soft', label: 'Outside what LawBuddy covers' },
  not_found: { box: 'border-warn bg-warn-soft', label: 'Not in my sources' },
  error: { box: 'border-danger bg-danger-soft', label: 'Something went wrong' },
  draft: { box: 'border-accent bg-accent-soft', label: 'Legal notice drafted' },
};

interface Props {
  reply: ChatResponse;
  showSteps: boolean;
  onCite: (n: number) => void;
  onOpenDraft: () => void;
}

export const ReplyCard: React.FC<Props> = ({ reply, showSteps, onCite, onOpenDraft }) => {
  const [open, setOpen] = useState(showSteps);
  const frame = FRAME[reply.kind];
  const citable = new Set(reply.sources.map((s) => s.n));
  // A drafted notice is shown in the side panel; the chat shows only the intro above the "---".
  const text = reply.kind === 'draft' ? reply.text.split('\n---\n')[0] : reply.text;
  const g = reply.guard;

  return (
    <div className={`rounded-xl border px-4 py-3.5 sm:px-5 ${frame ? frame.box : 'border-rule bg-surface'}`}>
      {frame?.label && (
        <div className="flex items-center gap-2 mb-2 text-xs font-semibold uppercase tracking-wide text-ink-2">
          {reply.kind === 'emergency' ? (
            <PhoneIcon className="w-3.5 h-3.5" />
          ) : reply.kind === 'draft' ? (
            <FileTextIcon className="w-3.5 h-3.5" />
          ) : (
            <AlertTriangleIcon className="w-3.5 h-3.5" />
          )}
          {frame.label}
        </div>
      )}

      <div className="text-[0.97rem] text-ink-2">
        <Markdown text={text} onCite={onCite} citable={citable} />
      </div>

      {reply.kind === 'draft' && reply.draft && (
        <button
          type="button"
          onClick={onOpenDraft}
          className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-ink text-bg text-sm font-medium hover:opacity-90"
        >
          <FileTextIcon className="w-4 h-4" /> Open the notice
        </button>
      )}

      {reply.error && <p className="mt-2 text-xs text-danger font-mono break-words">{reply.error}</p>}

      <div className="mt-3 pt-2.5 border-t border-rule/70 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        {g.checked && (
          <span className="inline-flex items-center gap-1" title="Every law named was traced to LawBuddy's sources">
            <ShieldCheckIcon className="w-3.5 h-3.5 text-accent" />
            {g.problems.length ? 'Some statements removed' : 'Legal references checked'}
          </span>
        )}
        <span className="font-mono">{(reply.latency_ms / 1000).toFixed(1)} s</span>
        {reply.model && <span className="font-mono truncate max-w-[16rem]">{reply.model}</span>}
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="ml-auto inline-flex items-center gap-0.5 hover:text-ink"
          aria-expanded={open}
        >
          Why this answer?
          <ChevronRightIcon className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-90' : ''}`} />
        </button>
      </div>

      {open && <Details reply={reply} />}
    </div>
  );
};

const Details: React.FC<{ reply: ChatResponse }> = ({ reply }) => {
  const { guard: g, retrieval: r, usage: u } = reply;
  return (
    <div className="mt-3 rounded-lg bg-sunken px-3 py-2.5 text-xs text-ink-2 space-y-2">
      <ol className="space-y-1 font-mono text-[0.72rem] leading-snug list-decimal pl-4">
        {reply.steps.map((s, i) => (
          <li key={i} className="break-words">{s}</li>
        ))}
      </ol>
      {r?.mode && (
        <p>
          Search: {r.mode === 'primary' ? 'meaning-based (rerank)' : 'keyword fallback'}
          {r.top_score != null && <> · best match {r.top_score.toFixed(3)}</>}
          {r.floor != null && <> (minimum {r.floor})</>}
        </p>
      )}
      {g.checked && (
        <p>
          Guard:{' '}
          {g.first_problems.length
            ? `first answer had ${g.first_problems.join('; ')} → ${g.removed ? 'sentences removed' : 'rewritten'}`
            : 'every law, section and rule named was traced to the sources'}
          {g.uncited_sentences > 0 && ` · ${g.uncited_sentences} sentence(s) without a citation`}
        </p>
      )}
      <p className="font-mono">
        {u.llm_calls} model calls · {u.input_tokens} in / {u.output_tokens} out tokens · model {u.llm_s}s · search{' '}
        {u.retrieval_s}s
      </p>
    </div>
  );
};
