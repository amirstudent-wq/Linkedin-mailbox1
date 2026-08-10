"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Edit2, Check, X, Loader2, Wand2 } from "lucide-react";
import { getUseCases, createUseCase, updateUseCase, deleteUseCase } from "@/services/api";
import type { UseCase } from "@/types";

export default function UseCasesPanel() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["use-cases"],
    queryFn: () => getUseCases().then((r) => r.data),
  });
  const useCases: UseCase[] = data ?? [];

  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", description: "", system_prompt: "" });
  const [saving, setSaving] = useState(false);

  function startCreate() {
    setForm({ name: "", description: "", system_prompt: "" });
    setCreating(true);
    setEditingId(null);
  }

  function startEdit(uc: UseCase) {
    setForm({
      name: uc.name,
      description: uc.description,
      system_prompt: uc.system_prompt,
    });
    setEditingId(uc.id);
    setCreating(false);
  }

  async function handleSave() {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      if (creating) {
        await createUseCase({
          name: form.name,
          description: form.description,
          system_prompt: form.system_prompt || "auto",
        });
      } else if (editingId) {
        await updateUseCase(editingId, form);
      }
      qc.invalidateQueries({ queryKey: ["use-cases"] });
      setCreating(false);
      setEditingId(null);
    } catch {
      /* noop */
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this use case?")) return;
    await deleteUseCase(id);
    qc.invalidateQueries({ queryKey: ["use-cases"] });
  }

  async function handleToggle(uc: UseCase) {
    await updateUseCase(uc.id, { is_active: !uc.is_active });
    qc.invalidateQueries({ queryKey: ["use-cases"] });
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-900 text-sm">AI Use Cases</h2>
          <p className="text-xs text-gray-400">Reply personas for the daily scan</p>
        </div>
        <button
          onClick={startCreate}
          className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-linkedin-500 text-white text-xs font-medium hover:bg-linkedin-600 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" /> New
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Create/Edit form */}
        {(creating || editingId) && (
          <div className="bg-linkedin-50 border border-linkedin-200 rounded-xl p-4 space-y-3">
            <p className="text-xs font-semibold text-linkedin-700">
              {creating ? "New Use Case" : "Edit Use Case"}
            </p>
            <input
              type="text"
              placeholder="Name (e.g. Sales Outreach)"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-linkedin-500"
            />
            <textarea
              placeholder="Description (optional)"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={2}
              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-linkedin-500"
            />
            <div className="relative">
              <textarea
                placeholder={`System prompt — or type "auto" to have AI write one for you`}
                value={form.system_prompt}
                onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
                rows={4}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-linkedin-500"
              />
              <button
                onClick={() => setForm((f) => ({ ...f, system_prompt: "auto" }))}
                title="Use AI to generate system prompt"
                className="absolute right-2 bottom-2 p-1 rounded text-purple-500 hover:text-purple-700"
              >
                <Wand2 className="h-4 w-4" />
              </button>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => { setCreating(false); setEditingId(null); }}
                className="px-3 py-1.5 text-xs rounded-full border border-gray-300 text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !form.name.trim()}
                className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-full bg-linkedin-500 text-white hover:bg-linkedin-600 disabled:opacity-50"
              >
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                Save
              </button>
            </div>
          </div>
        )}

        {isLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-linkedin-400 animate-spin" />
          </div>
        )}

        {useCases.map((uc) => (
          <div
            key={uc.id}
            className={`border rounded-xl p-4 space-y-2 transition-colors ${
              uc.is_active ? "bg-white border-gray-200" : "bg-gray-50 border-gray-100 opacity-60"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleToggle(uc)}
                  className={`w-8 h-4 rounded-full relative transition-colors ${
                    uc.is_active ? "bg-linkedin-500" : "bg-gray-300"
                  }`}
                  title={uc.is_active ? "Disable" : "Enable"}
                >
                  <span
                    className={`absolute top-0.5 w-3 h-3 bg-white rounded-full shadow transition-transform ${
                      uc.is_active ? "left-4.5 translate-x-0" : "left-0.5"
                    }`}
                  />
                </button>
                <span className="text-sm font-semibold text-gray-900">{uc.name}</span>
              </div>
              <div className="flex gap-1">
                <button
                  onClick={() => startEdit(uc)}
                  className="p-1.5 text-gray-400 hover:text-linkedin-500 rounded"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => handleDelete(uc.id)}
                  className="p-1.5 text-gray-400 hover:text-red-500 rounded"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            {uc.description && (
              <p className="text-xs text-gray-500">{uc.description}</p>
            )}
            <details className="text-xs">
              <summary className="cursor-pointer text-gray-400 hover:text-gray-600">
                System prompt
              </summary>
              <pre className="mt-1 p-2 bg-gray-50 rounded text-xs text-gray-600 whitespace-pre-wrap font-mono leading-relaxed overflow-x-auto">
                {uc.system_prompt}
              </pre>
            </details>
          </div>
        ))}

        {!isLoading && useCases.length === 0 && !creating && (
          <div className="text-center py-8 text-sm text-gray-400">
            <p>No use cases yet.</p>
            <p className="mt-1">Create one to power the AI daily scan.</p>
          </div>
        )}
      </div>
    </div>
  );
}
