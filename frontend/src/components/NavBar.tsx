"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth-context";

const LINKS = [
  { href: "/documents", label: "Documents" },
  { href: "/chat", label: "Chat" },
];

export default function NavBar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
        <Link href={user ? "/documents" : "/"} className="text-sm font-semibold text-slate-900">
          AI PDF Chatbot
        </Link>

        {user && (
          <nav className="flex items-center gap-1">
            {LINKS.map((link) => {
              const active = pathname?.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
            <span className="ml-3 hidden text-sm text-slate-500 sm:inline">
              {user.email}
            </span>
            <button
              onClick={handleLogout}
              className="ml-2 rounded-md px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              Log out
            </button>
          </nav>
        )}
      </div>
    </header>
  );
}
