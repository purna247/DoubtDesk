# Specification: Doubt Structuring, Semantic Topic Extraction & Triangulated Pedagogical Analytics

## Problem Statement

Students frequently encounter conceptual confusion during self-study and practice, posting doubts in the course community. However, today these doubts exist as isolated forum threads disconnected from the course syllabus and learning metrics. Concurrently, teachers lack visibility into where students are genuinely struggling:
1. Conventional Q&A forums resemble generic sites where students wait for answers, whereas standalone AI chatbots answer questions instantly in private, rendering traditional forums increasingly obsolete and leaving teachers blind to cohort confusion.
2. In the current platform, the teacher analytics dashboard only tracks formal **Quiz** marks (`AssessmentAttempt`), ignoring the rich struggle data generated during interactive **Learn** practice sessions (hints used, consecutive mistakes, difficulty regressions) and ignoring student natural language **Doubts**.
3. Teachers must manually guess why a cohort is struggling and manually author remediation primers and targeted practice questions from scratch without AI assistance grounded in actual student inquiries.

## Solution

A closed-loop, tri-signal learning intelligence system that unifies:
1. **Doubt Structuring & Semantic Pipeline**: An asynchronous classification engine that ingests student doubt text, extracts core confusion statements and propositions, matches them against the course syllabus hierarchy (`Module ➔ Topic ➔ Subtopic`) and canonical concept registry, and identifies recurring misconception patterns.
2. **Triangulated Pedagogical Evidence Engine**: An analytics aggregator that calculates a comprehensive **Concept & Topic Risk Index** combining:
   - **Quiz Evidence (Summative)**: Test accuracy, failure rate, and allocated concept scores.
   - **Learn Evidence (Formative Practice)**: Practice session mistake frequency, consecutive errors, hint usage, and adaptive remediation events.
   - **Doubt Evidence (Semantic Inquiry)**: Volume of questions, unanswered doubts, and detected misconception occurrences on that topic.
3. **AI-Assisted Intervention Drafting**: A teacher studio feature allowing faculty to generate a 1-click targeted remediation plan for weak topics. The engine synthesizes student doubt phrasing and syllabus objectives into an explanatory Phase B primer and recommends targeted practice questions for teacher review and approval.

---

## User Stories

### Student Doubts & Semantic Classification
1. As a student asking a doubt, I want to optionally select the relevant topic from my course syllabus so that my question is organized under the correct academic unit.
2. As a student asking a doubt, I want the system to automatically infer and tag the relevant topic, subtopic, and concept if I don't know where it belongs in the syllabus, so that asking questions remains frictionless.
3. As a student, I want to filter and search course doubts by specific syllabus modules, topics, and subtopics so that I can see existing discussions on the exact concept I am currently studying.
4. As a student, I want my doubt submission to be saved immediately without waiting for AI analysis so that my interface never experiences submission lag or timeouts.
5. As a student, I want peer and faculty answers to reference specific syllabus subtopics so that learning remains grounded in the course curriculum.

### Teacher Analytics & Triangulated Evidence
6. As a teacher, I want to see a unified Risk Index for every concept and syllabus topic in my course, combining quiz accuracy, practice session struggle, and doubt frequency, so that I can pinpoint real learning gaps.
7. As a teacher, I want to see when a topic has high test failure but low doubt volume ("Silent Failure"), so that I know students are struggling without seeking help.
8. As a teacher, I want to see when students struggle heavily during Learn practice but pass quizzes ("Recovered Mastery"), so that I can celebrate effective practice and avoid unnecessary interventions.
9. As a teacher, I want to see when a topic has high doubt activity despite passing quiz scores ("Conceptual Friction"), so that I can clarify subtle edge cases during live lectures.
10. As a teacher, I want to see the specific student doubts associated with a weak concept directly inside the analytics inspector so that I can read students' own words about their confusion.
11. As a teacher, I want to see emerging misconception tags extracted from student doubts so that I can approve valid misconceptions into the course registry.

### Targeted Intervention & Closed-Loop Remediation
12. As a teacher reviewing a weak topic, I want a single button to "Generate Targeted Intervention" that drafts an explanatory primer addressing the exact confusion phrases students used in their doubts.
13. As a teacher, I want to review and edit the AI-generated Phase B explanation primer before it is published to students so that academic quality and pedagogical authority remain with faculty.
14. As a teacher, I want the system to suggest diagnostic pre-test (Phase A), targeted practice (Phase B), and post-test (Phase C) assessments for the intervention based on the weak topic.
15. As a teacher, I want to track outcome reports measuring score change from Phase A to Phase C so that I have audited proof that the intervention resolved the learning gap.
16. As an institution administrator, I want historical doubt topics, practice struggles, and interventions preserved across semesters so that subsequent faculty cohorts inherit longitudinal pedagogical insights.

---

## Implementation Decisions

