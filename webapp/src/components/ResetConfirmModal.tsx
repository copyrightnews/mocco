export function ResetConfirmModal({ open, onCancel, onConfirm }: { open: boolean; onCancel: () => void; onConfirm: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onCancel}>
      <div className="bg-tg-bg rounded-2xl p-4 w-72 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold text-tg-text mb-1">Clear conversation?</h3>
        <p className="text-sm text-tg-hint mb-4">This will erase the current chat history.</p>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="px-3 py-1.5 rounded-lg text-sm text-tg-hint">Cancel</button>
          <button onClick={onConfirm} className="px-3 py-1.5 rounded-lg text-sm bg-tg-button text-tg-button-text">Reset</button>
        </div>
      </div>
    </div>
  );
}
