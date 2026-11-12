from __future__ import annotations
from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class ActivityEvaluationResult(BaseModel):
    is_correct: bool
    marks_awarded: float
    max_marks: float
    percentage: float
    misconception_hit: Optional[str] = None
    details: Dict[str, Any]


def score_mcq(
    response: Dict[str, Any],
    answer_key: Dict[str, Any],
    config: Dict[str, Any],
) -> ActivityEvaluationResult:
    max_marks = float(config.get("max_marks", 1.0))
    negative_marks = float(config.get("negative_marks", 0.0))
    selected = response.get("selected_option_id")
    correct = answer_key.get("correct_option_id")
    misconceptions = answer_key.get("misconceptions", {})

    is_correct = bool(selected and selected == correct)
    misconception = misconceptions.get(selected) if not is_correct and selected else None

    if is_correct:
        marks = max_marks
    elif selected and negative_marks > 0:
        marks = -negative_marks
    else:
        marks = 0.0

    percentage = round((marks / max_marks) * 100, 2) if max_marks > 0 else 0.0
    return ActivityEvaluationResult(
        is_correct=is_correct,
        marks_awarded=round(marks, 2),
        max_marks=max_marks,
        percentage=max(0.0, percentage),
        misconception_hit=misconception,
        details={
            "selected_option_id": selected,
            "correct_option_id": correct,
            "explanation": answer_key.get("explanation"),
        },
    )


def score_fill_blank(
    response: Dict[str, Any],
    answer_key: Dict[str, Any],
    config: Dict[str, Any],
) -> ActivityEvaluationResult:
    max_marks = float(config.get("max_marks", 1.0))
    answers = response.get("answers", {})  # {blank_id: student_text}
    blanks = answer_key.get("blanks", {})  # {blank_id: {accepted_answers: [...]}}

    total_blanks = len(blanks)
    if total_blanks == 0:
        return ActivityEvaluationResult(is_correct=True, marks_awarded=max_marks, max_marks=max_marks, percentage=100.0, details={})

    correct_count = 0
    blank_results: Dict[str, bool] = {}

    for b_id, b_meta in blanks.items():
        user_val = str(answers.get(b_id, "")).strip().casefold()
        accepted = [str(a).strip().casefold() for a in b_meta.get("accepted_answers", [])]
        matched = bool(user_val and user_val in accepted)
        blank_results[b_id] = matched
        if matched:
            correct_count += 1

    is_correct = (correct_count == total_blanks)
    partial = config.get("partial_credit", True)

    if partial:
        marks = round((correct_count / total_blanks) * max_marks, 2)
    else:
        marks = max_marks if is_correct else 0.0

    percentage = round((marks / max_marks) * 100, 2) if max_marks > 0 else 0.0
    return ActivityEvaluationResult(
        is_correct=is_correct,
        marks_awarded=marks,
        max_marks=max_marks,
        percentage=percentage,
        details={
            "correct_blanks": correct_count,
            "total_blanks": total_blanks,
            "blank_results": blank_results,
        },
    )


def score_matching_pairs(
    response: Dict[str, Any],
    answer_key: Dict[str, Any],
    config: Dict[str, Any],
) -> ActivityEvaluationResult:
    max_marks = float(config.get("max_marks", 1.0))
    student_pairs = response.get("pairs", [])  # [{"left_id": ..., "right_id": ...}]
    correct_pairs = answer_key.get("pairs", {})  # {left_id: correct_right_id}

    total_pairs = len(correct_pairs)
    if total_pairs == 0:
        return ActivityEvaluationResult(is_correct=True, marks_awarded=max_marks, max_marks=max_marks, percentage=100.0, details={})

    correct_matches = 0
    pair_results: Dict[str, bool] = {}

    for p in student_pairs:
        l_id = p.get("left_id")
        r_id = p.get("right_id")
        if l_id in correct_pairs and correct_pairs[l_id] == r_id:
            pair_results[l_id] = True
            correct_matches += 1
        elif l_id:
            pair_results[l_id] = False

    is_correct = (correct_matches == total_pairs)
    partial = config.get("partial_credit", True)

    if partial:
        marks = round((correct_matches / total_pairs) * max_marks, 2)
    else:
        marks = max_marks if is_correct else 0.0

    percentage = round((marks / max_marks) * 100, 2) if max_marks > 0 else 0.0
    return ActivityEvaluationResult(
        is_correct=is_correct,
        marks_awarded=marks,
        max_marks=max_marks,
        percentage=percentage,
        details={
            "correct_matches": correct_matches,
            "total_pairs": total_pairs,
            "pair_results": pair_results,
        },
    )


