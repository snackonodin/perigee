import type {
  BaselineOut,
  GuidanceCardOut,
  Instrument,
  InstrumentSummary,
  MeOut,
  NightOut,
  ResponseOut,
  TodayOut,
} from "../api/types";

// Typed against the generated schema: an API shape change breaks these at compile time.
export const me: MeOut = {
  id: "u-1",
  email: "ada@example.invalid",
  created_at: "2026-11-01T00:00:00Z",
  is_synthetic: true,
  display_name: "Ada",
  timezone: "UTC",
};

export function night(date: string, rr: number | null, valid = true): NightOut {
  return {
    id: `n-${date}`,
    date,
    rr_med: rr,
    rr_var: 0.4,
    presence_hours: 7.5,
    restless_frac: 0.08,
    onset: `${date}T22:40:00Z`,
    wake: `${date}T06:10:00Z`,
    midsleep: `${date}T02:25:00Z`,
    quality: valid ? 0.82 : 0.3,
    valid,
    source_kind: "synthetic",
    inputs: { session_ids: [] },
    run_id: null,
  };
}

export const rrBaseline: BaselineOut = {
  feature: "rr_med",
  maturity: "mature",
  n: 14,
  median: 14,
  mad: 0.8,
  window_days: 28,
  updated_at: "2026-11-10T08:00:00Z",
};

export const unreviewedCard: GuidanceCardOut = {
  card_key: "wind_down",
  title: "Try a wind-down routine",
  body: "Dim the lights 30 minutes before sleep.",
  contact_support_text: "If this keeps happening, talk to your flight surgeon.",
  source_note: "General sleep hygiene guidance",
  reviewed_by: null,
  matched_signals: ["rr_med"],
};

export const today: TodayOut & { context_engine: Record<string, unknown> | null } = {
  date: "2026-11-11",
  latest_night: night("2026-11-10", 17.9),
  flags: [
    {
      id: "f-1",
      date: "2026-11-10",
      domain_pair: "sleep_mood",
      phys_level: 1,
      mental_level: 0,
      state: "phys_only",
      priority: 1.6,
      message_key: "flag.phys_only",
      components: {
        alert_robust_z: 2.5,
        physiology: { rr_med: { value: 17.9, median: 14, mad: 0.8, n: 14, maturity: "mature", z: 3.29 } },
        mental: { phq2: { value: 1, skipped: "warm_up" } },
      },
      run_id: null,
      created_at: "2026-11-11T07:00:00Z",
      guidance: [unreviewedCard, { ...unreviewedCard, card_key: "c2", title: "Reviewed card", reviewed_by: "Dr. Example" }],
    },
  ],
  pending_checkins: [{ slot: "am", instrument_id: "daily_am", instrument_version: "1.0" }],
  checkins_consent: true,
  baselines: [rrBaseline],
  sync_status: { state: "offline" },
  context_engine: {
    safety_status: { crisis_override_triggered: false, escalation_type: "NONE", emergency_message: null },
    scores_and_metrics: { phys_level: 1, mental_level: 0 },
    fatigue_and_health_ratings: {
      mental_fatigue_score: 24,
      physiological_fatigue_score: 31,
      overall_health_resilience_index: 82,
    },
    classification: { quadrant: "Steady", priority_score: 12, persistence_days: 0 },
    dashboard_visualization_data: {
      dual_axis_timeline_point: { respiration_bpm: 14.2, respiration_baseline_band: [13.5, 14.8], mental_load_score: 24 },
      radar_traits: { E: 12, A: 17, C: 18, N: 14, O: 16 },
    },
    user_facing_advisory: {
      headline: "A small shift, in your context",
      personality_tailored_message: "Your signals can vary from night to night. We are comparing them with your own recent pattern.",
      actionable_recommendations: [],
      environmental_note: null,
    },
    flight_surgeon_briefing_snippet: "Personal snapshot available.",
  },
};

export const instruments: InstrumentSummary[] = [
  { id: "daily_am", name: "Morning check-in", version: "1.0", items: 3 },
  { id: "phq9", name: "Patient Health Questionnaire-9 (PHQ-9)", version: "1.0", items: 2 },
];

// Two items keep the form small; item 2 carries the safety trigger like phq9_9.
export const phq9: Instrument = {
  id: "phq9",
  name: "Patient Health Questionnaire-9 (PHQ-9)",
  version: "1.0",
  timeframe: "Over the last 2 weeks…",
  items: [
    { key: "phq9_1", text: "Little interest or pleasure", options: [{ value: 0, label: "Not at all" }, { value: 1, label: "Several days" }] },
    {
      key: "phq9_9",
      text: "Thoughts that you would be better off dead",
      options: [{ value: 0, label: "Not at all" }, { value: 1, label: "Several days" }],
      safety_trigger: { min_value: 1 },
    },
  ],
};

export const SERVER_SAFETY = { reason: "Server reason text.", resources: ["Server resource A", "Server resource B"] };

export function responseOut(over: Partial<ResponseOut> = {}): ResponseOut {
  return { ok: true, crisis: false, safety: { show: false, resources: [] }, id: "r-1", stored: true, total: 1, scores: {}, errors: [], ...over };
}
