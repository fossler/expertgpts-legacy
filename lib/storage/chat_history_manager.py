"""Chat history persistence manager for ExpertGPTs.

This module provides file-based persistence for chat conversations,
ensuring that chat history survives app restarts and is automatically
managed with size-based truncation.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from lib.storage.attachment_store import delete_expert_attachments

# Optional per-message fields kept alongside role/content: which provider and
# model produced an assistant answer (used for its avatar) and when the
# message was first saved
OPTIONAL_MESSAGE_FIELDS = ("provider", "model", "timestamp")


def assistant_message(content: str, provider: str, model: str) -> Dict:
    """Build an assistant message that records which LLM produced it.

    Args:
        content: Message text
        provider: Provider key (e.g. "openai")
        model: Model ID (e.g. "gpt-6.1-sol")

    Returns:
        dict: Message for the chat history
    """
    return {
        "role": "assistant",
        "content": content,
        "provider": provider,
        "model": model,
    }


def _copy_message(msg: Dict) -> Dict:
    """Copy role, content and the optional fields of a message."""
    copied = {"role": msg["role"], "content": msg["content"]}
    for field in OPTIONAL_MESSAGE_FIELDS:
        if msg.get(field):
            copied[field] = msg[field]
    return copied


from lib.shared.file_ops import ensure_directory_exists, get_project_root
from lib.shared.format_ops import read_json, write_json

# Default maximum chat history file size (1 MB)
DEFAULT_MAX_FILE_SIZE_MB = 1

# Minimum messages to preserve even if over size limit
MINIMUM_MESSAGES_PRESERVE = 10

# Chat history directory name
CHAT_HISTORY_DIR = "chat_history"


def get_chat_history_dir() -> Path:
    """Get the path to the chat history directory.

    Returns:
        Path: Path to chat_history/ directory in project root
    """
    return get_project_root() / CHAT_HISTORY_DIR


def ensure_chat_history_dir_exists() -> Path:
    """Ensure the chat_history directory exists with secure permissions.

    Creates the directory if it doesn't exist.

    Returns:
        Path: Path to chat_history directory
    """
    chat_dir = get_chat_history_dir()
    return ensure_directory_exists(chat_dir, permissions=0o700)


def get_chat_history_path(expert_id: str) -> Path:
    """Get the path to a specific expert's chat history file.

    Args:
        expert_id: Unique expert identifier (e.g., "1001_python_expert")

    Returns:
        Path: Path to {expert_id}.json in chat_history directory
    """
    ensure_chat_history_dir_exists()
    chat_dir = get_chat_history_dir()
    return chat_dir / f"{expert_id}.json"


def load_chat_history(expert_id: str) -> List[Dict]:
    """Load chat history for a specific expert from file.

    This function is fault-tolerant:
    - Returns empty list if file doesn't exist
    - Returns empty list if file is corrupted (JSON decode error)
    - Logs warnings for errors but doesn't raise exceptions

    Args:
        expert_id: Unique expert identifier

    Returns:
        List[Dict]: List of messages with role and content
                  Returns empty list on any error
    """
    chat_path = get_chat_history_path(expert_id)

    # Use shared read_json function (handles errors, returns None if missing/corrupted)
    data = read_json(chat_path)

    if data is None:
        # No history file or corrupted file - this is normal for new experts
        return []

    # Validate structure
    if not isinstance(data, dict):
        print(f"Warning: Invalid chat history structure for {expert_id}")
        return []

    messages = data.get("messages", [])

    # Validate messages list
    if not isinstance(messages, list):
        print(f"Warning: Invalid messages format for {expert_id}")
        return []

    # Ensure each message has required fields
    validated_messages = []
    for msg in messages:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            validated_messages.append(_copy_message(msg))

    return validated_messages


def save_chat_history(expert_id: str, messages: List[Dict]) -> bool:
    """Save chat history for a specific expert to file.

    Automatically truncates history if file size exceeds limit.
    Adds a timestamp to each message that has none. The timestamp is also
    set on the passed message itself, so later saves keep it.

    Args:
        expert_id: Unique expert identifier
        messages: List of messages to save

    Returns:
        bool: True if save was successful, False otherwise
    """
    chat_path = get_chat_history_path(expert_id)

    try:
        # Ensure directory exists
        ensure_chat_history_dir_exists()

        # Add timestamps to messages if not present
        timestamped_messages = []
        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                msg.setdefault("timestamp", datetime.now().isoformat())
                timestamped_messages.append(_copy_message(msg))

        # Create file structure
        file_data = {
            "expert_id": expert_id,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "messages": timestamped_messages,
        }

        # If file exists, preserve created_at timestamp (using shared read_json)
        if chat_path.exists():
            existing_data = read_json(chat_path)
            if existing_data and "created_at" in existing_data:
                file_data["created_at"] = existing_data["created_at"]

        # Truncate if needed (checks size internally)
        file_data["messages"] = truncate_messages_by_size(
            file_data["messages"], expert_id, DEFAULT_MAX_FILE_SIZE_MB
        )

        # Write using shared function (handles permissions and encoding)
        return write_json(chat_path, file_data, indent=2)

    except Exception as e:
        print(f"Warning: Error saving chat history for {expert_id}: {e}")
        return False


def truncate_messages_by_size(
    messages: List[Dict], expert_id: str, max_size_mb: int
) -> List[Dict]:
    """Truncate messages list to fit within size limit.

    Removes oldest messages first, but always preserves at least
    MINIMUM_MESSAGES_PRESERVE messages even if over size limit.

    Uses average message size for efficient binary search (O(n))
    instead of serializing JSON on every iteration (O(n²)).

    Args:
        messages: List of message dictionaries with timestamps
        expert_id: Expert ID for file path calculation
        max_size_mb: Maximum file size in MB

    Returns:
        List[Dict]: Truncated messages list
    """
    # Always preserve minimum messages
    if len(messages) <= MINIMUM_MESSAGES_PRESERVE:
        return messages

    # Calculate base size (file structure without messages)
    base_data = {
        "expert_id": expert_id,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "messages": [],
    }
    base_size = len(json.dumps(base_data, indent=2, ensure_ascii=False).encode("utf-8"))
    base_size_mb = base_size / (1024 * 1024)

    # If even base structure exceeds limit, return minimum messages
    if base_size_mb >= max_size_mb:
        return messages[-MINIMUM_MESSAGES_PRESERVE:]

    max_size_bytes = max_size_mb * (1024 * 1024)
    available_bytes = max_size_bytes - base_size

    # Pre-calculate average message size once (O(n))
    total_msg_size = sum(
        len(json.dumps(msg, ensure_ascii=False).encode("utf-8")) for msg in messages
    )
    avg_msg_size = total_msg_size / len(messages)

    # Quick check: if all messages fit, return as-is
    if base_size + total_msg_size <= max_size_bytes:
        return messages

    # Binary search using estimation (O(log n))
    low = MINIMUM_MESSAGES_PRESERVE
    high = len(messages)
    optimal_count = low

    while low <= high:
        mid = (low + high) // 2
        estimated_size = base_size + (avg_msg_size * mid)

        if estimated_size <= max_size_bytes:
            optimal_count = mid
            low = mid + 1
        else:
            high = mid - 1

    # Return most recent messages
    return messages[-optimal_count:]


def delete_chat_history(expert_id: str) -> bool:
    """Delete chat history file for a specific expert.

    Args:
        expert_id: Unique expert identifier

    Returns:
        bool: True if deleted (or didn't exist), False on error
    """
    chat_path = get_chat_history_path(expert_id)

    try:
        if chat_path.exists():
            chat_path.unlink()
        delete_expert_attachments(expert_id)
        return True
    except Exception as e:
        print(f"Warning: Error deleting chat history for {expert_id}: {e}")
        return False
