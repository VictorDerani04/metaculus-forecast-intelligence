"use client";

import { useState } from "react";

import { logout } from "../lib/api";

type SignOutButtonProps = {
  onLogout?: () => Promise<void>;
  onSignedOut?: () => void;
};

export function SignOutButton({
  onLogout = logout,
  onSignedOut = () => window.location.assign("/login"),
}: SignOutButtonProps) {
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [error, setError] = useState("");

  async function handleSignOut() {
    if (isSigningOut) return;
    setError("");
    setIsSigningOut(true);
    try {
      await onLogout();
      onSignedOut();
    } catch {
      setError("Unable to sign out. Please try again.");
    } finally {
      setIsSigningOut(false);
    }
  }

  return <>
    {error && <p role="alert">{error}</p>}
    <button type="button" onClick={handleSignOut} disabled={isSigningOut}>
      {isSigningOut ? "Signing out…" : "Sign out"}
    </button>
  </>;
}
