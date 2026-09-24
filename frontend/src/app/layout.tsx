import type { Metadata } from "next";
import "./globals.css";

import { AuthProvider } from "@/lib/auth-context";
import NavBar from "@/components/NavBar";

export const metadata: Metadata = {
  title: "AI PDF Chatbot",
  description: "Upload a PDF and ask questions about it, with page citations.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <AuthProvider>
          <NavBar />
          <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
