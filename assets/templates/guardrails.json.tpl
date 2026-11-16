{
  "project": "{{PROJECT_NAME}}",
  "tier": "{{TIER}}",
  "maxDocLines": 120,
  "maxAgentsLines": 80,
  "parts": {{PARTS_JSON}},
  "paths": {
    "docs": "docs",
    "parts": "docs/parts",
    "contracts": "contracts",
    "contractsDoc": "docs/contracts",
    "flows": "docs/flows",
    "paramsSchema": "params/params.schema.json",
    "paramsValues": "params/params.json",
    "units": "tests/units.json",
    "evidence": "tests/evidence",
    "reports": "reports/gate"
  },
  "policy": {
    "requireTask": true,
    "taskFile": ".agent/current-task.json",
    "protected": [
      "params/params.json",
      "**/.env",
      "**/*.key",
      "**/*.pem"
    ],
    "exempt": [
      "docs/code-index.md",
      "docs/code-index.json",
      "tests/evidence/**",
      "reports/**",
      ".agent/**",
      "data/**"
    ]
  },
  "task": {
    "requireTask": true,
    "tasksDir": ".agent/tasks",
    "maxFiles": 15,
    "maxSymbols": 20,
    "rewriteDeletionRatio": 0.6,
    "rewriteMinSymbols": 3,
    "rewriteMaxOverlap": 0.6,
    "reviewSections": ["改了什么", "为什么改", "影响哪些模块", "如何验证"]
  },
  "design": {
    "required": "L",
    "files": [
      "docs/design/modules.md",
      "docs/design/flows.md",
      "docs/design/data.md",
      "docs/design/api.md"
    ]
  },
  "index": {
    "sources": ["{{INDEX_SOURCES}}"],
    "skip": ["**/__pycache__/**"],
    "out": "docs/code-index.md",
    "json": "docs/code-index.json",
    "minCommentRatio": 0.03,
    "minCommentRatioLines": 50
  },
  "evidence": {
    "minCases": 5,
    "requireBoundary": true,
    "requireInvalidInput": true,
    "maxAgeHours": 720,
    "requireNewerThanSource": true,
    "requireProvenance": true,
    "requireCurrentCommit": false
  }
}
