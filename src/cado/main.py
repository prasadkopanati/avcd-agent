from agent import callAgent
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter 
from prompt_toolkit.history import FileHistory 
from dataclasses import dataclass
from typing import List
import os
from pydantic_ai import ModelMessage
from agent import MODEL_NAME, Deps
from ui import UI

PROMPT_HISTORY_PATH=os.path.expanduser("~/.avcdagent_history")

@dataclass
class AppState:
    model_name: str = MODEL_NAME
    approval_mode:bool = False # False = YOLOM, True = Human approval
    history: List[ModelMessage] | None = None

class AbortGeneration(Exception):
    pass

def main():

    # Prompt Session
    os.makedirs(os.path.dirname(PROMPT_HISTORY_PATH), exist_ok=True)
    history = FileHistory(PROMPT_HISTORY_PATH)
    completer = WordCompleter([], ignore_case=True)
    session = PromptSession(history=history, completer=completer)

    # Initialize AppState
    state = AppState()
    state.model_name = MODEL_NAME
    state.history = []

    # UI
    ui = UI.make()

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

        # show UI with user input
        #ui.user_box(user_input)

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
                deps=Deps(approval_mode=state.approval_mode, approve=approve, ui=ui, timeout=None)

                result = callAgent(user_input, message_history=state.history, deps=deps)

                messages = result.all_messages()

                # Show all text parts of the messages
                model_texts: list[str] = []
                for m in messages:
                    if getattr(m, "kind", None) == "response":
                        for p in m.parts:
                            if getattr(p, "part_kind", None) == "text" and p.content:
                                model_texts.append(p.content)
                if model_texts:
                    #ui.model_box("\n\n".join(model_texts))
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
