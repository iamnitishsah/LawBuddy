import React, { useState } from 'react';
import type { CaseInfo, DraftInfo, Source } from '../../types/api';
import { Markdown } from '../common/Markdown';
import { CheckIcon, CopyIcon, DownloadIcon, ExternalLinkIcon } from '../common/Icons';
import { CATEGORY_LABEL, KIND_LABEL, factLabel } from './labels';

export type PanelTab = 'case' | 'sources' | 'draft';

interface Props {
  tab: PanelTab;
  onTab: (t: PanelTab) => void;
  caseInfo: CaseInfo | null;
  sources: Source[];
  highlight: number | null;
  drafts: DraftInfo[];
  onDownload: (n: number) => Promise<void>;
}

export const SidePanel: React.FC<Props> = ({ tab, onTab, caseInfo, sources, highlight, drafts, onDownload }) => {
  const tabs: { id: PanelTab; label: string; count?: number }[] = [
    { id: 'case', label: 'Your case' },
    { id: 'sources', label: 'Sources', count: sources.filter((s) => s.cited).length || undefined },
    { id: 'draft', label: 'Notice', count: drafts.length || undefined },
  ];
  return (
    <aside className="rounded-xl border border-rule bg-surface flex flex-col min-h-0 lg:max-h-[calc(100vh-9rem)]">
      <div className="flex border-b border-rule" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => onTab(t.id)}
            className={`flex-1 px-3 py-2.5 text-sm transition-colors ${
              tab === t.id ? 'text-ink font-medium border-b-2 border-ink -mb-px' : 'text-muted hover:text-ink'
            }`}
          >
            {t.label}
            {t.count ? <span className="ml-1 text-xs text-faint tabular">{t.count}</span> : null}
          </button>
        ))}
      </div>
      <div className="p-4 overflow-y-auto">
        {tab === 'case' && <CaseView c={caseInfo} />}
        {tab === 'sources' && <SourcesView sources={sources} highlight={highlight} />}
        {tab === 'draft' && <DraftView drafts={drafts} onDownload={onDownload} />}
      </div>
    </aside>
  );
};

const Empty: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="text-sm text-muted leading-relaxed">{children}</p>
);

