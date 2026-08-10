"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Inbox, Sparkles, Settings, Cpu } from "lucide-react";
import { clsx } from "clsx";

import { getConversations, getConversation } from "@/services/api";
import type { ConversationFilters } from "@/types";

import StatusBar from "@/components/StatusBar";
import FilterBar from "@/components/FilterBar";
import ConversationList from "@/components/ConversationList";
import ConversationThread from "@/components/ConversationThread";
import ReplyComposer from "@/components/ReplyComposer";
import DraftsSidebar from "@/components/DraftsSidebar";
import UseCasesPanel from "@/components/UseCasesPanel";

type RightPanel = "drafts" | "use-cases" | null;

export default function HomePage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rightPanel, setRightPanel] = useState<RightPanel>(null);
  const [filters, setFilters] = useState<ConversationFilters>({
    unread_only: false,
    awaiting_reply: null,
    search: "",
    sort_by: "last_message_at",
    sort_dir: "desc",
  });

  const { data: conversations, isLoading: loadingList } = useQuery({
    queryKey: ["conversations", filters],
    queryFn: () => getConversations(filters).then((r) => r.data),
    refetchInterval: 30_000,
  });

  const { data: activeConversation, isLoading: loadingConv } = useQuery({
    queryKey: ["conversation", selectedId],
    queryFn: () => (selectedId ? getConversation(selectedId).then((r) => r.data) : null),
    enabled: !!selectedId,
  });

  function patchFilters(patch: Partial<ConversationFilters>) {
    setFilters((f) => ({ ...f, ...patch }));
  }

  function togglePanel(panel: RightPanel) {
    setRightPanel((p) => (p === panel ? null : panel));
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <StatusBar />

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Left sidebar: icon nav ── */}
        <nav className="w-14 bg-white border-r border-gray-200 flex flex-col items-center py-4 gap-3 flex-shrink-0">
          <NavIcon
            icon={<Inbox className="h-5 w-5" />}
            label="Inbox"
            active={rightPanel === null}
            onClick={() => setRightPanel(null)}
          />
          <NavIcon
            icon={<Sparkles className="h-5 w-5" />}
            label="AI Drafts"
            active={rightPanel === "drafts"}
            onClick={() => togglePanel("drafts")}
          />
          <NavIcon
            icon={<Cpu className="h-5 w-5" />}
            label="Use Cases"
            active={rightPanel === "use-cases"}
            onClick={() => togglePanel("use-cases")}
          />
        </nav>

        {/* ── Conversation list ── */}
        <div className="w-80 flex flex-col border-r border-gray-200 bg-white flex-shrink-0">
          <FilterBar filters={filters} onChange={patchFilters} />
          <ConversationList
            conversations={conversations ?? []}
            selectedId={selectedId}
            onSelect={(id) => { setSelectedId(id); setRightPanel(null); }}
            isLoading={loadingList}
          />
        </div>

        {/* ── Main content ── */}
        <div className="flex-1 flex flex-col min-w-0 bg-gray-50">
          <ConversationThread
            conversation={activeConversation ?? null}
            isLoading={loadingConv}
          />
          <ReplyComposer conversationId={selectedId} />
        </div>

        {/* ── Right panels ── */}
        {rightPanel === "drafts" && (
          <div className="w-80 border-l border-gray-200 bg-white flex-shrink-0">
            <DraftsSidebar
              onSelectConversation={(id) => { setSelectedId(id); setRightPanel(null); }}
            />
          </div>
        )}
        {rightPanel === "use-cases" && (
          <div className="w-80 border-l border-gray-200 bg-white flex-shrink-0">
            <UseCasesPanel />
          </div>
        )}
      </div>
    </div>
  );
}

function NavIcon({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      className={clsx(
        "w-10 h-10 rounded-xl flex items-center justify-center transition-colors",
        active
          ? "bg-linkedin-50 text-linkedin-600"
          : "text-gray-400 hover:bg-gray-50 hover:text-gray-700"
      )}
    >
      {icon}
    </button>
  );
}
