"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "@/lib/constants";

export default function Nav({ email }: { email: string }) {
  const pathname = usePathname();
  return (
    <aside className="border-b border-zinc-200 bg-white md:sticky md:top-0 md:h-screen md:w-56 md:shrink-0 md:border-b-0 md:border-r">
      <div className="px-5 py-5">
        <div className="text-sm font-semibold">InternshipPilot AI</div>
        <div className="mt-1 truncate text-xs text-zinc-500">{email}</div>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`whitespace-nowrap rounded-md px-3 py-2 text-sm ${
                active ? "bg-zinc-100 font-medium text-zinc-900" : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="hidden px-5 py-4 text-xs leading-relaxed text-zinc-400 md:block">
        Zero-cost stack. You approve every application, and you submit it yourself.
      </div>
    </aside>
  );
}