const CaseView: React.FC<{ c: CaseInfo | null }> = ({ c }) => {
  if (!c || !c.category) {
    return <Empty>As you describe your problem, LawBuddy builds your case here: the facts, the dates and the proof.</Empty>;
  }
  const known = Object.entries(c.facts).filter(([, v]) => v);
  return (
    <div className="space-y-5 text-sm">
      <div>
        <div className="text-xs uppercase tracking-wide text-muted">Problem</div>
        <div className="mt-0.5 font-medium text-ink">{CATEGORY_LABEL[c.category] || c.category}</div>
        {c.state && <div className="text-xs text-muted mt-0.5">State: {c.state}</div>}
      </div>
      {c.summary && <p className="text-ink-2 leading-relaxed">{c.summary}</p>}
      <div>
        <div className="text-xs uppercase tracking-wide text-muted mb-1.5">What you told me</div>
        {known.length ? (
          <dl className="space-y-1.5">
            {known.map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <CheckIcon className="w-3.5 h-3.5 mt-1 shrink-0 text-accent" />
                <div>
                  <dt className="text-xs text-muted">{factLabel(k)}</dt>
                  <dd className="text-ink-2">{v}</dd>
                </div>
              </div>
            ))}
          </dl>
        ) : (
          <Empty>Nothing yet.</Empty>
        )}
      </div>
      {c.missing.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-muted mb-1.5">Still useful to know</div>
          <ul className="space-y-1 text-ink-2">
            {c.missing.map((k) => (
              <li key={k} className="flex gap-2">
                <span className="w-3.5 text-center text-faint">○</span>
                {factLabel(k)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {c.timeline.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-muted mb-1.5">Timeline</div>
          <ol className="border-l border-rule-strong pl-3 space-y-1.5">
            {c.timeline.map((t, i) => (
              <li key={i}>
                <span className="font-mono text-xs text-muted">{t.date}</span>
                <div className="text-ink-2">{t.event}</div>
              </li>
            ))}
          </ol>
        </div>
      )}
      {(c.evidence_have.length > 0 || c.evidence_missing.length > 0) && (
        <div>
          <div className="text-xs uppercase tracking-wide text-muted mb-1.5">Proof</div>
          <ul className="space-y-1 text-ink-2">
            {c.evidence_have.map((e) => (
              <li key={e} className="flex gap-2">
                <CheckIcon className="w-3.5 h-3.5 mt-1 shrink-0 text-accent" /> {e}
              </li>
            ))}
            {c.evidence_missing.map((e) => (
              <li key={e} className="flex gap-2 text-muted">
                <span className="w-3.5 text-center">✕</span> {e}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

const SourcesView: React.FC<{ sources: Source[]; highlight: number | null }> = ({ sources, highlight }) => {
  if (!sources.length) {
    return <Empty>When LawBuddy gives legal information, the articles it used appear here, with links to the official law.</Empty>;
  }
  return (
    <ol className="space-y-3">
      {sources.map((s) => (
        <li
          key={s.n}
          id={`source-${s.n}`}
          className={`rounded-lg border px-3 py-2.5 text-sm transition-colors ${
            highlight === s.n ? 'border-accent bg-accent-soft' : 'border-rule'
          } ${s.cited ? '' : 'opacity-60'}`}
        >
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xs text-accent">[{s.n}]</span>
            <span className="font-medium text-ink">{s.title}</span>
          </div>
          <div className="mt-1 text-xs text-muted">
            {KIND_LABEL[s.kind] || s.kind}
            {s.verified_on && <> · checked against the law on {s.verified_on}</>}
            {!s.cited && <> · shown to the model, not cited</>}
          </div>
          {s.urls.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
              {s.urls.map((u) => (
                <a key={u} href={u} target="_blank" rel="noreferrer noopener"
                   className="inline-flex items-center gap-1 text-xs text-accent hover:underline break-all">
                  Official source <ExternalLinkIcon className="w-3 h-3" />
                </a>
              ))}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
};

const DraftView: React.FC<{ drafts: DraftInfo[]; onDownload: (n: number) => Promise<void> }> = ({ drafts, onDownload }) => {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const d = drafts[drafts.length - 1];
  if (!d) {
    return (
      <Empty>
        Once LawBuddy understands your case, it can draft a legal notice for you to send. Ask "draft the notice", or
        use the Draft notice button.
      </Empty>
    );
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(d.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setError('Copy is not available here; use Download.');
    }
  };
  const download = async () => {
    setError(null);
    try {
      await onDownload(d.n);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed.');
    }
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={download}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-ink text-bg text-sm font-medium hover:opacity-90">
          <DownloadIcon className="w-4 h-4" /> Download (.md)
        </button>
        <button type="button" onClick={copy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-rule-strong text-sm text-ink-2 hover:bg-bg">
          {copied ? <CheckIcon className="w-4 h-4" /> : <CopyIcon className="w-4 h-4" />} {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
      {d.placeholders.length > 0 && (
        <div className="rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
          <div className="font-medium">Fill in before sending:</div>
          <ul className="list-disc pl-5 mt-1">
            {d.placeholders.map((p) => <li key={p}>{p}</li>)}
          </ul>
        </div>
      )}
      {d.warnings.map((w) => (
        <p key={w} className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{w}</p>
      ))}
      <div className="rounded-lg border border-rule bg-bg px-4 py-4 text-sm text-ink-2">
        <Markdown text={d.text} />
      </div>
      <p className="text-xs text-muted">
        Check every fact, date and amount. Send by Registered Post AD or Speed Post and by email, and keep the receipt.
        This is a draft for you to review, not legal advice.
      </p>
    </div>
  );
};
