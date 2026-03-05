from agent import callAgent, OPENAI_COMPATIBLE_MODELS
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from dataclasses import dataclass
from typing import List
import os
import argparse
from pydantic_ai import ModelMessage
from agent import MODEL_NAME, Deps
from ui import UI

PROMPT_HISTORY_PATH = os.path.expanduser("~/.avcdagent_history")

@dataclass
class AppState:
    model_name: str = MODEL_NAME
    approval_mode: bool = False  # False = YOLO, True = Human approval
    history: List[ModelMessage] | None = None

class AbortGeneration(Exception):
    pass

def handle_models_command(state: AppState, ui: UI) -> None:
    """Display available OpenAI-compatible models and let the user switch."""
    models = list(OPENAI_COMPATIBLE_MODELS.items())
    ui.info("Available OpenAI-compatible models:")
    for i, (name, desc) in enumerate(models, 1):
        marker = "  <-- current" if name == state.model_name else ""
        ui.info(f"  {i}. {name}  —  {desc}{marker}")
    ui.info(f"\nCurrent model: {state.model_name}")
    ui.info("Enter a number to switch, or press Enter to cancel:")
    try:
        choice = input().strip()
    except (KeyboardInterrupt, EOFError):
        return
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            state.model_name = models[idx][0]
            ui.info(f"Switched to: {state.model_name}")
        else:
            ui.error(f"Invalid selection. Enter a number between 1 and {len(models)}.")

def main():
    # Parse optional CLI arguments
    parser = argparse.ArgumentParser(description="AVCD Coding Agent")
    parser.add_argument(
        "--model",
        default=None,
        metavar="MODEL_NAME",
        help=(
            "OpenAI-compatible model name to use (overrides MODEL_NAME env var). "
            f"Known models: {', '.join(OPENAI_COMPATIBLE_MODELS)}"
        ),
    )
    args = parser.parse_args()

    # Prompt Session
    os.makedirs(os.path.dirname(PROMPT_HISTORY_PATH), exist_ok=True)
    history = FileHistory(PROMPT_HISTORY_PATH)
    completer = WordCompleter([], ignore_case=True)
    session = PromptSession(history=history, completer=completer)

    # Initialize AppState — CLI --model arg takes precedence over env var
    state = AppState()
    if args.model:
        state.model_name = args.model
    state.history = []

    # UI
    ui = UI.make()

    if args.model:
        ui.info(f"Model set from CLI: {state.model_name}")

    while True:
        # Get user input
        try:
            user_input = session.prompt("> ")
        except KeyboardInterrupt:
            ui.info("Exiting...")
            break
        except EOFError:
            ui.info("EOFError detected. Exiting...")
            break

        if not user_input.strip():
            continue

        if user_input.lower() in ["exit", "q", "bye", "quit"]:
            ui.info("User requested exit. Exiting...")
            break

        # Handle /models slash command
        if user_input.strip().lower() == "/models":
            handle_models_command(state, ui)
            continue

        # If a tool call fails, analyze the error and retry with a corrected request.
        # Call Agent for a maximum of TOOL_CALL_MAX_RETRIES times
        try:
            with ui.thinking():
                # Define approval function
                def approve(name: str, args: dict) -> bool:
                    if not state.approval_mode:
                        return True
                    ui.info("Please approve or reject the following tool call:")
                    ui.info(f"Tool: {name}")
                    ui.info(f"Arguments: {args}")
                    try:
                        choice = input().strip().lower()
                    except KeyboardInterrupt:
                        return False
                    return choice in {"y", "yes"}

                # Get approval from the user
                deps = Deps(approval_mode=state.approval_mode, approve=approve, ui=ui, timeout=None)

                result = callAgent(
                    user_input,
                    message_history=state.history,
                    deps=deps,
                    model_name=state.model_name,
                )

                messages = result.all_messages()

                # Show all text parts of the messages
                model_texts: list[str] = []
                for m in messages:
                    if getattr(m, "kind", None) == "response":
                        for p in m.parts:
                            if getattr(p, "part_kind", None) == "text" and p.content:
                                model_texts.append(p.content)
                if model_texts:
                    ui.model_box(result.output)

                # Tools executed automatically by pydantic_ai;
                # Append to history
                if state.history:
                    try:
                        state.history = state.history + result.new_messages()
                    except Exception as e:
                        ui.error(f"Error appending new messages to history: {e}")
                        state.history = messages
                else:
                    state.history = messages

        except AbortGeneration:
            ui.info("AbortGeneration detected. Exiting...")
            continue
        except Exception as e:
            ui.error(f"The agent encountered an error: {e}")
            continue


if __name__ == "__main__":
    main()
