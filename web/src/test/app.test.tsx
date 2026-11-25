import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  report: { layout: "long", rows: 10, n_series: 2, first_date: "2011-01-29", last_date: "2016-05-22", n_days: 1941, notes: [],
    business: { columns: { price: "price", unit_cost: "cost", on_hand: "stock" }, values: { A: { price: 10, unit_cost: 6, on_hand: 50 }, B: { price: 10, unit_cost: 6, on_hand: 70, on_order: 5 } } } },
  detection: { layout: "long", date: "date", value: "units", item: "store", item_columns: [], item_cols: [], business: {}, duplicates: "sum", columns: [{ name: "date", examples: ["2011-01-29"], numeric_share: 0 }] },
  quality: [], adapter: null,
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
const planner = { item: "All items", method: "best method so far", days: 7, n_dates: 40, average_demand: 1000, note: "n", strategies: [{ key: "reference_guess", stockout_share: 0.5, lost_share: 0.02, leftover_share: 0.03, average_order: 990 }, { key: "model_guess", stockout_share: 0.49, lost_share: 0.013, leftover_share: 0.02, average_order: 1000 }, { key: "upper_80", stockout_share: 0.2, lost_share: 0.004, leftover_share: 0.07, average_order: 1060 }, { key: "upper_90", stockout_share: 0.1, lost_share: 0.002, leftover_share: 0.11, average_order: 1100 }] };
const effects = { window_weeks: 10, note: "n", effects: [{ kind: "egypt", name: "ramadan", n_days: 60, n_occurrences: 2, ratio: 1.18, ratio_low: 1.1, ratio_high: 1.26 }, { kind: "egypt", name: "eid_fitr", n_days: 6, n_occurrences: 2, ratio: 1.02, ratio_low: 0.8, ratio_high: 1.2 }, { kind: "event", name: "Thanksgiving", n_days: 5, n_occurrences: 5, ratio: 0.72, ratio_low: 0.7, ratio_high: 0.75 }] };
const strat = (order: number, target: number) => ({ service_target: target, order_up_to: order + 40, order, expected_leftover: 12.5, expected_shortage: 1.5, p_stockout: 1 - target, fill_rate: 0.98, investment: order * 6, expected_excess_cost: 4, expected_stockout_cost: 6, expected_cost: 10, expected_profit: 100 });
const inventory = {
  method: "best method so far", mode: "periodic_review", window_days: 10, cost_based: true, horizon: 28, missing: [], levels: { conservative: 0.78, balanced: 0.92, high_availability: 0.95 },
  assumptions: [{ field: "lead_time_days", value: 3, source: "user" }, { field: "review_days", value: 7, source: "default" }],
  items: ["A", "B"].map((id) => ({ item: id, forecast_demand: 400, on_hand: null, on_order: null, inventory_position: null, flags: ["stock_missing"], status: "ok", demand_range: [350, 450],
    by_strategy: { conservative: strat(380, 0.78), balanced: strat(430, 0.92), high_availability: strat(450, 0.95) } })),
  totals: { conservative: { order: 760, investment: 4560, expected_cost: 20, expected_leftover: 25, expected_shortage: 3 }, balanced: { order: 860, investment: 5160, expected_cost: 20, expected_leftover: 25, expected_shortage: 3 }, high_availability: { order: 900, investment: 5400, expected_cost: 20, expected_leftover: 25, expected_shortage: 3 } },
  calibration: [{ strategy: "balanced", target: 0.92, realized: 0.9, n_cases: 1410 }], notes: ["not_guarantee", "approximation", "sales_not_demand"],
};
const pair = (b: number, sc: number) => ({ baseline: b, scenario: sc, delta: sc - b, delta_pct: (sc - b) / b });
const scnTotals = Object.fromEntries(["conservative", "balanced", "high_availability"].map((k) => [k, Object.fromEntries(["order", "investment", "expected_leftover", "expected_shortage", "expected_cost"].map((m) => [m, pair(100, 120)]))]));
const scnKept = Object.fromEntries(["conservative", "balanced", "high_availability"].map((k) => [k, Object.fromEntries(["expected_leftover", "expected_shortage", "expected_cost"].map((m) => [m, pair(10, 18)]))]));
const scenarioRun = {
  baseline: inventory, notes: ["hypothetical", "not_validated", "flat_daily_demand", "effects_multiply", "baseline_calibration_only"],
  scenarios: [
    { name: "Demand up", spec: { demand_change_pct: 20 }, effects: [{ kind: "demand_change", pct: 20, demand_factor: 1.2 }], demand_factor: 1.2, window_days: 10, result: { ...inventory, calibration: [] },
      comparison: { totals: scnTotals, if_baseline_order: scnKept, items: ["A", "B"].map((id) => ({ item: id, status: "ok", by_strategy: { balanced: { order: pair(430, 516), p_stockout: pair(0.08, 0.1), if_baseline_order: { ...strat(430, 0.92), p_stockout: 0.3 } } } })) } },
    { name: "Price change", spec: { price_change_pct: 10 }, error: { message: "A price change needs a price elasticity from you.", code: "elasticity_missing", params: {} } },
  ],
};
const hsig = (key: string, value: number, status: string, watch: number, action: number) => ({ key, value, status, watch, action, recent: 0.09, earlier: 0.06, simple_rule: 0.08 });
const health = {
  method: "best method so far", as_of: dates[N - 1], horizon: 28,
  overall: { status: "watch", signals: [hsig("accuracy", 1.3, "watch", 1.25, 1.5), hsig("vs_simple", 0.95, "healthy", 1.1, 1.3), hsig("bias", 0.02, "healthy", 0.1, 0.2), hsig("coverage", 0.78, "healthy", 0.7, 0.55), hsig("drift", 0.4, "watch", 0.1, 0.25)], drift: { psi: 0.4, ks: 0.3, ks_p: 0.001, recent_mean: 110, earlier_mean: 100 } },
  counts: { healthy: 1, watch: 1, action: 0, unknown: 0 },
  items: ["A", "B"].map((id, i) => ({ item: id, status: i ? "watch" : "healthy", signals: [hsig("accuracy", 1.1, "healthy", 1.25, 1.5), hsig("vs_simple", 0.9, "healthy", 1.1, 1.3), hsig("bias", 0.01, "healthy", 0.1, 0.2), hsig("coverage", 0.8, "healthy", 0.7, 0.55), hsig("drift", 0.2, "watch", 0.1, 0.25)], drift: { psi: 0.2, ks: 0.2, ks_p: 0.01, recent_mean: 110, earlier_mean: 100 } })),
  timeline: Array.from({ length: 12 }, (_, i) => ({ origin: dates[40 + i], known: dates[68 + i], wape: 0.07, reference_wape: 0.08, rolling: 0.07 + i * 0.002, rolling_reference: 0.08 })),
  thresholds: {}, windows: { n_known: 100, n_recent: 8, n_earlier: 80, recent_from: dates[40], recent_to: dates[100] },
  notes: ["not_prediction", "conventions", "overlap", "drift_info_only", "sales_not_demand"],
};
const challenger = { method: "best method so far", verdict: "inconclusive", deployed: false, n_dates: 12, from: dates[40], to: dates[100], gain: 0.0004, gain_ci95: [-0.003, 0.0035], current: { wape: 0.074, bias: -0.007 }, challenger: { wape: 0.0737, bias: -0.004 }, config: { train_days: 365, refit_every: 14 }, notes: ["challenger_never_deployed", "challenger_small_sample", "challenger_overlap"] };
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
      : path.endsWith("/scorecard") ? scorecard : path.endsWith("/alerts") ? alerts : path.endsWith("/owner") ? { required: false, allowed: true } : path.endsWith("/dashboard") ? dashboard : path.endsWith("/planner") ? planner : path.endsWith("/effects") ? effects : path.endsWith("/inventory") ? inventory : path.endsWith("/scenarios") ? scenarioRun : path.endsWith("/health/challenger") ? challenger : path.endsWith("/health") ? health : path.includes("/datasets/") ? dataset : {};
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
    expect(nav.getAllByRole("link").map((l) => l.textContent)).toEqual(["Dashboard", "Items", "Orders", "Reliability", "Decision log", "Data", "Holiday effects", "Replay lab", "Scorecard"]) // the menu always says Items, even when the file groups by a store column;
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

