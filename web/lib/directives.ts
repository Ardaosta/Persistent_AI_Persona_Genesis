// The interface-directive contract — the TypeScript mirror of
// genesis_core/interface_directives.py. The guide emits these alongside its
// words; the AdaptiveCanvas animates each into being.
//
// Bounded by design ("vocabulary now, generative seam later"): the kinds and
// enums below are closed. A future RawBlock directive is the generative seam.

export const CAPABILITIES = ["voice", "screenshare", "photos", "email", "files"] as const;
export type Capability = (typeof CAPABILITIES)[number];

export const TYPE_REGISTERS = ["plain", "editorial", "cinematic", "technical", "gentle"] as const;
export type TypeRegister = (typeof TYPE_REGISTERS)[number];

export const SCALES = ["normal", "large", "xl"] as const;
export type Scale = (typeof SCALES)[number];

export type Palette = { base: string; accent: string; text?: string };

// A selectable option in a choice card. Picking it can carry its own directives
// (e.g. choosing a "warm" voice fires a setType), and a value the flow records.
export type Choice = { label: string; sublabel?: string; value: string; directives?: Directive[] };

export type Directive =
  | { kind: "setPalette"; palette: Palette }
  | { kind: "setType"; register: TypeRegister; scale?: Scale }
  | { kind: "unlockCapability"; capability: Capability }
  | { kind: "emphasize"; text: string }
  | { kind: "presentChoices"; prompt?: string; choices: Choice[] };

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

// Strict validation — a malformed directive must never reach the screen.
// Returns the directive (narrowed) or null.
export function validate(d: unknown): Directive | null {
  if (!d || typeof d !== "object") return null;
  const o = d as Record<string, unknown>;
  switch (o.kind) {
    case "setPalette": {
      const p = o.palette as Record<string, unknown> | undefined;
      if (!p || typeof p !== "object") return null;
      if (typeof p.base !== "string" || !HEX.test(p.base)) return null;
      if (typeof p.accent !== "string" || !HEX.test(p.accent)) return null;
      const palette: Palette = { base: p.base, accent: p.accent };
      if (typeof p.text === "string" && HEX.test(p.text)) palette.text = p.text;
      return { kind: "setPalette", palette };
    }
    case "setType": {
      if (!TYPE_REGISTERS.includes(o.register as TypeRegister)) return null;
      const out: Directive = { kind: "setType", register: o.register as TypeRegister };
      if (o.scale && SCALES.includes(o.scale as Scale)) out.scale = o.scale as Scale;
      return out;
    }
    case "unlockCapability": {
      if (!CAPABILITIES.includes(o.capability as Capability)) return null;
      return { kind: "unlockCapability", capability: o.capability as Capability };
    }
    case "emphasize": {
      if (typeof o.text !== "string" || !o.text.trim()) return null;
      return { kind: "emphasize", text: o.text.trim().slice(0, 280) };
    }
    case "presentChoices": {
      if (!Array.isArray(o.choices) || o.choices.length === 0) return null;
      const choices: Choice[] = [];
      for (const raw of o.choices) {
        if (!raw || typeof raw !== "object") return null;
        const c = raw as Record<string, unknown>;
        if (typeof c.label !== "string" || typeof c.value !== "string") return null;
        const choice: Choice = { label: c.label, value: c.value };
        if (typeof c.sublabel === "string") choice.sublabel = c.sublabel;
        if (Array.isArray(c.directives)) {
          const ds: Directive[] = [];
          for (const d of c.directives) {
            const v = validate(d);
            if (v) ds.push(v);
          }
          if (ds.length) choice.directives = ds;
        }
        choices.push(choice);
      }
      const out: Directive = { kind: "presentChoices", choices };
      if (typeof o.prompt === "string" && o.prompt.trim()) out.prompt = o.prompt.trim();
      return out;
    }
    default:
      return null;
  }
}

// The accumulated, persistable interface state (the "permanent surface").
export type InterfaceProfile = {
  palette: Partial<Palette>;
  register: TypeRegister | null;
  scale: Scale;
  unlocked: Capability[];
};

export function emptyProfile(): InterfaceProfile {
  return { palette: {}, register: null, scale: "normal", unlocked: [] };
}

export function foldDirective(p: InterfaceProfile, d: Directive): InterfaceProfile {
  switch (d.kind) {
    case "setPalette":
      return { ...p, palette: { ...d.palette } };
    case "setType":
      return { ...p, register: d.register, scale: d.scale ?? p.scale };
    case "unlockCapability":
      return p.unlocked.includes(d.capability)
        ? p
        : { ...p, unlocked: [...p.unlocked, d.capability] };
    case "emphasize":
    case "presentChoices":
      return p; // transient — animates/prompts but does not persist
  }
}
