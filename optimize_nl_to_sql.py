
"""DSPy optimization script for NL→SQL module."""

import dspy
from agent.dspy_signatures import NLtoSQLModule
from agent.tools.sqlite_tool import SQLiteTool


# Setup DSPy
lm = dspy.LM(
    model='ollama/llama3.2:1b',
    api_base='http://localhost:11434',
    max_tokens=500,
    temperature=0.1
)
dspy.configure(lm=lm)

# Get schema
db_tool = SQLiteTool()
schema = db_tool.get_schema_summary()


# Training examples for NL→SQL
training_examples = [
    dspy.Example(
        question="What are the top 3 products by revenue?",
        schema=schema,
        constraints="Revenue = SUM(UnitPrice * Quantity * (1 - Discount))",
        sql='SELECT p.ProductName, SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) as revenue FROM Products p JOIN "Order Details" od ON p.ProductID = od.ProductID GROUP BY p.ProductName ORDER BY revenue DESC LIMIT 3'
    ).with_inputs("question", "schema", "constraints"),
    
    dspy.Example(
        question="Total orders in June 1997",
        schema=schema,
        constraints="Dates: 1997-06-01 to 1997-06-30",
        sql="SELECT COUNT(*) FROM Orders WHERE OrderDate BETWEEN '1997-06-01' AND '1997-06-30'"
    ).with_inputs("question", "schema", "constraints"),
    
    dspy.Example(
        question="Which category had highest quantity sold?",
        schema=schema,
        constraints="Focus on Beverages category",
        sql='SELECT c.CategoryName, SUM(od.Quantity) as total_qty FROM Categories c JOIN Products p ON c.CategoryID = p.CategoryID JOIN "Order Details" od ON p.ProductID = od.ProductID GROUP BY c.CategoryName ORDER BY total_qty DESC LIMIT 1'
    ).with_inputs("question", "schema", "constraints"),
    
    dspy.Example(
        question="Average order value for December 1997",
        schema=schema,
        constraints="AOV = SUM(UnitPrice * Quantity * (1 - Discount)) / COUNT(DISTINCT OrderID). Dates: 1997-12-01 to 1997-12-31",
        sql='SELECT SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) / COUNT(DISTINCT o.OrderID) as aov FROM Orders o JOIN "Order Details" od ON o.OrderID = od.OrderID WHERE o.OrderDate BETWEEN \'1997-12-01\' AND \'1997-12-31\''
    ).with_inputs("question", "schema", "constraints"),
    
    dspy.Example(
        question="Revenue from Beverages category",
        schema=schema,
        constraints="Category: Beverages. Revenue calculation.",
        sql='SELECT SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) as revenue FROM "Order Details" od JOIN Products p ON od.ProductID = p.ProductID JOIN Categories c ON p.CategoryID = c.CategoryID WHERE c.CategoryName = \'Beverages\''
    ).with_inputs("question", "schema", "constraints"),
]


def validate_sql(example, pred, trace=None):
    """Validation function: check if generated SQL executes successfully."""
    try:
        result = db_tool.execute_query(pred.sql)
        return result["error"] is None
    except:
        return False


# Test baseline
print("Testing baseline NL→SQL module...")
baseline_module = NLtoSQLModule()
correct = 0
for ex in training_examples[:3]:  # Test on first 3
    pred = baseline_module.forward(
        question=ex.question,
        schema=ex.schema,
        constraints=ex.constraints
    )
    if validate_sql(ex, type('obj', (object,), {'sql': pred})()):
        correct += 1
baseline_accuracy = correct / 3
print(f"Baseline valid SQL rate: {baseline_accuracy:.1%}")


# Optimize using BootstrapFewShot
print("\nOptimizing with BootstrapFewShot...")
optimizer = dspy.BootstrapFewShot(
    metric=validate_sql,
    max_bootstrapped_demos=4,
    max_labeled_demos=4
)

optimized_module = optimizer.compile(
    NLtoSQLModule(),
    trainset=training_examples
)

# Test optimized
print("\nTesting optimized NL→SQL module...")
correct = 0
for ex in training_examples[:3]:
    pred = optimized_module.forward(
        question=ex.question,
        schema=ex.schema,
        constraints=ex.constraints
    )
    if validate_sql(ex, type('obj', (object,), {'sql': pred})()):
        correct += 1
optimized_accuracy = correct / 3
print(f"Optimized valid SQL rate: {optimized_accuracy:.1%}")

print(f"\n✓ Improvement: {baseline_accuracy:.1%} → {optimized_accuracy:.1%} (+{(optimized_accuracy-baseline_accuracy):.1%})")

# Save optimized module
optimized_module.save("optimized_nl_to_sql.json")
print("\n✓ Saved optimized module to optimized_nl_to_sql.json")