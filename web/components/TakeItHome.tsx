"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  type OS,
  type Seed,
  detectOS,
  installCommand,
  installFile,
} from "@/lib/seed";

// The culmination of onboarding: hand the person a way to stand their AI up on
// their OWN computer. Written for someone who has never opened a terminal and
// never will: one big download, three calm steps, a reassurance. The command is
// kept behind a small link for anyone who would rather do it by hand. They run
// it; nothing runs on them.
export default function TakeItHome({
  seed,
  from,
}: {
  seed: Seed;
  // The sponsor's first name (the `from` in a prepared link), for the
  // "a message away" line. Falls back to a plain phrase.
  from?: string | null;
}) {
  const [os, setOs] = useState<OS>(() => detectOS());
  const [copied, setCopied] = useState(false);
  const [showCmd, setShowCmd] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const cardRef = useRef<HTMLElement>(null);

  // The card appears below whatever came before it; bring it into view so the
  // person is looking at the one button that matters, not at the greeting.
  useEffect(() => {
    cardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

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
    setDownloaded(true);
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

  const claude = seed.harnesses.includes("claude-code");
  const codex = seed.harnesses.includes("codex");
  const aiName = seed.name || "your AI";
  const helper = from || "the person who sent you this";

  const osLabel: Record<OS, string> = { windows: "Windows", mac: "a Mac", linux: "Linux" };
  const others = (["windows", "mac", "linux"] as OS[]).filter((o) => o !== os);

  // Step one is the only step that differs by computer: what the first warning
  // looks like, and what to click. Worded so a warning reads as routine.
  const stepOne =
    os === "windows"
      ? `Open the file from your Downloads folder. Windows will ask whether you are sure, because it has never seen this program before. That question is normal. If it offers "Run", choose Run. If it says "Windows protected your PC", choose "More info", then "Run anyway".`
      : os === "mac"
        ? `Open the file from your Downloads folder. Your Mac may say it cannot check the file, because it has never seen this program before. That is normal. Right-click the file and choose "Open".`
        : `Open your Downloads folder, make the file runnable, and start it. If a window asks whether you are sure, say yes; that question is normal for a new program.`;

  const stepThree = claude
    ? `When it finishes, it tells you exactly what to click in the Claude app, and it copies the one thing you will need to paste. That is the whole job.`
    : codex
      ? `When it finishes, it tells you exactly what to click in the Codex app, and it copies the one thing you will need to paste. That is the whole job.`
      : `When it finishes, ${aiName} says hello right there, and you can start talking. That is the whole job.`;

  return (
    <section className="takehome" aria-labelledby="takehome-head" ref={cardRef}>
      <h2 className="takehome-head" id="takehome-head">
        {seed.name ? `Bring ${seed.name} home` : "Bring your AI home"}
      </h2>
      <p className="takehome-sub">
        One file does everything. Download it, open it, and it takes care of the
        rest while you watch.
      </p>

      <button className="primary download-btn" onClick={download}>
        {downloaded ? "Downloaded. Download again?" : "Download my setup"}
      </button>
      <div className="takehome-file">
        {downloaded ? (
          <>The file is called <strong>{file.name}</strong>. Look for it in your Downloads folder.</>
        ) : (
          <>For {osLabel[os]}. The file will be called <strong>{file.name}</strong>.</>
        )}
      </div>

      <h3 className="takehome-h3">What happens next</h3>
      <ol className="steps">
        <li>
          <span className="step-num" aria-hidden="true">1</span>
          <span className="step-text">{stepOne}</span>
        </li>
        <li>
          <span className="step-num" aria-hidden="true">2</span>
          <span className="step-text">
            A window opens and does the work for you. It may ask you to allow a
            change or two along the way. Say yes. It can take a few minutes, and
            it will tell you what it is doing as it goes.
          </span>
        </li>
        <li>
          <span className="step-num" aria-hidden="true">3</span>
          <span className="step-text">{stepThree}</span>
        </li>
      </ol>

      <p className="takehome-reassure">
        Nothing about you leaves your computer. {aiName === "your AI" ? "Your AI" : aiName} and
        everything it remembers stay there, with you. And if anything is unclear
        at any point, {helper} is a message away.
      </p>

      <div className="takehome-quiet">
        <span>Not on {osLabel[os]}?</span>
        {others.map((o) => (
          <button key={o} className="linkish" onClick={() => { setOs(o); setDownloaded(false); }}>
            I use {osLabel[o]}
          </button>
        ))}
      </div>

      <button className="linkish" onClick={() => setShowCmd((v) => !v)}>
        {showCmd ? "Hide the by-hand version" : "I'd rather do it by hand"}
      </button>
      {showCmd && (
        <div className="byhand">
          <p className="takehome-note">
            {os === "windows"
              ? "Paste this into PowerShell and press Enter."
              : "Paste this into Terminal and press Enter."}
          </p>
          <pre className="cmd" aria-label="setup command">
            <code>{command}</code>
          </pre>
          <button className="send copy-btn" onClick={copy}>
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      )}
    </section>
  );
}
