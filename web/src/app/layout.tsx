import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { ThemeProvider } from "@/components/layout/ThemeProvider";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "JobPilot - an agent that hunts jobs with you", template: "%s | JobPilot" },
  description:
    "Chat with an agent that searches real roles, explains the match, and tailors your resume to each job.",
};

export const viewport: Viewport = { themeColor: "#0e5a4b" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
