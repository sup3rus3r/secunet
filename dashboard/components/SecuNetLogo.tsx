import Image from "next/image";

interface SecuNetLogoProps {
  size?: number;          // icon size in px (default 32)
  wordmark?: boolean;     // show "SECUNET" text next to icon
  className?: string;
}

export default function SecuNetLogo({ size = 32, wordmark = true, className = "" }: SecuNetLogoProps) {
  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      <Image
        src="/logo.svg"
        alt="SecuNet"
        width={size}
        height={size}
        priority
      />
      {wordmark && (
        <span
          className="font-mono font-bold tracking-[0.2em] text-[#00D4FF]"
          style={{ fontSize: size * 0.44 }}
        >
          SECUNET
        </span>
      )}
    </div>
  );
}