describe("features beyond the forecast", () => {
  it("stock planner compares ordering rules in plain numbers", async () => {
    window.location.hash = "#/planner";
    const { container } = render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Stock planner" })).toBeInTheDocument();
    expect(await screen.findByText(/short in 49% of weeks/i)).toBeInTheDocument();
    expect(screen.getByText("Forecast, enough to cover 90% of past weeks")).toBeInTheDocument();
    expect(await audit(container)).toEqual([]);
  });

  it("holiday effects say when there is no clear effect instead of guessing", async () => {
    window.location.hash = "#/effects";
    const { container } = render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Holiday effects" })).toBeInTheDocument();
    expect(await screen.findByText("Ramadan")).toBeInTheDocument();
    expect(screen.getByText("Thanksgiving")).toBeInTheDocument();
    expect(screen.getByText("+18%")).toBeInTheDocument();
    expect(screen.getAllByText("No clear effect").length).toBe(1); // Eid al-Fitr: its range spans zero
    expect(screen.getByText(/US retail data/)).toBeInTheDocument(); // the sample warns it says nothing about Egypt
    expect(await audit(container)).toEqual([]);
  });

  it("hovering a chart reads out the measurements under the pointer", async () => {
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, left: 0, top: 0, right: 900, bottom: 400, width: 900, height: 400, toJSON: () => ({}) });
    render(<App />);
    const chart = await screen.findByRole("img", { name: /forecast for all items/i });
    expect(document.querySelector(".tooltip")).toBeNull();
    fireEvent.mouseMove(chart, { clientX: 300, clientY: 100 });
    await waitFor(() => expect(document.querySelector(".tooltip")?.textContent).toContain("Real sales"));
    fireEvent.mouseMove(chart, { clientX: 880, clientY: 100 }); // past today: the forecast and its range
    await waitFor(() => expect(document.querySelector(".tooltip")?.textContent).toMatch(/Forecast.*80% range/));
    fireEvent.mouseLeave(chart);
    await waitFor(() => expect(document.querySelector(".tooltip")).toBeNull());
    vi.restoreAllMocks();
  });
});
describe("loading your own data is for the owner only", () => {
  function keyedFetch(secret: string) {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const path = String(url).replace(/\?.*$/, "");
      const given = (init?.headers as Record<string, string> | undefined)?.["X-Owner-Key"];
      const body = path.endsWith("/owner") ? { required: true, allowed: given === secret } : path.endsWith("/overview") ? overview : path.endsWith("/dashboard") ? dashboard : path.endsWith("/total") ? { ...next, item: "All items" } : path.includes("/datasets/") ? dataset : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
  }

  it("shows no way to load a file, and no Load your data button, until the key is entered", async () => {
    keyedFetch("s3cret");
    window.location.hash = "#/data";
    render(<App />);
    expect(await screen.findByLabelText("Owner key")).toBeInTheDocument();
    expect(screen.queryByText(/drop your sales file/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Load your data" })).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Owner key"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Unlock" }));
    expect(await screen.findByText("That key was not accepted.")).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Owner key"));
    await userEvent.type(screen.getByLabelText("Owner key"), "s3cret");
    await userEvent.click(screen.getByRole("button", { name: "Unlock" }));
    expect(await screen.findByText(/drop your sales file here/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Load your data" })).toBeInTheDocument();
  });

  it("explains how to use your own data when this is not the owner's computer and no key exists", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(String(url).endsWith("/owner") ? { required: false, allowed: false } : String(url).endsWith("/overview") ? overview : String(url).includes("/datasets/") ? dataset : {}), { status: 200 })));
    window.location.hash = "#/data";
    render(<App />);
    expect(await screen.findByText(/limited to the owner/i)).toBeInTheDocument();
    expect(screen.queryByText(/drop your sales file/i)).not.toBeInTheDocument();
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

describe("inventory and decisions", () => {
  it("shows an answer at once from a labelled starting guess, treats blanks as unknown, and keeps every earlier number one click away", async () => {
    window.location.hash = "#/inventory";
    const { container } = render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "What should you order?" })).toBeInTheDocument();
    expect(await screen.findByText(/We started with a delivery time of 3 days and an order every 7 days/)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "What to order" })).toBeInTheDocument();
    expect(screen.getByText(/Order .* units across 2 items, enough for the next 10 days/)).toBeInTheDocument();
    const call = vi.mocked(fetch).mock.calls.find(([u]) => String(u).endsWith("/inventory"))!;
    const sent = JSON.parse(String((call[1] as RequestInit).body));
    expect(sent.lead_time_days).toBe(3);
    expect("price" in sent || "unit_cost" in sent || "holding_cost_per_day" in sent).toBe(false); // left empty means unknown, not zero
    await userEvent.clear(screen.getByLabelText("How many days does a delivery take?"));
    await userEvent.type(screen.getByLabelText("How many days does a delivery take?"), "5");
    expect(screen.queryByText(/We started with/)).toBeNull(); // once the person changes it, it is no longer a guess
    await userEvent.click(screen.getByLabelText("Play it safe on stock"));
    expect(screen.getByText(/half as costly/)).toBeInTheDocument();
    expect(screen.getAllByText("Stock not entered: the order is the full requirement.").length).toBe(2);
    expect(screen.getByText(/default, not from your data/)).toBeInTheDocument();
    expect(screen.getByText(/does not rule it out/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Did these cover levels hold on the past?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download the order list (CSV)" })).toBeInTheDocument();
    expect(await audit(container)).toEqual([]);
  });
  it("answers a what-if in one plain sentence from four buttons, sending only the change that was picked", async () => {
    window.location.hash = "#/inventory";
    render(<App />);
    expect(await screen.findByRole("heading", { name: "What if something changes?" })).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([u]) => String(u).endsWith("/scenarios"))).toBe(false); // nothing is worked out until a change is picked
    await userEvent.click(screen.getByRole("button", { name: "Sales go up 20%" }));
    expect(await screen.findByText(/To cover this, order 120 units instead of 100 \(\+20%\)\./)).toBeInTheDocument();
    expect(screen.getByText(/you would probably miss about 8 units of sales/)).toBeInTheDocument();
    const call = vi.mocked(fetch).mock.calls.filter(([u]) => String(u).endsWith("/scenarios")).at(-1)!;
    expect(JSON.parse(String((call[1] as RequestInit).body)).scenarios).toEqual([{ name: "Sales go up 20%", demand_change_pct: 20 }]);
    await userEvent.click(screen.getByRole("button", { name: "Sales go up 20%" })); // clicking it again puts it away
    expect(screen.queryByText(/To cover this/)).toBeNull();
    expect(screen.getByRole("button", { name: "Sales go up 20%" })).toHaveAttribute("aria-pressed", "false");
  });
  it("labels the example as an illustration and keeps the old backtest one click away", async () => {
    window.location.hash = "#/inventory";
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: "What should you order?" });
    await userEvent.click(screen.getByRole("button", { name: "Try example prices and stock" }));
    expect(screen.getByText(/an illustration, not your business/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Check how old ordering rules would have done" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Stock planner" })).toBeInTheDocument();
  });
});

