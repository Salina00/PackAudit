import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PackAudit - Legal Metrology Compliance",
  description: "Statutory compliance checker for India's Legal Metrology Rules",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased min-h-screen bg-[#0A0A0A] text-[#EDEDED] flex">
        {/* Sidebar Nav */}
        <aside className="w-64 border-r border-[#262626] bg-[#0F0F0F] flex flex-col h-screen sticky top-0">
          {/* Logo */}
          <div className="p-6 border-b border-[#262626] flex items-center gap-3">
            <svg className="w-6 h-6 text-[#10B981]" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            <span className="font-mono text-lg font-bold tracking-tight text-[#EDEDED]">PackAudit</span>
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 p-4 space-y-1">
            <a href="/" className="flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition bg-[#1A1A1A] text-[#10B981] hover:bg-[#222222]">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z" />
              </svg>
              Dashboard
            </a>
            <a href="/rules" className="flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition text-[#A3A3A3] hover:text-[#EDEDED] hover:bg-[#1A1A1A]">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
              Rules Database
            </a>
          </nav>

          {/* User/Status Footer */}
          <div className="p-4 border-t border-[#262626] bg-[#0B0B0B] flex items-center justify-between text-xs text-[#737373]">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#10B981] animate-pulse"></span>
              <span>System Online</span>
            </div>
            <span>v1.0.0</span>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col h-screen overflow-y-auto">
          {children}
        </main>
      </body>
    </html>
  );
}