### 1. Data Model & Schema Modifications
- **Doubt Model**:
  - Add optional foreign key `syllabus_node_id` referencing `syllabus_nodes.id` on delete set null.
  - Add JSON column `semantic_metadata` storing:
    ```json
    {
      "extracted_confusion": "Confused ECoG with ECG microelectrode placement",
      "suggested_topic_id": "uuid-string",
      "suggested_subtopic_title": "Invasive Cortical Interfaces",
      "suggested_concept_id": "uuid-string",
      "candidate_misconceptions": ["ecg_treated_as_cortical"],
      "confidence_score": 0.89,
      "analyzed_at": "2026-11-15T16:00:00Z"
    }
    ```
- **Syllabus Node Linkage**: Ensure doubts can be indexed by `(course_offering_id, syllabus_node_id)` for high-performance topic filtering and analytics aggregation.

### 2. Deep Module: `DoubtSemanticService`
- **Seam**: A clean interface accepting raw text and syllabus context, returning structured semantic verdicts.
- **Contract**:
  - `classify_doubt(doubt_text: str, course_syllabus_nodes: list) -> SemanticClassificationResult`
  - `enqueue_doubt_analysis(db, doubt_id)` (triggers non-blocking async background processing).
- **Architecture**:
  - **Stage 1 (Extractor)**: Identifies propositions, questions, and core confusion phrases.
  - **Stage 2 (Auditor / Matcher)**: Resolves semantic overlap against course syllabus nodes and existing concept registry.
  - **Stage 3 (Deterministic Merger)**: Pure code database transaction; commits metadata and updates frequency ledgers.
- **Swappable Adapters**:
  - `DeterministicSemanticAdapter`: Runs lightweight heuristic/token similarity for lightning-fast test execution.
  - `LLMSemanticAdapter`: Runs production model inference with strict JSON schema outputs.

### 3. Deep Module: `LearningEvidenceAggregator`
- **Seam**: Embedded within `app/modules/analytics/service.py` to power the concept analytics endpoint.
- **Contract**:
  - `get_triangulated_concept_evidence(course_offering_id: UUID, concept_id: UUID) -> TriangulatedEvidencePayload`
- **Aggregation Formula**:
  - Computes `RiskLevel` (`critical` | `moderate` | `healthy` | `insufficient_evidence`) based on:
    - *Summative*: Mean assessment accuracy < threshold.
    - *Formative*: Practice mistake rate > 40% OR hints used per question > 1.5.
    - *Semantic*: Unresolved doubt count > 3 OR detected misconception count > 0.
- **API Response Enhancement**:
  - Exposes `practice_struggle_summary` and `doubt_signal_summary` alongside existing `assessed_count` and `cohort_mean_accuracy`.

### 4. Deep Module: `InterventionDraftingService`
- **Seam**: Endpoint `POST /api/v1/courses/{course_offering_id}/interventions/draft-primer`.
- **Contract**: Accepts `concept_id` or `syllabus_node_id`, retrieves linked doubts and learning objectives, and returns a structured draft primer addressing student confusion.

### 5. Frontend UI Enhancements
- **Doubt Creation & Feed**:
  - Add syllabus topic dropdown in `AskQuestionModal` (optional for students).
  - Display topic/subtopic breadcrumbs on `FeedCard` and `PostDetailView`.
- **Teacher Analytics Studio**:
  - Show Triangulated Evidence breakdown in `TeacherAnalyticsPage`:
    - Quiz Accuracy %
    - Practice Struggle indicators
    - Doubt inquiries & misconception spikes
  - Add "Draft Intervention with AI" action that populates the Phase B primer with synthesized student feedback.

---

## Testing Decisions

1. **Test Highest External Seams**:
   - Test through public API endpoints using HTTP test client rather than testing internal private helper functions.
   - Test `POST /api/v1/doubts` creates the doubt and attaches semantic topic bindings.
   - Test `GET /api/v1/courses/{id}/analytics/concepts` returns aggregated tri-source signals.
   - Test `POST /api/v1/courses/{id}/interventions/draft-primer` produces a valid pedagogical explanation.
2. **Deterministic & Isolated Execution**:
   - Use `DeterministicSemanticAdapter` during automated pytest runs so tests never make external network calls, require API keys, or experience non-deterministic test flakes.
3. **Prior Art in Codebase**:
   - Follow conventions established in `backend/tests/test_doubts_phase11.py`, `backend/tests/test_analytics_phase9.py`, and `backend/tests/test_learning_phase7.py`.

---

## Out of Scope

1. Fully automated teacher-less intervention publishing (faculty approval must always gate intervention assignments).
2. Live real-time audio/speech dictation during doubt creation.
3. Modifying external institutional LMS gradebook synchronization protocols.

---

## Further Notes

- Maintains complete backward compatibility with existing doubts that lack `syllabus_node_id`.
- Adheres strictly to institutional peer-anonymity safeguards: semantic extraction runs on doubt content without exposing author identity to teachers or peers.