describe("what-if scenarios", () => {
  it("starts from the baseline, sends only what was typed, and shows hypotheses, errors and the kept-order view", async () => {
    window.location.hash = "#/inventory";
    const { container } = render(<App />);
    await screen.findByRole("heading", { level: 1, name: "What should you order?" });
    await userEvent.click(screen.getByRole("button", { name: "Build your own what-if (advanced)" }));
    expect(screen.getByText(/none of these results is a forecast/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Demand up" }));
    expect(await screen.findByRole("heading", { name: "Baseline and scenarios side by side" })).toBeInTheDocument();
    const call = vi.mocked(fetch).mock.calls.filter(([u]) => String(u).endsWith("/scenarios")).at(-1)!;
    const sent = JSON.parse(String((call[1] as RequestInit).body));
    expect(sent.lead_time_days).toBe(3);
    expect(sent.scenarios).toEqual([{ name: "Demand up", demand_change_pct: 20 }]); // empty fields are not sent as zero
    expect(screen.getByText(/Demand over the whole period \+20\.0%\./)).toBeInTheDocument();
    expect(screen.getByText(/Combined effect on demand: × 1\.200/)).toBeInTheDocument();
    expect(screen.getByText("A price change needs a price elasticity from you.")).toBeInTheDocument(); // refused scenario shown beside the others
    expect(screen.getByRole("heading", { name: "If you keep the baseline order" })).toBeInTheDocument();
    expect(await audit(container)).toEqual([]);
  });
  it("keeps scenarios in this browser and can remove them all", async () => {
    window.location.hash = "#/inventory";
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: "What should you order?" });
    await userEvent.click(screen.getByRole("button", { name: "Build your own what-if (advanced)" }));
    await userEvent.click(screen.getByRole("button", { name: "Supplier late" }));
    expect(JSON.parse(localStorage.getItem("hindsight.scenarios.v1")!)[0].f.delay).toBe("5");
    await userEvent.click(screen.getByRole("button", { name: "Remove all scenarios" }));
    expect(JSON.parse(localStorage.getItem("hindsight.scenarios.v1")!)).toEqual([]);
    expect(screen.getByText(/No scenarios yet/)).toBeInTheDocument();
  });
});

