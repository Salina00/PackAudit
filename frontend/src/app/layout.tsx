import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PackAudit - Consumer Packaging Compliance & Food Safety",
  description: "Statutory compliance checker for India's Legal Metrology Rules, FSSAI Food Safety, and Textile Standards",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased min-h-screen bg-[#0A0A0A] text-[#EDEDED]">
        {children}
      </body>
    </html>
  );
}
