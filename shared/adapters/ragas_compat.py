"""Compat shims for ragas imports on newer langchain-community."""

from __future__ import annotations

import sys
import types


def ensure_ragas_imports() -> None:
    """Stub removed Vertex chat model module so ragas can import."""
    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    try:
        __import__(module_name)
        return
    except ModuleNotFoundError:
        pass

    stub = types.ModuleType(module_name)

    class ChatVertexAI:  # noqa: D101 - ragas only needs the symbol at import time
        pass

    stub.ChatVertexAI = ChatVertexAI
    sys.modules[module_name] = stub
