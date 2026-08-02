"""Wire and compile the supervisor graph (Session 14).

The topology is a STAR, which is what a supervisor system should look like when you
draw it — not a line with more boxes::

            START
              |
              v
       +-> supervisor --Command(goto)--+--> requirements_extractor --+
       |                               +--> budget_searcher ---------+
       |                               +--> estimate_generator ------+
       +-------- static return --------+--> coherence_validator -----+
         edges                         |
                                       +--> human_review_gate --> END

* **Dynamic edges** — the five ``supervisor -> {4 agents, gate}`` hand-overs. These do
  not exist in the graph definition at all: ``Command(goto=...)`` draws them at
  runtime. That is the point of the session.
* **Static edges** — ``START -> supervisor``, the four ``agent -> supervisor`` return
  edges, and ``human_review_gate -> END``. Six in total.

``END`` is reached through exactly one edge, whether the gate paused for a human or
fell straight through. One exit is much easier to reason about than two.

Note the gate returns a plain dict rather than a ``Command``. Mixing ``interrupt()``
with a ``Command`` return in one node is legal, but the resume path re-executes and
would have to reconstruct the same ``Command`` — one more thing to get wrong, for no
benefit when there is only one destination.
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, START, StateGraph

from app.domain.graph.supervisor.agents import (
    budget_searcher,
    coherence_validator,
    estimate_generator,
    requirements_extractor,
)
from app.domain.graph.supervisor.gate import human_review_gate
from app.domain.graph.supervisor.state import SupervisorState
from app.domain.graph.supervisor.supervisor import supervisor

log = structlog.get_logger()

AGENT_NODES = {
    "requirements_extractor": requirements_extractor,
    "budget_searcher": budget_searcher,
    "estimate_generator": estimate_generator,
    "coherence_validator": coherence_validator,
}


def build_supervisor_graph(checkpointer=None):
    """Build and compile the supervisor graph.

    ``checkpointer`` persists state per ``thread_id`` (an ``AsyncPostgresSaver`` in the
    app, a ``MemorySaver`` in tests). It is REQUIRED for the human gate to resume: a
    ``None`` checkpointer compiles fine but cannot pause and come back.
    """
    builder = StateGraph(SupervisorState)

    builder.add_node(
        "supervisor",
        supervisor,
        # Declared EXPLICITLY, not inferred. Every module here uses
        # ``from __future__ import annotations``, so a ``Command[Literal[...]]`` return
        # hint is a string at runtime and LangGraph's destination inference cannot be
        # relied on. Declaring them keeps compile-time validation and
        # ``get_graph().draw_mermaid()`` honest.
        destinations=(*AGENT_NODES, "human_review_gate"),
    )
    for name, fn in AGENT_NODES.items():
        builder.add_node(name, fn)
    builder.add_node("human_review_gate", human_review_gate)

    builder.add_edge(START, "supervisor")
    for name in AGENT_NODES:
        # Every specialist hands control BACK to the router. These return edges are
        # what make the graph cyclic — and what make the step budget mandatory.
        builder.add_edge(name, "supervisor")
    builder.add_edge("human_review_gate", END)

    return builder.compile(checkpointer=checkpointer)
