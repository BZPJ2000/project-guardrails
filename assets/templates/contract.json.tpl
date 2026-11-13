{
  "contract": "{{PART}}",
  "version": "1.0.0",
  "owner": "{{PART}}",
  "fields": [
    {
      "name": "inputId",
      "type": "string",
      "required": true,
      "writer": "human",
      "source": "params.input.id"
    }
  ],
  "errorCodes": ["E_CONTRACT_VIOLATION", "E_PARAM_MISSING", "E_OUT_OF_RANGE"]
}
