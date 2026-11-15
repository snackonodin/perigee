// The live companion pet. Safety first: while safetyActive is true this returns null and
// the inner component (which owns every timer, listener and rAF) is unmounted.
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { FrostTrail } from "./frost/FrostTrail";
import { createTrail } from "./frost/trailBuffer";
import { initial, moodOf, reduce, type BehaviorEvent, type BehaviorState } from "./behavior";
import { unlocked } from "./accessories";
import { PetArt } from "./PetArt";
import {
  BLINK_MAX_MS, BLINK_MIN_MS, BREATHE_IN_S, BREATHE_MAX_CYCLES, BREATHE_OUT_S, IDLE_LONG_MS, SAFETY_QUIET_MS, DEFAULT_NAMES, DOUBLE_BLINK_CHANCE, EAR_TWITCH_MAX_MS, EAR_TWITCH_MIN_MS,
  FOLLOW_MIN_DIST_PX, FORM_WALK_SPEED_PX_S, HOP_MS, MOOD_ACTIVE_MS, SERVER_BUBBLE_MS, SIT_SETTLE_MS, WANDER_SPEED_PX_S, TAIL_FLICK_MAX_MS, TAIL_FLICK_MIN_MS, WALK_COOLDOWN_MS, WALK_IDLE_MS, WALK_SPEED_PX_S, YAWN_MIN_GAP_MS,
} from "./petConfig";
import { createScheduler, type Scheduler } from "./scheduler";
import type { PetProps } from "./types";
import { useInteractions } from "./useInteractions";
import cacheJson from "./dialog/cache.json";
import { DialogBubble, type BubbleLine } from "./dialog/DialogBubble";
import { fill, pickLine } from "./dialog/picker";
import { KEYS, readKey, writeKey } from "./dialog/storage";
import { toneFor } from "./dialog/toneFor";
import { subscribe } from "./emit";
import { PetControls } from "./PetControls";
import { petStore, usePetPrefs } from "./store";
import type { DialogCache, PetEvent, PetEventName } from "./types";
import { useRig } from "./useRig";
import { canWalk, perchTargets, stepToward, type Box, type Point } from "./walk";
import { advanceMood, createMoods, hopPose, hopSpeed, nearestSpot, otherSpot, spotTowardPointer } from "./follow";
import "./pet.css";

const CACHE = cacheJson as unknown as DialogCache;
/** perch spots skip headings, text and controls (extra avoid selectors) */
const TEXT = ", a, button, [role=button], label, h1, h2, h3, h4, p, li, dt, dd, th, td, figcaption, .meta-label, .section-meta";

export function Pet(props: PetProps) {
  const { hidden } = usePetPrefs();
  // after the safety screen closes the pet starts fresh and stays silent for 60 s
  const wasSafety = useRef(props.safetyActive);
  const quietUntil = useRef(0);
  if (wasSafety.current && !props.safetyActive) quietUntil.current = Date.now() + SAFETY_QUIET_MS;
  wasSafety.current = props.safetyActive;
  if (props.safetyActive) return null;
  if (hidden) return <div className="pet-shown-toggle"><button type="button" className="pet-control pet-show" style={{ minWidth: 44, minHeight: 44 }}
    onClick={() => { petStore.setHidden(false); props.onHiddenChange?.(false); }}>Show pet</button></div>;
  return <PetLive {...props} quietUntil={quietUntil.current} />;
}

function prefersReduced(): boolean {
  try { return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false; } catch { return false; }
}

/** Optional hooks used by later phases (frost trail, dialog). */
export interface PetLiveHooks { onStep?(p: Point): void; onTap?(): void; onState?(s: BehaviorState): void }

