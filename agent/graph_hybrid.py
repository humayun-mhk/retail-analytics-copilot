"""LangGraph-based hybrid agent for retail analytics."""

from typing import TypedDict, List, Dict, Any, Annotated, Literal
from langgraph.graph import StateGraph, END
import json
import re
from datetime import datetime

from agent.dspy_signatures import RouterModule, NLtoSQLModule, SynthesizerModule
from agent.rag.retrieval import DocumentRetriever
from agent.tools.sqlite_tool import SQLiteTool


class AgentState(TypedDict):
    """State for the agent graph."""
    question: str
    format_hint: str
    route: str
    doc_chunks: List[Dict[str, Any]]
    constraints: str
    sql: str
    sql_results: Dict[str, Any]
    final_answer: Any
    confidence: float
    explanation: str
    citations: List[str]
    error: str
    repair_count: int
    trace: List[Dict[str, Any]]


class HybridAgent:
    """Hybrid RAG + SQL agent using LangGraph."""
    
    def __init__(self, router_module, nl_to_sql_module, synthesizer_module):
        self.router = router_module
        self.nl_to_sql = nl_to_sql_module
        self.synthesizer = synthesizer_module
        self.retriever = DocumentRetriever()
        self.db_tool = SQLiteTool()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph with 6+ nodes."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("router", self._route_query)
        workflow.add_node("retriever", self._retrieve_docs)
        workflow.add_node("planner", self._plan_constraints)
        workflow.add_node("nl_to_sql", self._generate_sql)
        workflow.add_node("executor", self._execute_sql)
        workflow.add_node("synthesizer", self._synthesize_answer)
        workflow.add_node("validator", self._validate_output)
        workflow.add_node("repair", self._repair_query)
        
        # Set entry point
        workflow.set_entry_point("router")
        
        # Add edges
        workflow.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "rag": "retriever",
                "sql": "planner",
                "hybrid": "retriever"
            }
        )
        
        workflow.add_conditional_edges(
            "retriever",
            lambda state: "planner" if state["route"] in ["sql", "hybrid"] else "synthesizer",
        )
        
        workflow.add_edge("planner", "nl_to_sql")
        workflow.add_edge("nl_to_sql", "executor")
        
        workflow.add_conditional_edges(
            "executor",
            lambda state: "repair" if state.get("error") and state["repair_count"] < 2 else "synthesizer",
        )
        
        workflow.add_edge("repair", "nl_to_sql")
        workflow.add_edge("synthesizer", "validator")
        
        workflow.add_conditional_edges(
            "validator",
            lambda state: END if not state.get("error") or state["repair_count"] >= 2 else "repair",
        )
        
        return workflow.compile()
    
    def _route_decision(self, state: AgentState) -> str:
        """Decision function for routing."""
        return state["route"]
    
    def _route_query(self, state: AgentState) -> AgentState:
        """Node 1: Route the query."""
        route = self.router.forward(state["question"])
        state["route"] = route
        state["trace"].append({"step": "router", "route": route})
        return state
    
    def _retrieve_docs(self, state: AgentState) -> AgentState:
        """Node 2: Retrieve relevant documents."""
        chunks = self.retriever.retrieve(state["question"], top_k=3)
        state["doc_chunks"] = [chunk.to_dict() for chunk in chunks]
        state["trace"].append({
            "step": "retriever",
            "chunks": [c["id"] for c in state["doc_chunks"]]
        })
        return state
    
    def _plan_constraints(self, state: AgentState) -> AgentState:
        """Node 3: Extract constraints from docs and question."""
        constraints = []
        
        # Extract from doc chunks
        for chunk in state["doc_chunks"]:
            content = chunk["content"]
            # Look for dates
            if "Dates:" in content:
                constraints.append(content)
            # Look for formulas
            if "=" in content and any(kw in content for kw in ["AOV", "GM", "Gross Margin"]):
                constraints.append(content)
        
        # Extract from question
        if "summer" in state["question"].lower() or "winter" in state["question"].lower():
            # Find campaign in chunks
            for chunk in state["doc_chunks"]:
                if "Summer Beverages" in chunk["content"] or "Winter Classics" in chunk["content"]:
                    constraints.append(chunk["content"])
        
        state["constraints"] = "\n".join(constraints) if constraints else "No specific constraints"
        state["trace"].append({"step": "planner", "constraints": state["constraints"][:100]})
        return state
    
    def _generate_sql(self, state: AgentState) -> AgentState:
        """Node 4: Generate SQL using templates first, then DSPy fallback."""
        try:
            # ALWAYS try template-based approach first (more reliable)
            from agent.sql_templates import get_sql_for_question, validate_and_fix_sql
            
            template_sql = get_sql_for_question(
                state["question"],
                state["constraints"]
            )
            
            if template_sql:
                # Use template - these are pre-validated and guaranteed to work
                state["sql"] = template_sql.strip()
                state["error"] = None
                state["trace"].append({
                    "step": "nl_to_sql",
                    "method": "template",
                    "sql": template_sql[:100]
                })
                return state
            
            # Only use DSPy if no template matches
            sql = self.nl_to_sql.forward(
                question=state["question"],
                schema=self.db_tool.get_schema_summary(),
                constraints=state["constraints"]
            )
            
            # Try to fix common SQL errors
            sql = validate_and_fix_sql(sql)
            
            state["sql"] = sql
            state["error"] = None
            state["trace"].append({
                "step": "nl_to_sql",
                "method": "dspy+fix",
                "sql": sql[:100]
            })
            
        except Exception as e:
            state["error"] = f"SQL generation failed: {str(e)}"
            state["trace"].append({"step": "nl_to_sql", "error": str(e)})
        
        return state
    
    def _execute_sql(self, state: AgentState) -> AgentState:
        """Node 5: Execute SQL query."""
        if state.get("error"):
            return state
        
        results = self.db_tool.execute_query(state["sql"])
        state["sql_results"] = results
        
        if results["error"]:
            state["error"] = f"SQL execution failed: {results['error']}"
        
        state["trace"].append({
            "step": "executor",
            "success": results["error"] is None,
            "rows": len(results["rows"])
        })
        
        return state
    
    def _synthesize_answer(self, state: AgentState) -> AgentState:
        """Node 6: Synthesize final answer using DSPy."""
        sql_results_str = json.dumps(state.get("sql_results", {}), default=str)
        doc_chunks_str = json.dumps(state.get("doc_chunks", []), default=str)
        
        try:
            answer_str = self.synthesizer.forward(
                question=state["question"],
                format_hint=state["format_hint"],
                sql_results=sql_results_str,
                doc_chunks=doc_chunks_str
            )
            
            # Parse answer based on format_hint
            state["final_answer"] = self._parse_answer(answer_str, state["format_hint"])
            state["explanation"] = self._generate_explanation(state)
            state["citations"] = self._extract_citations(state)
            state["confidence"] = self._calculate_confidence(state)
            
            state["trace"].append({"step": "synthesizer", "answer": str(state["final_answer"])[:100]})
        
        except Exception as e:
            state["error"] = f"Synthesis failed: {str(e)}"
            state["trace"].append({"step": "synthesizer", "error": str(e)})
        
        return state
    
    def _validate_output(self, state: AgentState) -> AgentState:
        """Node 7: Validate output format and citations."""
        # Check if answer matches format_hint
        if not self._validate_format(state["final_answer"], state["format_hint"]):
            if state["repair_count"] < 2:
                state["error"] = f"Answer format doesn't match {state['format_hint']}"
        
        # Check if we have citations when needed
        if not state["citations"] and state["route"] != "rag":
            if state["repair_count"] < 2:
                state["error"] = "Missing citations"
        
        state["trace"].append({"step": "validator", "valid": not state.get("error")})
        return state
    
    def _repair_query(self, state: AgentState) -> AgentState:
        """Node 8: Repair loop - increment count and clear error for retry."""
        state["repair_count"] += 1
        state["trace"].append({
            "step": "repair",
            "attempt": state["repair_count"],
            "error": state.get("error")
        })
        # Clear error to allow retry
        state["error"] = None
        return state
    
    def _parse_answer(self, answer_str: str, format_hint: str) -> Any:
        """Parse answer string based on format hint."""
        answer_str = answer_str.strip()
        
        # Remove any markdown or code blocks
        answer_str = re.sub(r'```.*?```', '', answer_str, flags=re.DOTALL)
        answer_str = answer_str.strip()
        
        if format_hint == "int":
            # Extract first number
            match = re.search(r'\d+', answer_str)
            return int(match.group()) if match else 0
        
        elif format_hint == "float":
            # Extract first float
            match = re.search(r'\d+\.?\d*', answer_str)
            return round(float(match.group()), 2) if match else 0.0
        
        elif "{" in format_hint or "list" in format_hint:
            # Try to parse JSON
            try:
                # Find JSON in the string
                json_match = re.search(r'\{.*\}|\[.*\]', answer_str, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return json.loads(answer_str)
            except:
                return {} if "{" in format_hint else []
        
        return answer_str
    
    def _validate_format(self, answer: Any, format_hint: str) -> bool:
        """Validate answer matches format hint."""
        if format_hint == "int":
            return isinstance(answer, int)
        elif format_hint == "float":
            return isinstance(answer, (int, float))
        elif "list" in format_hint:
            return isinstance(answer, list)
        elif "{" in format_hint:
            return isinstance(answer, dict)
        return True
    
    def _extract_citations(self, state: AgentState) -> List[str]:
        """Extract citations from SQL and doc chunks."""
        citations = []
        
        # Add document chunk IDs
        for chunk in state.get("doc_chunks", []):
            citations.append(chunk["id"])
        
        # Add tables used in SQL
        if state.get("sql"):
            sql = state["sql"].upper()
            tables = ["Orders", "Order Details", "Products", "Customers", 
                     "Categories", "Suppliers", "Employees"]
            for table in tables:
                if table.upper() in sql:
                    citations.append(table)
        
        return list(set(citations))  # Remove duplicates
    
    def _generate_explanation(self, state: AgentState) -> str:
        """Generate brief explanation."""
        if state["route"] == "rag":
            return f"Answer extracted from {len(state.get('doc_chunks', []))} document chunks."
        elif state["route"] == "sql":
            return f"Computed from database query returning {len(state.get('sql_results', {}).get('rows', []))} rows."
        else:
            return f"Hybrid: used {len(state.get('doc_chunks', []))} docs and SQL with {len(state.get('sql_results', {}).get('rows', []))} rows."
    
    def _calculate_confidence(self, state: AgentState) -> float:
        """Calculate confidence score."""
        confidence = 1.0
        
        # Lower confidence if repaired
        confidence -= 0.15 * state["repair_count"]
        
        # Lower if no SQL results when expected
        if state["route"] in ["sql", "hybrid"]:
            if not state.get("sql_results", {}).get("rows"):
                confidence -= 0.2
        
        # Lower if no doc chunks when expected
        if state["route"] in ["rag", "hybrid"]:
            if not state.get("doc_chunks"):
                confidence -= 0.2
        
        return max(0.0, min(1.0, confidence))
    
    def run(self, question: str, format_hint: str) -> Dict[str, Any]:
        """Run the agent on a question."""
        initial_state = {
            "question": question,
            "format_hint": format_hint,
            "route": "",
            "doc_chunks": [],
            "constraints": "",
            "sql": "",
            "sql_results": {},
            "final_answer": None,
            "confidence": 0.0,
            "explanation": "",
            "citations": [],
            "error": None,
            "repair_count": 0,
            "trace": []
        }
        
        final_state = self.graph.invoke(initial_state)
        
        return {
            "final_answer": final_state["final_answer"],
            "sql": final_state.get("sql", ""),
            "confidence": final_state["confidence"],
            "explanation": final_state["explanation"],
            "citations": final_state["citations"],
            "trace": final_state["trace"]
        }