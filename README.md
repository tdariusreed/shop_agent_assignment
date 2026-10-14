
## Business case
A small mock online shop needs help with three tasks:
1. Look up an order.
2. Calculate a possible refund within strict limits.
3. Request a refund only after a human explicitly approves it.


## What is included
- `agent.py`: Ollama tool-using agent with baseline and hardened instruction sets.
- `test_prompts.json`: 12 fixed prompts in the three categories required by the assignment.
- `run_evaluation.py`: runs all 12 prompts three times by default, records traces/CSV/summary.
- `unit_tests.py`: deterministic checks for validation and the human gate.
- `ENGINEERING_MEMO.md`: project design, risk analysis, and honest reporting guidance.
- `DEMO_SCRIPT.md`: suggested five-minute demo.
- `results/`: destination for generated evaluation output.