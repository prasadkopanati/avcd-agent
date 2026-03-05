from typing import Any
from pydantic_ai import Agent 
from pydantic_ai.models.openai import OpenAIChatModel 
from pydantic_ai.providers.openai import OpenAIProvider
import os
import requests
from bs4 import BeautifulSoup
import logfire
from dataclasses import dataclass
from typing import Optional, Callable, List, Dict, Union
from pydantic_ai import ModelMessage
from pydantic import BaseModel
from pydantic_ai import ModelRequest
import json
import hashlib
from datetime import datetime
from dotenv import load_dotenv
import urllib.parse
import subprocess
from pydantic_ai import RunContext

# Load environment variables from .env file
load_dotenv()

TOOL_CALL_ERROR_MAX_RETRIES = int(os.getenv("TOOL_CALL_ERROR_MAX_RETRIES", 5))

# Database settings
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "myapp")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password123")

# MODEL settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "qwen3")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://192.168.86.34:8083/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen3-Coder-30b")
# MODEL_PROVIDER: "openai_compatible" (local/self-hosted), "openai" (OpenAI cloud), "anthropic"
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai_compatible")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Enumeration of known OpenAI-compatible (local/self-hosted) model names.
# These are models you can run on a local inference server (e.g. LM Studio, Ollama, llama.cpp).
# Add or remove entries to match the models available on your server.
OPENAI_COMPATIBLE_MODELS: dict[str, str] = {
    "Qwen3-Coder-30b":         "Qwen 3 Coder 30B  — large coding model (default)",
    "Qwen3-Coder-Next":        "Qwen 3 Coder Next   — fast, lighter coding model",
    "Qwen3-VL-32B":            "Qwen 3 Vision Model 32B        — large general-purpose model",
    "Qwen3-VL-32B-8BIT":       "Qwen 3 Vision Model 32B 8BIT       — large general-purpose model",
    "GLM47Flash-30b":          "GLM 4.7 Small model        — mid-size general-purpose model",
    "Nemotron-30b":            "Nemotron 30B     — Nvidia's coding model",
}

# API settings
API_KEY = os.getenv("API_KEY", "your_api_key_here")
API_URL = os.getenv("API_URL", "https://api.example.com")

# Application settings
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
PORT = int(os.getenv("PORT", "3000"))

# Web Search Settings
# Search provider: "exa", "firecrawl", "tavily", "brave", or "google_custom"
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "exa")

# Exa API
EXA_API_KEY = os.getenv("EXA_API_KEY")

# Firecrawl API
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_BASE_URL = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev")

# Tavily API
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_API_BASE_URL = os.getenv("TAVILY_API_BASE_URL", "https://api.tavily.com")

# Brave Search API
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

# Google Custom Search API
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Search configuration
DEFAULT_SEARCH_NUM_RESULTS = int(os.getenv("DEFAULT_SEARCH_NUM_RESULTS", 5))
SEARCH_QUERY_TYPE = os.getenv("SEARCH_QUERY_TYPE", "web")  # web, academic, news, etc.

# External Knowledge Layer
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

@dataclass
class Deps:
    """
    Dependencies to the tool functions via RunContext
    The CLI populates these dependencies when calling the agent, 
    to render UI, get approval from the user, and set a timeout for the agent.
    """
    approval_mode: bool
    approve: Callable[[str,dict],bool]
    ui: Any
    timeout: Optional[int] = None

class ToolExecError(BaseModel):
    """
    Error raised when a tool execution fails
    """
    tool_name: str
    error_type: str
    message: str
    attempted_input: dict

def _create_model():
    """
    Create the appropriate model instance based on MODEL_PROVIDER env var.
    Supports: openai_compatible (local/self-hosted), openai (OpenAI cloud), anthropic
    """
    if MODEL_PROVIDER == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        return AnthropicModel(MODEL_NAME, api_key=ANTHROPIC_API_KEY)
    elif MODEL_PROVIDER == "openai":
        return OpenAIChatModel(
            MODEL_NAME,
            provider=OpenAIProvider(api_key=OPENAI_API_KEY)
        )
    else:  # "openai_compatible" — local/self-hosted (default)
        return OpenAIChatModel(
            MODEL_NAME,
            provider=OpenAIProvider(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
        )

llamacp_model = _create_model()


def build_openai_compatible_model(model_name: str) -> OpenAIChatModel:
    """
    Build an OpenAIChatModel instance for a given local/self-hosted model name.
    Uses the same OPENAI_BASE_URL and OPENAI_API_KEY as the default model.
    """
    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    )

# Get current date and time in string format
CURRENT_DATE_TIME = datetime.now().strftime("%Y-%m-%d %H:%M")

