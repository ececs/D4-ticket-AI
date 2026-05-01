/**
 * Board page — the main dashboard.
 *
 * This is a lightweight Server Component shell. All interactive content
 * (filters, drag & drop, dialogs) is delegated to the BoardContent client
 * component, which handles data fetching via useTickets and view toggling.
 */

import { BoardContent } from "@/components/board/BoardContent";

export default function BoardPage() {
  return <BoardContent />;
}
