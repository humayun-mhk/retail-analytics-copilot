"""Get correct answers by running proper SQL queries."""

import json
import sqlite3
from rich.console import Console
from rich.table import Table

console = Console()

# Connect to database
conn = sqlite3.connect("data/northwind.sqlite")
cursor = conn.cursor()

console.print("\n[bold cyan]Getting Correct Answers[/bold cyan]\n")

# Question 1: RAG only - return days for beverages
answer1 = 14  # From product_policy.md
console.print("[green]✓[/green] Q1 (RAG): Beverages return days = [bold]14[/bold]")

# Question 2: Top category by quantity in Summer 1997 (June 1997)
sql2 = '''
SELECT c.CategoryName, SUM(od.Quantity) as total_qty
FROM Categories c
JOIN Products p ON c.CategoryID = p.CategoryID
JOIN "Order Details" od ON p.ProductID = od.ProductID
JOIN Orders o ON od.OrderID = o.OrderID
WHERE o.OrderDate BETWEEN '1997-06-01' AND '1997-06-30'
GROUP BY c.CategoryID, c.CategoryName
ORDER BY total_qty DESC
LIMIT 1
'''
cursor.execute(sql2)
result2 = cursor.fetchone()
answer2 = {"category": result2[0], "quantity": result2[1]} if result2 else {}
console.print(f"[green]✓[/green] Q2 (Hybrid): Top category Summer 1997 = [bold]{answer2}[/bold]")

# Question 3: AOV in Winter 1997 (December 1997)
sql3 = '''
SELECT 
    CAST(SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) AS FLOAT) / 
    COUNT(DISTINCT o.OrderID) as aov
FROM Orders o
JOIN "Order Details" od ON o.OrderID = od.OrderID
WHERE o.OrderDate BETWEEN '1997-12-01' AND '1997-12-31'
'''
cursor.execute(sql3)
result3 = cursor.fetchone()
answer3 = round(result3[0], 2) if result3 and result3[0] else 0.0
console.print(f"[green]✓[/green] Q3 (Hybrid): AOV Winter 1997 = [bold]${answer3}[/bold]")

# Question 4: Top 3 products by revenue all-time
sql4 = '''
SELECT p.ProductName, 
       SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) as revenue
FROM Products p
JOIN "Order Details" od ON p.ProductID = od.ProductID
GROUP BY p.ProductID, p.ProductName
ORDER BY revenue DESC
LIMIT 3
'''
cursor.execute(sql4)
result4 = cursor.fetchall()
answer4 = [{"product": row[0], "revenue": round(row[1], 2)} for row in result4]
console.print(f"[green]✓[/green] Q4 (SQL): Top 3 products by revenue:")
for i, item in enumerate(answer4, 1):
    console.print(f"   {i}. {item['product']}: ${item['revenue']}")

# Question 5: Revenue from Beverages in Summer 1997 (June 1997)
sql5 = '''
SELECT SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) as revenue
FROM "Order Details" od
JOIN Products p ON od.ProductID = p.ProductID
JOIN Categories c ON p.CategoryID = c.CategoryID
JOIN Orders o ON od.OrderID = o.OrderID
WHERE c.CategoryName = 'Beverages'
  AND o.OrderDate BETWEEN '1997-06-01' AND '1997-06-30'
'''
cursor.execute(sql5)
result5 = cursor.fetchone()
answer5 = round(result5[0], 2) if result5 and result5[0] else 0.0
console.print(f"[green]✓[/green] Q5 (Hybrid): Beverages revenue Summer 1997 = [bold]${answer5}[/bold]")

# Question 6: Top customer by gross margin in 1997
sql6 = '''
SELECT c.CompanyName as customer,
       SUM((od.UnitPrice - 0.7*od.UnitPrice) * od.Quantity * (1 - od.Discount)) as margin
FROM Customers c
JOIN Orders o ON c.CustomerID = o.CustomerID
JOIN "Order Details" od ON o.OrderID = od.OrderID
WHERE strftime('%Y', o.OrderDate) = '1997'
GROUP BY c.CustomerID, c.CompanyName
ORDER BY margin DESC
LIMIT 1
'''
cursor.execute(sql6)
result6 = cursor.fetchone()
answer6 = {"customer": result6[0], "margin": round(result6[1], 2)} if result6 else {}
console.print(f"[green]✓[/green] Q6 (Hybrid): Top customer by margin 1997 = [bold]{answer6}[/bold]")

conn.close()

# Create correct output file
correct_outputs = [
    {
        "id": "rag_policy_beverages_return_days",
        "final_answer": answer1,
        "sql": "",
        "confidence": 1.0,
        "explanation": "Answer extracted from product_policy.md document.",
        "citations": ["product_policy::chunk1"]
    },
    {
        "id": "hybrid_top_category_qty_summer_1997",
        "final_answer": answer2,
        "sql": sql2.strip(),
        "confidence": 0.95,
        "explanation": "Computed from database with date range from marketing calendar.",
        "citations": ["marketing_calendar::chunk0", "Categories", "Products", "Order Details", "Orders"]
    },
    {
        "id": "hybrid_aov_winter_1997",
        "final_answer": answer3,
        "sql": sql3.strip(),
        "confidence": 0.95,
        "explanation": "Computed AOV using KPI definition and Winter 1997 dates.",
        "citations": ["kpi_definitions::chunk0", "marketing_calendar::chunk2", "Orders", "Order Details"]
    },
    {
        "id": "sql_top3_products_by_revenue_alltime",
        "final_answer": answer4,
        "sql": sql4.strip(),
        "confidence": 1.0,
        "explanation": "Computed from database query returning 3 rows.",
        "citations": ["Products", "Order Details"]
    },
    {
        "id": "hybrid_revenue_beverages_summer_1997",
        "final_answer": answer5,
        "sql": sql5.strip(),
        "confidence": 0.95,
        "explanation": "Computed revenue from Beverages using Summer 1997 dates.",
        "citations": ["marketing_calendar::chunk0", "Categories", "Products", "Order Details", "Orders"]
    },
    {
        "id": "hybrid_best_customer_margin_1997",
        "final_answer": answer6,
        "sql": sql6.strip(),
        "confidence": 0.95,
        "explanation": "Computed gross margin using 70% cost approximation.",
        "citations": ["kpi_definitions::chunk1", "Customers", "Orders", "Order Details"]
    }
]

# Save correct answers
with open("outputs_hybrid_CORRECT.jsonl", "w") as f:
    for output in correct_outputs:
        f.write(json.dumps(output) + "\n")

console.print("\n[bold green]✅ Correct answers saved to outputs_hybrid_CORRECT.jsonl[/bold green]")

# Summary table
console.print("\n[bold]Summary of Correct Answers:[/bold]\n")
table = Table(show_header=True, header_style="bold cyan")
table.add_column("#", width=3)
table.add_column("Question", width=40)
table.add_column("Answer", width=30)

questions_summary = [
    ("Beverages return days", str(answer1)),
    ("Top category Summer 97", answer2.get("category", "N/A")),
    ("AOV Winter 97", f"${answer3}"),
    ("Top 3 products", f"{len(answer4)} products"),
    ("Beverages revenue Summer 97", f"${answer5}"),
    ("Top customer margin", answer6.get("customer", "N/A")[:20]),
]

for i, (q, a) in enumerate(questions_summary, 1):
    table.add_row(str(i), q, a)

console.print(table)

console.print("\n[yellow]Compare these with your outputs_hybrid.jsonl to see the difference![/yellow]")