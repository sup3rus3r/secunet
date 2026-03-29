"use client";

import { useState }  from "react";
import { useRouter } from "next/navigation";
import Link          from "next/link";
import { encryptPayload } from "@/lib/crypto";
import SecuNetLogo   from "@/components/SecuNetLogo";

const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_API_URL ?? "http://localhost:8000";

export default function RegisterPage() {
  const [username,  setUsername]  = useState("");
  const [email,     setEmail]     = useState("");
  const [password,  setPassword]  = useState("");
  const [error,     setError]     = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const encryptedData = encryptPayload({ username, email, password });

      const res = await fetch(`${AUTH_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ encrypted: encryptedData }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Registration failed");
      }

      router.push("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#080C14] flex items-center justify-center px-4">
      {/* Scanline overlay */}
      <div className="fixed inset-0 pointer-events-none"
        style={{ backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,212,255,0.015) 2px, rgba(0,212,255,0.015) 4px)" }}
      />

      <div className="w-full max-w-sm relative z-10">
        {/* Logo */}
        <div className="flex justify-center mb-10">
          <SecuNetLogo size={48} />
        </div>

        {/* Card */}
        <div className="rounded-lg border border-[#1E2D47] bg-[#0D1321] p-8 space-y-6">
          <div className="space-y-1">
            <h2 className="font-mono font-bold text-[#E8EDF5] text-lg tracking-wide">
              Create Account
            </h2>
            <p className="font-mono text-xs text-[#8B9AB5]">
              Register an operator account to access SecuNet
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="font-mono text-xs text-[#8B9AB5] tracking-wider uppercase">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full h-11 px-3 bg-[#080C14] border border-[#1E2D47] rounded text-[#E8EDF5] font-mono text-sm outline-none focus:border-[#00D4FF]/60 transition-colors placeholder:text-[#3A4A60]"
                placeholder="username"
                required
                autoComplete="username"
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-xs text-[#8B9AB5] tracking-wider uppercase">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full h-11 px-3 bg-[#080C14] border border-[#1E2D47] rounded text-[#E8EDF5] font-mono text-sm outline-none focus:border-[#00D4FF]/60 transition-colors placeholder:text-[#3A4A60]"
                placeholder="operator@example.com"
                required
                autoComplete="email"
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-mono text-xs text-[#8B9AB5] tracking-wider uppercase">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full h-11 px-3 bg-[#080C14] border border-[#1E2D47] rounded text-[#E8EDF5] font-mono text-sm outline-none focus:border-[#00D4FF]/60 transition-colors placeholder:text-[#3A4A60]"
                placeholder="••••••••"
                required
                autoComplete="new-password"
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2 rounded bg-[#FF3B30]/10 border border-[#FF3B30]/30">
                <span className="w-1.5 h-1.5 rounded-full bg-[#FF3B30] shrink-0" />
                <p className="font-mono text-xs text-[#FF3B30]">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 bg-[#00D4FF] text-[#080C14] rounded font-mono font-bold text-sm hover:bg-[#00D4FF]/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? "CREATING ACCOUNT..." : "REGISTER"}
            </button>
          </form>

          <p className="text-center font-mono text-xs text-[#8B9AB5]">
            Already have an account?{" "}
            <Link href="/login" className="text-[#00D4FF] hover:underline">
              Sign in
            </Link>
          </p>
        </div>

        <p className="text-center font-mono text-[10px] text-[#3A4A60] mt-6">
          Authorised access only · All activity is logged
        </p>
      </div>
    </div>
  );
}
