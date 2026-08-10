"use client";
import { useQuery } from "@tanstack/react-query";
import { getAuthStatus } from "@/services/api";
import { Wifi, WifiOff, Linkedin } from "lucide-react";

export default function StatusBar() {
  const { data } = useQuery({
    queryKey: ["auth-status"],
    queryFn: () => getAuthStatus().then((r) => r.data),
    refetchInterval: 60_000,
  });

  const connected = data?.connected ?? false;

  return (
    <div className="h-10 bg-gray-900 text-white flex items-center px-4 gap-4 text-xs">
      <div className="flex items-center gap-1.5">
        {/* LinkedIn "in" wordmark */}
        <div className="w-5 h-5 bg-linkedin-500 rounded flex items-center justify-center font-black text-xs">
          in
        </div>
        <span className="font-semibold text-gray-100">LinkedIn Mailbox Manager</span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {connected ? (
          <span className="flex items-center gap-1 text-green-400">
            <Wifi className="h-3.5 w-3.5" />
            {data?.linkedin_email ?? "Connected"}
          </span>
        ) : (
          <span className="flex items-center gap-1 text-red-400">
            <WifiOff className="h-3.5 w-3.5" />
            Not connected — set LINKEDIN_EMAIL + LINKEDIN_PASSWORD
          </span>
        )}
      </div>
    </div>
  );
}
