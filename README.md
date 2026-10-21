# UAQ DED Smart Services — Ibdaa License

A demonstration web application for the Umm Al Quwain Department of Economic Development (DED) Ibdaa home-business license workflow. It combines a React interface with a FastAPI backend for AI-assisted document analysis and business activity recommendations.

> **Prototype notice:** This project is not connected to DED systems, a payment gateway, or an identity provider. Applicant details shown in the UI are sample values. Submissions are not saved; the API validates the request and returns a generated reference number. AI document checks are not authenticity checks, and extracted information should be reviewed before use.

## Features

- Service catalogue and guided Ibdaa License application flow.
- Upload a social media page screenshot and/or site plan as an image or PDF.
- Extract business, contact, and location details with a configurable vision-language model; review field confidence and edit extracted values.
- Suggest a business activity from the bundled activity catalogue using the trade name and optional context.
- Review fees, accept terms, submit the application, and view a confirmation reference.
- Configure the backend to use Ollama, Groq, Google Gemini, OpenAI, or an OpenAI-compatible endpoint.

## Application flow

1. `/services` — browse services.
2. `/services/ibdaa-license` — review the service information and applicant details, upload documents, and start AI analysis.
3. `/services/ibdaa-license/review` — review and edit extracted information and activity recommendations.
4. `/services/ibdaa-license/validate` — check the trade name and activity, review the displayed fees, accept the terms, and submit.
5. `/services/ibdaa-license/success` — view the submission confirmation.
6. `/settings` — view the active AI provider and test its connection.

The frontend uses in-memory application state. Refreshing the page may clear the current application.

## Requirements

- Python 3.10 or newer
- Node.js and npm (use a Node version supported by the Vite version in `frontend/package.json`)
- One vision-capable AI provider. Ollama can run locally; the other providers require their own API credentials.

## Run locally

Run the backend and frontend in separate terminals.

### 1. Configure and start the backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and configure the provider you intend to use (see [AI provider configuration](#ai-provider-configuration)). With the defaults, install and start [Ollama](https://ollama.com/), then download the configured model:

```powershell
ollama pull qwen2.5vl:7b
```

Start the API from the `backend` directory:

```powershell
uvicorn main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive API documentation is at `http://localhost:8000/docs`.

### 2. Start the frontend

In a second terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to `http://localhost:8000`; if you change the backend address or port, update `frontend/vite.config.js` as well.

## AI provider configuration

Provider settings are read by the backend from `backend/.env`. `LLM_PROVIDER` accepts `ollama`, `groq`, `gemini`, `openai`, or `openai_compatible`. The backend must be restarted after changing environment variables.

| Provider | Required settings |
| --- | --- |
| Ollama (default) | `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434`, `OLLAMA_MODEL=qwen2.5vl:7b` |
| Groq | `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and optionally `GROQ_MODEL` |
| Google Gemini | `LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, and optionally `GEMINI_MODEL` |
| OpenAI | `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally `OPENAI_BASE_URL` and `OPENAI_MODEL` |
| OpenAI-compatible API | `LLM_PROVIDER=openai_compatible`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, and any API key required by that service in `OPENAI_API_KEY` |

Choose a model that supports image input for document analysis. Use Ollama when documents should be processed locally; cloud providers may receive uploaded document images for analysis. Keep API keys private and do not commit `.env`.

To allow a frontend hosted at a different origin, set `CORS_ORIGINS` to its origin (or a comma-separated list of allowed origins), for example:

```dotenv
CORS_ORIGINS=http://localhost:5173
```

## API

All application routes are prefixed with `/api`.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Check that the backend is running. |
| `POST` | `/api/documents/analyze` | Analyze uploaded documents and return extracted fields and document relevance checks. |
| `POST` | `/api/activity/suggest` | Recommend an activity for a trade name and optional context. |
| `GET` | `/api/activity/categories` | Return the bundled activity categories and representative activities. |
| `POST` | `/api/license/submit` | Validate a submission request and return a generated confirmation reference. |
| `GET` | `/api/llm/providers` | Return the active provider and non-secret configuration details. |
| `GET` | `/api/llm/health` | Check connectivity to the active AI provider. |

### Analyze documents

Send multipart form data. At least one file is required. `screenshot` and `site_plan` accept image files or PDFs; for a site plan, only the first PDF page is analyzed. `social_media_url` is optional.

```sh
curl -X POST http://localhost:8000/api/documents/analyze \
  -F "screenshot=@profile.png" \
  -F "site_plan=@site-plan.pdf" \
  -F "social_media_url=https://www.instagram.com/example"
```

A successful response includes `success`, `extraction`, `social_media_url`, and `document_validation`. Extracted fields include trade and activity names, social account, license contact details, and site location/address/coordinates/Makani number. Each extracted field includes a value, a confidence score, and a review status. If an upload does not appear relevant to its expected document type, `success` is `false` and `document_validation.issues` explains the problem. A `400` response is returned when no file is uploaded.

### Suggest a business activity

```sh
curl -X POST http://localhost:8000/api/activity/suggest \
  -H "Content-Type: application/json" \
  -d '{"trade_name":"Example Studio","trade_name_arabic":"","context":"Online photography services"}'
```

`trade_name` is required; `trade_name_arabic` and `context` are optional.

### Submit an application

All fields below are required by the submission model. `terms_accepted` must be `true`.

```sh
curl -X POST http://localhost:8000/api/license/submit \
  -H "Content-Type: application/json" \
  -d '{
    "email":"applicant@example.com",
    "mobile":"+971500000000",
    "emirates_id":"784-0000-0000000-0",
    "trade_name":"Example Studio",
    "main_activity":"Photography services",
    "activity_sections":["Photography"],
    "social_media_account":"@example",
    "license_mobile_number":"+971500000000",
    "license_email":"applicant@example.com",
    "social_media_url":"https://www.instagram.com/example",
    "location":"Umm Al Quwain",
    "address":"Example address",
    "makani_number":"",
    "terms_accepted":true
  }'
```

The prototype returns a generated `reference_number` and `under_review` status; it does not persist the application or initiate payment.

## Development

From `frontend/`:

```powershell
npm run lint
npm run build
```

The backend dependency list is in `backend/requirements.txt`. The repository does not currently define a backend test command.

## Project structure

```text
backend/
  data/                 Bundled business activity catalogue
  models/               Request and extraction models
  routers/              FastAPI routes
  services/              Document processing, extraction, activity matching, and LLM providers
  main.py               FastAPI application and router setup
  config.py             Environment-based settings
  requirements.txt      Python dependencies
frontend/
  src/
    components/         Shared layout and UI components
    context/            In-memory application state
    pages/              Application workflow and settings screens
    services/api.js     Backend API client
  vite.config.js        Vite development server and API proxy
```

## License

No project license is currently specified in this repository.
