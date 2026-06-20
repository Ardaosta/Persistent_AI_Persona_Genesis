// The onboarding seed — browser half of the web→local handoff. Mirrors
// genesis_core/seed.py: a base64url (no padding) blob of the seed JSON that
// `genesis init --seed` decodes on the user's machine. Only conditions ride in
// it (archetype + machinery + look), never personality content.
//
// Pull-not-push: the seed travels INSIDE the install command the user runs. The
// web never executes anything on their box and never phones home for the seed.

export type Seed = {
  v: number;
  archetype: Record<string, unknown>;
  machinery: Record<string, unknown>;
  look: string | null;
  provider: string | null;
  sponsor: string | null;
};

export const SEED_VERSION = 1;

export function makeSeed(opts: {
  archetype?: Record<string, unknown>;
  machinery?: Record<string, unknown>;
  look?: string | null;
  provider?: string | null;
  sponsor?: string | null;
}): Seed {
  return {
    v: SEED_VERSION,
    archetype: opts.archetype ?? {},
    machinery: opts.machinery ?? {},
    look: opts.look ?? null,
    provider: opts.provider ?? null,
    sponsor: opts.sponsor ?? null,
  };
}

// UTF-8-safe base64url, no padding — decodes byte-for-byte in seed.py's decode().
export function encodeSeed(seed: Seed): string {
  const json = JSON.stringify(seed);
  const bytes = new TextEncoder().encode(json);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export type OS = "mac" | "windows" | "linux";

export function detectOS(): OS {
  if (typeof navigator === "undefined") return "mac";
  const s = `${navigator.platform} ${navigator.userAgent}`.toLowerCase();
  if (s.includes("win")) return "windows";
  if (s.includes("mac") || s.includes("iphone") || s.includes("ipad")) return "mac";
  return "linux";
}

// The exact command the user pastes into their terminal. `host` defaults to the
// page origin, so install.sh / install.ps1 are served from this same app.
export function installCommand(seed: Seed, os: OS, host?: string): string {
  const blob = encodeSeed(seed);
  const base = (host ?? (typeof window !== "undefined" ? window.location.origin : "")).replace(/\/$/, "");
  if (os === "windows") {
    return `$env:GENESIS_SEED='${blob}'; irm ${base}/install.ps1 | iex`;
  }
  return `GENESIS_SEED='${blob}' sh -c "$(curl -fsSL ${base}/install.sh)"`;
}
