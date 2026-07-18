## OCR Engine

This project uses [docTR](https://github.com/mindee/doctr) (Document Text Recognition), 
a deep-learning OCR library that handles both scanned and digital PDFs without any 
manual configuration.

It runs two neural networks in sequence:
- **Detection** — finds where text is on the page
- **Recognition** — reads what the text says in each detected region

Both networks use pre-trained weights, so no training or labelled data is required.

## Pydantic

Pydantic is used whenever data arrives from outside the code and cannot be trusted to be in the right format. It validates automatically and raises a clear error if something is wrong.

Common use cases:

| Situation | Why Pydantic helps |
|---|---|
| LLM structured output | Forces Gemini to return a specific JSON schema |
| API responses | Validates and parses JSON from external APIs |
| User input | Ensures form data has the right types and format |
| Data pipelines | Ensures data matches expected structure between steps |

In this project, Pydantic does two jobs: sends a JSON schema blueprint to Gemini via `response_schema`, and automatically parses Gemini's JSON response into typed Python objects via `response.parsed`.