import { useCallback, useEffect, useRef, useState } from 'react';

// Records a voice message with the browser's MediaRecorder. The format is whatever the browser supports
// (Chrome/Firefox: webm or ogg, Safari: mp4); the server accepts all three. Recording stops by itself at MAX_SECONDS.

const MAX_SECONDS = 120;
const TYPES: [string, string][] = [
  ['audio/webm', 'webm'],
  ['audio/mp4', 'm4a'],
  ['audio/ogg', 'ogg'],
];

export type RecorderState = 'idle' | 'recording' | 'unsupported';

export function useRecorder(onDone: (audio: Blob, filename: string) => void) {
  const supported = typeof window !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && 'MediaRecorder' in window;
  const [state, setState] = useState<RecorderState>(supported ? 'idle' : 'unsupported');
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | null>(null);
  const doneRef = useRef(onDone);

  useEffect(() => {
    doneRef.current = onDone;
  }, [onDone]);

  const stop = useCallback(() => {
    if (timer.current) window.clearInterval(timer.current);
    timer.current = null;
    if (recorder.current && recorder.current.state !== 'inactive') recorder.current.stop();
  }, []);

  const start = useCallback(async () => {
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError('Microphone permission was denied. You can type your message instead.');
      return;
    }
    const [mimeType, ext] = TYPES.find(([t]) => MediaRecorder.isTypeSupported(t)) || ['', 'webm'];
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      setState('idle');
      const blob = new Blob(chunks, { type: rec.mimeType || mimeType || 'audio/webm' });
      if (blob.size > 0) doneRef.current(blob, `voice.${ext}`);
    };
    recorder.current = rec;
    rec.start();
    setSeconds(0);
    setState('recording');
    timer.current = window.setInterval(() => {
      setSeconds((s) => {
        if (s + 1 >= MAX_SECONDS) stop();
        return s + 1;
      });
    }, 1000);
  }, [stop]);

  useEffect(() => stop, [stop]);

  return { state, seconds, error, start, stop, maxSeconds: MAX_SECONDS };
}
