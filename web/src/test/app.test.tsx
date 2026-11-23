import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { addDays } from "../lib/format";

const N = 120;
const dates = Array.from({ length: N }, (_, i) => addDays("2024-01-01", i));
const row = (method: string, wape: number, ref = false, auto = false) => ({
  method, wape, wape_ci95: [wape * 0.9, wape * 1.1], wape_days_1_7: wape, wape_days_8_28: wape * 1.1, bias: 0, coverage_80: 0.8, width_80: 0.3, coverage_90: 0.9, width_90: 0.4,
  win_rate_vs_reference: ref ? 0 : 0.9, gain_vs_reference: ref ? 0 : 0.02, gain_ci95: ref ? [0, 0] : [0.01, 0.03], is_auto: auto, is_reference: ref,
});
const verdict = { kind: "beats", method: "learning model", wape: 0.075, reference_wape: 0.098, win_rate: 0.96, gain: 0.023, gain_ci95: [0.02, 0.026], text: "x" };
const dataset = {
  id: "d1", filename: "Sample", is_sample: true, n_series: 2, n_days: 1941, first_date: "2011-01-29", last_date: "2016-05-22", has_events: true, analyzed: true,
  report: { layout: "long", rows: 10, n_series: 2, first_date: "2011-01-29", last_date: "2016-05-22", n_days: 1941, notes: [] },
  detection: { layout: "long", date: "date", value: "units", item: "store", item_columns: [], columns: [{ name: "date", examples: ["2011-01-29"], numeric_share: 0 }] },
  plan: { tier: "full", text: "Enough for the full comparison.", params: { years: 5.3 } },
};
const overview = {
  tier: "full", tier_text: "", settings: { horizon: 3, calendar: "none" }, dates: { first: dates[0], last: dates[N - 1], n_days: N }, replay: { n_dates: 20, first_scored: dates[40], step_days: 5 },
  series: [{ id: "A", total: 100, average_per_day: 1 }, { id: "B", total: 200, average_per_day: 2 }],
  methods: [{ name: "average of the same weekday, last 4 weeks", is_reference: true, is_auto: false }, { name: "learning model", is_reference: false, is_auto: false }, { name: "best method so far", is_reference: false, is_auto: true }],
  verdict, source: "test",
};
const stage = {
  item: "A", method: "best method so far", level: 0.8, horizon: 3, first_day: 1821, dates, actual: dates.map((_, i) => 100 + (i % 7) * 10),
  origins: [1850, 1855, 1860], forecast: [[100, 110, 120], [100, 110, 120], [100, 110, 120]], low: [[90, 100, 110], [90, 100, 110], [90, 100, 110]], high: [[110, 120, 130], [110, 120, 130], [110, 120, 130]], chosen: ["m", "m", "m"],
  ribbon: { hit: dates.map((_, i) => (i < 30 ? null : i % 5 !== 0)), expected: [], low: [], high: [] }, coverage_80: 0.8,
};
const next = {
  item: "A", method: "best method so far", method_in_use: "learning model", level: 0.8, last_day: dates[N - 1], history: { dates: dates.slice(-30), actual: dates.slice(-30).map(() => 100) },
  dates: [addDays(dates[N - 1], 1), addDays(dates[N - 1], 2)], forecast: [100, 105], low: [90, 95], high: [110, 115], range_note: null, total_next_7: 700,
  reasons: { day: 0, date: addDays(dates[N - 1], 1), forecast: 100, items: [{ reason: "a typical day at the recent level", units: 98 }, { reason: "usual weekly pattern", units: 4 }, { reason: "time of year", units: -2 }], note: "n" },
};
const scorecard = {
  reference: "average of the same weekday, last 4 weeks", best_method: "learning model", verdict, methods: [row("average of the same weekday, last 4 weeks", 0.098, true), row("learning model", 0.075), row("best method so far", 0.075, false, true)],
  per_series: [{ series: "A", reference_wape: 0.1, best_wape: 0.08, coverage_80: 0.8, gain: 0.02 }, { series: "B", reference_wape: 0.09, best_wape: 0.07, coverage_80: 0.79, gain: 0.02 }],
  window: { n_dates: 20, horizon: 3 }, limits: ["Replay dates overlap, so the intervals shown are indicative."],
};
const alerts = { level: 0.98, method: "best method so far", count: 1, items: [{ item: "A", date: dates[50], actual: 500, expected: 100, low: 80, high: 120, direction: "higher", deviation_pct: 4 }], note: "n" };
const dashboard = {
  method: "best method so far", method_in_use: "learning model", horizon: 3, last_day: dates[N - 1], totals: { last_7: 1000, previous_7: 980, next_7: 940 },
  trust: { coverage_80: 0.81, wape: 0.075, reference_wape: 0.098, n_dates: 20 }, verdict, unusual_30d: 1,
  items: [
    { id: "A", last_7: 400, next_7: 360, change: -0.1, unusual_30d: 1, reference_wape: 0.1, best_wape: 0.08, coverage_80: 0.8, average_per_day: 60 },
    { id: "B", last_7: 600, next_7: 580, change: -0.033, unusual_30d: 0, reference_wape: 0.09, best_wape: 0.07, coverage_80: 0.79, average_per_day: 85 },
  ],
  recent_unusual: [{ item: "A", date: dates[100], actual: 500, expected: 100, direction: "higher" }],
};

