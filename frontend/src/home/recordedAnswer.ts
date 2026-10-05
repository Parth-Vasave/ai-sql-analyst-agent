import type { AgentResult } from '../api/types'

/**
 * A real POST /api/query response, recorded on 2026-10-05 from a local instance on the bundled
 * OWID demo database (openai/gpt-oss-120b). Kept verbatim except the request id, which only means
 * something in that server's logs. The homepage replays it; nothing here is edited for effect.
 */
export const RECORDED_AT = '2026-10-05'

export const RECORDED_ANSWER: AgentResult = {
  "status": "success",
  "question": "Which 5 countries emitted the most CO2 in 2023?",
  "resolved_question": null,
  "answer": "The five highest‑emitting countries in 2023 were China (12,172 Mt CO₂), the United States (4,918 Mt CO₂), India (3,063 Mt CO₂), Russia (1,733 Mt CO₂) and Japan (987 Mt CO₂).",
  "answer_source": "llm",
  "clarification_question": null,
  "explanation": "Ranks countries by total CO2 emissions in 2023 and returns the top five.",
  "plan": {
    "intent": "ranking",
    "tables": [
      "public.co2_emissions",
      "public.countries"
    ],
    "metrics": [
      "co2"
    ],
    "filters": [
      "year = 2023",
      "entity_type = 'country'",
      "co2 IS NOT NULL"
    ],
    "group_by": [],
    "order_by": "co2 DESC",
    "limit": 5,
    "assumptions": [
      "Use the production-based CO2 column (co2) for total emissions",
      "Only entities with entity_type='country' are considered"
    ]
  },
  "sql": "SELECT c.name AS country_name, e.co2 AS co2_mt FROM public.co2_emissions AS e JOIN public.countries AS c ON e.country_id = c.id WHERE e.year = 2023 AND c.entity_type = 'country' AND e.co2 IS NOT NULL ORDER BY e.co2 DESC LIMIT 5",
  "columns": [
    "country_name",
    "co2_mt"
  ],
  "rows": [
    [
      "China",
      12172.009
    ],
    [
      "United States",
      4918.407
    ],
    [
      "India",
      3062.756
    ],
    [
      "Russia",
      1733.135
    ],
    [
      "Japan",
      986.91
    ]
  ],
  "column_units": {
    "co2_mt": "Mt"
  },
  "chart_suggestion": "bar",
  "chart": {
    "type": "bar",
    "x": "country_name",
    "y": [
      "co2_mt"
    ],
    "series": null,
    "label": null,
    "orientation": "horizontal",
    "reason": "co2_mt compared across country_name"
  },
  "checks": [],
  "error": null,
  "trace": [
    {
      "step": "question_received",
      "status": "success",
      "duration_ms": 0,
      "detail": {
        "question_length": 47,
        "history_turns": 0
      }
    },
    {
      "step": "schema_retrieval",
      "status": "success",
      "duration_ms": 100,
      "detail": {
        "tables": [
          "public.co2_emissions",
          "public.countries",
          "public.country_indicators",
          "public.ghg_emissions"
        ]
      }
    },
    {
      "step": "sql_generation",
      "status": "success",
      "duration_ms": 1625,
      "detail": {
        "attempt": 1,
        "model": "openai/gpt-oss-120b",
        "prompt_version": "sql-generator/3",
        "prompt_tokens": 3032,
        "completion_tokens": 433,
        "provider_attempts": 1,
        "intent": "ranking"
      }
    },
    {
      "step": "sql_validation",
      "status": "success",
      "duration_ms": 10,
      "detail": {
        "attempt": 1,
        "tables": [
          "public.co2_emissions",
          "public.countries"
        ],
        "limit": 5,
        "limit_action": "kept",
        "plan_warnings": []
      }
    },
    {
      "step": "query_execution",
      "status": "success",
      "duration_ms": 21,
      "detail": {
        "attempt": 1,
        "rows": 5,
        "truncated": false
      }
    },
    {
      "step": "result_validation",
      "status": "success",
      "duration_ms": 0,
      "detail": {
        "attempt": 1,
        "checks": []
      }
    },
    {
      "step": "answer_generation",
      "status": "success",
      "duration_ms": 985,
      "detail": {
        "source": "llm",
        "model": "openai/gpt-oss-120b",
        "prompt_version": "answer/2",
        "prompt_tokens": 436,
        "completion_tokens": 222,
        "provider_attempts": 1
      }
    },
    {
      "step": "chart_selection",
      "status": "success",
      "duration_ms": 0,
      "detail": {
        "type": "bar",
        "reason": "co2_mt compared across country_name"
      }
    },
    {
      "step": "completed",
      "status": "success",
      "duration_ms": 0,
      "detail": {
        "retries": 0
      }
    }
  ],
  "metadata": {
    "database_id": "default",
    "dialect": "postgres",
    "model": "openai/gpt-oss-120b",
    "prompt_version": "sql-generator/3",
    "tables_used": [
      "public.co2_emissions",
      "public.countries"
    ],
    "execution_time_ms": 21,
    "row_count": 5,
    "truncated": false,
    "retry_count": 0,
    "request_id": null
  }
}
