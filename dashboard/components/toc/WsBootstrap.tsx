"use client";
import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { initWs, destroyWs } from "@/lib/ws-client";

/**
 * Mounts invisibly in the TOC layout.
 * Starts the WS connection once the session is authenticated.
 * Tears down on unmount (route change / logout).
 */
export default function WsBootstrap() {
  const { data: session, status } = useSession();

  useEffect(() => {
    if (status !== "authenticated") return;
    initWs(session?.accessToken as string | null);
    return () => { destroyWs(); };
  }, [status, session?.accessToken]);

  return null;
}
