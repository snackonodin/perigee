import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { SAFETY_ACK_DELAY_MS, type SafetyContent } from "./safety";

interface SafetyApi {
  /** Show the safety screen now (or update its text if it is already showing). */
  showSafety(content: SafetyContent): void;
}

const SafetyContext = createContext<SafetyApi | null>(null);

export function useSafety(): SafetyApi {
  const ctx = useContext(SafetyContext);
  if (!ctx) throw new Error("useSafety must be used inside <SafetyProvider>");
  return ctx;
}

/** Global safety screen. Rendered in a portal on document.body above every page, so any
 *  page can raise it and nothing in a page can cover it. */
export function SafetyProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<SafetyContent | null>(null);
  const [until, setUntil] = useState(0);
  const showSafety = useCallback((c: SafetyContent) => {
    setContent(c);
    // keep a running countdown: a second call (server result after the local check) only
    // updates the text
    setUntil((u) => (u > Date.now() ? u : Date.now() + SAFETY_ACK_DELAY_MS));
  }, []);
  return (
    <SafetyContext.Provider value={{ showSafety }}>
      {children}
      {content &&
        createPortal(<SafetyScreen content={content} until={until} onAck={() => setContent(null)} />, document.body)}
    </SafetyContext.Provider>
  );
}

/** Everything outside the overlay is made inert while it is open: no clicks, no focus, hidden
 *  from assistive tech. The app mounts in #root; the overlay is a sibling on <body>. */
function useInertApp() {
  useEffect(() => {
    const app = document.getElementById("root");
    const before = document.activeElement as HTMLElement | null;
    app?.setAttribute("inert", "");
    return () => {
      app?.removeAttribute("inert");
      before?.focus?.(); // back to where the person was
    };
  }, []);
}

function SafetyScreen({ content, until, onAck }: { content: SafetyContent; until: number; onAck(): void }) {
  const [left, setLeft] = useState(() => Math.max(0, Math.ceil((until - Date.now()) / 1000)));
  const box = useRef<HTMLDivElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const ack = useRef<HTMLButtonElement>(null);
  useInertApp();

  useEffect(() => title.current?.focus(), []);
  useEffect(() => {
    const tick = () => setLeft(Math.max(0, Math.ceil((until - Date.now()) / 1000)));
    tick();
    const id = window.setInterval(tick, 250);
    return () => window.clearInterval(id);
  }, [until]);
  useEffect(() => {
    if (left === 0) ack.current?.focus();
  }, [left]);

  return (
    <div
      className="safety"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="safety-title"
      aria-describedby="safety-reason"
      onKeyDown={(e) => {
        // Escape never dismisses this screen; Tab stays inside it (focus trap).
        if (e.key === "Escape") e.preventDefault();
        if (e.key !== "Tab") return;
        const stops = [title.current, ack.current].filter(
          (el): el is HTMLHeadingElement | HTMLButtonElement => !!el && !(el as HTMLButtonElement).disabled,
        );
        const i = stops.indexOf(document.activeElement as HTMLHeadingElement);
        const next = e.shiftKey ? stops[(i - 1 + stops.length) % stops.length] : stops[(i + 1) % stops.length];
        e.preventDefault();
        next?.focus();
      }}
    >
      <div className="safety-box" ref={box}>
        <h1 id="safety-title" tabIndex={-1} ref={title}>
          Please reach out for support now
        </h1>
        <p id="safety-reason">{content.reason}</p>
        <ul>
          {content.resources.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        <button type="button" ref={ack} className="ack" disabled={left > 0} onClick={onAck}>
          {left > 0 ? `Please read this (${left})` : "I have read this"}
        </button>
        <p className="sr-only" aria-live="polite">
          {left > 0 ? "" : "You can now close this screen."}
        </p>
      </div>
    </div>
  );
}
