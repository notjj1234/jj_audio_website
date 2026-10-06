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
