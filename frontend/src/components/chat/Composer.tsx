import React, { useState } from 'react';
import { useRecorder } from '../../hooks/useRecorder';
import { updateSettings, useSettings } from '../../services/settings';
import type { LanguageHint } from '../../services/settings';
import { FileTextIcon, MicIcon, SendIcon, StopIcon } from '../common/Icons';

const LANGUAGES: { id: LanguageHint; label: string; title: string }[] = [
  { id: '', label: 'Auto', title: 'Detect the spoken language' },
  { id: 'en', label: 'EN', title: 'English' },
  { id: 'hi', label: 'हिं', title: 'Hindi' },
  { id: 'kn', label: 'ಕನ್ನ', title: 'Kannada' },
];

interface Props {
  busy: boolean;
  canDraft: boolean;
  onSend: (text: string) => void;
  onAudio: (audio: Blob, filename: string) => void;
  onDraft: () => void;
}

export const Composer: React.FC<Props> = ({ busy, canDraft, onSend, onAudio, onDraft }) => {
  const [text, setText] = useState('');
  const { language } = useSettings();
  const rec = useRecorder(onAudio);
  const recording = rec.state === 'recording';

  const submit = () => {
    const t = text.trim();
    if (!t || busy) return;
    onSend(t);
    setText('');
  };

  return (
    <div className="rounded-xl border border-rule-strong bg-surface p-2.5 focus-within:border-accent transition-colors">
      {recording ? (
        <div className="flex items-center gap-3 px-2 py-3 text-sm">
          <span className="w-2.5 h-2.5 rounded-full bg-danger animate-pulse" />
          <span className="text-ink">Listening…</span>
          <span className="font-mono text-muted tabular">
            {Math.floor(rec.seconds / 60)}:{String(rec.seconds % 60).padStart(2, '0')} / 2:00
          </span>
          <span className="text-muted hidden sm:inline">Speak in English, Hindi or Kannada. Tap stop when done.</span>
        </div>
      ) : (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          rows={2}
          maxLength={4000}
          placeholder="Describe your problem in your own words, in English, Hindi or Kannada…"
          className="w-full resize-none bg-transparent px-2 py-1.5 text-[0.97rem] text-ink placeholder:text-faint focus:outline-none"
          aria-label="Your message"
          disabled={busy}
        />
      )}
      {rec.error && <p className="px-2 pb-1 text-xs text-danger">{rec.error}</p>}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <div className="flex rounded-md border border-rule overflow-hidden" role="group" aria-label="Spoken language">
          {LANGUAGES.map((l) => (
            <button
              key={l.id || 'auto'}
              type="button"
              title={`Voice language: ${l.title}`}
              onClick={() => updateSettings({ language: l.id })}
              className={`px-2 py-1 text-xs ${language === l.id ? 'bg-ink text-bg' : 'text-muted hover:text-ink'}`}
            >
              {l.label}
            </button>
          ))}
        </div>
        {canDraft && (
          <button
            type="button"
            onClick={onDraft}
            disabled={busy || recording}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-rule-strong text-xs text-ink-2 hover:bg-bg disabled:opacity-50"
          >
            <FileTextIcon className="w-3.5 h-3.5" /> Draft notice
          </button>
        )}
        <div className="ml-auto flex items-center gap-2">
          {rec.state !== 'unsupported' && (
            <button
              type="button"
              onClick={recording ? rec.stop : rec.start}
              disabled={busy}
              className={`p-2 rounded-full border transition-colors disabled:opacity-50 ${
                recording ? 'border-danger text-danger bg-danger-soft' : 'border-rule-strong text-ink-2 hover:bg-bg'
              }`}
              aria-label={recording ? 'Stop recording and send' : 'Record a voice message'}
              title={recording ? 'Stop and send' : 'Speak instead of typing'}
            >
              {recording ? <StopIcon className="w-4 h-4" /> : <MicIcon className="w-4 h-4" />}
            </button>
          )}
          <button
            type="button"
            onClick={submit}
            disabled={busy || recording || !text.trim()}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-ink text-bg text-sm font-medium hover:opacity-90 disabled:opacity-40"
          >
            <SendIcon className="w-4 h-4" /> Send
          </button>
        </div>
      </div>
    </div>
  );
};
