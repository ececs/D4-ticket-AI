/**
 * TicketForm — modal dialog for creating and editing tickets.
 *
 * Built with:
 *  - @radix-ui/react-dialog for the accessible modal
 *  - react-hook-form for form state management
 *  - zod for validation schema (title required, priority + assignee optional)
 *
 * Accepts an optional `ticket` prop for edit mode. In create mode, the form
 * submits to POST /tickets. In edit mode, it submits to PATCH /tickets/{id}.
 *
 * The `onSuccess` callback lets the parent refresh the ticket list.
 */

"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import api from "@/lib/api";
import { Ticket, TicketPriority, User } from "@/types";

const schema = z.object({
  title: z.string().min(1, "Title is required").max(200),
  description: z.string().optional(),
  priority: z.enum(["low", "medium", "high", "critical"]).default("medium"),
  assignee_id: z.string().uuid().nullable().optional(),
  client_url: z.string().url("Must be a valid URL").optional().or(z.literal("")),
  client_summary: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

const PRIORITIES: { value: TicketPriority; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

interface TicketFormProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (ticket: Ticket) => void;
  ticket?: Ticket; // If provided, form is in edit mode
  users: User[];
}

export function TicketForm({ open, onClose, onSuccess, ticket, users }: TicketFormProps) {
  const isEdit = !!ticket;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: ticket?.title ?? "",
      description: ticket?.description ?? "",
      priority: ticket?.priority ?? "medium",
      assignee_id: ticket?.assignee_id ?? null,
      client_url: ticket?.client_url ?? "",
      client_summary: ticket?.client_summary ?? "",
    },
  });

  // Reset form when ticket prop changes (edit mode switch)
  useEffect(() => {
    reset({
      title: ticket?.title ?? "",
      description: ticket?.description ?? "",
      priority: ticket?.priority ?? "medium",
      assignee_id: ticket?.assignee_id ?? null,
      client_url: ticket?.client_url ?? "",
      client_summary: ticket?.client_summary ?? "",
    });
  }, [ticket, reset]);

  const onSubmit = async (data: FormData) => {
    const payload = {
      ...data,
      assignee_id: data.assignee_id || null,
      client_url: data.client_url || null,
      client_summary: data.client_summary || null,
    };

    const response = isEdit
      ? await api.patch<Ticket>(`/tickets/${ticket.id}`, payload)
      : await api.post<Ticket>("/tickets", payload);

    onSuccess(response.data);
    onClose();
    reset();
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        {/* Backdrop */}
        <Dialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 animate-in fade-in" />

        {/* Panel */}
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 animate-in fade-in zoom-in-95">
          {/* Header */}
          <div className="flex items-center justify-between mb-5">
            <Dialog.Title className="text-lg font-semibold text-slate-800">
              {isEdit ? "Edit ticket" : "New ticket"}
            </Dialog.Title>
            <Dialog.Close asChild>
              <button className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors">
                <X className="w-4 h-4" />
              </button>
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Title <span className="text-red-500">*</span>
              </label>
              <input
                {...register("title")}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Short, descriptive title"
              />
              {errors.title && (
                <p className="text-xs text-red-600 mt-1">{errors.title.message}</p>
              )}
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Description
              </label>
              <textarea
                {...register("description")}
                rows={3}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                placeholder="Optional details, context or steps to reproduce..."
              />
            </div>

            {/* Client URL */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Client Website (for AI Analysis)
              </label>
              <input
                {...register("client_url")}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="https://example.com (landing page context)"
              />
              {errors.client_url && (
                <p className="text-xs text-red-600 mt-1">{errors.client_url.message}</p>
              )}
              <p className="text-[10px] text-slate-400 mt-1">
                Lanzará un escaneo automático para mejorar el diagnóstico de la IA.
              </p>
            </div>

            {/* Client Summary */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Resumen del Cliente / Contexto Negocio
              </label>
              <textarea
                {...register("client_summary")}
                rows={2}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                placeholder="Ej: Cliente de banca, usa GCP/K8s, muy técnico..."
              />
            </div>

            {/* Priority + Assignee row */}
            <div className="grid grid-cols-2 gap-3">
              {/* Priority */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Priority
                </label>
                <select
                  {...register("priority")}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {PRIORITIES.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>

              {/* Assignee */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Assignee
                </label>
                <select
                  {...register("assignee_id")}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Unassigned</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>{u.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {isSubmitting ? "Saving..." : isEdit ? "Save changes" : "Create ticket"}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
