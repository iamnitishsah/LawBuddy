import React from 'react';
import { Code, PageHeader, Section } from '../components/common/ui';

const STEPS = [
  {
    n: '1',
    title: 'Emergency rules',
    who: 'Code, no API',
    body: 'Words that signal danger (violence, threats, self-harm) in English, Hinglish and Hindi trigger helplines at once. Safety does not depend on any API being up.',
  },
  {
    n: '2',
    title: 'Understanding the message',
    who: 'One model call',
    body: 'The model reads the conversation and returns the problem type (deposit, refund, salary, out of scope, unclear), the language, the facts of the case, and an English search query in legal terms.',
  },
  {
    n: '3',
    title: 'Follow-up questions',
    who: 'Code decides',
    body: 'If key facts are missing (for a deposit: how much, and when you moved out), LawBuddy asks for them, at most twice. General questions are answered straight away.',
  },
  {
    n: '4',
    title: 'Finding the law',
    who: 'Search + rerank',
    body: 'The query searches 32 short articles written from the official texts and checked against them. If nothing matches well enough, LawBuddy says it does not know instead of guessing.',
  },
  {
    n: '5',
    title: 'Answer and check',
    who: 'Model + code',
    body: 'The model answers only from the articles found, citing each one. Code then checks every Act, section, rule and article named against a registry of allowed law; anything untraceable is rewritten once, then removed.',
  },
];

export const HowItWorksPage: React.FC = () => (
  <>
    <PageHeader eyebrow="How it works" title="The model never supplies law from memory.">
      AI models confidently invent laws, sections and court cases. LawBuddy is built so that every legal statement
      traces to a verified source, and code, not the model, checks that it does.
    </PageHeader>

    <Section title="Every message, step by step">
      <ol className="grid gap-4 lg:grid-cols-5">
        {STEPS.map((s) => (
          <li key={s.n} className="rounded-xl border border-rule bg-surface p-4">
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-2xl text-accent">{s.n}</span>
              <h3 className="font-semibold text-ink">{s.title}</h3>
            </div>
            <div className="mt-1 text-xs uppercase tracking-wide text-muted">{s.who}</div>
            <p className="mt-2 text-sm text-ink-2 leading-relaxed">{s.body}</p>
          </li>
        ))}
      </ol>
    </Section>

    <Section title="How invented law is stopped" description="Three layers, each in code.">
      <div className="grid gap-4 md:grid-cols-3 text-sm text-ink-2">
        <div className="rounded-xl border border-rule bg-surface p-4">
          <h3 className="font-semibold text-ink">A small, verified knowledge base</h3>
          <p className="mt-1">32 articles written from the bare acts (Consumer Protection Act 2019, Code on Wages 2019, Karnataka Rent Act 1999, Indian Contract Act, Limitation Act, Legal Services Authorities Act), each checked against its source and dated.</p>
        </div>
        <div className="rounded-xl border border-rule bg-surface p-4">
          <h3 className="font-semibold text-ink">A registry of allowed law</h3>
          <p className="mt-1">Only the laws and sections listed in <Code>kb/registry.yaml</Code> may be named. Repealed laws (IPC, CrPC, Consumer Protection Act 1986, Payment of Wages Act) are listed with what replaced them.</p>
        </div>
        <div className="rounded-xl border border-rule bg-surface p-4">
          <h3 className="font-semibold text-ink">A guard on every answer</h3>
          <p className="mt-1">Patterns find every law, section, rule, article and case citation, in English and Hindi. Court cases are never allowed; unknown laws, wrong years and unlisted sections are rewritten, then removed.</p>
        </div>
      </div>
    </Section>

    <Section title="Legal notices">
      <p className="text-ink-2 max-w-3xl leading-relaxed">
        Code writes everything with legal weight: the layout, the legal basis, the demand with a 15-day deadline, and
        what happens if it is ignored. The model writes only the facts, from what you said. Code then rejects any law
        in the facts and any amount or date you never gave, and leaves visible <Code>[● fill: …]</Code> blanks for what
        is still unknown.
      </p>
    </Section>

    <Section title="Your data and keys">
      <ul className="list-disc pl-5 space-y-1.5 text-ink-2 max-w-3xl text-sm">
        <li>A conversation lives in server memory and is forgotten after two idle hours; reloading the page starts a new one.</li>
        <li>You can use your own model provider key (Settings). It is sent with each message, never stored or logged, and forgotten when you reload.</li>
        <li>Voice is transcribed by Whisper. Choose Kannada if you speak Kannada: automatic detection can mistake it for Tamil.</li>
      </ul>
    </Section>
  </>
);
