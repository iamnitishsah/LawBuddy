import React from 'react';
import { PageHeader, Section } from '../components/common/ui';
import { ArrowRightIcon, FileTextIcon, MicIcon, ShieldCheckIcon } from '../components/common/Icons';

const PROBLEMS = [
  { title: 'Security deposit not returned', body: 'Your landlord is keeping your deposit after you moved out, or cutting money from it.' },
  { title: 'Refund that never came', body: 'A seller, app or service owes you a refund or a replacement for something faulty.' },
  { title: 'Salary that stopped', body: 'Your employer has not paid your wages or your final dues after you left.' },
];

const STEPS = [
  { icon: MicIcon, title: 'Tell your story', body: 'Type or speak, in English, Hindi, Hinglish or Kannada. LawBuddy asks only for what it needs.' },
  { icon: ShieldCheckIcon, title: 'Know where you stand', body: 'Plain-language answers that cite verified central and Karnataka law, never invented sections or cases.' },
  { icon: FileTextIcon, title: 'Act on it', body: 'A legal notice drafted from your facts, ready to fill in, sign and send.' },
];

export const OverviewPage: React.FC<{ onStart: () => void }> = ({ onStart }) => (
  <>
    <PageHeader eyebrow="LawBuddy" title="Legal help for everyday problems, in your language.">
      Most people give up on a deposit, a refund or unpaid salary because a lawyer feels too expensive and the process
      too confusing. LawBuddy turns your story into a case, explains where you stand, and prepares the legal notice.
      <div className="mt-6">
        <button
          type="button"
          onClick={onStart}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-full bg-ink text-bg text-base font-medium hover:opacity-90"
        >
          Talk to LawBuddy <ArrowRightIcon className="w-4 h-4" />
        </button>
      </div>
    </PageHeader>

    <Section title="What it helps with" description="Karnataka, under central and Karnataka law. Anything else is referred to a lawyer or free legal aid.">
      <div className="grid gap-4 sm:grid-cols-3">
        {PROBLEMS.map((p) => (
          <div key={p.title} className="rounded-xl border border-rule bg-surface p-5">
            <h3 className="font-semibold text-ink">{p.title}</h3>
            <p className="mt-1 text-sm text-muted">{p.body}</p>
          </div>
        ))}
      </div>
    </Section>

    <Section title="How it helps">
      <div className="grid gap-6 sm:grid-cols-3">
        {STEPS.map(({ icon: Icon, title, body }) => (
          <div key={title}>
            <Icon className="w-5 h-5 text-accent" />
            <h3 className="mt-2 font-semibold text-ink">{title}</h3>
            <p className="mt-1 text-sm text-muted">{body}</p>
          </div>
        ))}
      </div>
    </Section>

    <Section title="What it will not do">
      <ul className="list-disc pl-5 space-y-1.5 text-ink-2 max-w-3xl">
        <li>It gives legal information, not legal advice, and says when you need a real lawyer.</li>
        <li>It does not cover criminal cases, police matters, family disputes, property title, cheque bounce, PF or tax. It points you to your District Legal Services Authority (free if you qualify) or NALSA 15100.</li>
        <li>In an emergency it shows helplines first: call 112.</li>
      </ul>
    </Section>
  </>
);
