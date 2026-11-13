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
    "evidence": "tests/evidence"
  },
  "evidence": {
    "minCases": 5,
    "requireBoundary": true,
    "requireInvalidInput": true,
    "maxAgeHours": 720,
    "requireNewerThanSource": true
  }
}
