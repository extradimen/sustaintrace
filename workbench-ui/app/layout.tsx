import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SustainTrace — Evidence-Grounded ESG Knowledge Discovery",
  description: "Build verifiable, traceable and repairable ESG knowledge from corporate reports.",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
