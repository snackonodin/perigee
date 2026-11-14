// One line at a time, role=status + aria-live=polite, never focusable, auto-hides after 6 s
// (timer from the pet's scheduler). Glass style, above the pet.
import { useEffect } from "react";
import { DIALOG_SHOW_MS } from "../petConfig";
import type { Scheduler } from "../scheduler";

export function DialogBubble({ text, scheduler, onDone }: { text: string | null; scheduler: Scheduler; onDone(): void }) {
  useEffect(() => { if (text) return scheduler.after(DIALOG_SHOW_MS, onDone); }, [text, scheduler, onDone]);
  return <p className="pet-bubble" role="status" aria-live="polite" data-show={text ? "true" : undefined}>{text ?? ""}</p>;
}
