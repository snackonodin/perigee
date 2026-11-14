// One line at a time, role=status + aria-live=polite, auto-hides (timer from the pet's
// scheduler). A server bubble may add a small second line, a badge dot and a close button.
import { useEffect } from "react";
import { DIALOG_SHOW_MS } from "../petConfig";
import type { Scheduler } from "../scheduler";

export interface BubbleLine { text: string; sub?: string | null; badge?: "green" | "amber" | "neutral"; dismissible?: boolean; ms?: number }

export function DialogBubble({ line, scheduler, onDone }: { line: BubbleLine | null; scheduler: Scheduler; onDone(): void }) {
  useEffect(() => { if (line) return scheduler.after(line.ms ?? DIALOG_SHOW_MS, onDone); }, [line, scheduler, onDone]);
  return <div className="pet-bubble" data-show={line ? "true" : undefined} data-badge={line?.badge}>
    <p role="status" aria-live="polite">{line?.text ?? ""}</p>
    {line?.sub && <p className="pet-bubble-sub">{line.sub}</p>}
    {line?.dismissible && <button type="button" className="pet-bubble-close" aria-label="Dismiss" onClick={onDone}>×</button>}
  </div>;
}