describe("forecast health", () => {
  it("shows the status in words, the reasons, the drift as information only, and the checks table", async () => {
    window.location.hash = "#/health";
    const { container } = render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Forecast health" })).toBeInTheDocument();
    expect(await screen.findByText(/Something has moved, but not by much/)).toBeInTheDocument();
    expect(screen.getByText(/is ×1\.30 the earlier error/)).toBeInTheDocument();
    expect(screen.getAllByText(/information only/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/This does not change the status/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Rolling forecast error/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Item by item" })).toBeInTheDocument();
    expect(await audit(container)).toEqual([]);
  });
  it("runs a challenger test only when asked and says nothing was switched", async () => {
    window.location.hash = "#/health";
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: "Forecast health" });
    expect(vi.mocked(fetch).mock.calls.some(([u]) => String(u).endsWith("/health/challenger"))).toBe(false); // never run unprompted
    await userEvent.click(screen.getByRole("button", { name: "Run the test" }));
    expect(await screen.findByText(/No clear difference on 12 dates/)).toBeInTheDocument();
    expect(screen.getByText(/never switched on by Hindsight/)).toBeInTheDocument();
  });
});

describe("smart data onboarding", () => {
  const col = (name: string, share: number) => ({ name, examples: ["x"], numeric_share: share });
  const staged = {
    ...dataset, id: "u1", filename: "weekly.csv", is_sample: false, analyzed: false, has_events: false,
    report: { ...dataset.report, notes: [{ level: "warning", text: "2 rows are exact copies of another row.", code: "exact_duplicates", params: { n: 2 } }], business: { columns: { price: "price", on_hand: "stock" }, values: {} } },
    detection: { layout: "long", date: "date", value: "qty", item: "region", item_columns: [], item_cols: [], business: { price: "price", on_hand: "stock" }, duplicates: "sum",
      columns: [col("date", 0), col("region", 0), col("product", 0), col("qty", 1), col("price", 1), col("stock", 1)] },
    quality: [{ level: "warning", code: "stopped_selling", n_items: 1, items: ["Old milk"], params: { days: 28 } }],
    adapter: { name: "my-pos", description: "Friday export", applied: false },
  };
  function stub() {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const path = String(url).replace(/\?.*$/, "");
      const body = path.endsWith("/api/datasets") ? staged : path.endsWith("/mapping") ? (JSON.parse(String(init?.body)).adapter ? { ...staged, adapter: { ...staged.adapter, applied: true } } : staged) : path.endsWith("/owner") ? { required: false, allowed: true } : path.endsWith("/overview") ? overview : path.includes("/datasets/") ? dataset : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
  }
  it("shows what the file carries, asks how to name items, offers the saved adapter, and keeps quality findings as information", async () => {
    stub();
    window.location.hash = "#/data";
    const { container } = render(<App />);
    const input = await waitFor(() => { const el = container.querySelector('input[type="file"]'); expect(el).not.toBeNull(); return el as HTMLInputElement; });
    await userEvent.upload(input, new File(["date,region"], "weekly.csv", { type: "text/csv" }));
    expect(await screen.findByText("Things worth a look")).toBeInTheDocument();
    expect(screen.getByText(/Old milk/)).toBeInTheDocument();
    expect(screen.getByText(/These are checks, not changes/)).toBeInTheDocument();
    expect(screen.getByText(/selling price \(price\), stock on hand \(stock\)/)).toBeInTheDocument();
    expect(screen.getByText(/looks like the saved adapter/)).toBeInTheDocument();
    expect(screen.getByText("Rows that are exact copies")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("product"));
    const call = () => JSON.parse(String((vi.mocked(fetch).mock.calls.filter(([u]) => String(u).endsWith("/mapping")).at(-1)![1] as RequestInit).body));
    expect(call().item_cols).toEqual(["region", "product"]);
    expect(call().business).toEqual({ price: "price", on_hand: "stock" });
    await userEvent.click(screen.getByLabelText("Remove the extra copies (double entries)"));
    expect(call().duplicates).toBe("drop_exact");
    await userEvent.click(screen.getByRole("button", { name: "Use it" }));
    expect(call()).toEqual({ adapter: "my-pos" });
    expect(await audit(container)).toEqual([]);
  });
  it("fills stock from the file, and a price only when every item has the same one", async () => {
    window.location.hash = "#/inventory";
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: "What should you order?" });
    await userEvent.click(screen.getByRole("button", { name: "Use stock and prices from the file" }));
    expect(screen.getByText(/Stock was filled in for 2 items/)).toBeInTheDocument();
    expect(screen.getByLabelText("Selling price per unit")).toHaveValue("10");
    expect(screen.getByLabelText("A: On hand")).toHaveValue("50");
    expect(screen.getByText(/Holding cost is never in a sales file/)).toBeInTheDocument();
  });
});

