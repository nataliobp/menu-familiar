# F01-UC01 — Create a weekly menu on its first edit

**Status:** V2.2 replaces explicit creation from V1.

Opening a missing current or future week presents seven days of pending lunch and dinner slots with current suggestions. Viewing, opening a picker, changing a filter and searching leave storage untouched. A missing historical week is read-only.

The picker submits version 0 for a virtual week. A first assignment or skip creates the Monday root and all fourteen positions and commits the requested mutation in the same transaction. Only one first edit can win. A stale or replayed version 0 requires reviewing the saved week. Validation, snapshot or persistence failure rolls the whole operation back.

See the [persistence contract](../04-persistence.md#concurrency-and-atomicity) and [V2.2 product corrections](../V2.1-V2.2.md).
