import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Genesis",
  description: "An AI that learns who you are.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
