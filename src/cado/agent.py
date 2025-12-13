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
)

# Coonfigure logfire
logfire.configure()
logfire.instrument_pydantic_ai()

def list_directory(directory:str) -> list[str]:
    """
    List the contents of a directory
    """
    contents= os.listdir(directory)
    return contents

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
    try:
        with open(file_path, "r") as file:
            return file.read()
    except FileNotFoundError as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_file",
                error_type="FileNotFoundError",
                message=f"The file {file_path} does not exist. Use the list_directory tool to check the files in the directory and try again.",
                attempted_input={"file_path": file_path},
            ).model_dump_json()
        )
    except Exception as e:
        raise RuntimeError(
            ToolExecError(
                tool_name="read_file",
                error_type=type(e).__name__,
                message=f"An error occurred while reading the file {file_path}",
                attempted_input={"file_path": file_path},
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
                    list_directory, 
                    create_or_update_file, 
                    read_file, 
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
