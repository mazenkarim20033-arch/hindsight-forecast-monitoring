import { useEffect, useRef, useState } from "react";

/** Width of an element in pixels, kept current, so SVG text stays at its real size instead of being scaled. */
export function useWidth<T extends HTMLElement>(fallback = 900) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setWidth(Math.max(280, Math.round(el.getBoundingClientRect().width)) || fallback);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [fallback]);
  return [ref, width] as const;
}