function mockFetch() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = String(url).replace(/\?.*$/, "");
    const body = path.endsWith("/overview") ? overview : path.endsWith("/stage") ? stage : path.endsWith("/next") ? next : path.endsWith("/total") ? { ...next, item: "All items" }
      : path.endsWith("/scorecard") ? scorecard : path.endsWith("/alerts") ? alerts : path.endsWith("/dashboard") ? dashboard : path.includes("/datasets/") ? dataset : {};
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
}

async function audit(container: HTMLElement) {
  const result = await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } }); // contrast is checked in a real browser: jsdom has no layout
  return result.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(", ")})`);
}

beforeEach(() => { window.location.hash = "#/"; sessionStorage.clear(); sessionStorage.setItem("hindsight.dataset", "d1"); localStorage.clear(); mockFetch(); });
afterEach(() => vi.unstubAllGlobals());

describe("dashboard", () => {
  it("opens straight on the dashboard with a plain-language headline, key numbers, and no upload box", async () => {
    const { container } = render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument();
    expect(await screen.findByText(/forecast to fall 6\.0%/i)).toBeInTheDocument();
    expect(screen.queryByText(/drop your sales file/i)).not.toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "A" })).toHaveAttribute("href", "#/items/A");
    expect(await audit(container)).toEqual([]);
  });
  it("has a main menu with every feature, the replay being one of them", async () => {
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: "Dashboard" });
    const nav = within(screen.getByRole("navigation", { name: /main/i }));
    expect(nav.getAllByRole("link").map((l) => l.textContent)).toEqual(["Dashboard", "Items", "Replay lab", "Scorecard", "Data"]);
  });
});

describe("other pages", () => {
  it("lists items, filters them, and opens an item with its forecast, reasons and unusual days", async () => {
    window.location.hash = "#/items";
    const { container } = render(<App />);
    await screen.findByRole("heading", { level: 1, name: "Items" });
    expect(await screen.findByRole("link", { name: "B" })).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox"), "b");
    expect(screen.queryByRole("link", { name: "A" })).not.toBeInTheDocument();
    expect(await audit(container)).toEqual([]);
    await userEvent.click(screen.getByRole("link", { name: "B" }));
    expect(await screen.findByRole("heading", { level: 1, name: "B" })).toBeInTheDocument();
    expect(await screen.findByText(/usual weekly pattern/i)).toBeInTheDocument();
    expect(await screen.findByText(/above the 98% range/i)).toBeInTheDocument();
  });

  it("replay lab shows the stage, reads out the day and lets you play", async () => {
    window.location.hash = "#/lab";
    const { container } = render(<App />);
    expect(await screen.findByTestId("stage")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /replay stage for A/i })).toBeInTheDocument();
    expect(screen.getByTestId("held")).toHaveTextContent("%");
    await userEvent.click(screen.getByRole("button", { name: "Play" }));
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(await audit(container)).toEqual([]);
  });

  it("moves the replay with the keyboard", async () => {
    window.location.hash = "#/lab";
    render(<App />);
    await screen.findByTestId("stage");
    const slider = screen.getByRole("slider", { name: /replay date/i });
    const before = Number((slider as HTMLInputElement).value);
    await userEvent.click(document.body);
    await userEvent.keyboard("{ArrowRight}");
    await waitFor(() => expect(Number((slider as HTMLInputElement).value)).toBe(before + 1));
  });

  it("scorecard states the verdict, lists every number and passes the audit", async () => {
    window.location.hash = "#/scorecard";
    const { container } = render(<App />);
    expect(await screen.findByRole("heading", { name: /a cleverer method is worth using/i })).toBeInTheDocument();
    expect(screen.getAllByRole("table")).toHaveLength(2); // all the numbers, and by item
    expect(await audit(container)).toEqual([]);
  });

  it("the data page is where files are loaded, and it passes the audit", async () => {
    window.location.hash = "#/data";
    const { container } = render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Data" })).toBeInTheDocument();
    expect(screen.getByText(/drop your sales file here/i)).toBeInTheDocument();
    expect(await audit(container)).toEqual([]);
  });
});

describe("failures", () => {
  it("tells you when the server is not running", async () => {
    sessionStorage.clear();
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network"); }));
    render(<App />);
    await waitFor(() => expect(screen.getByText(/cannot reach its server/i)).toBeInTheDocument()); // the message moves from the loading page to the Data page, so look again rather than hold one element
  });
});