# Get current IP and geographic location — gracefully degraded if offline
try:
    _ip_response = requests.get("https://api.ipify.org?format=json", timeout=5)
    IP_ADDRESS = _ip_response.json().get("ip", "")
    if IP_ADDRESS:
        _geo = requests.get(f"https://ipinfo.io/{IP_ADDRESS}/json", timeout=5).json()
        CURRENT_GEOGRAPHIC_LOCATION = _geo.get("city", "")
        CURRENT_REGION = _geo.get("region", "")
        CURRENT_COUNTRY = _geo.get("country", "")
    else:
        CURRENT_GEOGRAPHIC_LOCATION = CURRENT_REGION = CURRENT_COUNTRY = ""
except Exception:
    IP_ADDRESS = ""
    CURRENT_GEOGRAPHIC_LOCATION = ""
    CURRENT_REGION = ""
    CURRENT_COUNTRY = ""

# Abstract System Prompt into an applicaation wide constant and import the constant from the main module
SYSTEM_PROMPT = (
    "You are an AI Coding Agent\n"
    "Your goal is to act on user requests to write code.\n"
    "Strip off the double asterisks **, double hashes ##, single hashes #, single asterisks * in your responses to the user.\n"
    "You will be given a user request and you will need to write the code to fulfill the request.\n"
    "You will be given a codebase and you will need to write the code to fulfill the request.\n"
    "You operate in a loop, repeatedly calling tools until you have completed the user request.\n"
    "You must explaing your thought process and the steps you are taking to complete the user request.\n"
    "You must use the provided tools to interact with the environment, specifically the file system.\n"
    "If no function is available, then you can use your own knowledge and do not say anything about unavailable functions\n"
    "If a tool fails, analyze the error and retry with a corrected request.\n"
    "If a tool fails:\n 1. Identify why it failed\n 2. Modify only the failing parameters\n 3. Do not repeat the same failing call\n"
    "If you are asked to read an environment file and print the contents, then you should mask the passwords and other sensitive information."
    f"Note that the current date and time is {CURRENT_DATE_TIME}, the current IP address is {IP_ADDRESS}, the current geographic location is {CURRENT_GEOGRAPHIC_LOCATION}, the current region is {CURRENT_REGION}, the current country is {CURRENT_COUNTRY}."
    "\n\n"
    "## File System Navigation Instructions\n"
    "When working with files and directories:\n"
    "1. Use the get_current_directory tool to determine your starting location.\n"
    "2. To read files in nested directories, you have two options:\n"
    "   a. Use absolute paths (e.g., /dir1/dir2/abc.html) - this is the most reliable method\n"
    "   b. Navigate step-by-step using change_directory tool, then read the file\n"
    "3. Always verify directory existence using list_directory before attempting to access files in nested paths.\n"
    "4. If you receive a FileNotFoundError when trying to read a file in a nested directory:\n"
    "   - First check your current directory with get_current_directory\n"
    "   - Then use list_directory on each level of the path to verify directories exist\n"
    "   - Consider using change_directory to navigate to the target directory first\n"
    "5. The read_file tool automatically normalizes paths, so you can use relative paths like ../sibling/file.txt or paths with .. and .\n"
    "6. Use absolute paths whenever possible for better reliability and clarity.\n"
    "\n\n"
    "## Code Execution Instructions\n"
    "- Use run_command to execute shell commands, run tests, install packages, or validate code.\n"
    "- Always prefer running code to verify it works before telling the user it is done.\n"
    "- Use working_dir to run commands in a specific directory.\n"
    "- Common uses: 'python3 script.py', 'pytest tests/', 'pip install ...', 'git status'\n"
    "\n\n"
    "## Web Search Instructions\n"
    "When searching the web for information:\n"
    f"- The current search provider is: {SEARCH_PROVIDER}\n"
    "- Available search providers: exa, firecrawl, tavily, brave, google_custom\n"
    "- Use the web_search tool for general queries\n"
    "- For specific URLs, use the read_data_from_url tool\n"
    "- Always verify information from multiple sources when accuracy is critical\n"
    "\n\n"
    "## External Knowledge Instructions\n"
    "Use these tools selectively — only when the query benefits from authoritative,\n"
    "version-specific, or security-aware information:\n"
    "\n"
    "- lookup_package_info: When the user asks about latest versions, changelogs, or\n"
    "  whether a package exists. Supported registries: pypi (default), npm, cargo\n"
    "\n"
    "- search_github: When debugging errors that may be upstream bugs, finding official\n"
    "  repos, or checking known issues/PRs.\n"
    "  Supported search_type: repositories (default), issues, code\n"
    "\n"
    "- lookup_security_advisory: When the user mentions CVE/vulnerability/security,\n"
    "  before recommending a new dependency, or during upgrade discussions.\n"
    "  Supported ecosystems: PyPI (default), npm, crates.io, Go, Maven, NuGet, Packagist, RubyGems\n"
    "\n"
    "Do NOT call these tools for every request. Invoke only when the user intent\n"
    "clearly benefits from authoritative, version-aware, or security-specific information."
)

