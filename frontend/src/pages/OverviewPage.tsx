import React from 'react';
import { PageHeader, Section } from '../components/common/ui';

const PROBLEMS = [
  { title: 'Security deposit not returned', body: 'Your landlord is keeping your deposit after you moved out.' },
  { title: 'Refund that never came', body: 'A seller or service provider owes you a refund or replacement.' },
  { title: 'Salary that stopped', body: 'Your employer has not paid your wages or final dues.' },
];

export const OverviewPage: React.FC = () => (
  <>
    <PageHeader eyebrow="LawBuddy" title="Legal help for everyday problems, in your language.">
      Tell LawBuddy what happened, by text or voice. It turns your story into a case, explains where you stand in
      plain language, and prepares what you need to act, such as a legal notice.
    </PageHeader>

    <Section title="What it helps with" description="Coverage grows phase by phase; anything else is referred to a real lawyer.">
      <div className="grid gap-4 sm:grid-cols-3">
        {PROBLEMS.map((p) => (
          <div key={p.title} className="rounded-xl border border-rule bg-surface p-5">
            <h3 className="font-semibold text-ink">{p.title}</h3>
            <p className="mt-1 text-sm text-muted">{p.body}</p>
          </div>
        ))}
      </div>
    </Section>
  </>
);
