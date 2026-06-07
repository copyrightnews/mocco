export function AccessDenied() {
  const close = () => {
    const wa = typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
    if (wa) wa.close();
    else window.close();
  };

  return (
    <div
      className="flex flex-col items-center justify-center h-full px-6 text-center"
      style={{
        backgroundColor: "var(--tg-bg, #ffffff)",
        color: "var(--tg-text, #0f172a)",
        paddingTop: "env(safe-area-inset-top)",
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
    >
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center mb-6"
        style={{
          backgroundColor: "var(--tg-secondary-bg, #f4f4f5)",
        }}
      >
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="4" y="11" width="16" height="10" rx="2" stroke="currentColor" strokeWidth="2" />
          <path
            d="M8 11V7a4 4 0 0 1 8 0v4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <circle cx="12" cy="16" r="1.5" fill="currentColor" />
        </svg>
      </div>
      <h1 className="text-[26px] font-bold tracking-tight mb-2">Access denied</h1>
      <p
        className="text-[15px] max-w-[320px] mb-8 leading-relaxed"
        style={{ color: "var(--tg-hint, #6b7280)" }}
      >
        This bot is private. If you think this is a mistake, contact the bot owner.
      </p>
      <button
        onClick={close}
        className="px-6 py-3 rounded-full text-[15px] font-medium active:scale-[0.98] transition-transform"
        style={{
          backgroundColor: "var(--tg-button, #2563eb)",
          color: "var(--tg-button-text, #ffffff)",
        }}
      >
        Close
      </button>
    </div>
  );
}