# Configure logfire
logfire.configure()
logfire.instrument_pydantic_ai()

def get_current_directory() -> str:
    """
    Get the current working directory
    """
    current_dir = os.getcwd()
    return f"Current working directory: {current_dir}"

def list_directory(directory:str) -> list[str]:
    """
    List the contents of a directory
    """
    contents= os.listdir(directory)
    return contents

def create_directory(ctx: RunContext[Deps], directory: str) -> str:
    """
    Create a directory
    """
    if not ctx.deps.approve("create_directory", {"directory": directory}):
        raise RuntimeError(
            ToolExecError(
                tool_name="create_directory",
                error_type="ApprovalDenied",
                message=f"User denied permission to create directory: {directory}",
                attempted_input={"directory": directory},
            ).model_dump_json()
        )
    os.makedirs(directory, exist_ok=True)
    return f"Directory {directory} created successfully"

def create_or_update_file(ctx: RunContext[Deps], file_path: str, content: str) -> str:
    """
    Create or update a file with the given content
    """
    if not ctx.deps.approve("create_or_update_file", {"file_path": file_path}):
        raise RuntimeError(
            ToolExecError(
                tool_name="create_or_update_file",
                error_type="ApprovalDenied",
                message=f"User denied permission to create/update file: {file_path}",
                attempted_input={"file_path": file_path},
            ).model_dump_json()
        )
    with open(file_path, "w") as file:
        file.write(content)
    return f"File {file_path} created successfully"

def read_file(file_path: str) -> str:
    """
    Read the contents of a file
    """
    print(f"Reading file: {file_path}")
    # Normalize the path to handle relative paths and resolve .., ., etc.
    normalized_path = os.path.abspath(os.path.normpath(file_path))
    try:
        with open(normalized_path, "r") as file:
            return file.read()
    except FileNotFoundError as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_file",
                error_type="FileNotFoundError",
                message=f"The file {file_path} does not exist. Try using the get_current_directory tool to see your starting point, then use list_directory on each level of the directory path to verify that each directory exists before attempting to read the file. Use absolute paths (starting with / or the drive letter) for better reliability.",
                attempted_input={"file_path": file_path},
            ).model_dump_json()
        )
    except PermissionError as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_file",
                error_type="PermissionError",
                message=f"Permission denied when trying to read the file {file_path}. You may need to check file permissions or try a different path.",
                attempted_input={"file_path": file_path},
            ).model_dump_json()
        )
    except IsADirectoryError as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_file",
                error_type="IsADirectoryError",
                message=f"The path {file_path} is a directory, not a file. Use list_directory to list the contents of the directory.",
                attempted_input={"file_path": file_path},
            ).model_dump_json()
        )
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_file",
                error_type=type(e).__name__,
                message=f"An error occurred while reading the file {file_path}: {str(e)}",
                attempted_input={"file_path": file_path},
            ).model_dump_json()
        )

def change_directory(ctx: RunContext[Deps], directory: str) -> str:
    """
    Change the current working directory
    Use this tool to navigate between directories when you need to access files in different locations.
    You can use absolute paths (e.g., /home/user/project) or relative paths (e.g., ../sibling_dir).
    """
    if not ctx.deps.approve("change_directory", {"directory": directory}):
        raise RuntimeError(
            ToolExecError(
                tool_name="change_directory",
                error_type="ApprovalDenied",
                message=f"User denied permission to change directory to: {directory}",
                attempted_input={"directory": directory},
            ).model_dump_json()
        )
    try:
        # Normalize and resolve the path
        new_dir = os.path.abspath(os.path.normpath(directory))
        os.chdir(new_dir)
        return f"Changed directory to: {new_dir}"
    except FileNotFoundError as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="change_directory",
                error_type="FileNotFoundError",
                message=f"The directory {directory} does not exist. Use list_directory on the parent directory to see available options.",
                attempted_input={"directory": directory},
            ).model_dump_json()
        )
    except NotADirectoryError as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="change_directory",
                error_type="NotADirectoryError",
                message=f"The path {directory} is not a directory, it's a file. Use list_directory on the parent directory to see available options.",
                attempted_input={"directory": directory},
            ).model_dump_json()
        )
    except PermissionError as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="change_directory",
                error_type="PermissionError",
                message=f"Permission denied when trying to access the directory {directory}. You may need to check directory permissions.",
                attempted_input={"directory": directory},
            ).model_dump_json()
        )
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="change_directory",
                error_type=type(e).__name__,
                message=f"An error occurred while changing directory to {directory}: {str(e)}",
                attempted_input={"directory": directory},
            ).model_dump_json()
        )

# ============== CODE EXECUTION ==============