describe("decision log", () => {
  const ev = { window: { from: "2016-05-23", to: "2016-06-01", days: 10 }, cost_known: true, best_in_hindsight: "high_availability", forecast_error: -0.1,
    totals: { actual: 900, forecast: 810, leftover: 0, shortage: 40, cost: 160 },
    by_strategy: { balanced: { leftover: 0, shortage: 40, cost: 160 }, high_availability: { leftover: 20, shortage: 0, cost: 20 } },
    items: [{ item: "A", actual: 900, forecast: 810, forecast_error: -0.1, chosen_order: 800, chosen: { level: 860, leftover: 0, shortage: 40, stocked_out: true, cost: 160 }, by_strategy: {} }] };
  const decision = {
    id: 1, ts: "2016-05-22T10:00:00+00:00", kind: "decision", ref: null, hash: "a".repeat(64), outcome: null,
    payload: { dataset: { filename: "weekly.csv", n_days: 100, as_of: "2016-05-22", as_of_index: 99, fingerprint: "f" }, method: "best method so far", mode: "periodic_review", window_days: 10, cost_based: true, cu: 4, co: 1, strategy: "balanced",
      scenario: null, demand_factor: 1, health: "watch", skipped: [], total_ordered: 800, note: "Ordered extra for the weekend",
      items: [{ item: "A", forecast_demand: 810, on_hand: 60, on_order: 0, position: 60, chosen_order: 800, overridden: true, by_strategy: { balanced: { order: 750, order_up_to: 810, p_stockout: 0.1, expected_cost: 5, expected_leftover: 2, expected_shortage: 1 } } }] },
  };
  let reviewStatus = "ready";
  let outcomeSaved = false;
  function stub() {
    outcomeSaved = false;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const path = String(url).replace(/\?.*$/, "");
      let body: unknown;
      if (path.endsWith("/audit/events")) body = { decisions: [outcomeSaved ? { ...decision, outcome: { id: 2, ts: "x", kind: "outcome", ref: 1, hash: "b".repeat(64), payload: { ...ev, decision: 1, dataset: { filename: "later.csv", last_day: "2016-06-01", n_days: 110 }, notes: [] } } } : decision], verify: { ok: true, n: outcomeSaved ? 2 : 1, bad_id: null, reason: null } };
      else if (path.endsWith("/audit/review")) body = { decisions: [{ decision_id: 1, status: reviewStatus, params: reviewStatus === "not_yet" ? { days: 4 } : {}, ...(reviewStatus === "ready" ? { preview: ev } : {}) }] };
      else if (path.endsWith("/audit/outcomes")) { outcomeSaved = true; body = { id: 2 }; }
      else if (path.endsWith("/audit/decisions")) body = { id: 5, kind: "decision" };
      else if (path.endsWith("/owner")) body = { required: false, allowed: true };
      else if (path.endsWith("/inventory")) body = inventory;
      else if (path.endsWith("/overview")) body = overview;
      else if (path.includes("/datasets/")) body = dataset;
      else body = {};
      void init;
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
  }
  it("lists decisions with the note and what was changed, says the log is intact, and previews an outcome without writing it", async () => {
    stub(); reviewStatus = "ready";
    window.location.hash = "#/audit";
    const { container } = render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Decision log" })).toBeInTheDocument();
    expect(await screen.findByText(/Intact: 1 records/)).toBeInTheDocument();
    expect(screen.getByText("Ordered extra for the weekend")).toBeInTheDocument();
    expect(screen.getByText(/1 items were ordered differently/)).toBeInTheDocument();
    expect(screen.getByText(/No outcome yet/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Check outcomes against the loaded file" }));
    expect(await screen.findByText(/Preview only. Nothing has been written/)).toBeInTheDocument();
    expect(screen.getByText(/the forecast was 10\.0% too low/)).toBeInTheDocument();
    expect(screen.getByText(/cheapest in hindsight/)).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([u]) => String(u).endsWith("/audit/outcomes"))).toBe(false);
    expect(await audit(container)).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: "Save this outcome" }));
    expect(await screen.findByText(/Outcome saved as record 2, from ‘later\.csv’/)).toBeInTheDocument();
  });
  it("explains why an outcome cannot be worked out yet", async () => {
    stub(); reviewStatus = "not_yet";
    window.location.hash = "#/audit";
    render(<App />);
    await screen.findByText(/Intact: 1 records/);
    await userEvent.click(screen.getByRole("button", { name: "Check outcomes against the loaded file" }));
    expect(await screen.findByText(/4 more days of sales are needed/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save this outcome" })).toBeNull();
  });
  it("records a decision from the inventory screen with the typed override and note, and the server does the arithmetic", async () => {
    stub();
    window.location.hash = "#/inventory";
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: "What should you order?" });
    await userEvent.click(await screen.findByRole("button", { name: "Record decision" }));
    await userEvent.type(screen.getByLabelText("A: Ordered"), "777");
    await userEvent.type(screen.getByLabelText("Why (optional)"), "Big weekend");
    await userEvent.click(screen.getByRole("button", { name: "Save to the log" }));
    expect(await screen.findByText(/Saved as decision 5/)).toBeInTheDocument();
    const call = vi.mocked(fetch).mock.calls.find(([u]) => String(u).endsWith("/audit/decisions"))!;
    const sent = JSON.parse(String((call[1] as RequestInit).body));
    expect(sent).toMatchObject({ lead_time_days: 3, strategy: "balanced", orders: { A: 777 }, note: "Big weekend" });
    expect(Object.keys(sent.orders)).toEqual(["A"]); // only what was typed
  });
});

