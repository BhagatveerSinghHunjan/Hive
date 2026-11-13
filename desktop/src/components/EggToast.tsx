interface EggToastProps {
  message: string | null;
}

export function EggToast({ message }: EggToastProps) {
  if (!message) return null;
  return (
    <div className="egg-toast" role="status">
      <span className="egg-toast-mark" aria-hidden>
        ⬡
      </span>
      <span>{message}</span>
    </div>
  );
}