def run_command(ctx: RunContext[Deps], command: str, working_dir: str = None) -> str:
    """
    Execute a shell command and return its output (stdout + stderr combined).

    Use this tool when:
    - You need to run or test code you have written
    - You need to install packages (pip install, npm install, uv add, etc.)
    - You need to run tests (pytest, npm test, cargo test, etc.)
    - You need to execute git commands
    - You need to compile, lint, or build a project

    Arguments:
    - command: The shell command to execute (e.g., "python3 script.py", "pytest tests/")
    - working_dir: Optional directory to run the command in. Defaults to current directory.

    Returns combined stdout and stderr. Times out after 60 seconds.
    Always prefer running code to verify it works before telling the user it is done.
    """
    resolved_dir = os.path.abspath(os.path.normpath(working_dir)) if working_dir else os.getcwd()

    if not ctx.deps.approve("run_command", {"command": command, "working_dir": resolved_dir}):
        raise RuntimeError(
            ToolExecError(
                tool_name="run_command",
                error_type="ApprovalDenied",
                message=f"User denied permission to run command: {command}",
                attempted_input={"command": command, "working_dir": resolved_dir},
            ).model_dump_json()
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=resolved_dir,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if not output.strip():
            output = f"Command exited with code {result.returncode} (no output)"
        return output[:10000]  # cap to avoid token overflow
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            ToolExecError(
                tool_name="run_command",
                error_type="TimeoutExpired",
                message=f"Command timed out after 60 seconds: {command}",
                attempted_input={"command": command, "working_dir": resolved_dir},
            ).model_dump_json()
        )
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="run_command",
                error_type=type(e).__name__,
                message=f"Command execution failed: {str(e)}",
                attempted_input={"command": command, "working_dir": resolved_dir},
            ).model_dump_json()
        )


# ============== WEB SEARCH IMPLEMENTATIONS ==============

def exa_search_tool(query: str) -> List[Dict[str, Any]]:
    """
    Searches the web for information related to the given query using Exa.
    Returns a list of search results with content.
    """
    try:
        from exa_py import Exa
        exa_client = Exa(api_key=EXA_API_KEY)
        results = exa_client.search_and_contents(
            query,
            num_results=DEFAULT_SEARCH_NUM_RESULTS,
            type="auto",
            text=True
        )
        return [result.model_dump() if hasattr(result, 'model_dump') else result for result in results.results]
    except ImportError:
        raise RuntimeError(
            ToolExecError(
                tool_name="exa_search_tool",
                error_type="ImportError",
                message="Exa Py library not installed. Install with: pip install exa-py",
                attempted_input={"query": query},
            ).model_dump_json()
        )
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="exa_search_tool",
                error_type=type(e).__name__,
                message=f"Exa search failed: {str(e)}",
                attempted_input={"query": query},
            ).model_dump_json()
        )

def firecrawl_search_tool(query: str) -> List[Dict[str, Any]]:
    """
    Searches the web using Firecrawl API - combines search + extraction.
    Returns search results with full page content.
    """
    try:
        import firecrawl
        app = firecrawl.FirecrawlApp(api_key=FIRECRAWL_API_KEY)
        
        # Use Firecrawl's search endpoint
        results = app.search(
            query,
            limit=DEFAULT_SEARCH_NUM_RESULTS,
            scrape_options={"formats": ["markdown"]}
        )
        
        # Convert results to dictionary format
        search_results = []
        for result in results.web if hasattr(results, 'web') else []:
            if hasattr(result, 'model_dump'):
                search_results.append(result.model_dump())
            elif hasattr(result, '__dict__'):
                search_results.append(result.__dict__)
            else:
                search_results.append(result)
        
        return search_results
    except ImportError:
        raise RuntimeError(
            ToolExecError(
                tool_name="firecrawl_search_tool",
                error_type="ImportError",
                message="Firecrawl library not installed. Install with: pip install firecrawl",
                attempted_input={"query": query},
            ).model_dump_json()
        )
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="firecrawl_search_tool",
                error_type=type(e).__name__,
                message=f"Firecrawl search failed: {str(e)}",
                attempted_input={"query": query},
            ).model_dump_json()
        )

def tavily_search_tool(query: str) -> List[Dict[str, Any]]:
    """
    Searches the web using Tavily API - optimized for AI agents and RAG.
    Returns search results with AI-optimized snippets.
    """
    try:
        response = requests.post(
            f"{TAVILY_API_BASE_URL}/search",
            json={
                "query": query,
                "max_results": DEFAULT_SEARCH_NUM_RESULTS,
                "api_key": TAVILY_API_KEY
            }
        )
        response.raise_for_status()
        data = response.json()

        # Format results
        return [
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
                "score": result.get("score", 0)
            }
            for result in data.get("results", [])
        ]
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="tavily_search_tool",
                error_type=type(e).__name__,
                message=f"Tavily search failed: {str(e)}",
                attempted_input={"query": query},
            ).model_dump_json()
        )

