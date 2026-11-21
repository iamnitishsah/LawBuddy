import React from 'react';
import { PageHeader, Section, Stat, StatRow } from '../components/common/ui';

// Numbers from docs/findings.md (measured 2026-11-21). Phase 6 adds the full test-case run.

const RETRIEVAL = [
  { mode: 'Keyword (BM25)', orig: '17 / 17', para: '8 / 20', hindi: '0 / 3' },
  { mode: 'Meaning-based (dense)', orig: '17 / 17', para: '18 / 20', hindi: '3 / 3' },
  { mode: 'Dense + rerank (used)', orig: '17 / 17', para: '20 / 20', hindi: '3 / 3' },
];

const FAILURES = [
  { what: 'An answer came back empty', why: 'The reasoning model spent its whole token budget thinking', fix: 'Low reasoning effort; empty replies retried with a larger budget' },
  { what: 'Told a user "you don\'t have a written agreement", which they never said', why: 'Unknown facts were shown to the model as null', fix: 'The model now sees "what you told us" and "not discussed yet"' },
  { what: 'Kannada speech was heard as Tamil and answered in Tamil', why: 'Whisper confused the languages', fix: 'Transcribed again as Kannada; a language picker in the chat' },
  { what: 'A notice\'s facts added "in good condition", which the user never said', why: 'The model embellished', fix: 'Stricter instructions; the user is told to check every fact (not checkable in code)' },
  { what: 'A civil-suit time limit attributed to the wrong law, in Hindi', why: 'Law names in Devanagari were not checked at first', fix: 'Hindi law names added to the registry; now checked' },
];

export const EvaluationPage: React.FC = () => (
  <>
    <PageHeader eyebrow="Evaluation" title="What was measured, and where it fails.">
      Every number here comes from real runs; the raw outputs are in the repository under <code>outputs/</code>.
    </PageHeader>

    <StatRow>
      <Stat value="20/20" label="Reworded questions find the right article" note="top 3, rerank, incl. Hindi" />
      <Stat value="0" label="Untraceable laws shown to a user" note="across all smoke runs" />
      <Stat value="182" label="Automated tests" note="offline, every turn branch" />
      <Stat value="~5 s" label="Typical answer time" note="Groq; Gemini much slower" />
    </StatRow>

    <Section title="Finding the right law" description="Questions in everyday words, not the knowledge base's wording. Correct article in the top 3.">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-muted border-b border-rule">
            <tr>
              <th className="py-2 pr-4 font-medium">Search</th>
              <th className="py-2 pr-4 font-medium">Original wording</th>
              <th className="py-2 pr-4 font-medium">Reworded</th>
              <th className="py-2 font-medium">Hindi</th>
            </tr>
          </thead>
          <tbody className="text-ink-2">
            {RETRIEVAL.map((r) => (
              <tr key={r.mode} className="border-b border-rule/70">
                <td className="py-2 pr-4">{r.mode}</td>
                <td className="py-2 pr-4 tabular">{r.orig}</td>
                <td className="py-2 pr-4 tabular">{r.para}</td>
                <td className="py-2 tabular">{r.hindi}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-sm text-muted max-w-3xl">
        A similarity score cannot tell a near-topic question (eviction, PF, a bounced cheque) from a real one, so scope
        is decided by the model's classification, with the score only as a safety floor.
      </p>
    </Section>

    <Section title="Traps it handles" description="From the scripted conversations.">
      <ul className="list-disc pl-5 space-y-1.5 text-ink-2 max-w-3xl text-sm">
        <li>"Is there a 2-month deposit cap in Karnataka?" → no such limit exists in the Karnataka Rent Act or its 2025 amendment.</li>
        <li>"Which Supreme Court judgment says…?" → it does not have reliable information on any judgment, and suggests the DLSA.</li>
        <li>"File under Section 420 IPC?" → outside its scope (criminal); referred to free legal aid.</li>
        <li>"He threatened to kill me" → helplines at once, from a rule, with no model call.</li>
      </ul>
    </Section>

    <Section title="Failures found, and what changed">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-muted border-b border-rule">
            <tr>
              <th className="py-2 pr-4 font-medium">What went wrong</th>
              <th className="py-2 pr-4 font-medium">Why</th>
              <th className="py-2 font-medium">Change</th>
            </tr>
          </thead>
          <tbody className="text-ink-2 align-top">
            {FAILURES.map((f) => (
              <tr key={f.what} className="border-b border-rule/70">
                <td className="py-2 pr-4">{f.what}</td>
                <td className="py-2 pr-4 text-muted">{f.why}</td>
                <td className="py-2">{f.fix}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-sm text-muted max-w-3xl">
        Still open: the guard checks references to law, not every claim, so a loose paraphrase of a correct rule can
        get through; real (non-synthetic) voices and noisy audio are not yet tested.
      </p>
    </Section>
  </>
);
