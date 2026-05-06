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

  it("filters out a new ticket that does not match the active assignee_id filter", () => {
    const prev = [makeTicket({ id: "existing", assignee_id: "user-1" })];
    const created = makeTicket({ id: "new", assignee_id: "user-2" });

    const result = integrateCreatedTicket(prev, created, { assignee_id: "user-1" });

    expect(result.needsRefetch).toBe(false);
    expect(result.totalDelta).toBe(0);
    expect(result.tickets).toEqual(prev);
  });

  it("sorts correctly when sort_by is priority descending", () => {
    const prev = [
      makeTicket({ id: "high", priority: "high" }),
      makeTicket({ id: "low", priority: "low" }),
    ];
    const created = makeTicket({ id: "critical", priority: "critical" });

    const result = integrateCreatedTicket(prev, created, { sort_by: "priority", order: "desc" });

    expect(result.needsRefetch).toBe(false);
    expect(result.totalDelta).toBe(1);
    expect(result.tickets.map((t) => t.id)).toEqual(["critical", "high", "low"]);
  });

  it("still increments totalDelta when the new ticket sorts outside the page size window", () => {
    const prev = [
      makeTicket({ id: "a", title: "Alpha" }),
      makeTicket({ id: "b", title: "Beta" }),
    ];
    // "Zeta" sorts last — after slicing to size 2 it won't be in the list
    const created = makeTicket({ id: "z", title: "Zeta" });

    const result = integrateCreatedTicket(prev, created, { sort_by: "title", order: "asc", size: 2 });

    expect(result.needsRefetch).toBe(false);
    expect(result.totalDelta).toBe(1); // backend total grew even though it's not visible
    expect(result.tickets).toHaveLength(2);
    expect(result.tickets.map((t) => t.id)).toEqual(["a", "b"]);
  });
});