def brave_search_tool(query: str) -> List[Dict[str, Any]]:
    """
    Searches the web using Brave Search API - independent search index.
    Returns search results with multiple snippets per result.
    """
    try:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": BRAVE_API_KEY
        }
        
        params = {"q": query, "count": DEFAULT_SEARCH_NUM_RESULTS}

        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        # Format results
        results = []
        if "web" in data and "results" in data["web"]:
            for result in data["web"]["results"]:
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("description", ""),
                    "snippets": result.get("snippets", [])
                })

        return results
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="brave_search_tool",
                error_type=type(e).__name__,
                message=f"Brave search failed: {str(e)}",
                attempted_input={"query": query},
            ).model_dump_json()
        )

def google_custom_search_tool(query: str) -> List[Dict[str, Any]]:
    """
    Searches the web using Google Custom Search API.
    Limited to custom search indexes (100 free queries/day).
    """
    try:
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "num": DEFAULT_SEARCH_NUM_RESULTS
        }
        
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        # Format results
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "content": item.get("snippet", ""),
                "display_link": item.get("displayLink", "")
            })
        
        return results
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="google_custom_search_tool",
                error_type=type(e).__name__,
                message=f"Google Custom Search failed: {str(e)}",
                attempted_input={"query": query},
            ).model_dump_json()
        )

# ============== SELECT SEARCH PROVIDER ==============

def select_search_provider() -> callable:
    """
    Selects the appropriate search function based on configuration.
    Returns the search function to use.
    """
    provider_map = {
        "exa": exa_search_tool,
        "firecrawl": firecrawl_search_tool,
        "tavily": tavily_search_tool,
        "brave": brave_search_tool,
        "google_custom": google_custom_search_tool
    }
    
    provider = SEARCH_PROVIDER.lower()
    
    if provider not in provider_map:
        # Default to exa if provider not found
        print(f"Warning: Unknown search provider '{provider}'. Defaulting to 'exa'")
        return exa_search_tool
    
    # Check if required environment variables are present
    required_vars = {
        "exa": ["EXA_API_KEY"],
        "firecrawl": ["FIRECRAWL_API_KEY"],
        "tavily": ["TAVILY_API_KEY"],
        "brave": ["BRAVE_API_KEY"],
        "google_custom": ["GOOGLE_API_KEY", "GOOGLE_CSE_ID"]
    }
    
    missing_vars = [var for var in required_vars.get(provider, []) if not os.getenv(var)]
    
    if missing_vars:
        raise RuntimeError(
            f"Missing required environment variables for {provider}: {', '.join(missing_vars)}"
        )
    
    return provider_map[provider]

# ============== MAIN WEB SEARCH FUNCTION ==============

def web_search(query: str) -> List[Dict[str, Any]]:
    """
    Main web search function that routes to the configured search provider.
    This is the function that should be used by the agent.
    """
    search_func = select_search_provider()
    return search_func(query)

# ============== EXTERNAL KNOWLEDGE TOOLS ==============

