export function ResetConfirmModal({ open, onCancel, onConfirm }: { open: boolean; onCancel: () => void; onConfirm: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/40" onClick={onCancel}>
      <div
        className="absolute inset-x-0 bottom-0 bg-tg-secondary-bg rounded-t-[28px] p-5 pb-8 shadow-sheet"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-10 h-1 rounded-full bg-tg-hint/30 mx-auto mb-4" />
        <h3 className="text-[20px] font-bold text-tg-text text-center">Clear conversation?</h3>
        <p className="text-[14px] text-tg-hint text-center mt-2 mb-6">
          This will erase the current chat history.
        </p>
        <button
          onClick={onConfirm}
          className="w-full py-3.5 rounded-2xl bg-red-500 text-white font-semibold text-[15px] active:scale-[0.99] transition-transform"
        >
          Reset
        </button>
        <button
          onClick={onCancel}
          className="w-full py-3.5 rounded-2xl bg-tg-bg text-tg-text font-semibold text-[15px] mt-2 active:scale-[0.99] transition-transform"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
