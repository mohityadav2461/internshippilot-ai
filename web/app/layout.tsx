import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InternshipPilot AI",
  description: "Internship discovery and manual-approval application preparation.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
