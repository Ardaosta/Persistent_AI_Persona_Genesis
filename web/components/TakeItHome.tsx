"use client";

import { useMemo, useState } from "react";
import {
  type OS,
  type Seed,
  detectOS,
  installCommand,
  installFile,
} from "@/lib/seed";

// The culmination of onboarding: hand the person a way to stand their tuned AI up
// on their OWN machine. The default path is download-and-double-click (no terminal
// for someone who'd find one intimidating); the command is kept as an "advanced"
// fallback. They run it; nothing runs on them.
export default function TakeItHome({ seed }: { seed: Seed }) {
  const [os, setOs] = useState<OS>(() => detectOS());
  const [copied, setCopied] = useState(false);
  const [showCmd, setShowCmd] = useState(false);

  const command = useMemo(() => installCommand(seed, os), [seed, os]);
  const file = useMemo(() => installFile(seed, os), [seed, os]);

  const download = () => {
    const blob = new Blob([file.content], { type: file.mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

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

  const dblclick =
    os === "windows"
      ? "Double-click the downloaded file. Windows may warn it's from an unknown publisher; click “More info” then “Run anyway.”"
      : os === "mac"
        ? "Double-click the downloaded file. If macOS blocks it, right-click it and choose Open."
        : "Make it executable and run it (chmod +x, then ./genesis-setup.sh).";

  return (
    <div className="takehome">
      <div className="takehome-head">Take it home</div>
      <div className="takehome-sub">
        Everything you just shaped lives on your machine, not ours. Download the
        setup file and open it; it carries your answers with it and walks you the
        rest of the way.
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

      <button className="send download-btn" onClick={download}>
        Download for {tabs.find((t) => t.id === os)?.label}
      </button>
      <div className="takehome-note">{dblclick} It downloads your AI, sets it
        up tuned to your answers, then starts talking to you and helps you connect
        a brain.</div>

      <button className="linkish" onClick={() => setShowCmd((v) => !v)}>
        {showCmd ? "Hide the terminal command" : "Prefer the terminal? Show the command"}
      </button>
      {showCmd && (
        <>
          <pre className="cmd" aria-label="install command">
            <code>{command}</code>
          </pre>
          <button className="send copy-btn" onClick={copy}>
            {copied ? "Copied" : "Copy command"}
          </button>
        </>
      )}
    </div>
  );
}