describe("features work together", () => {
  it("keeps the menu short and puts the deep-dive pages under More", async () => {
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: "Dashboard" });
    const nav = within(screen.getByRole("navigation", { name: "Main" }));
    const more = nav.getByText("More").closest("details")!;
    expect(within(more).getAllByRole("link").map((l) => l.textContent)).toEqual(["Holiday effects", "Replay lab", "Scorecard"]);
    expect(nav.getAllByRole("link").length - within(more).getAllByRole("link").length).toBe(6);
  });
  it("shows the forecast's health on the dashboard, with the ways on to the details and to ordering", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Can the forecast be trusted?" })).toBeInTheDocument();
    expect(screen.getAllByText("Watch").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "See reliability details" })).toHaveAttribute("href", "#/health");
    expect(screen.getByRole("link", { name: "Plan orders" })).toHaveAttribute("href", "#/inventory");
  });
  it("warns on the order screen when the forecast behind the advice is on watch, and the health page leads back to the orders", async () => {
    window.location.hash = "#/inventory";
    render(<App />);
    expect(await screen.findByText(/The forecast behind this advice is on watch/)).toBeInTheDocument();
    window.location.hash = "#/health";
    expect(await screen.findByRole("link", { name: "Review your orders" })).toHaveAttribute("href", "#/inventory");
  });
});