def lookup_package_info(package_name: str, registry: str = "pypi") -> Dict[str, Any]:
    """
    Look up a package in an official package registry to get the latest version,
    description, homepage URL, and changelog URL.

    Use this tool when:
    - The user asks about the latest version of a library or package
    - You need to verify a package exists before recommending it
    - The user asks for the homepage, documentation, or changelog of a package
    - Keywords appear: 'latest version', 'current version', 'changelog', 'what version'

    Supported registries:
    - pypi: Python packages (https://pypi.org)
    - npm: Node.js packages (https://registry.npmjs.org)
    - cargo: Rust crates (https://crates.io)
    """
    try:
        registry_lower = registry.lower().strip()

        if registry_lower == "pypi":
            url = f"https://pypi.org/pypi/{package_name}/json"
            response = requests.get(url, timeout=15)
            if response.status_code == 404:
                return {"error": f"Package '{package_name}' not found on PyPI."}
            response.raise_for_status()
            data = response.json()
            info = data.get("info", {})
            return {
                "registry": "pypi",
                "package": package_name,
                "latest_version": info.get("version"),
                "summary": info.get("summary"),
                "homepage": info.get("home_page") or info.get("project_url"),
                "project_urls": info.get("project_urls", {}),
                "requires_python": info.get("requires_python"),
                "license": info.get("license"),
                "author": info.get("author"),
                "pypi_url": f"https://pypi.org/project/{package_name}/",
            }

        elif registry_lower == "npm":
            # URL-encode package name to handle scoped packages like @types/node
            encoded_name = urllib.parse.quote(package_name, safe="")
            url = f"https://registry.npmjs.org/{encoded_name}"
            response = requests.get(url, timeout=15)
            if response.status_code == 404:
                return {"error": f"Package '{package_name}' not found on npm."}
            response.raise_for_status()
            data = response.json()
            latest_tag = data.get("dist-tags", {}).get("latest", "")
            latest_info = data.get("versions", {}).get(latest_tag, {})
            repository = latest_info.get("repository", {})
            return {
                "registry": "npm",
                "package": package_name,
                "latest_version": latest_tag,
                "summary": data.get("description"),
                "homepage": latest_info.get("homepage") or data.get("homepage"),
                "repository": repository.get("url") if isinstance(repository, dict) else repository,
                "license": latest_info.get("license"),
                "npm_url": f"https://www.npmjs.com/package/{package_name}",
            }

        elif registry_lower == "cargo":
            url = f"https://crates.io/api/v1/crates/{package_name}"
            # crates.io requires a User-Agent header per their API policy
            headers = {"User-Agent": "avcd-agent/1.0 (coding-assistant)"}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 404:
                return {"error": f"Crate '{package_name}' not found on crates.io."}
            response.raise_for_status()
            data = response.json()
            crate_info = data.get("crate", {})
            return {
                "registry": "cargo",
                "package": package_name,
                "latest_version": crate_info.get("newest_version"),
                "max_stable_version": crate_info.get("max_stable_version"),
                "summary": crate_info.get("description"),
                "homepage": crate_info.get("homepage"),
                "repository": crate_info.get("repository"),
                "documentation": crate_info.get("documentation"),
                "downloads": crate_info.get("downloads"),
                "crates_io_url": f"https://crates.io/crates/{package_name}",
            }

        else:
            return {
                "error": f"Unknown registry '{registry}'. Supported values are: pypi, npm, cargo"
            }

    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="lookup_package_info",
                error_type=type(e).__name__,
                message=f"Failed to look up package '{package_name}' on registry '{registry}': {str(e)}",
                attempted_input={"package_name": package_name, "registry": registry},
            ).model_dump_json()
        )


def search_github(query: str, search_type: str = "repositories") -> List[Dict[str, Any]]:
    """
    Search GitHub for repositories, issues, or code using the GitHub Search API.

    Use this tool when:
    - Debugging errors to find known GitHub issues or bug reports
    - Looking for reference implementations or example code
    - Checking if a bug has been reported upstream
    - Finding the official repository for a library
    - Keywords appear: 'bug', 'issue', 'error', 'known problem', 'workaround'

    Arguments:
    - query: The search query. For issues, include the repo for best results
             (e.g., "memory leak repo:pydantic/pydantic-ai").
    - search_type: One of "repositories", "issues", or "code". Defaults to "repositories".

    Set GITHUB_TOKEN environment variable for 5000 requests/hr (vs 60/hr unauthenticated).
    """
    try:
        valid_types = {"repositories", "issues", "code"}
        if search_type not in valid_types:
            return [{"error": f"Invalid search_type '{search_type}'. Use one of: {', '.join(sorted(valid_types))}"}]

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        params = {"q": query, "per_page": 8, "sort": "best-match"}
        url = f"https://api.github.com/search/{search_type}"

        response = requests.get(url, headers=headers, params=params, timeout=15)

        if response.status_code == 403:
            rate_remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
            return [{"error": f"GitHub API rate limit reached (remaining: {rate_remaining}). Set GITHUB_TOKEN for 5000 requests/hour."}]
        if response.status_code == 422:
            return [{"error": f"GitHub search query is invalid: {response.json().get('message', 'unknown')}"}]

        response.raise_for_status()
        items = response.json().get("items", [])

        if search_type == "repositories":
            return [
                {
                    "name": item.get("full_name"),
                    "description": item.get("description"),
                    "url": item.get("html_url"),
                    "stars": item.get("stargazers_count"),
                    "language": item.get("language"),
                    "topics": item.get("topics", []),
                    "updated_at": item.get("updated_at"),
                    "open_issues_count": item.get("open_issues_count"),
                }
                for item in items
            ]

        elif search_type == "issues":
            return [
                {
                    "title": item.get("title"),
                    "url": item.get("html_url"),
                    "state": item.get("state"),
                    "body_preview": (item.get("body") or "")[:500],
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                    "labels": [label.get("name") for label in item.get("labels", [])],
                    "comments": item.get("comments"),
                    "repository": item.get("repository_url", "").replace("https://api.github.com/repos/", ""),
                    "is_pull_request": "pull_request" in item,
                }
                for item in items
            ]

        elif search_type == "code":
            return [
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "url": item.get("html_url"),
                    "repository": item.get("repository", {}).get("full_name"),
                    "repository_url": item.get("repository", {}).get("html_url"),
                    "score": item.get("score"),
                }
                for item in items
            ]

        return []

    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="search_github",
                error_type=type(e).__name__,
                message=f"GitHub search failed for query '{query}' (type: {search_type}): {str(e)}",
                attempted_input={"query": query, "search_type": search_type},
            ).model_dump_json()
        )


