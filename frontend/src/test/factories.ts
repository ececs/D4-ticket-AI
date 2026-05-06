import { Notification, Ticket, User } from "@/types";

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: "user-1",
    email: "user@example.com",
    name: "User Example",
    avatar_url: null,
    created_at: "2026-05-01T10:00:00.000Z",
    ...overrides,
  };
}

export function makeTicket(overrides: Partial<Ticket> = {}): Ticket {
  const author = makeUser({ id: "author-1", email: "author@example.com", name: "Author" });
  return {
    id: "ticket-1",
    title: "Ticket title",
    description: "Ticket description",
    status: "open",
    priority: "medium",
    author_id: author.id,
    assignee_id: null,
    client_url: null,
    client_summary: null,
    created_at: "2026-05-01T10:00:00.000Z",
    updated_at: "2026-05-01T10:00:00.000Z",
    author,
    assignee: null,
    ...overrides,
  };
}

export function makeNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: "notification-1",
    user_id: "user-1",
    type: "assigned",
    ticket_id: "ticket-1",
    message: "Assigned",
    read: false,
    created_at: "2026-05-01T10:00:00.000Z",
    ...overrides,
  };
}
