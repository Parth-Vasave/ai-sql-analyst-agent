import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { AgentResult } from "./api/types";
import App from "./App";
import { event, success } from "./test/fixtures";

const DATABASES = [
  { id: "default", name: "OWID CO2 emissions (demo)", dialect: "postgresql", source: "config", sampling: "safe", status: "ready", issues: [] },
];
const PROFILE = {
  database_id: "default",
  dialect: "postgresql",
  tables: [
    {
      schema_name: "public",
      name: "countries",
      kind: "table",
      comment: "Countries and aggregates.",
      estimated_rows: 242,
      columns: [{ name: "name", type: "TEXT", nullable: false, comment: null, primary_key: false, sensitive: false }],
    },
  ],
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "X-Request-ID": "r1" } });
}

function mockApi(query: (body: { question: string }) => Response) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/api/databases")) return json(DATABASES);
    if (url.includes("/profile")) return json(PROFILE);
    if (url.endsWith("/api/query")) return query(JSON.parse(String(init?.body)));
    return json({ detail: "not found" }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function askQuestion(text: string) {
  const user = userEvent.setup();
  const box = await screen.findByLabelText("Question");
  await user.clear(box);
  await user.type(box, text);
  await user.click(screen.getByRole("button", { name: "Ask" }));
  return user;
}

afterEach(() => vi.unstubAllGlobals());

it("explains the plan before a question is asked", async () => {
  mockApi(() => json({}));
  render(<App />);
  expect(await screen.findByRole("option", { name: "OWID CO2 emissions (demo)" })).toBeInTheDocument();
  const plan = screen.getByRole("region", { name: "How a question is answered" });
  expect(within(plan).getByText("Validation")).toBeInTheDocument();
  expect(within(plan).getByText(/parsed, never trusted/)).toBeInTheDocument();
  expect(await screen.findByText(/What this database contains \(1 tables\)/)).toBeInTheDocument();
});

it("shows the answer, the table and the executed plan", async () => {
  const api = mockApi(() => json(success()));
  render(<App />);
  const user = await askQuestion("Which 3 countries emitted the most CO2 in 2023?");

  expect(await screen.findByText(/China emitted 12,172.009 Mt/)).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "4,918.407" })).toBeInTheDocument();
  expect(screen.getByText("'countries' excludes regions")).toBeInTheDocument();
  const plan = screen.getByRole("region", { name: /Plan for:/ });
  expect(within(plan).getByText("SQL repair")).toBeInTheDocument();
  expect(within(plan).getByText("Rejected: unknown column")).toBeInTheDocument();

  const body = JSON.parse(String(api.mock.calls.find(([u]) => String(u).endsWith("/api/query"))?.[1]?.body));
  expect(body).toEqual({ question: "Which 3 countries emitted the most CO2 in 2023?", database_id: "default" });

  // the SQL that ran is one click away, under Execution
  await user.click(within(plan).getByRole("button", { name: /Execution/ }));
  expect(within(plan).getByText(/as rewritten by the validator/)).toBeInTheDocument();
  expect(within(plan).getAllByText("SELECT").length).toBeGreaterThan(0);
});

it("explains a provider rate limit and how to recover", async () => {
  const limited: AgentResult = success({
    status: "error",
    answer: null,
    rows: [],
    columns: [],
    chart: null,
    sql: null,
    error: { category: "llm_error", message: "LLM provider returned HTTP 429 after 3 attempts", code: null },
    trace: [event("sql_generation", 3700, { attempt: 1, error: "LLM provider returned HTTP 429 after 3 attempts" }, "failed")],
  });
  mockApi(() => json(limited));
  render(<App />);
  await askQuestion("anything");
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("The language model is rate-limiting requests");
  expect(alert).toHaveTextContent("Wait a minute and ask again.");
});

it("asks back when the question is ambiguous", async () => {
  mockApi(() =>
    json(success({ status: "needs_clarification", clarification_question: "The trend of which measure, for which country?", rows: [], columns: [], chart: null, sql: null })),
  );
  render(<App />);
  const user = await askQuestion("Show me the trend.");
  expect(await screen.findByText("The trend of which measure, for which country?")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Edit the question" }));
  expect(screen.getByLabelText("Question")).toHaveFocus();
});

it("says plainly when no language model is configured", async () => {
  mockApi(() => json({ detail: "No LLM configured: set LLM_API_KEY." }, 503));
  render(<App />);
  await askQuestion("anything");
  expect(await screen.findByRole("alert")).toHaveTextContent("No language model is configured");
});

it("asks with Ctrl+Enter and ignores empty questions", async () => {
  const api = mockApi(() => json(success()));
  render(<App />);
  const user = userEvent.setup();
  const box = await screen.findByLabelText("Question");
  expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  await user.type(box, "Which 3 countries emitted the most CO2 in 2023?{Control>}{Enter}{/Control}");
  expect(await screen.findByText(/China emitted/)).toBeInTheDocument();
  expect(api.mock.calls.filter(([u]) => String(u).endsWith("/api/query"))).toHaveLength(1);
});
