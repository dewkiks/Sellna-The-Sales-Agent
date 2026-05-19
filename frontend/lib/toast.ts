
export interface ToastMessage {
  id: number;
  text: string;
  tone: "success" | "error";
}

type Listener = (toasts: ToastMessage[]) => void;

let toasts: ToastMessage[] = [];
const listeners = new Set<Listener>();
let seq = 0;

function emit() {
  for (const l of listeners) l([...toasts]);
}

function push(text: string, tone: "success" | "error") {
  const id = ++seq;
  toasts = [...toasts, { id, text, tone }];
  emit();
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    emit();
  }, 3200);
}

export const toast = {
  success: (text: string) => push(text, "success"),
  error: (text: string) => push(text, "error"),
};

export function subscribeToasts(listener: Listener): () => void {
  listeners.add(listener);
  listener([...toasts]);
  return () => {
    listeners.delete(listener);
  };
}
