import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import { AppContextProvider } from "@/context/AppContext";
import { Sidebar } from "@/components/Sidebar";

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
        <AppContextProvider>
          <div className="flex h-screen w-full flex-row overflow-hidden bg-slate-950 text-slate-200">
            <Sidebar />
            <main className="flex flex-1 flex-col relative overflow-hidden">
              {children}
            </main>
          </div>
        </AppContextProvider>
      </body>
    </html>
  );
}
