
type RefreshListener = () => void;

const listeners = new Set<RefreshListener>();

export function subscribeToAppRefresh(listener: RefreshListener) {
  listeners.add(listener);

  return () => {
    listeners.delete(listener);
  };
}

export function notifyAppDataChanged() {
  listeners.forEach((listener) => {
    listener();
  });
}