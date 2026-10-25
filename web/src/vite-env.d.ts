/// <reference types="vite/client" />

interface HTMLAudioElement {
  playsInline: boolean;
}

declare module "node:fs" {
  export function readFileSync(path: string, encoding: "utf-8"): string;
}

declare module "node:path" {
  export function resolve(...paths: string[]): string;
}

declare const process: { cwd(): string };

declare module "*.md?raw" {
  const content: string;
  export default content;
}
