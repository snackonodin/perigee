// Friendly display names for questionnaires (B7). The UI never leads with diagnostic wording;
// the official name appears only as a small muted line on the questionnaire's own sheet.
const FRIENDLY: Record<string, string> = {
  gad2: "Two quick worry questions",
  phq2: "Mood, two questions",
  phq9: "Mood, nine questions",
  who5: "Wellbeing, five questions",
  daily_am: "Morning check-in",
  daily_pm: "Evening check-in",
  psyche60: "Persona questions",
};

export function friendlyName(id: string, fallback?: string): string {
  return FRIENDLY[id] ?? fallback ?? id;
}

/** The official instrument name, or undefined when it is the same as the friendly one. */
export function officialName(id: string, name?: string): string | undefined {
  return FRIENDLY[id] && name ? name : undefined;
}
