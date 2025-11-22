"""Compare agent output with correct answers."""

import json
from rich.console import Console
from rich.table import Table

console = Console()

# Load both files
with open("outputs_hybrid.jsonl") as f:
    agent_outputs = [json.loads(line) for line in f if line.strip()]

try:
    with open("outputs_hybrid_CORRECT.jsonl") as f:
        correct_outputs = [json.loads(line) for line in f if line.strip()]
except FileNotFoundError:
    console.print("[yellow]Run: python get_correct_answers.py first![/yellow]")
    exit(1)

# Create comparison table
console.print("\n[bold cyan]Comparing Agent Output vs Correct Answers[/bold cyan]\n")

table = Table(show_header=True, header_style="bold cyan", show_lines=True)
table.add_column("#", width=3)
table.add_column("Question ID", width=35)
table.add_column("Agent Answer", width=25)
table.add_column("Correct Answer", width=25)
table.add_column("Match?", width=8)

# Create lookup
correct_dict = {o["id"]: o for o in correct_outputs}

matches = 0
for i, agent in enumerate(agent_outputs, 1):
    q_id = agent["id"]
    correct = correct_dict.get(q_id, {})
    
    agent_ans = str(agent["final_answer"])[:23]
    correct_ans = str(correct.get("final_answer", "N/A"))[:23]
    
    # Check if match
    match = agent["final_answer"] == correct.get("final_answer")
    if match:
        matches += 1
        status = "[green]✓[/green]"
    else:
        status = "[red]✗[/red]"
    
    table.add_row(
        str(i),
        q_id[:35],
        agent_ans,
        correct_ans,
        status
    )

console.print(table)

# Detailed comparison
console.print("\n[bold]Detailed Analysis:[/bold]\n")

for i, agent in enumerate(agent_outputs, 1):
    q_id = agent["id"]
    correct = correct_dict.get(q_id, {})
    
    match = agent["final_answer"] == correct.get("final_answer")
    
    if not match:
        console.print(f"[bold red]❌ Question {i}: {q_id}[/bold red]")
        console.print(f"   Agent:   {agent['final_answer']}")
        console.print(f"   Correct: {correct.get('final_answer')}")
        
        # Show SQL comparison
        if agent.get("sql") and correct.get("sql"):
            console.print(f"\n   [dim]Agent SQL:[/dim]")
            console.print(f"   [dim]{agent['sql'][:100]}...[/dim]")
            console.print(f"\n   [dim]Correct SQL:[/dim]")
            console.print(f"   [dim]{correct['sql'][:100]}...[/dim]")
        
        console.print()

# Summary
console.print("\n[bold]Summary:[/bold]")
console.print(f"  Correct: [green]{matches}/{len(agent_outputs)}[/green]")
console.print(f"  Incorrect: [red]{len(agent_outputs) - matches}/{len(agent_outputs)}[/red]")
console.print(f"  Accuracy: [cyan]{matches/len(agent_outputs)*100:.1f}%[/cyan]")

if matches == 0:
    console.print("\n[bold red]⚠️  CRITICAL: Agent is generating completely wrong SQL![/bold red]")
    console.print("\n[yellow]Recommended fixes:[/yellow]")
    console.print("  1. Run: python optimize_with_better_examples.py")
    console.print("  2. Or manually fix SQL generation in graph_hybrid.py")
    console.print("  3. Check that Ollama model understands SQL syntax")
elif matches < len(agent_outputs):
    console.print("\n[yellow]⚠️  Some answers are incorrect. Review SQL queries above.[/yellow]")
else:
    console.print("\n[bold green]✅ All answers correct![/bold green]")