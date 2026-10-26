let lockCount = 0;
let originalOverflow = '';

/**
 * Reference-counted body scroll lock shared by the detail panel and modals.
 * Nested overlays must not restore the previous `overflow` out of order.
 */
export function lockBodyScroll(): () => void {
  if (lockCount === 0) {
    originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  lockCount += 1;

  let released = false;
  return () => {
    if (released) return;
    released = true;
    lockCount = Math.max(0, lockCount - 1);
    if (lockCount === 0) {
      document.body.style.overflow = originalOverflow;
    }
  };
}
