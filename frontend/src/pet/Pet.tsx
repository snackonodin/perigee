// The live companion pet. Safety first: while safetyActive is true this returns null and
// the inner component (which owns every timer, listener and rAF) is unmounted.
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { FrostTrail } from "./frost/FrostTrail";
import { createTrail } from "./frost/trailBuffer";
import { initial, moodOf, reduce, type BehaviorEvent, type BehaviorState } from "./behavior";
import { unlocked } from "./accessories";
import { PetArt } from "./PetArt";
import {
  BLINK_MAX_MS, BLINK_MIN_MS, DEFAULT_NAMES, DOUBLE_BLINK_CHANCE, EAR_TWITCH_MAX_MS, EAR_TWITCH_MIN_MS,
  SIT_SETTLE_MS, TAIL_FLICK_MAX_MS, TAIL_FLICK_MIN_MS, WALK_COOLDOWN_MS, WALK_IDLE_MS, WALK_SPEED_PX_S, YAWN_MIN_GAP_MS,
} from "./petConfig";
import { createScheduler, type Scheduler } from "./scheduler";
import type { PetProps } from "./types";
import { useInteractions } from "./useInteractions";
import { useRig } from "./useRig";
import { canWalk, perchTargets, stepToward, type Box, type Point } from "./walk";
import "./pet.css";

export function Pet(props: PetProps) {
  if (props.safetyActive) return null;
  return <PetLive {...props} />;
}

function prefersReduced(): boolean {
  try { return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false; } catch { return false; }
}

/** Optional hooks used by later phases (frost trail, dialog). */
export interface PetLiveHooks { onStep?(p: Point): void; onTap?(): void; onState?(s: BehaviorState): void }

export function PetLive({ species, timeOfDay, reducedMotion, nightsLogged, petName, placement = "corner", size = 96, hooks }: PetProps & { hooks?: PetLiveHooks }) {
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
  const onTap = useCallback(() => hooksRef.current?.onTap?.(), []);
  useEffect(() => { hooksRef.current?.onState?.(b); }, [b]);

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

  // walking on wide screens ("stage" placement): along the top edge of [data-pet-perch]
  const [perched, setPerched] = useState(false);
  const trail = useMemo(() => createTrail(300), []);
  const frostKick = useRef<(() => void) | null>(null);
  const lastWalk = useRef(0);
  useEffect(() => {
    if (placement !== "stage" || reduced) return;
    let raf = 0;
    const home = () => ({ x: window.innerWidth - 16 - size / 2, y: window.innerHeight - 16 });
    const stopWalk = () => { if (raf) cancelAnimationFrame(raf); raf = 0; };
    const goHome = () => { stopWalk(); if (root.current) root.current.style.transform = ""; setPerched(false); dispatch({ type: "leavePerch" }); };
    const tryWalk = () => {
      if (!canWalk(window.innerWidth, reduced) || raf) return;
      if (Date.now() - lastInput.current < WALK_IDLE_MS || Date.now() - lastWalk.current < WALK_COOLDOWN_MS) return;
      const box = (el: Element): Box => { const r = el.getBoundingClientRect(); return { left: r.left, top: r.top, width: r.width, height: r.height }; };
      const avoid = [...document.querySelectorAll("[data-pet-avoid], form, input, textarea, select, [role=dialog]")].map(box);
      if (document.activeElement && document.activeElement !== document.body) avoid.push(box(document.activeElement));
      const spots = perchTargets([...document.querySelectorAll("[data-pet-perch]")].map(box), { width: window.innerWidth, height: window.innerHeight }, size, avoid);
      if (!spots.length) return;
      lastWalk.current = Date.now();
      const target = spots[Math.floor(Math.random() * spots.length)];
      let pos = home(), last = performance.now();
      dispatch({ type: "perchFound" });
      setPerched(true);
      const frame = (t: number) => {
        const r = stepToward(pos, target, WALK_SPEED_PX_S, Math.min(.05, (t - last) / 1000));
        last = t; pos = r.pos;
        const h = home();
        if (root.current) root.current.style.transform = `translate(${(pos.x - h.x).toFixed(1)}px, ${(pos.y - h.y).toFixed(1)}px)`;
        if (trail.add(pos.x, pos.y - 4, performance.now())) frostKick.current?.();
        hooksRef.current?.onStep?.(pos);
        if (r.arrived) { raf = 0; scheduler.after(SIT_SETTLE_MS, () => dispatch({ type: "arrived" })); return; }
        raf = requestAnimationFrame(frame);
      };
      raf = requestAnimationFrame(frame);
    };
    const stopCheck = scheduler.every(5000, 5000, tryWalk);
    window.addEventListener("scroll", goHome, { passive: true });
    window.addEventListener("resize", goHome);
    return () => { stopCheck(); stopWalk(); window.removeEventListener("scroll", goHome); window.removeEventListener("resize", goHome); };
  }, [placement, reduced, size, scheduler, dispatch, trail]);
  // any interaction while perched sends the pet home
  useEffect(() => {
    if (perched && (b.state === "happy" || b.state === "petting" || b.state === "playful")) { if (root.current) root.current.style.transform = ""; setPerched(false); }
  }, [b.state, perched]);

  const handlers = useInteractions(scheduler, dispatch, onTap);
  const accessories = useMemo(() => unlocked(nightsLogged), [nightsLogged]);
  const mood = moodOf(b.state, timeOfDay);
  const style = { "--pet-size": `${size}px` } as CSSProperties;
  return <div ref={root} className="pet" data-state={b.state} data-species={species} data-placement={placement}
    data-reduced={reduced ? "true" : undefined} data-perched={perched ? "true" : undefined} style={style}>
    <button type="button" className="pet-hit" aria-label={`Pet ${name}`} {...handlers}>
      <PetArt species={species} mood={mood} size={size} accessories={accessories} animated />
    </button>
    {b.state === "sleeping" && <span className="pet-z" aria-hidden="true">z</span>}
    {placement === "stage" && !reduced && <FrostTrail trail={trail} kickRef={frostKick} />}
  </div>;
}
