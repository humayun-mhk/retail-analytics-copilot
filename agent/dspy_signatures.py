"""DSPy Signatures and Modules for the Retail Analytics Copilot."""

import dspy
from typing import Literal


class RouteQuery(dspy.Signature):
    """Classify whether a query needs RAG, SQL, or both (hybrid)."""
    
    question: str = dspy.InputField(desc="User's retail analytics question")
    route: Literal["rag", "sql", "hybrid"] = dspy.OutputField(
        desc="'rag' if only docs needed, 'sql' if only DB needed, 'hybrid' if both"
    )


class GenerateSQL(dspy.Signature):
    """Generate SQLite query from natural language question and schema."""
    
    question: str = dspy.InputField(desc="Natural language question")
    db_schema: str = dspy.InputField(desc="Database schema with table and column info")
    constraints: str = dspy.InputField(desc="Extracted constraints like dates, categories, KPIs")
    sql: str = dspy.OutputField(
        desc="Valid SQLite query. Use exact table/column names from schema. No markdown."
    )


class SynthesizeAnswer(dspy.Signature):
    """Synthesize final answer from SQL results and/or retrieved docs."""
    
    question: str = dspy.InputField(desc="Original question")
    format_hint: str = dspy.InputField(desc="Expected output format (int, float, dict, list)")
    sql_results: str = dspy.InputField(desc="SQL query results as JSON, or empty")
    doc_chunks: str = dspy.InputField(desc="Retrieved document chunks with IDs, or empty")
    answer: str = dspy.OutputField(
        desc="Final answer matching format_hint exactly. Just the value, no explanation."
    )


class RouterModule(dspy.Module):
    """DSPy module for query routing."""
    
    def __init__(self):
        super().__init__()
        self.route = dspy.ChainOfThought(RouteQuery)
    
    def forward(self, question: str) -> str:
        result = self.route(question=question)
        return result.route


class NLtoSQLModule(dspy.Module):
    """DSPy module for NL to SQL conversion."""
    
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(GenerateSQL)
    
    def forward(self, question: str, schema: str, constraints: str) -> str:
        result = self.generate(
            question=question,
            db_schema=schema,
            constraints=constraints
        )
        # Clean up any markdown formatting
        sql = result.sql.strip()
        if sql.startswith("```sql"):
            sql = sql.replace("```sql", "").replace("```", "").strip()
        elif sql.startswith("```"):
            sql = sql.replace("```", "").strip()
        return sql


class SynthesizerModule(dspy.Module):
    """DSPy module for answer synthesis."""
    
    def __init__(self):
        super().__init__()
        self.synthesize = dspy.ChainOfThought(SynthesizeAnswer)
    
    def forward(self, question: str, format_hint: str, 
                sql_results: str, doc_chunks: str) -> str:
        result = self.synthesize(
            question=question,
            format_hint=format_hint,
            sql_results=sql_results,
            doc_chunks=doc_chunks
        )
        return result.answer.strip()