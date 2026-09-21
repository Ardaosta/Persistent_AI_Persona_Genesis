// The onboarding seed, browser half of the web-to-local handoff. Mirrors
// genesis_core/seed.py: a base64url (no padding) blob of the seed JSON that
// `genesis init --seed` decodes on the user's machine. Only conditions ride in
// it (archetype + machinery + look), never personality content.
//
// Pull-not-push: the seed travels INSIDE the install command the user runs. The
// web never executes anything on their box and never phones home for the seed.

export type Harness = "claude-code" | "codex";
export const HARNESSES: Harness[] = ["claude-code", "codex"];
// Mirrors seed.py CAPABILITIES: the domains the person asked for help with.
// Pointers at content-free recipes copied into the vault at init; unknown
// slugs are dropped on decode, so this list and seed.py must agree.
export type Capability = "website" | "social" | "calendar" | "email" | "finances";
export const CAPABILITIES: Capability[] = ["website", "social", "calendar", "email", "finances"];

export type Seed = {
  v: number;
  archetype: Record<string, unknown>;
  machinery: Record<string, unknown>;
  look: string | null;
  provider: string | null;
  sponsor: string | null;
  mode: string | null;
  // 2026-09-10 conditions (mirrored in seed.py): the person's chosen name for
  // the AI or null to let it choose its own; which Mode-B doors to wire (mode
  // stays the primary); a repository the AI is joining; the getting-to-know-you
  // drip opt-in. Conditions, never content.
  name: string | null;
  harnesses: Harness[];
  project_repo: string | null;
  drip: boolean;
  // 2026-09-21: what it helps with (mirrored in seed.py). Conditions, never content.
  capabilities: Capability[];
  // Named online services the person already uses (mirrored in seed.py
  // SERVICES). Only a sponsor who knows the setup names these; the generic
  // flow never presupposes one.
  services: Service[];
  // 2026-09-21: remote help (mirrored in seed.py HELPER). A sponsor may include
  // their PUBLIC ssh keys; the person decides on screen. `consented` rides
  // through decode so the page can show the offer, but the download carries
  // a helper only when the person said yes here; otherwise it is null and the
  // installer never sees the keys.
  helper: Helper | null;
};

export type Helper = { name: string; keys: string[]; consented: boolean };
export const HELPER_KEY_RE = /^(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) [A-Za-z0-9+/=]+( [^\s]{1,64})?$/;
const HELPER_KEY_MAX = 600;
const HELPER_KEYS_MAX = 4;
const HELPER_NAME_MAX = 40;

