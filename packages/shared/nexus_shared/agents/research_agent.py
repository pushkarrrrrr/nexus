"""ResearchAgent specializing in hybrid Vector + Knowledge Graph context retrieval."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.agents.base import AgentStepResult, BaseAgent
from packages.shared.nexus_shared.knowledge.rag import get_rag_engine
from packages.types.nexus_types.schemas import (
    AgentType,
    PlanStep,
    RAGQueryRequest,
)


class ResearchAgent(BaseAgent):
    """Specialized agent for grounded research across semantic memory and knowledge graph."""

    def __init__(self) -> None:
        super().__init__(
            agent_type=AgentType.RESEARCH,
            name="Research Agent",
            description="Executes grounded semantic retrieval across personal knowledge, indexed vectors, and graph relations.",
            allowed_tools=["vector_search", "graph_retrieval", "source_attributor"],
            assigned_model="gpt-4o",
        )
        self.rag_engine = get_rag_engine()

    async def run(
        self,
        step: PlanStep,
        context: dict[str, Any],
        user_id: str,
        db: AsyncSession,
    ) -> AgentStepResult:
        """Execute grounded research for the given step."""
        query_text = step.description
        if "query" in context:
            query_text = str(context["query"])

        self.logger.info("research_executing_rag", query=query_text, user_id=user_id)

        try:
            rag_req = RAGQueryRequest(
                query=query_text,
                max_context_chunks=context.get("top_k", 3),
                include_graph=True,
            )
            rag_response = await self.rag_engine.execute_rag_query(db, user_id, rag_req)

            citations = [c.model_dump() for c in rag_response.supporting_sources]
            triples = [t.model_dump() for t in rag_response.graph_triples]

            return AgentStepResult(
                success=True,
                result_payload={
                    "answer": rag_response.answer,
                    "citations_count": len(citations),
                    "citations": citations,
                    "graph_triples": triples,
                    "tokens_used": rag_response.tokens_used,
                },
                tokens_used=rag_response.tokens_used,
            )

        except Exception as exc:  # noqa: BLE001
            self.logger.error("research_agent_failed", error=str(exc))
            return AgentStepResult(
                success=False,
                error_message=f"Research agent retrieval failed: {exc}",
            )