def lookup_security_advisory(package_name: str, ecosystem: str = "PyPI") -> List[Dict[str, Any]]:
    """
    Query the OSV.dev database for known security vulnerabilities (CVEs) affecting
    a given package in a specific ecosystem.

    Use this tool when:
    - The user mentions security, CVE, vulnerability, or exploit
    - You are about to add or recommend a dependency
    - The user asks if a package version is safe to use
    - A package upgrade is being considered and security context is needed

    Supported ecosystems: PyPI, npm, crates.io, Go, Maven, NuGet, Packagist, RubyGems
    Common aliases are accepted: python, node, rust, golang, java, dotnet, php, ruby

    An empty result means no known vulnerabilities were found in OSV.dev — this does
    not guarantee the package is fully secure.
    """
    try:
        # Normalize common ecosystem aliases to OSV.dev expected values
        ecosystem_map = {
            "python": "PyPI", "pypi": "PyPI",
            "node": "npm", "nodejs": "npm", "npm": "npm",
            "rust": "crates.io", "cargo": "crates.io", "crates.io": "crates.io",
            "go": "Go", "golang": "Go",
            "java": "Maven", "maven": "Maven",
            "nuget": "NuGet", "dotnet": "NuGet",
            "php": "Packagist", "packagist": "Packagist",
            "ruby": "RubyGems", "rubygems": "RubyGems",
        }
        normalized_ecosystem = ecosystem_map.get(ecosystem.lower(), ecosystem)

        payload = {
            "package": {
                "name": package_name,
                "ecosystem": normalized_ecosystem,
            }
        }

        response = requests.post(
            "https://api.osv.dev/v1/query",
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        vulns = response.json().get("vulns", [])

        if not vulns:
            return [{"message": f"No known vulnerabilities found for '{package_name}' in ecosystem '{normalized_ecosystem}' on OSV.dev."}]

        results = []
        for vuln in vulns[:10]:  # Cap at 10 to avoid context overflow
            # Extract affected version ranges
            affected_ranges = []
            for affected in vuln.get("affected", []):
                for r in affected.get("ranges", []):
                    events = r.get("events", [])
                    introduced = next((e.get("introduced") for e in events if "introduced" in e), None)
                    fixed = next((e.get("fixed") for e in events if "fixed" in e), None)
                    affected_ranges.append({"introduced": introduced, "fixed": fixed})

            severity_list = vuln.get("severity", [])
            severity = severity_list[0].get("score") if severity_list else None

            aliases = vuln.get("aliases", [])
            cve_ids = [a for a in aliases if a.startswith("CVE-")]

            results.append({
                "id": vuln.get("id"),
                "cve_ids": cve_ids,
                "summary": vuln.get("summary"),
                "details": (vuln.get("details") or "")[:600],
                "severity": severity,
                "published": vuln.get("published"),
                "modified": vuln.get("modified"),
                "affected_ranges": affected_ranges,
                "references": [ref.get("url") for ref in vuln.get("references", [])[:3]],
                "osv_url": f"https://osv.dev/vulnerability/{vuln.get('id')}",
            })

        return results

    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="lookup_security_advisory",
                error_type=type(e).__name__,
                message=f"Security advisory lookup failed for '{package_name}' (ecosystem: {ecosystem}): {str(e)}",
                attempted_input={"package_name": package_name, "ecosystem": ecosystem},
            ).model_dump_json()
        )


# ============== WEBSITE READING FUNCTIONS ==============

def read_website(url: str) -> str:
    """
    Read the contents of a website given the url for the website.
    Returns cleaned text content.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean it up
        text = soup.get_text()
        
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text[:10000]  # Limit to 10k characters to avoid token overflow
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_website",
                error_type=type(e).__name__,
                message=f"Failed to read website {url}: {str(e)}",
                attempted_input={"url": url},
            ).model_dump_json()
        )

# Read JSON data from a URL
def read_json_from_url(url: str) -> str:
    """
    Read JSON data from a URL and return formatted string.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return json.dumps(data, indent=2)
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_json_from_url",
                error_type=type(e).__name__,
                message=f"Failed to read JSON from {url}: {str(e)}",
                attempted_input={"url": url},
            ).model_dump_json()
        )

# Read CSV data from a URL
def read_csv_from_url(url: str) -> str:
    """
    Read CSV data from a URL.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text[:10000]  # Limit to 10k characters
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_csv_from_url",
                error_type=type(e).__name__,
                message=f"Failed to read CSV from {url}: {str(e)}",
                attempted_input={"url": url},
            ).model_dump_json()
        )

# Read XML data from a URL
def read_xml_from_url(url: str) -> str:
    """
    Read XML data from a URL and return formatted string.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text[:10000]  # Limit to 10k characters
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_xml_from_url",
                error_type=type(e).__name__,
                message=f"Failed to read XML from {url}: {str(e)}",
                attempted_input={"url": url},
            ).model_dump_json()
        )

