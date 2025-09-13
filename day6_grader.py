
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import json
import re

# ---------------------------
# Load Model in 4-bit
# ---------------------------
model_id = "microsoft/phi-3.5-mini-instruct"
device = "cuda" if torch.cuda.is_available() else "cpu"

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,   # or bfloat16 if supported
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4"
)

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="auto"
)

# ---------------------------
# JSON Validator
# ---------------------------
def validate_and_fix_json(filename):
    """Try to load JSON, report errors if invalid."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = [data]  # Ensure it's always a list
        print(f"✅ JSON file '{filename}' loaded successfully with {len(data)} questions.")
        return data
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return None

# ---------------------------
# JSON Extraction Helper
# ---------------------------
import json
import re

def safe_json_extract(text):
    """Extract and parse JSON from model output safely."""
    try:
        # Find all JSON-like objects
        matches = re.findall(r"\{.*?\}", text, re.DOTALL)
        if not matches:
            raise ValueError("No JSON found")

        # Pick the longest block (most complete JSON)
        best_match = max(matches, key=len)

        # Try parsing directly
        try:
            return json.loads(best_match)
        except json.JSONDecodeError:
            # Attempt auto-fix: balance braces
            open_count = best_match.count("{")
            close_count = best_match.count("}")
            if open_count > close_count:
                best_match += "}" * (open_count - close_count)

            return json.loads(best_match)

    except Exception:
        return {"score": 0, "feedback": f"Parsing error. Raw output: {text}"}


# ---------------------------
# Companion Feedback Function
# ---------------------------
def companion_feedback(question, student_answer, correct_answer, max_score=5):
    """
    Companion mode: acts like a tutor, explaining what’s missing and guiding improvement.
    """
    prompt = f"""
You are a helpful tutor. A student has answered a question, and you must guide them to a perfect answer.

Return ONLY valid JSON in this exact format:
{{
  "feedback": "<string>",
  "keywords": ["<keyword1>", "<keyword2>", ...],
  "improvement_steps": ["<step1>", "<step2>", ...]
}}

Instructions:
1. Summarize the student's answer and politely highlight what they did well.
2. List the essential keywords/points that a perfect answer should contain.
3. Give clear, constructive steps the student can follow to improve their answer.
4. Do NOT grade harshly here; focus on teaching.
5. Avoid scoring; this is only feedback and guidance.
"""

    inputs = tokenizer(prompt + f"\nQuestion: {question}\nStudent Answer: {student_answer}\nCorrect Answer: {correct_answer}\n",
                       return_tensors="pt").to(device)
    outputs = model.generate(**inputs, max_new_tokens=250)
    raw_output = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return safe_json_extract(raw_output)


def build_system_prompt(difficulty):
    base_prompt = """
You are a fair and intelligent grading assistant.
You must return ONLY valid JSON.
No extra text, no explanations, no markdown, no comments, no repeating rules in feedback or the answer. Return the marks in decimal format example: 2.5 or 4.5 or 5.0.

The JSON format is exactly:
{"score": <int>, "feedback": "<string>"}

Grading Rules:
1. Theory Questions:
   - If keywords are uploaded by the examiner, check if the answer includes those keywords or closely related concepts (synonyms and paraphrases count).
   - If no keywords are uploaded, grade based on accuracy, coverage, and relevance of the answer.
   - Do not cut marks if the answer could be more concise and directly align with the correct answer format. In such cases just award max_score.
   - Award partial credit if the answer demonstrates understanding, even if wording differs.
   - Extra but correct details should NOT lower the score.

2. Numeric Questions:
   - Exact match required for integers.
   - For decimal answers, allow ±0.1 tolerance.
3. Chemistry Questions:
   - No two chemical symbols are partially the same, for instance Au is not at all equal to Ag, N (for nitrogen) is not equal to Ne (for neon).

Scoring:
- Give a score between 0 and max_score.
- Always remember this one critical rul that you as a top quality examinor have to award marks in decimal value, e.g., 2.5. If you find a small negligible mistake reduce 0.5 marks from max_score. If the mistake is significant reduce 1 mark per mistake from the max_score.
- Reward partial correctness rather than strict matching.

Feedback:
- Always include both keys: score AND feedback.
- Feedback must be a short, constructive explanation (1–2 sentences).
- Always include a short, constructive explanation (1–2 sentences) for the score.
- Even if the answer is perfect, provide positive feedback like "Excellent answer, covers all points."

