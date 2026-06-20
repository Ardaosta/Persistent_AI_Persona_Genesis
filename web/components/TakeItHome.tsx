"use client";

import { useMemo, useState } from "react";
import { type OS, type Seed, detectOS, installCommand } from "@/lib/seed";

// The culmination of onboarding: hand the person a single command that stands up
// their tuned AI on their OWN machine. They run it; nothing runs on them.
export default function TakeItHome({ seed }: { seed: Seed }) {
  const [os, setOs] = useState<OS>(() => detectOS());
  const [copied, setCopied] = useState(false);

  const command = useMemo(() => installCommand(seed, os), [seed, os]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked; the user can still select the text */
    }
  };

  const tabs: { id: OS; label: string }[] = [
    { id: "mac", label: "macOS" },
    { id: "windows", label: "Windows" },
    { id: "linux", label: "Linux" },
  ];

  return (
    <div className="takehome">
      <div className="takehome-head">Take it home</div>
      <div className="takehome-sub">
        Everything you just shaped lives on your machine, not ours. Paste this into
        your terminal to set it up — it carries your answers with it.
      </div>
      <div className="os-tabs">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={t.id === os ? "os-tab active" : "os-tab"}
            onClick={() => setOs(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <pre className="cmd" aria-label="install command">
        <code>{command}</code>
      </pre>
      <button className="send copy-btn" onClick={copy}>
        {copied ? "Copied" : "Copy command"}
      </button>
      <div className="takehome-note">
        {os === "windows"
          ? "Open PowerShell, paste, and press Enter."
          : "Open Terminal, paste, and press Enter."}{" "}
        It downloads Genesis, sets up a private home tuned to your answers, then
        walks you through connecting a brain.
      </div>
    </div>
  );
}