export function PetLive({ species, personaId, timeOfDay, reducedMotion, nightsLogged, petName, placement = "corner", size = 96, onHiddenChange, hooks, quietUntil = 0, bubble, tip, onTipShown }: PetProps & { hooks?: PetLiveHooks; quietUntil?: number }) {
  const reduced = reducedMotion || prefersReduced();
  const name = petName ?? DEFAULT_NAMES[species];
  const root = useRef<HTMLDivElement>(null);
  const scheduler = useMemo<Scheduler>(() => createScheduler(), []);
  useEffect(() => () => scheduler.clearAll(), [scheduler]);

  const bedtime = timeOfDay === "night";
  const [b, setB] = useState<BehaviorState>(() => initial(bedtime));
  const lastInput = useRef(Date.now());
  const lastYawn = useRef(0);
  const dispatch = useCallback((e: BehaviorEvent) => {
    if (e.type !== "tick" && e.type !== "idleFor") lastInput.current = Date.now();
    setB((s) => reduce(s, e, Date.now()));
  }, []);
  const hooksRef = useRef(hooks); hooksRef.current = hooks;
  // dialog: one line at a time, picked from the offline cache in the persona's tone
  const [line, setLine] = useState<BubbleLine | null>(null);
  const lineRef = useRef(line); lineRef.current = line;
  // a server bubble wins: while it shows, offline cache lines wait
  const serverShowing = useRef(false);
  const [serverShown, setServerShown] = useState(false);
  // playful:false (a support or context bubble) keeps the pet calm while that bubble shows
  const playful = serverShown && bubble?.playful === false ? false : undefined;
  const lastShown = useRef<Partial<Record<PetEventName, number>>>({});
  const say = useCallback((event: PetEvent) => {
    if (Date.now() < quietUntil) return;
    const l = pickLine(CACHE, event.name, toneFor(personaId), timeOfDay, Date.now(), { lastShown: lastShown.current });
    if (l && !serverShowing.current) setLine({ text: fill(l.text, name) });
    if (event.name === "quiz_complete") dispatch({ type: "cheer" });
  }, [quietUntil, personaId, timeOfDay, name, dispatch]);
  const sayRef = useRef(say); sayRef.current = say;
  useEffect(() => subscribe((e) => sayRef.current(e)), []);
  const clearLine = useCallback(() => { serverShowing.current = false; setServerShown(false); setLine(null); }, []);
  // a host tip (once): waits until the pet is not speaking, then shows dismissibly
  const tipShown = useRef<string | null>(null);
  useEffect(() => {
    if (!tip || line || tipShown.current === tip.id || Date.now() < quietUntil) return;
    tipShown.current = tip.id;
    setLine({ text: tip.text, badge: "neutral", dismissible: true, ms: SERVER_BUBBLE_MS });
    onTipShown?.(tip.id);
  }, [tip, line, quietUntil, onTipShown]);
  // the server bubble: shown once per id, dismissible, with its small "try" line
  useEffect(() => {
    if (!bubble?.text || Date.now() < quietUntil) return;
    serverShowing.current = true;
    setServerShown(true);
    setLine({ text: bubble.text, sub: bubble.tryLine, badge: bubble.badge, dismissible: true, ms: SERVER_BUBBLE_MS });
  }, [bubble?.id, bubble?.text]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (readKey(KEYS.firstRun) === "true") return;
    writeKey(KEYS.firstRun, "true");
    sayRef.current({ name: "first_run" });
  }, []);
  const onTap = useCallback(() => { sayRef.current({ name: "pet_tap" }); hooksRef.current?.onTap?.(); }, []);
  const prevState = useRef(b.state);
  useEffect(() => {
    hooksRef.current?.onState?.(b);
    const prev = prevState.current; prevState.current = b.state;
    if (b.state === "sleeping" && prev === "yawning") sayRef.current({ name: "sleep_start" });
    if (b.state === "stretching" && !b.bedtime && (prev === "sleeping" || prev === "waking" || prev === "yawning")) sayRef.current({ name: "wake" });
  }, [b]);
  useEffect(() => {
    let fired = false;
    return scheduler.every(30000, 30000, () => {
      const idle = Date.now() - lastInput.current;
      if (idle < IDLE_LONG_MS) { fired = false; return; }
      if (!fired) { fired = true; sayRef.current({ name: "idle_long" }); }
    });
  }, [scheduler]);

  // "Breathe with me": 4 s in / 6 s out, at most 10 cycles. Stops when the pet unmounts (safety).
  const [buddy, setBuddy] = useState(false);
  useEffect(() => petStore.onBuddy(() => {
    setBuddy(true);
    setMenu(false); // the options menu would cover the cue
    scheduler.after((BREATHE_IN_S + BREATHE_OUT_S) * BREATHE_MAX_CYCLES * 1000, () => setBuddy(false));
  }), [scheduler]);
  // "Breathe in" / "Breathe out" cue, on the same 4 s / 6 s clock as the CSS breath. Boundaries are
  // computed from the start time so the text never drifts from the animation over 10 cycles.
  const [phase, setPhase] = useState<"in" | "out">("in");
  useEffect(() => {
    if (!buddy) return;
    const start = Date.now(), cycle = (BREATHE_IN_S + BREATHE_OUT_S) * 1000;
    let cancel = () => {};
    const at = (k: number, p: "in" | "out") => {
      const due = start + k * cycle + (p === "out" ? BREATHE_IN_S * 1000 : 0);
      cancel = scheduler.after(Math.max(0, due - Date.now()), () => {
        setPhase(p);
        if (p === "out") at(k + 1, "in"); else at(k, "out");
      });
    };
    setPhase("in");
    at(0, "out");
    return () => cancel();
  }, [buddy, scheduler]);
  const [menu, setMenu] = useState(false);

  // timed states end with a tick at `until`
  useEffect(() => {
    if (b.until == null && b.resleepAt == null) return;
    const at = Math.min(b.until ?? Infinity, b.resleepAt ?? Infinity);
    return scheduler.after(Math.max(0, at - Date.now()), () => dispatch({ type: "tick" }));
  }, [b.until, b.resleepAt, scheduler, dispatch]);

  useEffect(() => { dispatch({ type: bedtime ? "enterBedtime" : "leaveBedtime" }); }, [bedtime, dispatch]);
  useRig(root, b.rig);

  // idle loops: blink, ear twitch, tail flicks, idle stretch / yawn. None under reduced motion.
  useEffect(() => {
    if (reduced) return;
    const el = () => root.current;
    const flash = (attr: string, value: string, ms: number) => { el()?.setAttribute(attr, value); scheduler.after(ms, () => el()?.removeAttribute(attr)); };
    const stops = [
      scheduler.every(BLINK_MIN_MS, BLINK_MAX_MS, () => {
        flash("data-blink", "1", 140);
        if (Math.random() < DOUBLE_BLINK_CHANCE) scheduler.after(260, () => flash("data-blink", "1", 140));
      }),
      scheduler.every(EAR_TWITCH_MIN_MS, EAR_TWITCH_MAX_MS, () => flash("data-twitch", Math.random() < .5 ? "l" : "r", 220)),
      scheduler.every(5000, 5000, () => {
        const idle = Date.now() - lastInput.current;
        dispatch({ type: "idleFor", ms: idle });
        const chance = bedtime ? .5 : .25;
        if (idle > 20000 && Date.now() - lastYawn.current > YAWN_MIN_GAP_MS && Math.random() < chance) { lastYawn.current = Date.now(); dispatch({ type: "yawn" }); }
      }),
    ];
    if (species !== "cat") stops.push(scheduler.every(TAIL_FLICK_MIN_MS[species], TAIL_FLICK_MAX_MS[species], () => flash("data-flick", "1", species === "fox" ? 600 : 900)));
    return () => stops.forEach((s) => s());
  }, [reduced, scheduler, species, bedtime, dispatch]);

  // eyes and head follow the pointer, smoothed by a CSS transition on --look-x/y
  useEffect(() => {
    if (reduced) return;
    const move = (e: PointerEvent) => {
      const el = root.current; if (!el) return;
      const r = el.getBoundingClientRect();
      const clamp = (n: number) => Math.max(-1, Math.min(1, n));
      el.style.setProperty("--look-x", clamp((e.clientX - (r.left + r.width / 2)) / 400).toFixed(2));
      el.style.setProperty("--look-y", clamp((e.clientY - (r.top + r.height / 2)) / 300).toFixed(2));
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => window.removeEventListener("pointermove", move);
  }, [reduced]);

  // Moving on wide screens ("stage" placement). One position (pet centre, viewport px;
  // null = home corner) shared by two movers: cursor follow (mouse/pen only) and the idle
  // walk to the top edge of a [data-pet-perch] card. Touch devices keep the corner.
  const [perched, setPerched] = useState(false);
  const perchedRef = useRef(false); perchedRef.current = perched;
  const stateRef = useRef(b.state); stateRef.current = b.state;
  const trail = useMemo(() => createTrail(300), []);
  const frostKick = useRef<(() => void) | null>(null);
  const lastWalk = useRef(0);
  const lastPointer = useRef(0);
  const pos = useRef<Point | null>(null);
  const homeCenter = useCallback((): Point => ({ x: window.innerWidth - 16 - size / 2, y: window.innerHeight - 16 - size / 2 }), [size]);
  const place = useCallback((p: Point | null) => {
    pos.current = p;
    const el = root.current; if (!el) return;
    const h = homeCenter();
    el.style.transform = p ? `translate(${(p.x - h.x).toFixed(1)}px, ${(p.y - h.y).toFixed(1)}px)` : "";
    // bubble and menu open toward the roomier side
    if (p && p.x < window.innerWidth / 2) el.setAttribute("data-side", "left"); else el.removeAttribute("data-side");
    if (p && p.y < 220) el.setAttribute("data-vside", "below"); else el.removeAttribute("data-vside");
  }, [homeCenter]);
  useEffect(() => {
    // playful:false (server bubble, e.g. a support or safety moment): calm idle only, no roaming
    if (placement !== "stage" || reduced || playful === false) return;
    // The pet moves only between FIXED spots (the top edge of [data-pet-perch] cards on this tab)
    // and its home corner, in small hops. During a check-in or quiz it sits on the form's top edge.
    let raf = 0, last = 0, mode: "none" | "hop" = "none", hopPhase = 0, sitting = false;
    const viewport = () => ({ width: window.innerWidth, height: window.innerHeight });
    const fine = (() => { try { return window.matchMedia?.("(pointer: fine)").matches ?? false; } catch { return false; } })();
    const moods = createMoods(Date.now());
    let pointer: Point | null = null;
    const svg = () => root.current?.querySelector<SVGElement>(".pet-svg") ?? null;
    // one hop clock drives the pose and the travel speed, so it only covers ground while airborne
    const hopFrame = (dt: number): number => {
      hopPhase = (hopPhase + dt * 1000 / HOP_MS) % 1;
      const pose = hopPose(hopPhase), el = svg();
      if (el) {
        el.style.setProperty("--hop", pose.hop.toFixed(2)); el.style.setProperty("--squash", pose.squash.toFixed(3));
        el.style.setProperty("--ear-l", pose.ears.toFixed(3)); el.style.setProperty("--ear-r", pose.ears.toFixed(3)); el.style.setProperty("--tail", pose.tail.toFixed(3));
      }
      return hopSpeed(hopPhase);
    };
    const restPose = () => { hopPhase = 0; const el = svg(); if (el) for (const v of ["--hop", "--squash", "--ear-l", "--ear-r", "--tail"]) el.style.removeProperty(v); };
    const stop = () => {
      if (raf) cancelAnimationFrame(raf); raf = 0;
      if (mode === "hop") dispatch({ type: "followStop" });
      mode = "none"; restPose();
    };
    const step = (p: Point) => { place(p); if (trail.add(p.x, p.y + size / 2 - 4, performance.now())) frostKick.current?.(); hooksRef.current?.onStep?.(p); };
    const leavePerch = () => { if (!perchedRef.current) return; setPerched(false); dispatch({ type: "leavePerch" }); };
    const goHome = () => { if (mode !== "none") stop(); sitting = false; if (perchedRef.current || pos.current) { place(null); leavePerch(); } };
    const box = (el: Element): Box => { const r = el.getBoundingClientRect(); return { left: r.left, top: r.top, width: r.width, height: r.height }; };
    const avoidBoxes = (extra = ""): Box[] => {
      const out = [...document.querySelectorAll(`[data-pet-avoid], form, input, textarea, select, [role=dialog]${extra}`)].map(box);
      if (document.activeElement && document.activeElement !== document.body) out.push(box(document.activeElement));
      return out;
    };
    /** this tab's designated spots (pet centres), never on text or controls */
    const spots = (): Point[] => perchTargets([...document.querySelectorAll("[data-pet-perch]")].map(box), viewport(), size, avoidBoxes(TEXT))
      .map((p) => ({ x: p.x, y: p.y - size / 2 }));
    const busy = () => ["sleeping", "yawning", "waking", "petting", "playful"].includes(stateRef.current);
    /** Hop to a point (or home when null), then sit. */
    const hopTo = (target: Point | null, speed = WANDER_SPEED_PX_S, onArrive?: () => void) => {
      stop(); leavePerch();
      const goal = target ?? homeCenter();
      let p = pos.current ?? homeCenter();
      if (Math.hypot(goal.x - p.x, goal.y - p.y) < 4) return;
      dispatch({ type: "followStart" });
      mode = "hop"; last = performance.now();
      const frame = (t: number) => {
        if (busy()) { stop(); return; }
        const dt = Math.min(.05, (t - last) / 1000); last = t;
        const r = stepToward(p, goal, speed * hopFrame(dt), dt);
        p = r.pos; step(p);
        if (r.arrived) {
          raf = 0; mode = "none"; restPose();
          if (!target) { place(null); dispatch({ type: "followStop" }); }
          else { setPerched(true); dispatch({ type: "arrived" }); }
          onArrive?.();
          return;
        }
        raf = requestAnimationFrame(frame);
      };
      raf = requestAnimationFrame(frame);
    };
    const lookAround = () => {
      const look = (x: number) => root.current?.style.setProperty("--look-x", x.toFixed(2));
      scheduler.after(700, () => look(-.8)); scheduler.after(1700, () => look(.8)); scheduler.after(2600, () => look(0));
    };
    // check-in or quiz open: walk to the top edge of the form card and sit quietly until it closes
    const formSpot = (): Point | null => {
      const form = document.querySelector("[data-pet-sit]");
      if (!form) return null;
      const r = form.getBoundingClientRect();
      const p = { x: Math.min(r.right - size / 2 - 8, r.left + r.width * 0.85), y: r.top - size / 2 + 6 };
      return p.y - size / 2 >= 0 && p.x + size / 2 <= window.innerWidth ? p : null;
    };
    const sitCheck = (): boolean => {
      const form = document.querySelector("[data-pet-sit]");
      if (!form) { sitting = false; return false; }
      // first finish what it is saying, sitting where it is; then hop slowly to the form
      if (!sitting && mode === "none" && !lineRef.current) { sitting = true; hopTo(formSpot(), FORM_WALK_SPEED_PX_S); }
      return true;
    };
    // keep away: never let the cursor within FOLLOW_MIN_DIST_PX while out of the corner; escape
    // to the nearest designated spot that is far enough, else home
    const keepAway = () => {
      if (!pointer || !pos.current || mode !== "none" || busy() || sitting || document.querySelector("[data-pet-sit]")) return;
      if (Math.hypot(pos.current.x - pointer.x, pos.current.y - pointer.y) >= FOLLOW_MIN_DIST_PX) return;
      hopTo(nearestSpot(spots(), pos.current, pointer, pos.current), WANDER_SPEED_PX_S * 1.5, lookAround);
    };
    const moodTick = () => {
      if (sitCheck()) return;
      if (!fine || !canWalk(window.innerWidth, reduced) || busy() || mode !== "none") return;
      if (Date.now() - lastPointer.current > MOOD_ACTIVE_MS) return;
      if (!advanceMood(moods, Date.now())) return;
      if (moods.mood === "follow" && pointer) { const s = spotTowardPointer(spots(), pointer, pos.current); if (s) hopTo(s); }
      else if (moods.mood === "wander") { const s = otherSpot(spots(), pos.current, pointer); if (s) hopTo(s, WANDER_SPEED_PX_S, lookAround); }
      // ignore: stay where it is
    };
    const move = (e: PointerEvent) => {
      if (!fine || (e.pointerType !== "mouse" && e.pointerType !== "pen")) return;
      if (!canWalk(window.innerWidth, reduced) || busy()) return;
      lastPointer.current = Date.now();
      pointer = { x: e.clientX, y: e.clientY };
      keepAway();
    };
    // idle: hop to a designated spot after 20 s without pet input or pointer movement
    const tryWalk = () => {
      if (sitCheck() || !canWalk(window.innerWidth, reduced) || mode !== "none" || perchedRef.current || stateRef.current !== "idle") return;
      const now = Date.now();
      if (now - lastInput.current < WALK_IDLE_MS || now - lastPointer.current < WALK_IDLE_MS || now - lastWalk.current < WALK_COOLDOWN_MS) return;
      const s = otherSpot(spots(), pos.current, null);
      if (!s) return;
      lastWalk.current = now;
      hopTo(s, WALK_SPEED_PX_S, () => scheduler.after(SIT_SETTLE_MS, lookAround));
    };
    const onResize = () => { goHome(); };
    const stopCheck = scheduler.every(5000, 5000, tryWalk);
    const stopMoods = scheduler.every(1000, 1000, moodTick);
    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("scroll", goHome, { passive: true });
    window.addEventListener("resize", onResize);
    return () => {
      stopCheck(); stopMoods(); if (raf) cancelAnimationFrame(raf); restPose();
      window.removeEventListener("pointermove", move); window.removeEventListener("scroll", goHome); window.removeEventListener("resize", onResize);
    };
  }, [placement, reduced, playful, size, scheduler, dispatch, trail, place, homeCenter]);
  // any interaction while perched sends the pet home
  useEffect(() => {
    if (perched && (b.state === "happy" || b.state === "petting" || b.state === "playful")) { place(null); setPerched(false); }
  }, [b.state, perched, place]);

  const handlers = useInteractions(scheduler, dispatch, onTap);
  const accessories = useMemo(() => unlocked(nightsLogged), [nightsLogged]);
  const mood = moodOf(b.state, timeOfDay);
  const style = { "--pet-size": `${size}px`, "--buddy-s": `${BREATHE_IN_S + BREATHE_OUT_S}s` } as CSSProperties;
  return <div ref={root} className="pet" data-state={b.state} data-species={species} data-placement={placement}
    data-reduced={reduced ? "true" : undefined} data-anim={bubble?.animation && bubble.animation !== "calm" ? bubble.animation : undefined} data-calm={playful === false ? "true" : undefined} data-perched={perched ? "true" : undefined} data-buddy={buddy ? "true" : undefined} style={style}>
    <DialogBubble line={line} scheduler={scheduler} onDone={clearLine} />
    {buddy && <span className="pet-buddy-halo" data-phase={phase} aria-hidden="true" />}
    <button type="button" className="pet-hit" aria-label={`Pet ${name}`} {...handlers}>
      <PetArt species={species} mood={mood} size={size} accessories={accessories} animated />
    </button>
    {b.state === "sleeping" && <span className="pet-z" aria-hidden="true">z</span>}
    {buddy && <div className="pet-buddy-label">
      <p className="pet-buddy-cue" data-phase={phase} aria-live="polite">{phase === "in" ? "Breathe in" : "Breathe out"}</p>
      <p className="pet-buddy-note">{b.state === "sleeping" ? "" : "Breathe with me · relaxation exercise, not a medical tool"}<button type="button" className="pet-control" style={{ minWidth: 44, minHeight: 44 }} onClick={() => setBuddy(false)}>Stop</button></p>
    </div>}
    {!perched && <button type="button" className="pet-menu-toggle" aria-label="Companion options" aria-expanded={menu} onClick={() => setMenu((m) => !m)}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="18" cy="12" r="2" /></svg></button>}
    {menu && <div className="pet-menu"><PetControls onHiddenChange={(h) => { setMenu(false); onHiddenChange?.(h); }} /></div>}
    {placement === "stage" && !reduced && <FrostTrail trail={trail} kickRef={frostKick} />}
  </div>;
}
