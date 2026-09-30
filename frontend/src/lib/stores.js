import { writable } from 'svelte/store';

export const currentUser = writable(null);
export const toastMessage = writable(null);

let toastTimeout = null;

export function showToast(message, type = 'info', duration = 4000) {
  if (toastTimeout) clearTimeout(toastTimeout);
  toastMessage.set({ message, type });
  toastTimeout = setTimeout(() => {
    toastMessage.set(null);
  }, duration);
}

export function hideToast() {
  if (toastTimeout) clearTimeout(toastTimeout);
  toastMessage.set(null);
}
