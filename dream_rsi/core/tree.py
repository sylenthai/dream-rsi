from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    id: str
    parent_id: str | None
    depth: int
    created_order: int
    score: float | None = None
    success: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)


class DiscoveryTree:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {
            "root": Node("root", None, 0, 0)
        }
        self._counter = 0

    def add_child(self, parent_id: str, score: float, success: bool = True,
                  diagnostics: dict[str, Any] | None = None) -> Node:
        if parent_id not in self.nodes:
            raise KeyError(parent_id)
        self._counter += 1
        node_id = f"n{self._counter}"
        parent = self.nodes[parent_id]
        node = Node(node_id, parent_id, parent.depth + 1, self._counter,
                    score, success, diagnostics or {})
        self.nodes[node_id] = node
        parent.children.append(node_id)
        return node

    def leaves(self) -> list[str]:
        return [n.id for n in self.nodes.values() if not n.children]

    def eligible(self) -> list[str]:
        # Paper: root plus current leaves.
        return ["root", *self.leaves()]

    def best_score(self) -> float:
        scores = [n.score for n in self.nodes.values() if n.score is not None]
        return max(scores) if scores else float("-inf")

    def clone_view(self) -> "TreeView":
        return TreeView(self)


class TreeView:
    """Prefix-observable view. Policies cannot inspect hidden/unrevealed nodes in replay."""
    def __init__(self, tree: DiscoveryTree, revealed: set[str] | None = None) -> None:
        self._tree = tree
        self.revealed = set(revealed) if revealed is not None else set(tree.nodes)

    def observed_nodes(self) -> list[Node]:
        return [self._tree.nodes[n] for n in self.revealed]

    def eligible(self) -> list[str]:
        if not self.revealed:
            return ["root"]
        result = ["root"] if "root" in self.revealed else []
        for node_id in self.revealed:
            node = self._tree.nodes[node_id]
            if not any(child in self.revealed for child in node.children):
                result.append(node_id)
        return list(dict.fromkeys(result))

    def best_score(self) -> float:
        scores = [n.score for n in self.observed_nodes() if n.score is not None]
        return max(scores) if scores else float("-inf")

    def node(self, node_id: str) -> Node:
        if node_id not in self.revealed:
            raise KeyError("unrevealed node")
        return self._tree.nodes[node_id]
