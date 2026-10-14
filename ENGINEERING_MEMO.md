# Engineering Memo: Reliable Mock Shop Support Agent

## 1. Business problem and scope
The agent supports a fictional online shop using a synthetic dataset. It can look up an order, calculate refund eligibility, and request a mock refund.

## 2. Capability and risk design

| Capability | Purpose / inputs | Output | Risk | Treatment and rationale |
|---|---|---|---|---|
| `lookup_order(order_id)` | Retrieve a known order's status and details; exact order ID | Mock order record or unknown-ID error | Low | **AUTO-RUN.** Read-only, no external side effect. |
| `calculate_refund(order_id, amount=None)` | Check the maximum eligible refund or validate a proposed amount | Eligibility and validation result; explicitly calculation-only | Medium | **CONSTRAIN.** Validates order existence, numeric positive amount, $5,000 global ceiling, and order-specific eligibility. Does not move money. |
| `request_refund(order_id, amount, reason)` | Propose a refund request with required details | Approved mock receipt or denial result | High | **HUMAN GATE.** It is a consequential action even in this mock design. The tool cannot execute without explicit approval; denial means no action. No real transaction integration exists. |

## 3. Architecture
User prompt → local Ollama model → proposed tool call → Python allowlist and validation → tool result returned to model → final answer. Python, not the model, executes functions. The loop is capped at five model/tool steps. Tool execution is wrapped in exception handling. Tool names and argument schemas are explicit.

## 4. Baseline and hardening plan
The baseline uses a broad instruction: be helpful and use tools when useful. The hardened condition adds explicit tool-selection rules, a no-action rule for general/ambiguous prompts, required fields for consequential requests, a prohibition on inferring "my last order", and rules for handling denials and tool results. Validation and the human gate are enforced in Python in both modes; safety should not depend on prompt wording alone.

Meaningful changes:
1. **Prompt/routing hardening:** distinguish explicit lookup/calculation/refund requests from general questions and ambiguous requests.
2. **Argument and action constraints:** validate known order IDs, positive amounts, a $5,000 maximum, order-level refund eligibility, and non-empty reason; require explicit approval before the mock refund action.
3. **Bounded execution and error handling:** cap the loop and return tool failures as observations rather than crashing the entire program.

## 5. Test set
`test_prompts.json` contains 12 fixed prompts: four clear-action prompts, four ambiguous/difficult prompts, and four prompts that should not trigger tools. `run_evaluation.py` runs each prompt three times by default (36 trials per condition) and writes a CSV plus a JSONL trace. A test's expected behavior is a rubric, not a claim that the model passed it.

## 6. Evaluation status and evidence
**Do not invent evaluation results.** The attached assignment instructions require real baseline failures and the same tests rerun after hardening. This environment has not established that an Ollama server/model is available, so this package does not claim live-model baseline or hardened scores. Run the commands in `README.md`, preserve the generated trace files, and use the actual outputs to fill the table below.

| Metric | Baseline | Hardened |
|---|---:|---:|
| Correct action/tool selection | Fill from `*_summary.json` | Fill from `*_summary.json` |
| Correct arguments | Fill from row-level CSV review | Fill from row-level CSV review |
| Correct final answer | Fill from `*_summary.json` | Fill from `*_summary.json` |
| Unnecessary tool calls on no-action prompts | Fill from `*_summary.json` | Fill from `*_summary.json` |
| Runtime errors | Fill from `*_summary.json` | Fill from `*_summary.json` |

The summary JSON computes initial indicators. Inspect traces manually too: automated substring scoring is only a screening aid and can misclassify semantically correct answers. For the assignment's "break your agent" section, cite at least two actual trace rows with prompt ID, expected action, observed tool/arguments, and why that behavior is a failure. If no failure appears in the first 36 trials, expand the test set or try a documented harder prompt rather than making one up.

## 7. Human-gate evidence
The evaluation runner sets the clear refund test to denial and verifies the returned trace. For the live demo, run the agent interactively and show both:
- Approve: provide a valid explicit refund request and type `y`; output should say a mock action was recorded and no real money moved.
- Deny: repeat with valid details and type `n` (or press Enter); output should say denied and not executed.

Save terminal screenshots or a screen recording for evidence. A model proposing a refund is not proof that the action executed; the Python result must show `executed: true` only after approval.

## 8. Limitations
- The data and action are fictional; there is no external order API or payment processor.
- LLM behavior is nondeterministic. Use identical model, prompts, and repetition count for comparison.
- The runner's expected-action rubric is intentionally simple and should be checked against raw traces.
- A tool call on an ambiguous prompt may be inappropriate even if its arguments are syntactically valid.
