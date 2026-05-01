/**
 * useUsers — fetches the user list for assignee selects.
 *
 * Used in TicketForm (new/edit ticket) and TicketTable filters.
 * The list is fetched once on mount and memoised — users rarely change
 * during a session, so there is no need for polling or re-fetch.
 */

"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { User } from "@/types";

export function useUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api
      .get<User[]>("/users")
      .then(({ data }) => setUsers(data))
      .catch(() => setUsers([]))
      .finally(() => setIsLoading(false));
  }, []);

  return { users, isLoading };
}
