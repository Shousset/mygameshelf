import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import ConnectionStatus from "@/components/ConnectionStatus";

export const metadata: Metadata = {
  title: "MyGameShelf",
  description: "Your personal game collection & progress tracker",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div style={{ display: "flex", minHeight: "100vh" }}>
          <Sidebar />
          <main style={{ flex: 1, overflowY: "auto", maxWidth: "100%" }}>
            <ConnectionStatus />
            <div className="fade-in" style={{ padding: "2rem" }}>{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
