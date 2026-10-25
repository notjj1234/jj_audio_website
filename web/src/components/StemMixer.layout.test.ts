import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function read(rel: string): string {
  return readFileSync(resolve(process.cwd(), rel), "utf-8");
}

describe("website player layout", () => {
  const mixer = read("src/components/StemMixer.tsx");

  it("puts the practice sheet after transport, mix, speed, and the stem stage", () => {
    const transport = mixer.indexOf('className="mixer-transport');
    const mix = mixer.indexOf('id="mix-menu"');
    const speed = mixer.indexOf('id="practice-speed-popover"');
    const stage = mixer.indexOf('className="mixer-stage"');
    const master = mixer.indexOf('className="master-vol"');
    const stems = mixer.indexOf('className="mixer-stems"');
    const sheet = mixer.indexOf('id="practice-panel"');
    expect(transport).toBeGreaterThan(-1);
    expect(transport).toBeLessThan(mix);
    expect(mix).toBeLessThan(speed);
    expect(speed).toBeLessThan(stage);
    expect(stage).toBeLessThan(master);
    expect(master).toBeLessThan(stems);
    expect(stems).toBeLessThan(sheet);
    expect(mixer).toContain(">Practice<");
    expect(mixer).toContain(">Mix<");
    expect(mixer).toContain("Speed &amp; Key");
    expect(mixer).toContain('key !== "Escape"');
  });
});

describe("pan law stays shared", () => {
  it("keeps the website pan file identical to the desktop pan file", () => {
    const web = read("src/mixer/pan.ts");
    const desktop = readFileSync(
      resolve(process.cwd(), "../ui/stem_mixer_component/frontend/src/pan.ts"),
      "utf-8"
    );
    expect(web).toBe(desktop);
  });
});
