/**
 * UserAvatar — robust user profile picture component.
 * 
 * Features:
 *  1. Image loading: uses the provided `src` (e.g. Google or DiceBear URL).
 *  2. Error handling: if the image fails to load (404, blocked, etc.), 
 *     it automatically falls back to a stylish initials-based avatar.
 *  3. Fallback: also falls back to initials if `src` is null or empty.
 */

"use client";

import { useState, useEffect } from "react";

interface UserAvatarProps {
  src?: string | null;
  name: string;
  size?: "xs" | "sm" | "md" | "lg";
  className?: string;
}

const SIZE_MAP = {
  xs: "w-5 h-5 text-[10px]",
  sm: "w-7 h-7 text-xs",
  md: "w-10 h-10 text-sm",
  lg: "w-16 h-16 text-xl",
};

export function UserAvatar({ src, name, size = "sm", className = "" }: UserAvatarProps) {
  const [hasError, setHasError] = useState(false);
  const initials = name ? name.charAt(0).toUpperCase() : "?";
  
  // Reset error state if src changes
  useEffect(() => {
    setHasError(false);
  }, [src]);

  const sizeClass = SIZE_MAP[size];

  if (!src || hasError) {
    return (
      <div 
        className={`${sizeClass} rounded-full bg-slate-100 flex items-center justify-center font-semibold text-slate-500 border border-slate-200 shrink-0 ${className}`}
        title={name}
      >
        {initials}
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={name}
      onError={() => setHasError(true)}
      className={`${sizeClass} rounded-full object-cover border border-slate-200 shrink-0 ${className}`}
    />
  );
}
