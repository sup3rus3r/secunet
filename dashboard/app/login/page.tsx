"use client";

import { signIn }    from "next-auth/react";
import { useState }  from "react";
import { useRouter } from "next/navigation";
import Link          from "next/link";
import SecuNetLogo   from "@/components/SecuNetLogo";

export default function LoginPage() {
  const [username,  setUsername]  = useState("");
  const [password,  setPassword]  = useState("");
  const [error,     setError]     = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    const result = await signIn("credentials", {
      username,
      password,
      redirect: false,
    });

    setIsLoading(false);

    if (result?.error) {
      setError("Invalid username or password");
    } else {
      router.push("/home");
      router.refresh();
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
              Sign In
            </h2>
            <p className="font-mono text-xs text-[#8B9AB5]">
              Authenticate to access the Tactical Operations Center
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
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full h-11 px-3 bg-[#080C14] border border-[#1E2D47] rounded text-[#E8EDF5] font-mono text-sm outline-none focus:border-[#00D4FF]/60 transition-colors placeholder:text-[#3A4A60]"
                placeholder="••••••••"
                required
                autoComplete="current-password"
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
              {isLoading ? "AUTHENTICATING..." : "SIGN IN"}
            </button>
          </form>

          <p className="text-center font-mono text-xs text-[#8B9AB5]">
            No account?{" "}
            <Link href="/register" className="text-[#00D4FF] hover:underline">
              Register
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
