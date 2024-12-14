# AI-Powered Fact Checker

An intelligent fact-checking assistant that combines Brave Search API with AI analysis using Meta's Llama 3.3 70B model through GLHF.chat. This project provides both a command-line interface and a Streamlit web interface for verifying statements and claims using real-time web search results.

Source code: [https://github.com/jdluu/TruthSeeker](https://github.com/jdluu/TruthSeeker)

## Demo

A live demo of the application is available at:
[https://journeytotruth.streamlit.app](https://journeytotruth.streamlit.app)

## Features

- Real-time fact-checking using Brave Search API
- AI-powered analysis using Meta's Llama 3.3 70B model
- Performance metrics display:
  - Search time
  - Analysis time
  - Total processing time
- Detailed accuracy ratings with explanations:
  - TRUE: Completely accurate
  - MOSTLY TRUE: Generally accurate with minor inaccuracies
  - MIXED: Contains both true and false elements
  - MOSTLY FALSE: Contains significant inaccuracies
  - FALSE: Completely inaccurate
- Comprehensive results display:
  - Verdict with color-coding
  - Detailed explanation
  - Context and nuance
  - Referenced sources with links
- Modern, responsive UI features:
  - Mobile-friendly design
  - Dark theme for better readability
  - Clear typography and spacing
  - Collapsible sections
- Two interfaces:
  - Command-line interface (CLI)
  - Web interface using Streamlit
- Robust error handling:
  - API connection issues
  - Rate limiting
  - Invalid inputs
- Comprehensive logging with logfire

## Prerequisites

- Python 3.10 or higher
- Brave Search API key (free tier available, requires payment info but no charges unless upgraded)
- GLHF.chat API key (currently free as of December 2024, may change in future)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/jdluu/TruthSeeker.git
cd TruthSeeker
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
LLM_MODEL=hf:meta-llama/Llama-3.3-70B-Instruct  # Default model
# Or use any GLHF-compatible or Hugging Face model:
# LLM_MODEL=hf:your_custom_model_here
```

## Model Customization

While the application defaults to Meta's Llama 3.3 70B model, you can easily use any GLHF-compatible model or model from Hugging Face by updating the `LLM_MODEL` variable in your `.env` file:

```env
# Example model configurations:
LLM_MODEL=hf:meta-llama/Llama-3.3-70B-Instruct  # Default
LLM_MODEL=hf:your_custom_model_here             # Custom model
```

## API Keys

### Brave Search API

- Sign up for a free API key at the [Brave API Portal](https://api.search.brave.com/app/signup)
- Free tier available with generous limits
- Payment information required but no charges unless upgraded to a paid plan
- Rate limits apply to prevent abuse

### GLHF.chat API

- Required for accessing the language models
- Sign up through GLHF.chat platform
- Currently free to create an account and get an API key (as of December 2024)
- Pricing model may change in the future
- Rate limits apply to prevent abuse

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

The web interface will open in your default browser. Enter your statement in the text input field and click "Fact Check" to begin the analysis.

## Key Components

- `web_search_agent.py`:

  - Core search functionality
  - Brave API integration
  - CLI interface
  - Logging setup

- `streamlit_ui.py`:
  - Web interface implementation
  - Responsive design
  - Real-time updates
  - Error handling

## Environment Variables

- `GLHF_API_KEY` - Your GLHF.chat API key
- `BRAVE_API_KEY` - Your Brave Search API key (free tier available)
- `LLM_MODEL` - Language model selection (default: Llama-3.3-70B-Instruct, can be any GLHF-compatible or Hugging Face model using the format `hf:model_name`)

## Error Handling

The application includes robust error handling for:

- API connection issues
- Rate limiting
- Invalid user inputs
- Empty search results
- Timeout scenarios

## Logging

Comprehensive logging using logfire includes:

- Search operations
- API interactions
- Performance metrics
- Error conditions
- User interactions

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
- GLHF.chat for AI model access
- Streamlit for the web interface framework
- logfire for comprehensive logging
