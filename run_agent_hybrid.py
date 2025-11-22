"""Main entrypoint for running the hybrid agent."""

import click
import json
import dspy
from pathlib import Path
from rich.console import Console
from rich.progress import track

from agent.dspy_signatures import RouterModule, NLtoSQLModule, SynthesizerModule
from agent.graph_hybrid import HybridAgent


console = Console()


def setup_dspy_lm():
    """Setup DSPy with local Ollama model."""
    model_name = "llama3.2:1b"  # Change this to your model
    
    console.print(f"[yellow]Attempting to connect to Ollama with model: {model_name}[/yellow]")
    
    # Try multiple connection methods
    methods = [
        # Method 1: dspy.LM with ollama prefix
        lambda: dspy.LM(
            model=f'ollama/{model_name}',
            api_base='http://localhost:11434',
            max_tokens=500,
            temperature=0.1
        ),
        # Method 2: OpenAI-compatible API
        lambda: dspy.OpenAI(
            model=model_name,
            api_base='http://localhost:11434/v1',
            api_key='ollama',
            max_tokens=500,
            temperature=0.1
        ),
        # Method 3: Try without prefix
        lambda: dspy.LM(
            model=model_name,
            api_base='http://localhost:11434',
            max_tokens=500,
            temperature=0.1
        ),
    ]
    
    for i, method in enumerate(methods, 1):
        try:
            console.print(f"[dim]Trying connection method {i}...[/dim]")
            lm = method()
            dspy.configure(lm=lm)
            
            # Test with a simple query
            console.print("[dim]Testing connection...[/dim]")
            test_module = dspy.ChainOfThought("question -> answer")
            result = test_module(question="What is 2+2?")
            
            console.print(f"[green]✓ Successfully connected using method {i}[/green]")
            return lm
        except Exception as e:
            console.print(f"[dim]Method {i} failed: {str(e)[:50]}...[/dim]")
            continue
    
    # If all methods fail
    console.print("[red]✗ Could not connect to Ollama[/red]")
    console.print("[yellow]Please ensure:[/yellow]")
    console.print("  1. Ollama is running: ollama serve")
    console.print(f"  2. Model is downloaded: ollama pull {model_name}")
    console.print("  3. Test manually: ollama run " + model_name)
    raise RuntimeError("Failed to connect to Ollama with any method")


@click.command()
@click.option('--batch', required=True, help='Input JSONL file with questions')
@click.option('--out', required=True, help='Output JSONL file for results')
def main(batch: str, out: str):
    """Run the Retail Analytics Copilot on a batch of questions."""
    
    console.print("[bold blue]🚀 Starting Retail Analytics Copilot[/bold blue]")
    
    # Setup DSPy
    console.print("[yellow]Setting up DSPy with Ollama...[/yellow]")
    lm = setup_dspy_lm()
    
    # Initialize DSPy modules
    router = RouterModule()
    nl_to_sql = NLtoSQLModule()
    synthesizer = SynthesizerModule()
    
    # Create agent
    console.print("[yellow]Building LangGraph agent...[/yellow]")
    agent = HybridAgent(router, nl_to_sql, synthesizer)
    
    # Load questions
    questions = []
    with open(batch, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:  # Skip empty lines
                continue
            try:
                questions.append(json.loads(line))
            except json.JSONDecodeError as e:
                console.print(f"[yellow]⚠ Skipping invalid JSON on line {line_num}: {e}[/yellow]")
                continue
    
    console.print(f"[green]Loaded {len(questions)} questions[/green]")
    
    # Process each question
    results = []
    for q in track(questions, description="Processing questions..."):
        console.print(f"\n[cyan]Question: {q['question']}[/cyan]")
        
        try:
            result = agent.run(q["question"], q["format_hint"])
            
            output = {
                "id": q["id"],
                "final_answer": result["final_answer"],
                "sql": result["sql"],
                "confidence": result["confidence"],
                "explanation": result["explanation"],
                "citations": result["citations"]
            }
            
            console.print(f"[green]✓ Answer: {result['final_answer']}[/green]")
            console.print(f"[dim]Confidence: {result['confidence']:.2f}[/dim]")
            
        except Exception as e:
            console.print(f"[red]✗ Error: {str(e)}[/red]")
            output = {
                "id": q["id"],
                "final_answer": None,
                "sql": "",
                "confidence": 0.0,
                "explanation": f"Error: {str(e)}",
                "citations": []
            }
        
        results.append(output)
    
    # Write results
    with open(out, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')
    
    console.print(f"\n[bold green]✓ Results written to {out}[/bold green]")


if __name__ == "__main__":
    main()