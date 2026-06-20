import type { Capability } from "@/lib/directives";

// Outline icons, drawn inline so the tray has no icon-font dependency and each
// glyph inherits the learned accent color via currentColor.
export function CapabilityIcon({ cap }: { cap: Capability }) {
  switch (cap) {
    case "voice":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
        </svg>
      );
    case "screenshare":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="4" width="18" height="13" rx="2" />
          <path d="M8 21h8M12 8v5M9.5 10.5 12 8l2.5 2.5" />
        </svg>
      );
    case "photos":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <circle cx="8.5" cy="10" r="1.5" />
          <path d="m4 17 5-4 4 3 3-2 4 3" />
        </svg>
      );
    case "email":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="m3 7 9 6 9-6" />
        </svg>
      );
    case "files":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />
        </svg>
      );
  }
}

export const CAP_LABELS: Record<Capability, string> = {
  voice: "Voice",
  screenshare: "Share my screen",
  photos: "Show a photo",
  email: "Send an email",
  files: "Open a file",
};
