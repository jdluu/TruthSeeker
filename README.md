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

1. **Install uv (if not already installed)**

   This project uses `uv` for dependency management. Install it first:
   
   **On macOS/Linux:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   
   **On Windows:**
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   
   Or via pip:
   ```bash
   pip install uv
   ```
   
   **Verify installation:**
   ```bash
   uv --version
   ```

2. **Clone the repository**
   ```bash
   git clone https://github.com/jdluu/TruthSeeker.git
   cd TruthSeeker
   ```

3. **Install dependencies using uv**

   ```bash
   uv sync
   ```

   This will automatically create a virtual environment (`.venv`) if it doesn't exist and install all dependencies.

   **Note**: To add new dependencies, use `uv add <package>`. Dependencies are managed in `pyproject.toml` and locked in `uv.lock`.

4. **Activate the virtual environment**

   On Windows:
   ```bash
   .\.venv\Scripts\activate.ps1
   ```

   On macOS/Linux:
   ```bash
   source .venv/bin/activate
   ```

5. **Set up environment variables**
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
streamlit run main.py
```

Then open your browser. Enter a statement in the chat input and click **Fact Check**.

---

## 🛠 Developer Notes

**Code organization**

The project follows clean architecture principles:

```
Root level:
main.py                  # Main entry point (Streamlit UI)

src/truthseeker/         # All implementation code (clean architecture)
├── domain/              # Core business models (no external dependencies)
├── application/         # Business logic services
├── infrastructure/      # External system integrations
│   ├── http/           # HTTP clients
│   ├── search/         # Search implementations  
│   └── llm/            # LLM clients and parsers
├── interfaces/         # UI adapters
│   └── streamlit/      # Streamlit web UI
├── config/             # Configuration management
└── utils/              # Shared utilities
```

**Other details**

* 🔒 **Type safety**: Uses Pydantic models + `mypy`, `ruff`, `black` (see `pyproject.toml`).
* ⚡ **Caching**: BraveSearchClient includes an in-memory TTL cache; optional file persistence via `cache_file`.

---

## 📄 License

[MIT](./LICENSE)