def score_ordering(
    response: Dict[str, Any],
    answer_key: Dict[str, Any],
    config: Dict[str, Any],
) -> ActivityEvaluationResult:
    max_marks = float(config.get("max_marks", 1.0))
    student_order = response.get("order", [])  # [item_id_1, item_id_2, ...]
    correct_order = answer_key.get("correct_order", [])

    total_items = len(correct_order)
    if total_items == 0:
        return ActivityEvaluationResult(is_correct=True, marks_awarded=max_marks, max_marks=max_marks, percentage=100.0, details={})

    correct_positions = sum(
        1 for idx in range(min(len(student_order), total_items))
        if student_order[idx] == correct_order[idx]
    )

    is_correct = (student_order == correct_order)
    partial = config.get("partial_credit", True)

    if is_correct:
        marks = max_marks
    elif partial:
        marks = round((correct_positions / total_items) * max_marks, 2)
    else:
        marks = 0.0

    percentage = round((marks / max_marks) * 100, 2) if max_marks > 0 else 0.0
    return ActivityEvaluationResult(
        is_correct=is_correct,
        marks_awarded=marks,
        max_marks=max_marks,
        percentage=percentage,
        details={
            "correct_positions": correct_positions,
            "total_items": total_items,
            "expected_order": correct_order,
        },
    )


def score_classification(
    response: Dict[str, Any],
    answer_key: Dict[str, Any],
    config: Dict[str, Any],
) -> ActivityEvaluationResult:
    max_marks = float(config.get("max_marks", 1.0))
    student_class = response.get("classifications", {})  # {item_id: category_id}
    correct_items = answer_key.get("items", {})  # {item_id: correct_category_id}

    total_items = len(correct_items)
    if total_items == 0:
        return ActivityEvaluationResult(is_correct=True, marks_awarded=max_marks, max_marks=max_marks, percentage=100.0, details={})

    correct_count = 0
    item_results: Dict[str, bool] = {}

    for item_id, correct_cat in correct_items.items():
        user_cat = student_class.get(item_id)
        matched = (user_cat == correct_cat)
        item_results[item_id] = matched
        if matched:
            correct_count += 1

    is_correct = (correct_count == total_items)
    partial = config.get("partial_credit", True)

    if partial:
        marks = round((correct_count / total_items) * max_marks, 2)
    else:
        marks = max_marks if is_correct else 0.0

    percentage = round((marks / max_marks) * 100, 2) if max_marks > 0 else 0.0
    return ActivityEvaluationResult(
        is_correct=is_correct,
        marks_awarded=marks,
        max_marks=max_marks,
        percentage=percentage,
        details={
            "correct_classified": correct_count,
            "total_items": total_items,
            "item_results": item_results,
        },
    )


def score_key_points_check(
    response: Dict[str, Any],
    answer_key: Dict[str, Any],
    config: Dict[str, Any],
) -> ActivityEvaluationResult:
    max_marks = float(config.get("max_marks", 1.0))
    selected = set(response.get("selected_point_ids", []))
    essential = set(answer_key.get("essential_point_ids", []))
    non_essential = set(answer_key.get("non_essential_point_ids", []))

    total_essential = len(essential)
    if total_essential == 0:
        return ActivityEvaluationResult(is_correct=True, marks_awarded=max_marks, max_marks=max_marks, percentage=100.0, details={})

    correct_selected = len(selected & essential)
    wrong_selected = len(selected & non_essential)

    is_exact = (correct_selected == total_essential and wrong_selected == 0)
    partial = config.get("partial_credit", True)

    if is_exact:
        marks = max_marks
    elif partial:
        raw = (correct_selected / total_essential) * max_marks
        penalty = (wrong_selected / max(len(non_essential), 1)) * 0.25 * max_marks
        marks = max(0.0, round(raw - penalty, 2))
    else:
        marks = 0.0

    percentage = round((marks / max_marks) * 100, 2) if max_marks > 0 else 0.0
    return ActivityEvaluationResult(
        is_correct=(marks == max_marks),
        marks_awarded=marks,
        max_marks=max_marks,
        percentage=percentage,
        details={
            "correct_essential_selected": correct_selected,
            "total_essential": total_essential,
            "wrong_selected": wrong_selected,
        },
    )


SCORING_DISPATCHER = {
    "mcq": score_mcq,
    "fill_blank": score_fill_blank,
    "matching_pairs": score_matching_pairs,
    "ordering": score_ordering,
    "classification": score_classification,
    "key_points_check": score_key_points_check,
}


def evaluate_activity_response(
    activity_type: str,
    response_data: Dict[str, Any],
    answer_key: Dict[str, Any],
    scoring_config: Dict[str, Any],
) -> ActivityEvaluationResult:
    scorer = SCORING_DISPATCHER.get(activity_type)
    if not scorer:
        raise ValueError(f"No deterministic scorer implemented for activity type: '{activity_type}'")
    return scorer(response_data, answer_key, scoring_config)

