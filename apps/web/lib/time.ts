const LOS_ANGELES_TIME_ZONE = "America/Los_Angeles";

const dateTimeFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "medium",
  timeZone: LOS_ANGELES_TIME_ZONE,
});

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  timeStyle: "medium",
  timeZone: LOS_ANGELES_TIME_ZONE,
});

export function formatLosAngelesDateTime(value?: string): string {
  if (!value) return "n/a";
  return dateTimeFormatter.format(new Date(value));
}

export function formatLosAngelesTime(value?: string): string {
  if (!value) return "n/a";
  return timeFormatter.format(new Date(value));
}

export function losAngelesTimeZoneLabel(): string {
  return "America/Los_Angeles";
}
