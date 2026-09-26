import { buildPlan, formatDuration, idlePlan, IDLE_ORDER } from "./planTree";
import { event, success } from "./test/fixtures";

describe("buildPlan", () => {
  it("puts the answer first and the steps newest first, like EXPLAIN output", () => {
    const nodes = buildPlan(success());
    expect(nodes.map((n) => n.name)).toEqual([
      "Answer",
      "Chart choice",
      "Answer text",
      "Result checks",
      "Execution",
      "Validation",
      "SQL repair",
      "Validation",
      "SQL generation",
      "Schema retrieval",
      "Question",
    ]);
  });

  it("gives every step its time and share of the total", () => {
    const nodes = buildPlan(success());
    const total = 0 + 120 + 2000 + 5 + 1500 + 6 + 20 + 2 + 900 + 1;
    expect(nodes[0]?.durationMs).toBe(total);
    const generation = nodes.find((n) => n.name === "SQL generation");
    expect(generation?.share).toBeCloseTo(2000 / total);
  });

  it("marks attempts only when there was a repair, and shows failures with their error", () => {
    const nodes = buildPlan(success());
    expect(nodes.find((n) => n.name === "SQL repair")?.attempt).toBe(2);
    const rejected = nodes.find((n) => n.status === "failed");
    expect(rejected?.summary).toBe("Rejected: unknown column");
    expect(rejected?.error).toBe("Column 'emissions' could not be resolved.");

    const single = success({ trace: [event("sql_generation", 10, { attempt: 1, model: "m" }), event("completed", 0)] });
    expect(buildPlan(single)[1]?.attempt).toBeNull();
  });

  it("summarizes steps in plain words", () => {
    const nodes = buildPlan(success());
    const summary = (name: string) => nodes.find((n) => n.name === name)?.summary;
    expect(summary("Answer")).toBe("3 rows");
    expect(summary("Execution")).toBe("3 rows");
    expect(summary("Validation")).toBe("2 tables, LIMIT 3");
    expect(summary("SQL generation")).toBe("gemini-test, ranking plan, 980 tokens");
    expect(summary("Result checks")).toBe("Nothing flagged");
    expect(summary("Answer text")).toBe("Written by the model; every number checked against the rows");
    expect(summary("Chart choice")).toBe("Bar chart");
  });

  it("explains a rejected model answer", () => {
    const result = success({
      trace: [event("answer_generation", 5, { source: "template", ungrounded_numbers: ["60"] }, "failed")],
    });
    expect(buildPlan(result)[1]?.summary).toBe("Model answer rejected (60 not in the rows); built from the rows");
  });

  it("reports an error result on the root", () => {
    const result = success({
      status: "error",
      rows: [],
      error: { category: "llm_error", message: "LLM provider returned HTTP 429 after 3 attempts", code: null },
      trace: [event("sql_generation", 3700, { attempt: 1, error: "LLM provider returned HTTP 429 after 3 attempts" }, "failed")],
    });
    const [root, generation] = buildPlan(result);
    expect(root?.status).toBe("failed");
    expect(root?.summary).toBe("Failed: the language model did not answer");
    expect(generation?.summary).toBe("Rate-limited by the model provider (HTTP 429)");
  });
});

describe("idlePlan", () => {
  it("describes every step before anything runs", () => {
    const nodes = idlePlan();
    expect(nodes.map((n) => n.step)).toEqual(IDLE_ORDER);
    expect(nodes.every((n) => n.status === "pending" && n.durationMs === null && n.summary.length > 20)).toBe(true);
  });
});

describe("formatDuration", () => {
  it.each([
    [null, ""],
    [0, "0 ms"],
    [129, "129 ms"],
    [2540, "2.5 s"],
    [16044, "16 s"],
  ])("%s -> %s", (ms, text) => {
    expect(formatDuration(ms)).toBe(text);
  });
});
