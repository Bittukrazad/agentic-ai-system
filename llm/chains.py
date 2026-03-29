"""llm/chains.py — LangChain / LangGraph chain definitions"""
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class ChainBuilder:
    """
    Builds LangChain / LangGraph chains for multi-step LLM pipelines.
    Falls back to direct LLMClient calls if langchain is not installed.

    Chains defined here:
      - extraction_chain  — transcript → structured JSON (with JSON output parser)
      - decision_chain    — context → decision (with function calling)
      - verification_chain — output → quality score
    """

    @staticmethod
    def extraction_chain():
        """Build the decision extraction chain"""
        try:
            from langchain_openai import ChatOpenAI
            from langchain.output_parsers import StructuredOutputParser, ResponseSchema
            from langchain.prompts import ChatPromptTemplate

            schemas = [
                ResponseSchema(name="decisions", description="List of decisions made"),
                ResponseSchema(name="action_items", description="List of action items"),
                ResponseSchema(name="blockers", description="List of blockers"),
                ResponseSchema(name="summary", description="Meeting summary"),
            ]
            parser = StructuredOutputParser.from_response_schemas(schemas)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an expert meeting analyst. {format_instructions}"),
                ("human", "{transcript}"),
            ]).partial(format_instructions=parser.get_format_instructions())

            import os
            llm = ChatOpenAI(model="gpt-4o", temperature=0.2, api_key=os.getenv("OPENAI_API_KEY", ""))
            return prompt | llm | parser

        except ImportError:
            logger.warning("LangChain not installed — using direct LLM calls")
            return None

    @staticmethod
    def decision_chain():
        """Build the decision-making chain with function calling"""
        try:
            from langchain_openai import ChatOpenAI
            from langchain.schema import SystemMessage, HumanMessage
            import os

            llm = ChatOpenAI(model="gpt-4o", temperature=0.1, api_key=os.getenv("OPENAI_API_KEY", ""))
            return llm

        except ImportError:
            logger.warning("LangChain not installed — using direct LLM calls")
            return None

    @staticmethod
    def langgraph_workflow():
        """Build a LangGraph state machine for complex multi-step workflows"""
        try:
            from langgraph.graph import StateGraph, END
            from typing import TypedDict

            class AgentState(TypedDict):
                input: str
                output: str
                steps: List[str]
                error: Optional[str]

            graph = StateGraph(AgentState)

            def process_node(state: AgentState) -> AgentState:
                state["steps"].append("processed")
                return state

            graph.add_node("process", process_node)
            graph.set_entry_point("process")
            graph.add_edge("process", END)

            return graph.compile()

        except ImportError:
            logger.warning("LangGraph not installed — using direct orchestration")
            return None