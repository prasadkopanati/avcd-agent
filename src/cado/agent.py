from typing import Any
from pydantic_ai import Agent 
from pydantic_ai.models.openai import OpenAIChatModel 
from pydantic_ai.providers.openai import OpenAIProvider
import os
import requests
from bs4 import BeautifulSoup
import logfire
from dataclasses import dataclass
from typing import Optional, Callable, List
from pydantic_ai import ModelMessage
from pydantic import BaseModel
from pydantic_ai import ModelRequest
import json
from exa_py import Exa
from datetime import datetime
from dotenv import load_dotenv

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

# API settings
API_KEY = os.getenv("API_KEY", "your_api_key_here")
API_URL = os.getenv("API_URL", "https://api.example.com")

# Application settings
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
PORT = int(os.getenv("PORT", "3000"))

# Exa API key
EXA_API_KEY = os.getenv("EXA_API_KEY")

# Initialize Exa client
exa_client = Exa(api_key=EXA_API_KEY)

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

llamacp_model = OpenAIChatModel(
    model_name=MODEL_NAME, 
    provider=OpenAIProvider(
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY
    )
)

# Get current date and time in string format
CURRENT_DATE_TIME = datetime.now().strftime("%Y-%m-%d %H:%M")

# Get current IP address by calling the IP Geolocation API
IP_ADDRESS = requests.get("https://api.ipify.org?format=json").json()["ip"]
# Get current geographic location by calling the IP Geolocation API in string format
CURRENT_GEOGRAPHIC_LOCATION = requests.get(f"https://ipinfo.io/{IP_ADDRESS}/json").json()["city"]
# Get current ISP by calling the IP Geolocation API in string format
CURRENT_REGION = requests.get(f"https://ipinfo.io/{IP_ADDRESS}/json").json()["region"]
# Get current country by calling the IP Geolocation API in string format
CURRENT_COUNTRY = requests.get(f"https://ipinfo.io/{IP_ADDRESS}/json").json()["country"]

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
)

# Coonfigure logfire
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

def create_directory(directory:str) -> None:
    """
    Create a directory
    """
    os.makedirs(directory, exist_ok=True)
    return f"Directory {directory} created successfully"

def create_or_update_file(file_path:str, content:str) -> None:
    """
    Create or update a file with the given content
    """
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

def change_directory(directory: str) -> str:
    """
    Change the current working directory
    Use this tool to navigate between directories when you need to access files in different locations.
    You can use absolute paths (e.g., /home/user/project) or relative paths (e.g., ../sibling_dir).
    """
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

# Search web for a given query and return the contents of the top results
def exa_search_tool(query: str): 
    """
    Searches the web for information related to the given query and returns the contents of the top results.
    """
    results = exa_client.search_and_contents(
        query,
        num_results=int(os.getenv("EXA_SEARCH_NUM_RESULTS", 3)),
        type="auto",
        text=True
    )
    return results.results

def read_website(url:str) -> str:
    """
    Read the contents of a website given the url for the website
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text()

# Read JSON data from a URL
def read_json_from_url(url:str) -> str:
    """
    Read JSON data from a URL
    """
    response = requests.get(url)
    return response.json()

# Read CSV data from a URL
def read_csv_from_url(url:str) -> str:
    """
    Read CSV data from a URL
    """
    response = requests.get(url)
    return response.text

# Read XML data from a URL
def read_xml_from_url(url:str) -> str:
    """
    Read XML data from a URL
    """
    response = requests.get(url)
    return response.text

# Read YAML data from a URL
def read_yaml_from_url(url:str) -> str:
    """
    Read YAML data from a URL
    """
    response = requests.get(url)
    return response.text

# Read Excel data from a URL
def read_excel_from_url(url:str) -> str:
    """
    Read Excel data from a URL
    """
    response = requests.get(url)
    return response.text

# Read PDF data from a URL
def read_pdf_from_url(url:str) -> str:
    """
    Read PDF data from a URL
    """
    response = requests.get(url)
    return response.text

# Refactor various reading functions into one function 
# with conditional logic to determine the type of data to read
# and return the data as a string
def read_data_from_url(url:str) -> str:
    """
    Given a URL, read data from a URL based on the file extension
    If the file extension is not supported, then return the contents of the website
    Supported file extensions: .json, .csv, .xml, .yaml, .excel, .pdf
    """
    if url.endswith(".json"):
        return read_json_from_url(url)
    elif url.endswith(".csv"):
        return read_website(url)
    elif url.endswith(".xml"):
        return read_website(url)
    elif url.endswith(".yaml"):
        return read_website(url)
    elif url.endswith(".excel"):
        return read_website(url)
    elif url.endswith(".pdf"):
        return read_website(url)
    else:
        return read_website(url)

avcCodingAgent = Agent(
                model=llamacp_model, 
                system_prompt=SYSTEM_PROMPT,
                tools=[
                    get_current_directory,
                    list_directory, 
                    create_directory, 
                    create_or_update_file, 
                    read_file, 
                    change_directory,
                    read_data_from_url, 
                    exa_search_tool
                    ]
            )

def callAgent(
    prompt: str,
    message_history: List[ModelMessage] | None = None,
    deps: Deps | None = None,
    ) -> str:
    tool_error = None

    for attempt in range(1, TOOL_CALL_ERROR_MAX_RETRIES + 1):
        try:
            result = avcCodingAgent.run_sync(
                prompt, message_history=message_history, deps=deps
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