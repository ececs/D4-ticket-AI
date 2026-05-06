import { describe, expect, it } from "vitest";
import { integrateCreatedTicket } from "@/lib/ticketRealtime";
import { makeTicket } from "@/test/factories";

describe("integrateCreatedTicket", () => {
  it("updates an existing ticket in place without changing total", () => {
    const prev = [makeTicket({ id: "t-1", title: "Old title" })];
    const created = makeTicket({ id: "t-1", title: "New title" });

    const result = integrateCreatedTicket(prev, created, {});

    expect(result.needsRefetch).toBe(false);
    expect(result.totalDelta).toBe(0);
    expect(result.tickets[0].title).toBe("New title");
  });

  it("requests a refetch when a search filter is active", () => {
    const result = integrateCreatedTicket([], makeTicket(), { search: "login" });

    expect(result).toEqual({
      tickets: [],
      totalDelta: 0,
      needsRefetch: true,
    });
  });

  it("ignores a created ticket that does not match active non-search filters", () => {
    const prev = [makeTicket({ id: "existing" })];
    const created = makeTicket({ id: "created", priority: "high" });

    const result = integrateCreatedTicket(prev, created, { priority: "critical" });

    expect(result.needsRefetch).toBe(false);
    expect(result.totalDelta).toBe(0);
    expect(result.tickets).toEqual(prev);
  });

  it("requests a refetch when the user is on a page beyond the first", () => {
    const result = integrateCreatedTicket([], makeTicket(), { page: 2 });

    expect(result.needsRefetch).toBe(true);
    expect(result.totalDelta).toBe(0);
  });

  it("inserts and sorts by created_at descending by default", () => {
    const prev = [
      makeTicket({ id: "older", created_at: "2026-05-01T10:00:00.000Z" }),
      makeTicket({ id: "oldest", created_at: "2026-05-01T09:00:00.000Z" }),
    ];
    const created = makeTicket({ id: "newest", created_at: "2026-05-01T11:00:00.000Z" });

    const result = integrateCreatedTicket(prev, created, {});

    expect(result.needsRefetch).toBe(false);
    expect(result.totalDelta).toBe(1);
    expect(result.tickets.map((ticket) => ticket.id)).toEqual(["newest", "older", "oldest"]);
  });

  it("respects explicit sort order and page size limits", () => {
    const prev = [
      makeTicket({ id: "b", title: "Bravo" }),
      makeTicket({ id: "c", title: "Charlie" }),
    ];
    const created = makeTicket({ id: "a", title: "Alpha" });

    const result = integrateCreatedTicket(prev, created, {
      sort_by: "title",
      order: "asc",
      size: 2,
    });

    expect(result.needsRefetch).toBe(false);
    expect(result.totalDelta).toBe(1);
    expect(result.tickets.map((ticket) => ticket.title)).toEqual(["Alpha", "Bravo"]);
  });
});
