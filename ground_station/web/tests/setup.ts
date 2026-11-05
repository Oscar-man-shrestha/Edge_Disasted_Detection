import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());

// jsdom gaps used by Radix / sonner / cmdk
if (!window.matchMedia) {
  window.matchMedia = (q: string) => ({
    matches: false, media: q, onchange: null,
    addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false,
  }) as unknown as MediaQueryList;
}
class RO { observe() {} unobserve() {} disconnect() {} }
(globalThis as any).ResizeObserver ??= RO;
(Element.prototype as any).scrollIntoView ??= function () {};
(Element.prototype as any).hasPointerCapture ??= () => false;
