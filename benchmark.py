import os
import re
import sys
import json
import time
import subprocess
import psutil
import torch
import requests
import numpy as np

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Import our custom backend modules
from retrieve import initialize_retrieval_components
from answer import answer_question, OLLAMA_HOST, OLLAMA_MODEL, NUM_CTX, GRADER_MODEL

# =====================================================
# RESOURCE TRACKERS
# =====================================================
def get_system_ram_usage():
    """Returns system RAM usage in MB."""
    return psutil.virtual_memory().used / (1024 * 1024)

def get_process_ram_usage():
    """Returns current python process RAM usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def get_gpu_vram_usage():
    """Returns current GPU VRAM usage in MB via nvidia-smi."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL
        )
        return float(out.decode("utf-8").strip())
    except Exception:
        return 0.0

# =====================================================
# EVALUATION GRADER
# =====================================================
def grade_answer_llm(question, generated, ground_truth):
    """
    Grades the generated answer against ground truth using Ollama.
    Returns True if correct, False otherwise.
    """
    prompt = f"""System:
You are an expert physics teacher grading a student's answer.
Compare the student's generated answer against the ground truth answer.
If the student's answer is conceptually correct and contains the correct values, formulas, or conclusions as the ground truth, output 'CORRECT'.
Otherwise, output 'INCORRECT'.
Be strict but fair. Do not write anything else, only 'CORRECT' or 'INCORRECT'.

Question: {question}
Ground Truth: {ground_truth}
Generated Answer: {generated}

Grade:"""
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": GRADER_MODEL,  # Pinned: grading stays on fast llama
                "prompt": prompt,       # independent of the generation default
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 128,
                    "num_ctx": NUM_CTX  # Same context as serving path: avoids model unload/reload cycles
                }
            },
            timeout=60
        )
        resp.raise_for_status()
        resp_json = resp.json()
        grade = resp_json.get("response", "").strip().upper()
        thinking = resp_json.get("thinking", "").strip().upper()
        
        combined = f"{grade}\n{thinking}"
        grade_clean = re.sub(r"<think>.*?</think>", "", combined, flags=re.IGNORECASE|re.DOTALL).strip()
        
        if "INCORRECT" in grade_clean:
            return False
        if "CORRECT" in grade_clean:
            return True
        return False
    except Exception as e:
        print(f"  [Grader Error]: {e}")
        return False

