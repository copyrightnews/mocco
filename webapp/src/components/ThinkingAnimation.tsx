export function ThinkingAnimation() {
  return (
    <div className="flex items-center gap-3 py-1">
      <span className="relative inline-flex h-8 w-8 items-center justify-center">
        <span className="absolute inset-0 rounded-full bg-white/20 animate-think-ping" />
        <span className="absolute inset-1 rounded-full bg-white/10 animate-think-pulse" />
        <svg viewBox="0 0 32 32" fill="none" className="relative h-8 w-8 text-white/90">
          <circle cx="16" cy="16" r="14" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
          <path
            d="M10 20V12l6 4 6-4v8"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className="flex items-center gap-[1px] text-[14px] font-medium text-white/80">
        <span>Thinking</span>
        <span className="flex items-center gap-[1px]">
          <span className="h-1 w-1 rounded-full bg-white/60 animate-think-dot" style={{ animationDelay: "0ms" }} />
          <span className="h-1 w-1 rounded-full bg-white/60 animate-think-dot" style={{ animationDelay: "160ms" }} />
          <span className="h-1 w-1 rounded-full bg-white/60 animate-think-dot" style={{ animationDelay: "320ms" }} />
        </span>
      </span>
    </div>
  );
}
