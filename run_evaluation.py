"""Run fixed test prompts against baseline/hardened Ollama agent and save evidence."""
import argparse, csv, json, time
from pathlib import Path
from agent import run_agent

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

def assess(test, result):
    trace = result.get("trace", [])
    tools = [x.get("tool") for x in trace]
    expected = test["expected_tool"]
    if expected == "no_action":
        action_correct = len(tools) == 0
    elif expected == "clarify":
        action_correct = len(tools) == 0
    elif expected == "clarify_or_calculate":
        action_correct = len(tools) == 0 or tools == ["calculate_refund"]
    else:
        action_correct = bool(tools) and tools[0] == expected
    expected_text = test.get("expected_final_contains", "").lower()
    final_correct = expected_text in result.get("answer", "").lower() if expected_text else bool(result.get("answer"))
    args_correct = True
    if tools:
        first = trace[0]
        args = first.get("arguments", {})
        if expected in ("lookup_order","calculate_refund","request_refund"):
            prompt = test["prompt"].upper()
            import re
            ids = re.findall(r"ORD-\d+", prompt)
            if ids and args.get("order_id","").upper() != ids[0]:
                args_correct = False
            if first["tool"] == "request_refund":
                args_correct = args_correct and bool(str(args.get("reason","")).strip()) and float(args.get("amount",0) or 0) > 0
    return action_correct, args_correct, final_correct

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="qwen2.5:7b")
    p.add_argument("--mode", choices=["baseline","hardened"], required=True)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--base-url", default="http://localhost:11434")
    p.add_argument("--pause", type=float, default=0.2)
    args = p.parse_args()
    tests = json.loads((ROOT / "test_prompts.json").read_text())
    csv_path = RESULTS / f"{args.mode}_runs.csv"
    trace_path = RESULTS / f"{args.mode}_trace.jsonl"
    rows, traces = [], []
    with trace_path.open("w", encoding="utf-8") as tracefile:
        for test in tests:
            for repeat in range(1, args.runs + 1):
                # The one clear refund test is deliberately denied to demonstrate the gate.
                approval = test.get("approval") or "deny"
                started = time.time()
                try:
                    result = run_agent(test["prompt"], model=args.model, mode=args.mode,
                        approval=approval, interactive=False, base_url=args.base_url)
                    action_ok, args_ok, final_ok = assess(test, result)
                    row = {"test_id":test["id"],"category":test["category"],"repeat":repeat,
                        "prompt":test["prompt"],"expected":test["expected_tool"],
                        "actual_tools":";".join(x.get("tool","") for x in result.get("trace",[])) or "no_action",
                        "action_correct":action_ok,"arguments_correct":args_ok,
                        "final_answer_correct":final_ok,"answer":result.get("answer",""),
                        "error":"","duration_seconds":round(time.time()-started,2)}
                    tracefile.write(json.dumps({"test":test,"repeat":repeat,"result":result,"assessment":row}, ensure_ascii=False)+"\n")
                except Exception as exc:
                    row = {"test_id":test["id"],"category":test["category"],"repeat":repeat,
                        "prompt":test["prompt"],"expected":test["expected_tool"],"actual_tools":"ERROR",
                        "action_correct":False,"arguments_correct":False,"final_answer_correct":False,
                        "answer":"","error":f"{type(exc).__name__}: {exc}",
                        "duration_seconds":round(time.time()-started,2)}
                    tracefile.write(json.dumps({"test":test,"repeat":repeat,"error":row["error"]}, ensure_ascii=False)+"\n")
                rows.append(row)
                print(f'{test["id"]} run {repeat}: action={row["action_correct"]}, args={row["arguments_correct"]}, final={row["final_answer_correct"]}')
                time.sleep(args.pause)
    fields = list(rows[0].keys()) if rows else []
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    n = len(rows)
    summary = {"mode":args.mode,"model":args.model,"runs_per_prompt":args.runs,"total_trials":n,
        "action_accuracy":sum(bool(r["action_correct"]) for r in rows)/n if n else 0,
        "argument_accuracy":sum(bool(r["arguments_correct"]) for r in rows)/n if n else 0,
        "final_answer_accuracy":sum(bool(r["final_answer_correct"]) for r in rows)/n if n else 0,
        "tool_calls_on_no_action_prompts":sum(r["actual_tools"]!="no_action" for r in rows if r["expected"]=="no_action"),
        "errors":sum(bool(r["error"]) for r in rows),
        "note":"Computed from live Ollama calls made by this run; inspect CSV and JSONL traces before reporting failures."}
    summary_path = RESULTS / f"{args.mode}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nSummary:", json.dumps(summary, indent=2))
    print(f"Saved {csv_path}, {trace_path}, {summary_path}")

if __name__ == "__main__":
    main()
