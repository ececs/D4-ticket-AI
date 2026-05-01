/**
 * Utility functions used throughout the app.
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS class names with conflict resolution.
 *
 * This is the standard shadcn/ui helper. It combines clsx (conditional classes)
 * with tailwind-merge (deduplicate conflicting Tailwind utilities like p-2 + p-4).
 *
 * Example:
 *   cn("p-2 text-red-500", isPrimary && "text-blue-500")
 *   // Returns "p-2 text-blue-500" — tailwind-merge resolves the color conflict
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a file size in bytes to a human-readable string.
 * Example: 1536000 → "1.5 MB"
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Return a relative time string from an ISO timestamp.
 * Example: "2 hours ago", "just now", "3 days ago"
 */
export function timeAgo(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

/** Map ticket status to a display label. */
export const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  in_review: "In Review",
  closed: "Closed",
};

/** Map ticket priority to a display label and color class. */
export const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: "Low", color: "text-green-600 bg-green-50" },
  medium: { label: "Medium", color: "text-yellow-600 bg-yellow-50" },
  high: { label: "High", color: "text-orange-600 bg-orange-50" },
  critical: { label: "Critical", color: "text-red-600 bg-red-50" },
};
