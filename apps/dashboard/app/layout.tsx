import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "../src/components/layout/AppShell";
import { AuthProvider } from "../src/context/AuthContext";

export const metadata: Metadata = {
  title: "NEXUS Operating System — Console",
  description: "Unified Command Center for NEXUS Agentic AI Operating System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#06090e] bg-grid-pattern text-slate-100 antialiased selection:bg-cyan-500 selection:text-black">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
