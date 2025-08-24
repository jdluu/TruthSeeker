# AI-Powered Fact Checker

AI-Powered Fact Checker verifies short statements and claims by performing live web searches and using a language model to analyze the evidence.  
The primary interface is a **Streamlit** web application.

---

## ✨ Features
- 🔎 Real-time web search using Brave Search  
- 🤖 LLM-based analysis that returns a structured **verdict, explanation, context, and references**  
- 🖥️ Streamlit web UI with responsive layout and accessibility improvements  
- 🧩 Typed domain models (Pydantic) for robust validation and serialization  
- 🌐 BraveSearch client with retries, backoff, and simple TTL caching  
- 🛡️ Sanitization of HTML and user-provided input to reduce XSS risk  
- 📤 Export history to JSON or PDF  
- 🧪 CI linting and type-checking configuration included  

---

## 🚀 Quickstart (Developer)

1. **Clone the repository**
   ```bash
   git clone https://github.com/jdluu/TruthSeeker.git
   cd TruthSeeker
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the project root with your API keys:

   ```dotenv
   SYNTHETIC_API_KEY=your_synthetic_api_key
   BRAVE_API_KEY=your_brave_api_key
   LLM_MODEL=hf:meta-llama/Llama-3.3-70B-Instruct
   ```

---

## 🔧 Environment Variables

| Variable            | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `SYNTHETIC_API_KEY` | API key for Synthetic.new (preferred)                |
| `BRAVE_API_KEY`     | Brave Search API key                                 |
| `LLM_MODEL`         | Model identifier (optional; defaults can be used)    |

---

## 🏃 Running the Streamlit UI

Start the app:

```bash
streamlit run streamlit_ui.py
```

Then open your browser. Enter a statement in the chat input and click **Fact Check**.

---

## 🛠 Developer Notes

**Code organization**

```
streamlit_ui.py                 # Streamlit web interface (entrypoint)
src/truthseeker/models.py       # Pydantic models and enums
src/truthseeker/http.py         # Shared AsyncClient factory
src/truthseeker/search/client.py# BraveSearchClient (retries + caching)
src/truthseeker/llm/parser.py   # LLM JSON prompt + parser (validates models)
tools/web_search.py             # Compatibility wrapper for older callers
utils/                          # Helpers (client loader, sanitization, PDF export)
```

**Other details**

* 🔒 **Type safety**: Uses Pydantic models + `mypy`, `ruff`, `black` (see `pyproject.toml`).
* ⚡ **Caching**: BraveSearchClient includes an in-memory TTL cache; optional file persistence via `cache_file`.

---

## 📄 License

[MIT](./LICENSE)
