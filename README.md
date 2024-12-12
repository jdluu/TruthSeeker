# AI-Powered Fact Checker

An intelligent fact-checking assistant that combines Brave Search API with AI analysis using GLHF.chat's LLama 3.3 70B model. This project provides both a command-line interface and a Streamlit web interface for verifying statements and claims using real-time web search results.

## Features

- Statement verification using Brave Search API
- AI-powered fact analysis using LLama 3.3 70B model
- Detailed accuracy ratings:
  - TRUE: Completely accurate
  - MOSTLY TRUE: Generally accurate with minor inaccuracies
  - MIXED: Contains both true and false elements
  - MOSTLY FALSE: Contains significant inaccuracies
  - FALSE: Completely inaccurate
- Two interfaces:
  - Command-line interface (CLI)
  - Web interface using Streamlit
- Comprehensive logging with logfire
- Modern, dark-themed UI for better readability

## Prerequisites

- Python 3.10 or higher
- Brave Search API key
- GLHF.chat API key

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd <repository-name>
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On Unix or MacOS
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with your API keys:

```env
GLHF_API_KEY=your_glhf_api_key
BRAVE_API_KEY=your_brave_api_key
LLM_MODEL=hf:meta-llama/Llama-3.3-70B-Instruct
```

## Usage

### Command Line Interface

Run the CLI version:

```bash
python web_search_agent.py
```

Enter statements to fact-check when prompted. Type 'quit' to exit.

Example:

```
Enter a statement to fact-check (or 'quit' to exit):
> The Earth is flat

Searching and fact-checking...
[Results will appear here]
```

### Web Interface

Run the Streamlit web interface:

```bash
streamlit run streamlit_ui.py
```

The web interface will open in your default browser. Enter your statement in the text input field to start fact-checking.

## Logging

The application uses logfire for comprehensive logging of:

- Search operations
- AI analysis process
- User interactions
- Performance metrics
- Error conditions

Logs include:

- Operation timing
- Process spans
- Contextual information
- Error details
- Response metrics

## Project Structure

- `web_search_agent.py` - Core functionality and CLI interface
- `streamlit_ui.py` - Web interface using Streamlit
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (API keys)
- `README.md` - Project documentation

## Environment Variables

- `GLHF_API_KEY` - Your GLHF.chat API key
- `BRAVE_API_KEY` - Your Brave Search API key
- `LLM_MODEL` - The language model to use (default: LLama 3.3 70B model)

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/YourFeature`)
3. Commit your changes (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature/YourFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Brave Search API for web search capabilities
- GLHF.chat for providing the Llama model access
- Streamlit for the web interface framework
- logfire for comprehensive logging
