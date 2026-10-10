/** Hosted Isolate submit helpers. Desktop length is not clamped here. */

export function fullFileTrimNotice(
  durationSec: number | null,
  modeCapSec: number | null,
  useRegion: boolean,
): string | null {
  if (useRegion || durationSec == null || modeCapSec == null) return null;
  if (!(durationSec > modeCapSec)) return null;
  return `This mode uses the first ${modeCapSec} s of the file.`;
}

export function isolateStartLabel(
  busy: boolean,
  status: string | undefined,
): string {
  if (busy) return "Starting…";
  if (status === "pending" || status === "running") return "Job running…";
  return "Start isolation";
}

export function isolateStartDisabled(
  startBlocked: boolean,
  status: string | undefined,
): boolean {
  return startBlocked || status === "pending" || status === "running";
}

export function isolateRepairBody(opts: {
  lowEndRestoreDb: number;
  subBassDebleed: boolean;
}): { low_end_restore_db?: number; sub_bass_debleed?: boolean } {
  const body: { low_end_restore_db?: number; sub_bass_debleed?: boolean } = {};
  if (opts.lowEndRestoreDb > 0) {
    body.low_end_restore_db = opts.lowEndRestoreDb;
  }
  if (opts.subBassDebleed) {
    body.sub_bass_debleed = true;
  }
  return body;
}
