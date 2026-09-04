from __future__ import annotations


class SessionHistory:
    def __init__(self, limit: int = 25) -> None:
        self.limit = limit
        self._items: list[str] = []
        self._cursor = 0
        self._draft = ""

    @property
    def items(self) -> tuple[str, ...]:
        return tuple(self._items)

    def add(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if not self._items or self._items[-1] != text:
            self._items.append(text)
            self._items = self._items[-self.limit :]
        self.reset_navigation()

    def reset_navigation(self, draft: str = "") -> None:
        self._cursor = len(self._items)
        self._draft = draft

    def previous(self, current: str) -> str:
        if not self._items:
            return current
        if self._cursor == len(self._items):
            self._draft = current
        self._cursor = max(0, self._cursor - 1)
        return self._items[self._cursor]

    def next(self) -> str:
        if self._cursor >= len(self._items):
            return self._draft
        self._cursor += 1
        if self._cursor == len(self._items):
            return self._draft
        return self._items[self._cursor]

