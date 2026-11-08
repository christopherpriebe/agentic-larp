"""The agent wall and the widgets that fill its regions."""

from agentic_larp._draw import render_entry
from agentic_larp._grid import Grid
from agentic_larp._wall import SPOTLIGHT_HOLD, Wall
from agentic_larp._widgets import (
    REGIONS,
    WIDGET_ENTRY_POINT_GROUP,
    AgentPanel,
    FooterWidget,
    HeaderWidget,
    PanelWidget,
    QuestionWidget,
    SwarmWidget,
    Widget,
    widget_registry,
)

__all__ = [
    "REGIONS",
    "SPOTLIGHT_HOLD",
    "WIDGET_ENTRY_POINT_GROUP",
    "AgentPanel",
    "FooterWidget",
    "Grid",
    "HeaderWidget",
    "PanelWidget",
    "QuestionWidget",
    "SwarmWidget",
    "Wall",
    "Widget",
    "render_entry",
    "widget_registry",
]
