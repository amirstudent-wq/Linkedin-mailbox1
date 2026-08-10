"use client";
import { Search, SortAsc, SortDesc, RefreshCw, Play, Loader2 } from "lucide-react";
import { useState } from "react";
import type { ConversationFilters, SortBy, SortDir } from "@/types";
import { syncConversations, triggerDailyScan } from "@/services/api";
import { useQueryClient } from "@tanstack/react-query";

interface Props {
  filters: ConversationFilters;
  onChange: (f: Partial<ConversationFilters>) => void;
}

export default function FilterBar({ filters, onChange }: Props) {
  const qc = useQueryClient();
  const [syncing, setSyncing] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");

  async function handleSync() {
    setSyncing(true);
    setSyncMsg("");
    try {
      const res = await syncConversations();
      setSyncMsg(`✓ ${res.data.message}`);
      qc.invalidateQueries({ queryKey: ["conversations"] });
    } catch {
      setSyncMsg("Sync failed — check LinkedIn credentials.");
    } finally {
      setSyncing(false);
    }
  }

  async function handleScan() {
    setScanning(true);
    setSyncMsg("");
    try {
      const res = await triggerDailyScan();
      const d = res.data;
      setSyncMsg(
        `✓ Scan done: ${d.unanswered_found} unanswered, ${d.drafts_created} drafts created.`
      );
      qc.invalidateQueries({ queryKey: ["conversations"] });
      qc.invalidateQueries({ queryKey: ["drafts"] });
    } catch {
      setSyncMsg("Scan failed.");
    } finally {
      setScanning(false);
    }
  }

  const toggleSort = () =>
    onChange({ sort_dir: filters.sort_dir === "desc" ? "asc" : "desc" });

  return (
    <div className="border-b border-gray-200 bg-white px-4 py-3 space-y-3">
      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          placeholder="Search conversations…"
          value={filters.search}
          onChange={(e) => onChange({ search: e.target.value })}
          className="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-linkedin-500 focus:border-transparent"
        />
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap gap-2 items-center">
        {/* Unread toggle */}
        <button
          onClick={() => onChange({ unread_only: !filters.unread_only })}
          className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
            filters.unread_only
              ? "bg-linkedin-500 text-white border-linkedin-500"
              : "bg-white text-gray-600 border-gray-300 hover:border-linkedin-400"
          }`}
        >
          Unread
        </button>

        {/* Awaiting reply */}
        <button
          onClick={() =>
            onChange({
              awaiting_reply:
                filters.awaiting_reply === true
                  ? null
                  : filters.awaiting_reply === null
                  ? false
                  : null,
            })
          }
          className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
            filters.awaiting_reply === true
              ? "bg-amber-500 text-white border-amber-500"
              : filters.awaiting_reply === false
              ? "bg-green-500 text-white border-green-500"
              : "bg-white text-gray-600 border-gray-300 hover:border-amber-400"
          }`}
        >
          {filters.awaiting_reply === true
            ? "Needs reply"
            : filters.awaiting_reply === false
            ? "Replied"
            : "Reply status"}
        </button>

        {/* Sort by */}
        <select
          value={filters.sort_by}
          onChange={(e) => onChange({ sort_by: e.target.value as SortBy })}
          className="px-3 py-1 rounded-full text-xs font-medium border border-gray-300 bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-linkedin-500"
        >
          <option value="last_message_at">Sort: Date</option>
          <option value="participant_name">Sort: Name</option>
        </select>

        {/* Sort direction */}
        <button
          onClick={toggleSort}
          className="p-1.5 rounded-full border border-gray-300 hover:border-linkedin-400 text-gray-600"
          title={filters.sort_dir === "desc" ? "Newest first" : "Oldest first"}
        >
          {filters.sort_dir === "desc" ? (
            <SortDesc className="h-3.5 w-3.5" />
          ) : (
            <SortAsc className="h-3.5 w-3.5" />
          )}
        </button>

        <div className="ml-auto flex gap-2">
          {/* Sync */}
          <button
            onClick={handleSync}
            disabled={syncing}
            title="Sync conversations from LinkedIn"
            className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-linkedin-500 text-white hover:bg-linkedin-600 disabled:opacity-50 transition-colors"
          >
            {syncing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Sync
          </button>

          {/* Daily scan */}
          <button
            onClick={handleScan}
            disabled={scanning}
            title="Run AI daily scan now"
            className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {scanning ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            AI Scan
          </button>
        </div>
      </div>

      {syncMsg && (
        <p className="text-xs text-gray-500">{syncMsg}</p>
      )}
    </div>
  );
}
