/**
 * Root page — redirects to /board.
 *
 * The middleware handles the redirect to /login if the user is not authenticated.
 * If they are authenticated, this redirect takes them to the main dashboard.
 */

import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/board");
}
