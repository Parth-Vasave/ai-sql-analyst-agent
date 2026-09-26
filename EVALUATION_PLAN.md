AI SQL Analyst — Evaluation Plan

Objective

Measure how reliably the AI SQL Analyst converts natural-language questions into correct database results.

The evaluation must use real, manually verified ground truth.

Never fabricate evaluation metrics.

⸻

Evaluation Categories

1. Simple Filtering

Questions involving:

* country / region / income group
* year or year range
* emission metric (total, per capita, by fuel, greenhouse gas)
* entity type (countries vs aggregates such as World or continents)

Target: 10 questions.

⸻

2. Aggregation

Questions involving:

* AVG
* MIN
* MAX
* COUNT
* SUM where appropriate

Target: 10 questions.

⸻

3. Ranking

Questions involving:

* top N
* bottom N
* highest
* lowest

Target: 10 questions.

⸻

4. Time-Series

Questions involving:

* yearly comparisons
* monthly comparisons
* date ranges
* price trends

Target: 10 questions.

⸻

5. Multi-Condition Queries

Questions combining:

* multiple filters
* aggregation
* grouping
* sorting

Target: 10 questions.

⸻

6. Joins

Questions requiring multiple database tables.

Target: 5 questions.

⸻

7. Ambiguous Questions

Questions where the system should request clarification.

Target: 5 questions.

⸻

8. No-Result Questions

Questions that should correctly return no matching records.

Target: 5 questions.

⸻

Metrics

Track:

* Total questions
* Correct answers
* Incorrect answers
* Answer accuracy
* SQL execution success
* Result correctness
* Empty-result accuracy
* Clarification accuracy
* Average latency
* Median latency
* Retry rate
* Timeout rate
* Safety violation rate

⸻

Result Evaluation

Do not require generated SQL to exactly match expected SQL.

Two different SQL queries may produce the same correct result.

Evaluate primarily using the final result.

Where practical, compare:

* returned rows
* returned columns
* values
* ordering when meaningful
* aggregation correctness

⸻

Safety Evaluation

Include adversarial queries attempting:

* DELETE
* UPDATE
* INSERT
* DROP
* ALTER
* TRUNCATE
* multiple statements
* unauthorized tables
* prompt injection
* secret extraction

Expected behavior is rejection or safe handling.

⸻

Evaluation Dataset Format

Use JSON.

Example:

{
  "id": "Q001",
  "category": "ranking",
  "question": "Which country had the highest CO2 emissions per capita in 2024?",
  "expected_behavior": "query",
  "ground_truth": {
    "description": "Verified result for the question"
  }
}

Do not add final accuracy numbers until the evaluation has actually been executed.

⸻

Evaluation History

Record evaluation runs here.

Example:

Date:
Commit:
Model:
Questions:
Accuracy:
Execution Success:
Safety:
Average Latency:
