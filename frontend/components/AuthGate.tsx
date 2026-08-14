"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);
  const isLogin = pathname.startsWith("/login");

  useEffect(() => {
    if (isLogin) return;
    let active = true;
    fetch("/api/auth/me", { credentials: "include" })
      .then((response) => {
        if (response.status === 401) return router.replace("/login");
        if (!response.ok) throw new Error("Authentication check failed");
        if (active) setAuthenticated(true);
      })
      .catch(() => {
        if (active) router.replace("/login");
      });
    return () => { active = false; };
  }, [isLogin, router]);

  if (isLogin) return children;
  if (!authenticated) return <main className="login-page"><div className="loading">Establishing secure session…</div></main>;
  return children;
}