// Display-only, sanitized like cleanName in AdaptiveCanvas: letters, marks,
// spaces, apostrophes, dots and hyphens; short.
function cleanHelperName(v: unknown): string {
  if (typeof v !== "string") return "";
  return v.replace(/[^\p{L}\p{M}' .-]/gu, "").trim().slice(0, HELPER_NAME_MAX);
}

// Keep a helper only when shape-valid and at least one key is valid. Invalid
// keys are dropped; more than HELPER_KEYS_MAX are truncated.
function cleanHelper(value: unknown): Helper | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const o = value as Record<string, unknown>;
  if (!Array.isArray(o.keys)) return null;
  const keys: string[] = [];
  for (const k of o.keys) {
    if (typeof k !== "string") continue;
    const t = k.trim();
    if (t.length > HELPER_KEY_MAX || !HELPER_KEY_RE.test(t) || keys.includes(t)) continue;
    keys.push(t);
    if (keys.length >= HELPER_KEYS_MAX) break;
  }
  if (keys.length === 0) return null;
  return { name: cleanHelperName(o.name), keys, consented: o.consented === true };
}

export type Service = "wix";
export const SERVICES: Service[] = ["wix"];

function cleanServices(value: unknown): Service[] {
  const out: Service[] = [];
  if (!Array.isArray(value)) return out;
  for (const x of value) {
    if (typeof x === "string" && (SERVICES as string[]).includes(x) && !out.includes(x as Service)) {
      out.push(x as Service);
    }
  }
  return out;
}

export const SEED_VERSION = 1;

function cleanCapabilities(value: unknown): Capability[] {
  const out: Capability[] = [];
  if (!Array.isArray(value)) return out;
  for (const x of value) {
    if (typeof x === "string" && (CAPABILITIES as string[]).includes(x) && !out.includes(x as Capability)) {
      out.push(x as Capability);
    }
  }
  return out;
}

export function makeSeed(opts: {
  archetype?: Record<string, unknown>;
  machinery?: Record<string, unknown>;
  look?: string | null;
  provider?: string | null;
  sponsor?: string | null;
  mode?: string | null;
  name?: string | null;
  harnesses?: Harness[];
  project_repo?: string | null;
  drip?: boolean;
  capabilities?: Capability[];
  services?: Service[];
  helper?: Helper | null;
}): Seed {
  return {
    v: SEED_VERSION,
    archetype: opts.archetype ?? {},
    machinery: opts.machinery ?? {},
    look: opts.look ?? null,
    provider: opts.provider ?? null,
    sponsor: opts.sponsor ?? null,
    mode: opts.mode ?? null,
    name: (opts.name ?? "").trim().slice(0, 60) || null,
    harnesses: (opts.harnesses ?? []).filter((h) => HARNESSES.includes(h)),
    project_repo: (opts.project_repo ?? "").trim().slice(0, 300) || null,
    drip: opts.drip ?? false,
    capabilities: cleanCapabilities(opts.capabilities),
    services: cleanServices(opts.services),
    helper: cleanHelper(opts.helper),
  };
}

// UTF-8-safe base64url, no padding. Decodes byte-for-byte in seed.py's decode().
export function encodeSeed(seed: Seed): string {
  const json = JSON.stringify(seed);
  const bytes = new TextEncoder().encode(json);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function cleanString(v: unknown, max: number): string | null {
  if (typeof v === "string") return v.trim().slice(0, max) || null;
  if (typeof v === "number" || typeof v === "boolean") return String(v).slice(0, max);
  return null;
}

function cleanObject(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

// The inverse of encodeSeed, mirroring seed.py's decode(): keep only the known
// keys, coerce every shape, drop unknown capability slugs and harnesses. A
// malformed blob returns null rather than throwing, so a bad link degrades to
// the ordinary flow instead of a broken page.
export function decodeSeed(blob: string | null | undefined): Seed | null {
  const s = (blob ?? "").trim();
  if (!s) return null;
  let data: unknown;
  try {
    const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (s.length % 4)) % 4);
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    data = JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) return null;
  const o = data as Record<string, unknown>;
  return {
    v: SEED_VERSION,
    archetype: cleanObject(o.archetype),
    machinery: cleanObject(o.machinery),
    look: cleanString(o.look, 200),
    provider: cleanString(o.provider, 40),
    sponsor: cleanString(o.sponsor, 200),
    mode: cleanString(o.mode, 40),
    name: cleanString(o.name, 60),
    harnesses: Array.isArray(o.harnesses)
      ? o.harnesses.filter((h): h is Harness => typeof h === "string" && (HARNESSES as string[]).includes(h))
      : [],
    project_repo: cleanString(o.project_repo, 300),
    drip: Boolean(o.drip),
    capabilities: cleanCapabilities(o.capabilities),
    services: cleanServices(o.services),
    helper: cleanHelper(o.helper),
  };
}

export type OS = "mac" | "windows" | "linux";

export function detectOS(): OS {
  if (typeof navigator === "undefined") return "mac";
  const s = `${navigator.platform} ${navigator.userAgent}`.toLowerCase();
  if (s.includes("win")) return "windows";
  if (s.includes("mac") || s.includes("iphone") || s.includes("ipad")) return "mac";
  return "linux";
}

function baseUrl(host?: string): string {
  return (host ?? (typeof window !== "undefined" ? window.location.origin : "")).replace(/\/$/, "");
}

// The exact command for someone who would rather do it by hand. `host` defaults
// to the page origin, so install.sh / install.ps1 are served from this same app.
export function installCommand(seed: Seed, os: OS, host?: string): string {
  const blob = encodeSeed(seed);
  const base = baseUrl(host);
  if (os === "windows") {
    return `$env:GENESIS_SEED='${blob}'; irm ${base}/install.ps1 | iex`;
  }
  return `GENESIS_SEED='${blob}' sh -c "$(curl -fsSL ${base}/install.sh)"`;
}

// A friendly file name for the download: "Set up Carson" when the AI has a
// name, "Set up my AI" otherwise. Characters a file system rejects are dropped.
export function installFileStem(seed: Seed): string {
  // eslint-disable-next-line no-control-regex
  const safe = (seed.name ?? "").replace(/[\\/:*?"<>|\x00-\x1f]/g, "").trim();
  return safe ? `Set up ${safe}` : "Set up my AI";
}

// A double-clickable setup file with the seed baked in, so a non-technical
// person never opens a terminal: download, open, watch. Returns the filename,
// contents, and a mime type for the download blob.
export function installFile(
  seed: Seed,
  os: OS,
  host?: string,
): { name: string; content: string; mime: string } {
  const blob = encodeSeed(seed);
  const base = baseUrl(host);
  const stem = installFileStem(seed);
  if (os === "windows") {
    // The .bat only sets the seed and hands off to the guided (windowed)
    // installer. CRLF line endings; no pause, the GUI owns the experience and a
    // console should not linger behind it.
    const content =
      "@echo off\r\n" +
      "setlocal\r\n" +
      `set "GENESIS_SEED=${blob}"\r\n` +
      `powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "irm ${base}/install-gui.ps1 | iex"\r\n`;
    return { name: `${stem}.bat`, content, mime: "application/octet-stream" };
  }
  // macOS .command double-clicks open in Terminal; Linux gets a plain .sh.
  const name = os === "mac" ? `${stem}.command` : `${stem.toLowerCase().replace(/\s+/g, "-")}.sh`;
  const content =
    "#!/bin/bash\n" +
    `export GENESIS_SEED='${blob}'\n` +
    `/bin/bash -c "$(curl -fsSL ${base}/install.sh)"\n`;
  return { name, content, mime: "application/octet-stream" };
}
