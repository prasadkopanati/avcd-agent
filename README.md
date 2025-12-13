# Project Documentation

## Overview

This project is a coding agent implementation following specific development guidelines outlined in `AGENTS.md`.

## Development Process

This project follows the development process defined in `AGENTS.md`:

- Always work in the `main` branch
- Commit frequently with clear and concise messages
- Use `author="AI <ai.agent@example.com>"` for all commits
- Consult documentation and conduct web searches when needed
- Work only in this directory/repo
- Manage environment using `uv`
- Test changes before committing

## Coding Style

The project follows these coding style guidelines:

- PEP8 for Python code
- Prioritize readability
- Write modular code
- Add concise but clear explanatory comments
- Use docstrings for functions, classes, and modules

## Project Structure

- `main.py` - Main entry point
- `agent.py` - Agent implementation
- `AGENTS.md` - Development instructions
- `pyproject.toml` - Project configuration
- `uv.lock` - Dependency lock file

## Getting Started

1. Ensure you have `uv` installed
2. Install dependencies: `uv sync`
3. Run the application: `python main.py`

## Development Guidelines

Refer to `AGENTS.md` for detailed development instructions and coding standards.

## Self-Healing Agent

Encode this policy in the system prompt and tool descriptions.

- If file not found → list directory
- If permission denied → try alternative path
- If API error → inspect error code and backoff

