"""Autonomous self-evolution and codebase introspection module."""
from __future__ import annotations

from .introspector import CodebaseIntrospector, CodebaseMap, ModuleSummary
from .safety import SafetyGatekeeper, SafetyViolation
from .architect import SelfArchitectAgent, EvolutionProposal
from .engine import AutonomousEvolutionEngine, EvolutionCycleReport, EvolutionReport

__all__ = [
    "CodebaseIntrospector",
    "CodebaseMap",
    "ModuleSummary",
    "SafetyGatekeeper",
    "SafetyViolation",
    "SelfArchitectAgent",
    "EvolutionProposal",
    "AutonomousEvolutionEngine",
    "EvolutionCycleReport",
    "EvolutionReport",
]
