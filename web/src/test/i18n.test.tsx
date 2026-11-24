import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { ar } from "../i18n/ar";
import { en } from "../i18n/en";
import { nounFor, plural, translate } from "../i18n";

const holes = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("translations", () => {
  it("has an Arabic string for every English one, with the same blanks to fill", () => {
    for (const [key, text] of Object.entries(en)) {
      expect(ar[key], `missing Arabic for ${key}`).toBeTruthy();
      if (!key.startsWith("unit.")) expect(holes(ar[key]), `blanks differ in ${key}`).toEqual(holes(text)); // Arabic one/two forms are words without a number
    }
  });
  it("has no Arabic string that English lacks, except extra plural forms", () => {
    const extra = Object.keys(ar).filter((k) => !(k in en));
    expect(extra.every((k) => /^unit\.\w+\.(zero|one|two|few|many|other)(@\w+)?$/.test(k))).toBe(true);
  });
  it("falls back to English and then to the key, never to an empty string", () => {
    expect(translate("ar", "no.such.key")).toBe("no.such.key");
    expect(translate("en", "state.retry")).toBe("Try again");
  });
  it("uses each language's own plural rules", () => {
    expect(plural("en", "unit.day", 1)).toBe("1 day");
    expect(plural("en", "unit.day", 3)).toBe("3 days");
    expect(plural("ar", "unit.day", 1)).toBe("يوم");
    expect(plural("ar", "unit.day", 2)).toBe("يومان");
    expect(plural("ar", "unit.day", 5)).toBe("5 أيام");
    expect(plural("ar", "unit.day", 15)).toBe("15 يومًا");
  });
});

describe("naming the things tracked", () => {
  it("has a store wording in both languages for every store key in English", () => {
    for (const key of Object.keys(en).filter((k) => k.includes("@"))) expect(ar[key], `missing Arabic for ${key}`).toBeTruthy();
  });
  it("picks the noun from the grouping column", () => {
    expect([nounFor("store"), nounFor("Branch name"), nounFor("الفرع"), nounFor("product"), nounFor(null)]).toEqual(["store", "store", "store", "item", "item"]);
    expect(translate("en", "items.title", undefined, "store")).toBe("Stores");
    expect(translate("en", "items.title")).toBe("Items");
    expect(translate("en", "next.col.day", undefined, "store")).toBe("Day"); // keys without a store wording are unchanged
    expect(plural("en", "unit.item", 3, "store")).toBe("3 stores");
    expect(plural("ar", "unit.item", 5, "store")).toBe("5 متاجر");
  });
});

describe("language switch", () => {
  beforeEach(() => {
    window.location.hash = "#/";
    sessionStorage.clear();
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 500 })));
  });

  it("flips the page to right-to-left Arabic and back, and remembers the choice", async () => {
    const { container, unmount } = render(<App />);
    expect(document.documentElement.dir).toBe("ltr");
    await userEvent.click(screen.getByRole("button", { name: /language/i }));
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    expect(await screen.findByRole("link", { name: /لوحة المتابعة/ })).toBeInTheDocument();
    const violations = (await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } })).violations;
    expect(violations.map((v) => v.id)).toEqual([]);
    unmount();
    render(<App />); // a new visit starts in the saved language
    expect(document.documentElement.dir).toBe("rtl");
    await userEvent.click(screen.getByRole("button", { name: /اللغة/ }));
    expect(document.documentElement.dir).toBe("ltr");
  });
});
