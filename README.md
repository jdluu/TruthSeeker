# AI-Powered Fact Checker

AI-Powered Fact Checker verifies short statements and claims by performing live web searches and using a language model to analyze the evidence.  
The application provides both a **Streamlit web interface** and a **command-line interface** (CLI) for fact-checking.

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red?logo=streamlit&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-2.10+-green?logo=pydantic&logoColor=white)
![DeepSeek](https://img.shields.io/badge/DeepSeek-API-purple?logo=openai&logoColor=white)
![uv](https://img.shields.io/badge/uv-Package%20Manager-orange?logo=python&logoColor=white)
![Rich](https://img.shields.io/badge/Rich-13.9+-brightgreen?logo=python&logoColor=white)

---

## ✨ Features
- 🔎 Real-time web search using Brave Search with function calling  
- 🤖 LLM-based analysis that returns a structured **verdict, explanation, context, and references**  
- 🖥️ Streamlit web UI with unified dark theme and modern interface  
- 💻 CLI interface with rich terminal formatting for automation and testing  
- 🧩 Typed domain models (Pydantic) for robust validation and serialization  
- 🌐 BraveSearch client with retries, backoff, and simple TTL caching  
- 🛡️ Sanitization of HTML and user-provided input to reduce XSS risk  
- 📤 Export history to JSON, PDF, or TXT format  
- 🧪 CI linting and type-checking configuration included  
- ⚡ Streaming support for real-time feedback during analysis  

---

## 🚀 Quickstart (Developer)

### Requirements

- **Python 3.13+** (The project uses Python 3.13.9 and requires `>=3.13`)
- **uv** (Fast Python package installer)

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

   This will automatically:
   - Install Python 3.13.9 (if not already installed via uv)
   - Create a virtual environment (`.venv`) 
   - Install all dependencies from `pyproject.toml`

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
   DEEPSEEK_API_KEY=your_deepseek_api_key
   BRAVE_API_KEY=your_brave_api_key
   ```

   **Getting API Keys:**
   - **DeepSeek API Key**: Get your API key from [DeepSeek Platform](https://platform.deepseek.com/api_keys)
   - **Brave API Key**: Get your API key from [Brave Search API](https://api.search.brave.com/)

---

## 🔧 Environment Variables

| Variable           | Description                                                           |
| ------------------ | --------------------------------------------------------------------- |
| `DEEPSEEK_API_KEY` | API key for DeepSeek (required) - [Get your key](https://platform.deepseek.com/api_keys) |
| `BRAVE_API_KEY`    | Brave Search API key (required)                                       |

**DeepSeek API**: The project uses [DeepSeek API](https://api-docs.deepseek.com/) which is OpenAI-compatible and supports function calling for dynamic web search. The model used is `deepseek-chat` (DeepSeek-V3.2-Exp non-thinking mode). The implementation leverages function calling to allow the LLM to request web searches dynamically during analysis.

---

## 🏃 Running the Application

### Streamlit UI (Web Interface)

Start the web app:

```bash
streamlit run main.py
```

Then open your browser. Enter a statement in the chat input and click **Fact Check**.

### CLI (Command Line Interface)

Test the application from the terminal:

```bash
# After installing with: uv sync
truthseeker "The capital of France is Paris"
```

**Alternative ways to run CLI:**
```bash
# Using the installed command
truthseeker "<statement>"

# Using Python module (if command not available)
python -m truthseeker.interfaces.cli.cli "<statement>"
```

**CLI Options:**

```bash
# Fact-check a statement
truthseeker "<statement>"

# Run a test fact-check
truthseeker --test

# Output results as JSON (useful for automation)
truthseeker --json "<statement>"

# Show help
truthseeker --help
```

**Example:**
```bash
truthseeker "Python was created in 1991"
```

The CLI is useful for:
- Automated testing
- CI/CD pipelines
- Scripting and automation
- Quick fact-checks without opening a browser
- AI agent testing and validation

---

## 🛠 Developer Notes

**Code organization**

The project follows clean architecture principles:

```
Root level:
main.py                  # Main entry point (Streamlit UI)

src/truthseeker/         # All implementation code (clean architecture)
├── domain/              # Core business models (no external dependencies)
├── application/         # Business logic services (FactCheckerService)
├── infrastructure/      # External system integrations
│   ├── http/           # HTTP clients (httpx)
│   ├── search/         # Search implementations (BraveSearchClient)
│   └── llm/            # LLM clients and parsers (DeepSeek API)
├── interfaces/         # UI adapters
│   ├── streamlit/      # Streamlit web UI
│   └── cli/            # Command-line interface
├── config/             # Configuration management (Settings)
└── utils/              # Shared utilities (PDF, sanitization)
```

**Other details**

* 🔒 **Type safety**: Uses Pydantic models + `mypy`, `ruff`, `black` (see `pyproject.toml`).
* ⚡ **Caching**: BraveSearchClient includes an in-memory TTL cache; optional file persistence via `cache_file`.
* 🐍 **Python Version**: Requires Python 3.13+ (currently tested with 3.13.9).
* 📦 **Dependencies**: Minimal direct dependencies (10 packages); transitive dependencies managed automatically by uv.

---

## 📄 License

[MIT](./LICENSE)
