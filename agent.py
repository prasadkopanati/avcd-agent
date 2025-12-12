from typing import Any
from pydantic_ai import Agent 
from pydantic_ai.models.openai import OpenAIChatModel 
from pydantic_ai.providers.openai import OpenAIProvider
import os
import requests
from bs4 import BeautifulSoup
import logfire
from dataclasses import dataclass
from typing import Optional, Callable

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

llamacp_model = OpenAIChatModel(
    model_name=MODEL_NAME, 
    provider=OpenAIProvider(
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY
    )
)

SYSTEM_PROMPT = (
    "You are an AI Coding Agent\n"
    "Your goal is to act on user requests to write code.\n"
    "You will be given a user request and you will need to write the code to fulfill the request.\n"
    "You will be given a codebase and you will need to write the code to fulfill the request.\n"
    "You operate in a loop, repeatedly calling tools until you have completed the user request.\n"
    "You must explaing your thought process and the steps you are taking to complete the user request.\n"
    "You must use the provided tools to interact with the environment, specifically the file system."
    "If no function is available, then you can use your own knowledge and do not say anything about unavailable functions"
    "If you are asked to read an environment file and print the contents, then you should mask the passwords and other sensitive information."
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

def read_file(file_path:str) -> str:
    """
    Read the contents of a file
    """
    with open(file_path, "r") as file:
        return file.read()

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
    Read data from a URL based on the file extension
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
                tools=[list_directory, create_or_update_file, read_file, read_data_from_url]
            )

def callAgent(prompt: str) -> str:
    try:
        result = avcCodingAgent.run_sync(prompt)
        return result
    # Handle token limit errors
    except Exception as e:
        return f"Error: {e}"