# =====================================================
# MAIN BENCHMARK RUNNER
# =====================================================
def run_benchmark():
    # 1. Load benchmark questions
    with open("benchmark_questions.json", encoding="utf-8") as f:
        questions = json.load(f)
        
    print(f"Loaded {len(questions)} total benchmark questions.")
    
    # We will pick a representative sample of 20 questions (5 from each category)
    categories = ["NCERT Theory", "NCERT Exercise", "JEE Main", "NEET"]
    sample_questions = []
    for cat in categories:
        cat_qs = [q for q in questions if q["category"] == cat]
        # Sort by ID to ensure deterministic sampling
        cat_qs.sort(key=lambda x: x["id"])
        # Take the first 5 questions of each category
        sample_questions.extend(cat_qs[:5])
        
    print(f"Selected {len(sample_questions)} mixed sample questions for verification.")
    
    # Initialize retrieval
    initialize_retrieval_components()
    
    # Warm up Ollama model with matched options to avoid model load latency inside benchmark
    print(f"Warming up Ollama model `{OLLAMA_MODEL}` in VRAM...")
    try:
        requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": "",
                "stream": False,
                "options": {"num_ctx": NUM_CTX}
            },
            timeout=60
        )
        print("Warmup complete. Starting benchmark...")
    except Exception as e:
        print(f"Warmup failed: {e}")
    
    # Baseline resources
    baseline_process_ram = get_process_ram_usage()
    baseline_system_ram = get_system_ram_usage()
    baseline_gpu_vram = get_gpu_vram_usage()
    
    print("\n" + "="*50)
    print("BASELINE RESOURCE METRICS")
    print("="*50)
    print(f"Python Process RAM : {baseline_process_ram:.2f} MB")
    print(f"System Virtual RAM : {baseline_system_ram:.2f} MB")
    print(f"GPU VRAM Memory    : {baseline_gpu_vram:.2f} MB")
    print("="*50 + "\n")
    
    results = []
    
    peak_process_ram = baseline_process_ram
    peak_system_ram = baseline_system_ram
    peak_gpu_vram = baseline_gpu_vram
    
    latencies = []
    retrieval_latencies = []
    generation_latencies = []
    recalls = []
    accuracies = []
    citation_accuracies = []
    
    for idx, q in enumerate(sample_questions, 1):
        print(f"[{idx}/{len(sample_questions)}] Category: {q['category']} | Question: {q['question'][:60]}...")
        
        # Run QA pipeline
        start_time = time.perf_counter()
        res = answer_question(q["question"], verbose=False)
        total_time = time.perf_counter() - start_time
        
        # Measure resources immediately
        proc_ram = get_process_ram_usage()
        sys_ram = get_system_ram_usage()
        vram = get_gpu_vram_usage()
        
        peak_process_ram = max(peak_process_ram, proc_ram)
        peak_system_ram = max(peak_system_ram, sys_ram)
        peak_gpu_vram = max(peak_gpu_vram, vram)
        
        # Evaluate Recall with flexible cleaning (newline/spacing normalized)
        recall = 0.0
        gt_sec_clean = q["reference_section"].replace("#", "").replace("*", "").replace("\n", " ").strip().lower()
        gt_sec_clean = re.sub(r"\s+", " ", gt_sec_clean)
        
        retrieved_sections = []
        if "retrieved_chunks" in res:
            for hit in res["retrieved_chunks"]:
                ret_sec_clean = hit["metadata"]["section"].replace("#", "").replace("*", "").replace("\n", " ").strip().lower()
                ret_sec_clean = re.sub(r"\s+", " ", ret_sec_clean)
                retrieved_sections.append(ret_sec_clean)
                
                # Check for match (clean substring or exact section number)
                if gt_sec_clean in ret_sec_clean or ret_sec_clean in gt_sec_clean:
                    recall = 1.0
                else:
                    # check section number match (e.g. "5.6")
                    num_gt = re.search(r"\d+\.\d+", gt_sec_clean)
                    num_ret = re.search(r"\d+\.\d+", ret_sec_clean)
                    if num_gt and num_ret and num_gt.group(0) == num_ret.group(0):
                        recall = 1.0
                        
        # Evaluate Correctness
        is_correct = grade_answer_llm(q["question"], res["answer"], q["ground_truth_answer"])
        accuracy = 1.0 if is_correct else 0.0
        
        # Evaluate Citations: Did the LLM cite the target section or did we trace it?
        cited_correctly = 0.0
        # Simple check: check if the ground truth section's text numbers (e.g. "5.6") are mentioned in the citations or answer
        sec_num_match = re.search(r"\d+\.\d+", q["reference_section"])
        if sec_num_match:
            sec_num = sec_num_match.group(0)
            # check in answer or citations
            res_citations_str = " ".join(res["citations"]).lower()
            if sec_num in res["answer"].lower() or sec_num in res_citations_str:
                cited_correctly = 1.0
                
        # Append stats
        latencies.append(total_time)
        ret_lat = res.get("retrieval_latency", 0.0)
        gen_lat = res.get("generation_latency", total_time - ret_lat)
        retrieval_latencies.append(ret_lat)
        generation_latencies.append(gen_lat)
        recalls.append(recall)
        accuracies.append(accuracy)
        citation_accuracies.append(cited_correctly)
        
        print(f"  -> Time: {total_time:.2f}s (Rtr: {ret_lat:.2f}s, Gen: {gen_lat:.2f}s) | Recall: {recall} | Accuracy: {accuracy} | Process RAM: {proc_ram:.1f} MB | VRAM: {vram:.1f} MB")
        
        results.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "ground_truth": q["ground_truth_answer"],
            "answer": res["answer"],
            "citations": res["citations"],
            "latency": total_time,
            "retrieval_latency": ret_lat,
            "generation_latency": gen_lat,
            "recall": recall,
            "accuracy": accuracy,
            "cited_correctly": cited_correctly,
            "resources": {
                "process_ram_mb": proc_ram,
                "system_ram_mb": sys_ram,
                "gpu_vram_mb": vram
            }
        })
        
    # Write full results to JSON
    with open("benchmark_results.json", "w", encoding="utf-8") as out_f:
        json.dump(results, out_f, indent=2)
        
    # 5. Output Summary Table
    print("\n" + "="*55)
    print("BENCHMARK EXECUTION SUMMARY")
    print("="*55)
    print(f"Average Query Latency   : {np.mean(latencies):.2f} seconds")
    print(f"  - Avg Retrieval Time  : {np.mean(retrieval_latencies):.2f} seconds")
    print(f"  - Avg LLM Gen Time    : {np.mean(generation_latencies):.2f} seconds")
    print(f"Retrieval Recall Rate   : {np.mean(recalls)*100:.1f}%")
    print(f"Answer Correctness      : {np.mean(accuracies)*100:.1f}%")
    print(f"Source Citation Accuracy: {np.mean(citation_accuracies)*100:.1f}%")
    print("-" * 55)
    print(f"Peak Python Process RAM : {peak_process_ram:.2f} MB")
    print(f"Peak System Virtual RAM : {peak_system_ram:.2f} MB (Target < 12GB/12288MB)")
    print(f"Peak GPU VRAM Usage     : {peak_gpu_vram:.2f} MB (Target < 8GB/8192MB)")
    print("="*55)
    print("\nFull benchmark results saved to `benchmark_results.json`.")
 
if __name__ == "__main__":
    run_benchmark()