# Read YAML data from a URL
def read_yaml_from_url(url: str) -> str:
    """
    Read YAML data from a URL and return formatted string.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text[:10000]  # Limit to 10k characters
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_yaml_from_url",
                error_type=type(e).__name__,
                message=f"Failed to read YAML from {url}: {str(e)}",
                attempted_input={"url": url},
            ).model_dump_json()
        )

# Read Excel data from a URL
def read_excel_from_url(url: str) -> str:
    """
    Read Excel data from a URL.
    Note: This returns raw bytes, for actual parsing use pandas or openpyxl.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return f"Excel file received ({len(response.content)} bytes). Use pandas to parse."
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_excel_from_url",
                error_type=type(e).__name__,
                message=f"Failed to read Excel from {url}: {str(e)}",
                attempted_input={"url": url},
            ).model_dump_json()
        )

# Read PDF data from a URL
def read_pdf_from_url(url: str) -> str:
    """
    Read PDF data from a URL and return text content.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return f"PDF file received ({len(response.content)} bytes). Use PyPDF2 or pdfplumber to extract text."
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_pdf_from_url",
                error_type=type(e).__name__,
                message=f"Failed to read PDF from {url}: {str(e)}",
                attempted_input={"url": url},
            ).model_dump_json()
        )

# Refactor various reading functions into one function 
# with conditional logic to determine the type of data to read
# and return the data as a string
def read_data_from_url(url: str) -> str:
    """
    Given a URL, read data from a URL based on the file extension.
    If the file extension is not supported, then return the contents of the website.
    Supported file extensions: .json, .csv, .xml, .yaml, .yml, .excel, .xlsx, .pdf
    """
    url_lower = url.lower()
    
    if url_lower.endswith(".json"):
        return read_json_from_url(url)
    elif url_lower.endswith(".csv"):
        return read_csv_from_url(url)
    elif url_lower.endswith(".xml"):
        return read_xml_from_url(url)
    elif url_lower.endswith(".yaml") or url_lower.endswith(".yml"):
        return read_yaml_from_url(url)
    elif url_lower.endswith(".excel") or url_lower.endswith(".xlsx"):
        return read_excel_from_url(url)
    elif url_lower.endswith(".pdf"):
        return read_pdf_from_url(url)
    else:
        return read_website(url)

# ============== AGENT INITIALIZATION ==============

avcCodingAgent = Agent(
    model=llamacp_model,
    deps_type=Deps,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        get_current_directory,
        list_directory,
        create_directory,
        create_or_update_file,
        read_file,
        change_directory,
        run_command,
        read_data_from_url,
        web_search,
        lookup_package_info,
        search_github,
        lookup_security_advisory,
    ]
)

def callAgent(
    prompt: str,
    message_history: List[ModelMessage] | None = None,
    deps: Deps | None = None,
    model_name: str | None = None,
) -> str:
    # Build a per-call model override when a non-default model is selected.
    # Only applies to openai_compatible provider; cloud providers use their own keys.
    model_override = None
    if model_name and model_name != MODEL_NAME and MODEL_PROVIDER == "openai_compatible":
        model_override = build_openai_compatible_model(model_name)

    tool_error = None

    for attempt in range(1, TOOL_CALL_ERROR_MAX_RETRIES + 1):
        try:
            result = avcCodingAgent.run_sync(
                prompt, message_history=message_history, deps=deps, model=model_override
            )
            return result
        except RuntimeError as e:
            tool_error = str(e)
            try:
                error_object = json.loads(tool_error)
                error_summary = (
                    f"Tool: {error_object['tool_name']} \n"
                    f"Error Type: {error_object['error_type']} \n"
                    f"Error Message: {error_object['message']} \n"
                    f"Attempted Input: {error_object['attempted_input']} \n"
                )
            except json.JSONDecodeError:
                error_summary = tool_error

            if attempt == TOOL_CALL_ERROR_MAX_RETRIES:
                raise RuntimeError(
                    f"Tool call failed after {TOOL_CALL_ERROR_MAX_RETRIES} retries. \nLast error: \n{tool_error}"
                )

            # Analyze the tool error and retry with a corrected request
            message_history.append(
                ModelRequest.user_text_prompt(
                    f"""
                    The previous tool call failed with the following error:
                    {error_summary}

                    Please retry with a corrected or alternative request.

                    Instructions:
                        1. Identify why the tool call failed.
                        2. Modify only the failing parameters.
                        3. Do NOT repeat the same failing call.
                        4. If retry is impossible, explain why.
                        5. If the error is not clear, ask the user for clarification.
                    """
                )
            )
        except Exception as e:
            raise RuntimeError(f"An error occurred while calling the agent: {e}")