import React, { useEffect, useState } from 'react';
import { API_BASE_URL, checkHealth, getBackends } from '../../services/api';
import { getSettings, updateSettings } from '../../services/settings';
import type { BackendsResponse } from '../../types/api';
import { XIcon } from '../common/Icons';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfigChanged: () => void;
}

const input =
  'mt-1.5 w-full bg-bg border border-rule-strong rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:border-accent transition-colors';

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, onConfigChanged }) => {
  if (!isOpen) return null;
  return <SettingsForm onClose={onClose} onConfigChanged={onConfigChanged} />;
};

// Mounted only while open, so each opening starts from the current settings.
const SettingsForm: React.FC<Omit<SettingsModalProps, 'isOpen'>> = ({ onClose, onConfigChanged }) => {
  const initial = getSettings();
  const [serverKey, setServerKey] = useState(initial.serverKey);
  const [backend, setBackend] = useState(initial.llm.backend || '');
  const [model, setModel] = useState(initial.llm.model || '');
  const [llmKey, setLlmKey] = useState(initial.llmKey);
  const [showKey, setShowKey] = useState(false);
  const [showSteps, setShowSteps] = useState(initial.showSteps);
  const [backends, setBackends] = useState<BackendsResponse | null>(null);
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    getBackends().then(setBackends).catch(() => setBackends(null));
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const chosen = backends?.backends.find((b) => b.name === backend);
  const serverDefault = backends?.backends.find((b) => b.default);
  const needsKey = chosen ? !chosen.server_key : serverDefault ? !serverDefault.server_key : false;

  const save = () => {
    updateSettings({
      serverKey: serverKey.trim(),
      llm: { backend: backend || null, model: model.trim() || null },
      llmKey: llmKey.trim(),
      showSteps,
    });
    onConfigChanged();
  };

  const test = async () => {
    save();
    setStatus(null);
    try {
      const { data, pingMs } = await checkHealth();
      setStatus({ ok: true, text: `Connected in ${pingMs} ms · ${data.kb_chunks} legal articles · search: ${data.retrieval}` });
    } catch (e) {
      setStatus({ ok: false, text: e instanceof Error ? e.message : 'Connection failed' });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px] p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-surface border border-rule rounded-xl shadow-[0_24px_64px_-16px_rgba(0,0,0,0.25)]"
      >
        <div className="flex items-start justify-between px-6 pt-5">
          <div>
            <h3 id="settings-title" className="text-base font-semibold">Settings</h3>
            <p className="mt-1 text-sm text-muted font-mono break-all">{API_BASE_URL}</p>
          </div>
          <button onClick={onClose} className="p-1 -mr-1 rounded text-muted hover:text-ink" aria-label="Close">
            <XIcon className="w-4 h-4" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          <fieldset className="space-y-3">
            <legend className="text-sm font-medium text-ink">Model</legend>
            <label className="block">
              <span className="text-xs font-medium text-muted">Provider</span>
              <select value={backend} onChange={(e) => setBackend(e.target.value)} className={input}>
                <option value="">
                  Server default{serverDefault ? ` (${serverDefault.name} · ${serverDefault.model})` : ''}
                </option>
                {backends?.backends.map((b) => (
                  <option key={b.name} value={b.name}>
                    {b.name} · {b.model}
                    {b.server_key ? '' : ' (needs your key)'}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-muted">Model name (optional, another model of this provider)</span>
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={chosen?.model || serverDefault?.model || 'default'}
                spellCheck={false}
                className={`${input} font-mono`}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-muted">
                Your API key for this provider {needsKey ? '(required: the server has none)' : '(optional)'}
              </span>
              <div className="flex gap-2">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={llmKey}
                  onChange={(e) => setLlmKey(e.target.value)}
                  placeholder="Uses the server's key if empty"
                  spellCheck={false}
                  autoComplete="off"
                  className={`${input} font-mono`}
                />
                <button type="button" onClick={() => setShowKey((s) => !s)}
                        className="mt-1.5 px-3 rounded-lg border border-rule-strong text-xs text-muted hover:text-ink">
                  {showKey ? 'Hide' : 'Show'}
                </button>
              </div>
              <span className="mt-1 block text-xs text-muted">
                Replaces the server's key for your messages. Kept only in this page's memory: never saved, and
                forgotten when you reload.
              </span>
            </label>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium text-ink">Server access</legend>
            <label className="block">
              <span className="text-xs font-medium text-muted">Access key (only if the server requires one)</span>
              <input type="password" value={serverKey} onChange={(e) => setServerKey(e.target.value)}
                     autoComplete="off" spellCheck={false} className={`${input} font-mono`} />
            </label>
          </fieldset>

          <label className="flex items-center gap-2 text-sm text-ink-2">
            <input type="checkbox" checked={showSteps} onChange={(e) => setShowSteps(e.target.checked)} />
            Show "Why this answer?" details open by default
          </label>

          {status && (
            <div className={`rounded-lg px-3 py-2.5 text-sm ${status.ok ? 'bg-accent-soft text-accent' : 'bg-danger-soft text-danger'}`}>
              {status.text}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-rule">
          <button type="button" onClick={test}
                  className="px-3.5 py-1.5 rounded-md border border-rule-strong text-sm text-ink-2 hover:bg-bg">
            Test connection
          </button>
          <button type="button" onClick={() => { save(); onClose(); }}
                  className="px-3.5 py-1.5 rounded-md bg-ink text-bg text-sm font-medium hover:opacity-90">
            Save
          </button>
        </div>
      </div>
    </div>
  );
};
