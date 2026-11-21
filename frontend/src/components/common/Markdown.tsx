import React from 'react';

// A small Markdown renderer for LawBuddy's replies and notices. It builds React elements only (no innerHTML), so
// model output cannot inject markup. Supported: paragraphs, line breaks, # headings, --- rules, "-"/"*"/"•" and
// "1." lists, **bold**, *italic*, [n] citations (clickable), and [● fill: ...] placeholders (highlighted).

interface Props {
  text: string;
  onCite?: (n: number) => void;
  citable?: Set<number>; // citation numbers that exist; others render as plain text
}

const INLINE_RE = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|\[● fill: [^\]]+\]|\[\d+\])/g;

function inline(text: string, props: Props, keyBase: string): React.ReactNode[] {
  return text.split(INLINE_RE).map((part, i) => {
    const key = `${keyBase}-${i}`;
    if (!part) return null;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={key} className="font-semibold text-ink">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('[● fill:')) {
      return (
        <mark key={key} className="rounded px-1 py-px bg-warn-soft text-warn font-medium">
          {part}
        </mark>
      );
    }
    const cite = /^\[(\d+)\]$/.exec(part);
    if (cite) {
      const n = Number(cite[1]);
      if (props.onCite && (!props.citable || props.citable.has(n))) {
        return (
          <button
            key={key}
            type="button"
            onClick={() => props.onCite?.(n)}
            className="mx-px align-super text-[0.7em] font-mono font-medium text-accent hover:underline"
            aria-label={`Show source ${n}`}
          >
            [{n}]
          </button>
        );
      }
      return <span key={key} className="align-super text-[0.7em] font-mono text-muted">[{n}]</span>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    return <React.Fragment key={key}>{part}</React.Fragment>;
  });
}

type Block =
  | { type: 'p'; lines: string[] }
  | { type: 'h'; level: number; text: string }
  | { type: 'hr' }
  | { type: 'ul' | 'ol'; items: string[] };

function parse(text: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: { type: 'ul' | 'ol'; items: string[] } | null = null;
  const flush = () => {
    if (para.length) blocks.push({ type: 'p', lines: para });
    if (list) blocks.push(list);
    para = [];
    list = null;
  };
  for (const raw of text.replace(/\r/g, '').split('\n')) {
    const line = raw.replace(/\s+$/, '');
    if (!line.trim()) {
      flush();
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (/^-{3,}$/.test(line.trim())) {
      flush();
      blocks.push({ type: 'hr' });
    } else if (heading) {
      flush();
      blocks.push({ type: 'h', level: heading[1].length, text: heading[2] });
    } else if (bullet || numbered) {
      const type = bullet ? 'ul' : 'ol';
      if (para.length) {
        blocks.push({ type: 'p', lines: para });
        para = [];
      }
      if (!list || list.type !== type) {
        if (list) blocks.push(list);
        list = { type, items: [] };
      }
      list.items.push((bullet || numbered)![1]);
    } else if (list && /^\s{2,}/.test(raw)) {
      list.items[list.items.length - 1] += `\n${line.trim()}`; // continuation of a list item
    } else {
      if (list) {
        blocks.push(list);
        list = null;
      }
      para.push(line);
    }
  }
  flush();
  return blocks;
}

export const Markdown: React.FC<Props> = (props) => {
  const blocks = parse(props.text);
  return (
    <div className="space-y-3 leading-relaxed">
      {blocks.map((b, i) => {
        const k = `b${i}`;
        if (b.type === 'hr') return <hr key={k} className="border-rule my-4" />;
        if (b.type === 'h') return <h3 key={k} className="font-semibold text-ink">{inline(b.text, props, k)}</h3>;
        if (b.type === 'p') {
          return (
            <p key={k}>
              {b.lines.map((l, j) => (
                <React.Fragment key={j}>
                  {j > 0 && <br />}
                  {inline(l, props, `${k}-${j}`)}
                </React.Fragment>
              ))}
            </p>
          );
        }
        const Tag = b.type;
        return (
          <Tag key={k} className={`${b.type === 'ol' ? 'list-decimal' : 'list-disc'} pl-5 space-y-1.5`}>
            {b.items.map((item, j) => (
              <li key={j}>
                {item.split('\n').map((l, m) => (
                  <React.Fragment key={m}>
                    {m > 0 && <br />}
                    {inline(l, props, `${k}-${j}-${m}`)}
                  </React.Fragment>
                ))}
              </li>
            ))}
          </Tag>
        );
      })}
    </div>
  );
};
