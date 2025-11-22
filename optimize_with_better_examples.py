"""Improved DSPy optimizer with correct SQL examples."""

import dspy
from agent.dspy_signatures import NLtoSQLModule
from agent.tools.sqlite_tool import SQLiteTool

# Setup
lm = dspy.LM(
    model='ollama/llama3.2:1b',
    api_base='http://localhost:11434',
    max_tokens=500,
    temperature=0.1
)
dspy.configure(lm=lm)

db_tool = SQLiteTool()
schema = db_tool.get_schema_summary()

# CORRECTED training examples with proper SQL
training_examples = [
    # Example 1: Top products by revenue
    dspy.Example(
        question="Top 3 products by total revenue all-time",
        db_schema=schema,
        constraints="Revenue = SUM(UnitPrice * Quantity * (1 - Discount))",
        sql='SELECT p.ProductName, SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) as revenue FROM Products p JOIN "Order Details" od ON p.ProductID = od.ProductID GROUP BY p.ProductID, p.ProductName ORDER BY revenue DESC LIMIT 3'
    ).with_inputs("question", "db_schema", "constraints"),
    
    # Example 2: Revenue by category with date filter
    dspy.Example(
        question="Total revenue from Beverages category in June 1997",
        db_schema=schema,
        constraints="Dates: 1997-06-01 to 1997-06-30. Category: Beverages",
        sql='SELECT SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) as revenue FROM "Order Details" od JOIN Products p ON od.ProductID = p.ProductID JOIN Categories c ON p.CategoryID = c.CategoryID JOIN Orders o ON od.OrderID = o.OrderID WHERE c.CategoryName = \'Beverages\' AND o.OrderDate BETWEEN \'1997-06-01\' AND \'1997-06-30\''
    ).with_inputs("question", "db_schema", "constraints"),
    
    # Example 3: Average Order Value with date filter
    dspy.Example(
        question="What was the Average Order Value in December 1997?",
        db_schema=schema,
        constraints="AOV = SUM(UnitPrice * Quantity * (1 - Discount)) / COUNT(DISTINCT OrderID). Dates: 1997-12-01 to 1997-12-31",
        sql='SELECT CAST(SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) AS FLOAT) / COUNT(DISTINCT o.OrderID) as aov FROM Orders o JOIN "Order Details" od ON o.OrderID = od.OrderID WHERE o.OrderDate BETWEEN \'1997-12-01\' AND \'1997-12-31\''
    ).with_inputs("question", "db_schema", "constraints"),
    
    # Example 4: Category with highest quantity sold in date range
    dspy.Example(
        question="Which category had highest quantity sold in June 1997?",
        db_schema=schema,
        constraints="Dates: 1997-06-01 to 1997-06-30",
        sql='SELECT c.CategoryName, SUM(od.Quantity) as total_qty FROM Categories c JOIN Products p ON c.CategoryID = p.CategoryID JOIN "Order Details" od ON p.ProductID = od.ProductID JOIN Orders o ON od.OrderID = o.OrderID WHERE o.OrderDate BETWEEN \'1997-06-01\' AND \'1997-06-30\' GROUP BY c.CategoryID, c.CategoryName ORDER BY total_qty DESC LIMIT 1'
    ).with_inputs("question", "db_schema", "constraints"),
    
    # Example 5: Customer by gross margin
    dspy.Example(
        question="Top customer by gross margin in 1997",
        db_schema=schema,
        constraints="Gross Margin = SUM((UnitPrice - 0.7*UnitPrice) * Quantity * (1 - Discount)). Year: 1997",
        sql='SELECT c.CompanyName as customer, SUM((od.UnitPrice - 0.7*od.UnitPrice) * od.Quantity * (1 - od.Discount)) as margin FROM Customers c JOIN Orders o ON c.CustomerID = o.CustomerID JOIN "Order Details" od ON o.OrderID = od.OrderID WHERE strftime(\'%Y\', o.OrderDate) = \'1997\' GROUP BY c.CustomerID, c.CompanyName ORDER BY margin DESC LIMIT 1'
    ).with_inputs("question", "db_schema", "constraints"),
    
    # Example 6: Simple count with date range
    dspy.Example(
        question="How many orders in June 1997?",
        db_schema=schema,
        constraints="Dates: 1997-06-01 to 1997-06-30",
        sql='SELECT COUNT(*) as order_count FROM Orders WHERE OrderDate BETWEEN \'1997-06-01\' AND \'1997-06-30\''
    ).with_inputs("question", "db_schema", "constraints"),
]

# Test each example to ensure they work
print("Testing training examples...")
for i, ex in enumerate(training_examples, 1):
    result = db_tool.execute_query(ex.sql)
    if result["error"]:
        print(f"❌ Example {i} FAILED: {result['error']}")
        print(f"   SQL: {ex.sql[:80]}...")
    else:
        print(f"✅ Example {i} OK: {len(result['rows'])} rows")

print("\n" + "="*60)
print("Training DSPy module with corrected examples...")
print("="*60)

# Optimize
def validate_sql(example, pred, trace=None):
    """Check if SQL executes successfully."""
    try:
        result = db_tool.execute_query(pred.sql)
        return result["error"] is None and len(result.get("rows", [])) > 0
    except:
        return False

# Use BootstrapFewShot with our good examples
optimizer = dspy.BootstrapFewShot(
    metric=validate_sql,
    max_bootstrapped_demos=5,
    max_labeled_demos=5
)

baseline_module = NLtoSQLModule()
optimized_module = optimizer.compile(
    baseline_module,
    trainset=training_examples
)

print("\n✅ Optimization complete!")
print("Testing optimized module on sample queries...")

# Test optimized module
test_queries = [
    ("Top 3 products by revenue", "Revenue calculation"),
    ("Revenue from Beverages in June 1997", "Date filtering and category"),
    ("Average order value in December 1997", "AOV calculation"),
]

for question, desc in test_queries:
    sql = optimized_module.forward(
        question=question,
        schema=schema,
        constraints=desc
    )
    result = db_tool.execute_query(sql)
    
    if result["error"]:
        print(f"\n❌ {question}")
        print(f"   Error: {result['error']}")
        print(f"   SQL: {sql[:100]}...")
    else:
        print(f"\n✅ {question}")
        print(f"   Rows: {len(result['rows'])}")
        print(f"   SQL: {sql[:100]}...")

# Save optimized module
optimized_module.save("optimized_nl_to_sql_v2.json")
print("\n✅ Saved optimized module to optimized_nl_to_sql_v2.json")
print("\nTo use this, update graph_hybrid.py to load this optimized module.")