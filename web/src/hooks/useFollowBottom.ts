import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

const FOLLOW_THRESHOLD_PX = 80;

const nearBottom = (el: HTMLElement): boolean => el.scrollTop + el.clientHeight >= el.scrollHeight - FOLLOW_THRESHOLD_PX;

/** Keeps a scroll box pinned to its newest entry, unless the user has scrolled up to read. */
export function useFollowBottom(ref: RefObject<HTMLElement | null>, items: readonly unknown[], footer: unknown): void {
  const follow = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let lastTop = el.scrollTop;
    const onScroll = () => {
      follow.current = nearBottom(el) || (follow.current && el.scrollTop >= lastTop);
      lastTop = el.scrollTop;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [ref]);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && follow.current && (items.length || footer)) el.scrollTop = el.scrollHeight;
  }, [ref, items, footer]);
}