Difficulty Level:
"""
    if difficulty.lower() == "easy":
        base_prompt += "Lenient grading. Award partial credit generously."
    elif difficulty.lower() == "hard":
        base_prompt += "Strict grading. Full marks only for exact correctness. Only if all the keywords are mentioned and the answer is precise with some extra information around the topic. Do not treat the answers in an easy way."
    else:
        base_prompt += "Balanced grading. If answer covers some of the keywords reduce one mark from the max_score. If there are no keywords present in the answer, reduce marks."

    return base_prompt

# ---------------------------
# Model-based Scoring
# ---------------------------
def get_model_score(question, student_answer, correct_answer, max_score=5, difficulty="medium"):
    """Ask the model to score and retry if it fails."""
    difficulty_text = {
        "easy": "Lenient grading. Award partial credit generously.",
        "hard": "Strict grading. Full marks only for exact correctness.",
        "medium": "Balanced grading. Award partial credit fairly."
    }.get(difficulty.lower(), "Balanced grading. Award partial credit fairly.")

    # First attempt prompt
    base_prompt = f"""
You are a grading assistant. Your ONLY output should be a single valid JSON object.
No explanations, no text outside JSON, no markdown.
JSON format:
{{"score": <int>, "feedback": "<1-2 short sentences>"}}
Question: {question}
Student Answer: {student_answer}
Correct Answer: {correct_answer}
Max Score: {max_score}
Difficulty: {difficulty_text}
"""

    for attempt in range(2):  # Retry up to 2 times
        # Move tensors to device
        inputs = tokenizer(base_prompt, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}

        # Generate response
        outputs = model.generate(**inputs, max_new_tokens=200, do_sample=False)
        raw_output = tokenizer.decode(outputs[0], skip_special_tokens=True)

        print(f"\n--- RAW MODEL OUTPUT (Attempt {attempt+1}) ---\n{raw_output}\n-----------------------\n")

        # Try parsing
        parsed = safe_json_extract(raw_output)
        if "Parsing error" not in parsed["feedback"]:
            return parsed

        # If parsing failed, adjust the prompt for retry
        base_prompt = f"""
ONLY return JSON like this: {{"score": 0-5, "feedback": "short feedback"}}
Question: {question}
Student Answer: {student_answer}
Correct Answer: {correct_answer}
Max Score: {max_score}
Difficulty: {difficulty_text}
"""

    # If both attempts fail, return fallback
    return {"score": 0, "feedback": f"Parsing error. Raw output: {raw_output}"}

# ---------------------------
# Main Pipeline
# ---------------------------
def evaluate(input_file, output_file, difficulty="medium", max_score=5, correct_answers_file=None):
    """
    Evaluates questions in the input JSON file and writes results.
    If a correct answers file is provided, it is used as the authoritative reference.

    Args:
        input_file (str): Path to the input JSON file.
        output_file (str): Path to save results.
        difficulty (str): Grading difficulty (easy/medium/hard).
        max_score (int): Default maximum score (overridden if JSON has max_score).
        correct_answers_file (str, optional): Path to JSON file with correct answers.
    """
    data = validate_and_fix_json(input_file)
    if not data:
        print("🚨 Exiting due to invalid JSON.")
        return

    # Load correct answers if provided
    correct_answers = {}
    if correct_answers_file:
        try:
            with open(correct_answers_file, "r", encoding="utf-8") as f:
                ca_data = json.load(f)
                for q in ca_data:
                    qid = q.get("question_id")
                    answer = q.get("correct_answer", "")
                    if qid:
                        correct_answers[qid] = answer
        except Exception as e:
            print(f"⚠️ Failed to load correct answers file: {e}")
            correct_answers = {}

    results = []
    for q in data:
        question_id = q.get("question_id", "")
        question = q.get("question", "")
        student_answer = q.get("student_answer", "")
        grading_mode = q.get("grading_mode", difficulty)

        # Use max_score from JSON or fallback
        question_max_score = q.get("max_score", max_score)

        # Override correct answer from external file if available
        correct_answer = correct_answers.get(question_id, q.get("correct_answer", ""))

        # Case 1: Exact match → full marks
        if correct_answer and student_answer.strip().lower() == correct_answer.strip().lower():
            model_score = question_max_score
            model_feedback = "✅ Perfect! Answer matches the correct answer exactly."
        # Case 2: Correct answer exists but not an exact match → let model grade
        elif correct_answer:
            model_result = get_model_score(
                question, student_answer, correct_answer, question_max_score, grading_mode
            )
            model_score = model_result.get("score", 0)
            model_feedback = model_result.get("feedback", "No feedback")
        # Case 3: No correct answer provided → fallback to model general knowledge
        else:
            model_result = get_model_score(
                question, student_answer, None, question_max_score, grading_mode
            )
            model_score = model_result.get("score", 0)
            model_feedback = model_result.get("feedback", "No feedback")

        graded_entry = {
            "question_id": question_id,
            "question": question,
            "correct_answer": correct_answer,
            "student_answer": student_answer,
            "grading_mode": grading_mode,
            "rule_score": q.get("rule_score", None),
            "model_score": model_score,
            "feedback": model_feedback,
            "max_score": question_max_score,
            "final_score": model_score
        }

        results.append(graded_entry)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"✅ Evaluation complete! Results saved to {output_file}")




# ---------------------------
# Run (Manual)
# ---------------------------
if __name__ == "__main__":
    evaluate("day6_questions.json", "graded_results.json", difficulty="medium")
