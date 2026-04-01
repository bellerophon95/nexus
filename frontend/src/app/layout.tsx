import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Nexus AI | Intelligent Grounding Layer",
  description: "Advanced semantic search and agentic reasoning dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={cn(inter.className, "bg-slate-950 antialiased selection:bg-blue-500/30 selection:text-blue-200")}>
        {children}
      </body>
    </html>
  );
}
