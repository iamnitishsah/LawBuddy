import { useCallback, useRef, useState } from 'react';
import { ApiError, createSession, draftNow, sendMessage, sendVoice } from '../services/api';
import type { CaseInfo, ChatResponse, DraftInfo, Turn } from '../types/api';

// One conversation, kept in page memory only (a reload starts a new one: a legal problem may be private, and the
// device may be shared). The server session is created on the first message and recreated once if it expired.

export interface ChatState {
  turns: Turn[];
  busy: boolean;
  caseInfo: CaseInfo | null;
  drafts: DraftInfo[];
  sessionId: string | null;
}

let counter = 0;
const nextId = () => `t${Date.now()}-${counter++}`;

export function useChat() {
  const [state, setState] = useState<ChatState>({ turns: [], busy: false, caseInfo: null, drafts: [], sessionId: null });
  const sessionRef = useRef<string | null>(null);

  const ensureSession = useCallback(async (fresh = false): Promise<string> => {
    if (sessionRef.current && !fresh) return sessionRef.current;
    const s = await createSession();
    sessionRef.current = s.session_id;
    setState((st) => ({ ...st, sessionId: s.session_id }));
    return s.session_id;
  }, []);

  // Runs one request with the session; if the server has forgotten the session (404), starts a new one and retries.
  const withSession = useCallback(
    async (call: (sid: string) => Promise<ChatResponse>): Promise<ChatResponse> => {
      const sid = await ensureSession();
      try {
        return await call(sid);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return call(await ensureSession(true));
        throw e;
      }
    },
    [ensureSession],
  );

  const run = useCallback(
    async (turn: Turn, call: (sid: string) => Promise<ChatResponse>) => {
      setState((st) => ({ ...st, busy: true, turns: [...st.turns, turn] }));
      try {
        const reply = await withSession(call);
        setState((st) => ({
          ...st,
          busy: false,
          caseInfo: reply.case,
          drafts: reply.draft ? [...st.drafts.filter((d) => d.n !== reply.draft!.n), reply.draft] : st.drafts,
          turns: st.turns.map((t) =>
            t.id === turn.id ? { ...t, reply, user: turn.viaVoice ? reply.transcript || t.user : t.user } : t,
          ),
        }));
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Something went wrong.';
        setState((st) => ({
          ...st,
          busy: false,
          turns: st.turns.map((t) => (t.id === turn.id ? { ...t, failed: message } : t)),
        }));
      }
    },
    [withSession],
  );

  const send = useCallback(
    (text: string) => run({ id: nextId(), user: text, viaVoice: false }, (sid) => sendMessage(sid, text)),
    [run],
  );

  const sendAudio = useCallback(
    (audio: Blob, filename: string) =>
      run({ id: nextId(), user: 'Voice message…', viaVoice: true }, (sid) => sendVoice(sid, audio, filename)),
    [run],
  );

  const draft = useCallback(
    () => run({ id: nextId(), user: 'Draft the legal notice', viaVoice: false }, (sid) => draftNow(sid)),
    [run],
  );

  const reset = useCallback(() => {
    sessionRef.current = null;
    setState({ turns: [], busy: false, caseInfo: null, drafts: [], sessionId: null });
  }, []);

  return { ...state, send, sendAudio, draft, reset };
}
