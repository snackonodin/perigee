// Pet behavior timing (pet-handoff BRIEF §2). These are animation and interaction numbers
// for a decorative companion, not health thresholds.
export const BLINK_MIN_MS = 3000;
export const BLINK_MAX_MS = 6000;
export const DOUBLE_BLINK_CHANCE = 0.15;
export const BREATH_AWAKE_S = 4;
export const BREATH_ASLEEP_S = 6;
export const EAR_TWITCH_MIN_MS = 5000;
export const EAR_TWITCH_MAX_MS = 12000;
export const TAIL_FLICK_MIN_MS = { fox: 8000, bunny: 10000 } as const;
export const TAIL_FLICK_MAX_MS = { fox: 15000, bunny: 20000 } as const;

export const TAP_MAX_MS = 300;
export const TAP_MAX_MOVE_PX = 8;
export const LONG_PRESS_MS = 600;
export const PET_MAX_MS = 5000;
export const POKE_COUNT = 3;
export const POKE_WINDOW_MS = 1500;

export const HAPPY_MS = 1200;
export const PLAYFUL_MS = 900;
export const YAWN_MS = 1400;
export const YAWN_MIN_GAP_MS = 60000;
export const STRETCH_MS = 1800;
export const STRETCH_IDLE_MS = 45000;
export const CURL_MS = 1200;
export const RESLEEP_MS = 30000;
export const Z_EVERY_MS = 2500;

export const WALK_MIN_WIDTH_PX = 768;
export const WALK_SPEED_PX_S = 95;
/** to the check-in or quiz form: a slow, unhurried hop (after any speech bubble has finished) */
export const FORM_WALK_SPEED_PX_S = 55;
export const WALK_IDLE_MS = 20000;
export const WALK_COOLDOWN_MS = 45000;
export const SIT_SETTLE_MS = 1000;

// Cursor follow (mouse/pen only; touch keeps the corner). Animation numbers, not health values.
/** the pet chases where the pointer was this long ago */
export const FOLLOW_LAG_MS = 350;
/** within this distance of the (lagged) pointer the pet stops: never covers what you click */
export const FOLLOW_DEADZONE_PX = 380;
/** never closer to the cursor than about one card width; if the cursor comes closer it hops away */
export const FOLLOW_MIN_DIST_PX = 320;
/** it aims to stand this far short of the pointer (>= pet radius + 24 px) */
export const FOLLOW_GAP_PX = 340;
export const FOLLOW_MAX_SPEED_PX_S = 260;
/** desired speed = distance x this (per second), so it lags more the farther it is */
export const FOLLOW_EASE = 2.2;
/** how fast velocity catches up with the desired velocity (per second) */
export const FOLLOW_ACCEL = 4;
export const FOLLOW_STOP_SPEED_PX_S = 6;
export const FOLLOW_WOBBLE_PX = 14;
export const FOLLOW_WOBBLE_HZ = 0.6;
/** chance per second of starting a detour while far from the pointer */
export const FOLLOW_DETOUR_CHANCE_S = 0.35;
export const FOLLOW_DETOUR_MIN_DIST_PX = 220;
export const FOLLOW_DETOUR_MIN_PX = 50;
export const FOLLOW_DETOUR_MAX_PX = 140;
export const FOLLOW_DETOUR_MAX_MS = 1600;
export const FOLLOW_EDGE_PX = 8;

// Moods while the pointer is active: it does not always chase. Picked again when the current
// mood runs out; after a chase it will not chase again for FOLLOW_COOLDOWN_MS.
export const MOOD_WEIGHTS = { follow: 0.5, wander: 0.35, ignore: 0.15 } as const;
/** a chase lasts this long before it loses interest */
export const FOLLOW_INTEREST_MIN_MS = 4000;
export const FOLLOW_INTEREST_MAX_MS = 8000;
export const FOLLOW_COOLDOWN_MS = 6000;
/** wander: hop to a free spot, sit and look around */
export const WANDER_MIN_MS = 5000;
export const WANDER_MAX_MS = 9000;
export const WANDER_SPEED_PX_S = 95;
/** a wander spot keeps at least this far from the pointer */
export const WANDER_POINTER_CLEAR_PX = 380;
export const WANDER_TRIES = 16;
export const IGNORE_MIN_MS = 4000;
export const IGNORE_MAX_MS = 8000;
/** moods only run while the pointer moved within this window */
export const MOOD_ACTIVE_MS = 10000;
/** One travel hop, calm chibi style (about 7 px high, a ~45 px stride at 95 px/s): crouch, spring up, ~0.3 s airborne arc, soft landing with a
 *  tiny settle bounce, then a short pause. The pet only moves while airborne. */
export const HOP_MS = 480;
/** a server speech bubble stays this long unless dismissed */
export const SERVER_BUBBLE_MS = 14000;
export const HOP_HEIGHT_PX = 7;
/** fraction of the hop cycle: crouch ends / take-off, landing, settle ends (rest = pause) */
export const HOP_TAKEOFF = 0.14;
export const HOP_LAND = 0.68;
export const HOP_SETTLE = 0.84;
/** squash: + crouch/landing (~10 % shorter), - stretch (~8 % taller); rig: scaleY = 1 - .12 x squash */
export const HOP_CROUCH = 0.85;
export const HOP_STRETCH = -0.67;

/** Bedtime window, station time (the host passes timeOfDay "night" inside it). */
export const BEDTIME_START = "22:00";
export const BEDTIME_END = "06:30";
export const ACCESSORY_NIGHTS = [3, 7, 14, 30] as const;

export const FROST_REFORM_S = 30; // allowed 20-40
export const FROST_BRUSH_R0 = 28;
export const FROST_TINT_ALPHA = 0.55; // maximum: higher breaks AA contrast for --muted

export const DIALOG_COOLDOWN_MS: Record<string, number> = { default: 120000, pet_tap: 20000, idle_long: 600000, app_open: 300000 };
export const DIALOG_SHOW_MS = 6000;
export const DIALOG_RECENT = 8;
export const IDLE_LONG_MS = 600000;
export const BEDTIME_NEAR_MS = 30 * 60000;
export const SAFETY_QUIET_MS = 60000;
export const BREATHE_IN_S = 4;
export const BREATHE_OUT_S = 6;
export const BREATHE_MAX_CYCLES = 10;
export const SNOOZE_MS = 3600000;

export const DEFAULT_NAMES = { cat: "Miso", fox: "Ember", bunny: "Clover" } as const;
