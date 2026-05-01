/**
 * Ticket detail page — /tickets/[id]
 *
 * Server Component shell. The interactive content (comments, attachments,
 * inline editing) is all in the TicketDetail client component.
 *
 * We accept `params` as a Promise in Next.js 15 (the new async params API).
 */

import { TicketDetail } from "@/components/tickets/TicketDetail";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function TicketDetailPage({ params }: Props) {
  const { id } = await params;
  return <TicketDetail ticketId={id} />;
}
