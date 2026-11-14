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
export const WALK_SPEED_PX_S = 60;
export const WALK_IDLE_MS = 20000;
export const WALK_COOLDOWN_MS = 45000;
export const SIT_SETTLE_MS = 1000;

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
