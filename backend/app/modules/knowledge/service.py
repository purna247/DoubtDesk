from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException
from app.modules.knowledge.models import (
    CourseContentVersion,
    SyllabusNode,
    Concept,
    ConceptVersion,
    CourseContentConcept,
    LearningObjective,
)
from app.modules.knowledge.schemas import (
    CourseContentVersionCreate,
    PublishContentVersionRequest,
    CourseContentVersionOut,
    SyllabusNodeCreate,
    SyllabusNodeUpdate,
    SyllabusNodeOut,
    SyllabusNodeTreeOut,
    ConceptCreate,
    ConceptVersionCreate,
    ConceptOut,
    ConceptVersionOut,
    ConceptSummaryOut,
    CourseContentConceptBindRequest,
    CourseContentConceptOut,
    LearningObjectiveCreate,
    LearningObjectiveOut,
    SyllabusTreeResponse,
)
from app.modules.academics.models import (
    CourseOffering,
    CourseOfferingFaculty,
    CourseOfferingEnrolment,
)
from app.modules.auth.models import InstitutionMembership


class KnowledgeService:

    @staticmethod
    async def verify_teacher_access(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool = False,
    ) -> bool:
        if is_admin:
            return True

        stmt = (
            select(CourseOfferingFaculty)
            .join(InstitutionMembership, CourseOfferingFaculty.institution_membership_id == InstitutionMembership.id)
            .where(
                CourseOfferingFaculty.course_offering_id == offering_id,
                CourseOfferingFaculty.institution_id == tenant_id,
                InstitutionMembership.user_id == user_id,
                CourseOfferingFaculty.status == "active",
                CourseOfferingFaculty.can_manage_content == True,
            )
        )
        res = await db.execute(stmt)
        if not res.scalars().first():
            raise AppException(
                status_code=403,
                code="TEACHER_NOT_ASSIGNED",
                message="You are not authorized to manage content for this course offering.",
            )
        return True

    @staticmethod
    async def verify_student_access(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        stmt = (
            select(CourseOfferingEnrolment)
            .join(InstitutionMembership, CourseOfferingEnrolment.institution_membership_id == InstitutionMembership.id)
            .where(
                CourseOfferingEnrolment.course_offering_id == offering_id,
                CourseOfferingEnrolment.institution_id == tenant_id,
                InstitutionMembership.user_id == user_id,
                CourseOfferingEnrolment.enrolment_status == "active",
            )
        )
        res = await db.execute(stmt)
        if not res.scalars().first():
            raise AppException(
                status_code=403,
                code="STUDENT_NOT_ENROLLED",
                message="You are not actively enrolled in this course offering.",
            )
        return True

    @staticmethod
    async def get_or_create_draft_version(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CourseContentVersion:
        # Check if offering exists in tenant
        offering = await db.get(CourseOffering, offering_id)
        if not offering or offering.institution_id != tenant_id:
            raise AppException(
                status_code=404,
                code="OFFERING_NOT_FOUND",
                message="Course offering not found in this institution.",
            )

        # Check for existing draft or in_review version
        stmt = select(CourseContentVersion).where(
            CourseContentVersion.course_offering_id == offering_id,
            CourseContentVersion.institution_id == tenant_id,
            CourseContentVersion.status.in_(["draft", "in_review"]),
        ).order_by(CourseContentVersion.version_number.desc())
        res = await db.execute(stmt)
        draft = res.scalars().first()
        if draft:
            return draft

        # Determine next version number
        v_stmt = select(func.max(CourseContentVersion.version_number)).where(
            CourseContentVersion.course_offering_id == offering_id,
            CourseContentVersion.institution_id == tenant_id,
        )
        v_res = await db.execute(v_stmt)
        current_max = v_res.scalar() or 0
        new_version_num = current_max + 1

        new_version = CourseContentVersion(
            institution_id=tenant_id,
            course_offering_id=offering_id,
            version_number=new_version_num,
            status="draft",
            created_by_user_id=user_id,
        )
        db.add(new_version)
        await db.flush()

        # If there is a previous published version, clone its nodes and concept bindings
        if current_max > 0:
            pub_stmt = (
                select(CourseContentVersion)
                .where(
                    CourseContentVersion.course_offering_id == offering_id,
                    CourseContentVersion.institution_id == tenant_id,
                    CourseContentVersion.status.in_(["published", "superseded"]),
                )
                .order_by(CourseContentVersion.version_number.desc())
                .limit(1)
            )
            pub_res = await db.execute(pub_stmt)
            prev_pub = pub_res.scalars().first()
            if prev_pub:
                # Clone nodes
                nodes_stmt = (
                    select(SyllabusNode)
                    .where(SyllabusNode.course_content_version_id == prev_pub.id)
                    .order_by(SyllabusNode.sequence_no)
                )
                old_nodes = (await db.execute(nodes_stmt)).scalars().all()
                old_to_new_id: Dict[uuid.UUID, uuid.UUID] = {}

                # First pass: root nodes
                for node in old_nodes:
                    if node.parent_node_id is None:
                        new_node_id = uuid.uuid4()
                        old_to_new_id[node.id] = new_node_id
                        cloned_node = SyllabusNode(
                            id=new_node_id,
                            institution_id=tenant_id,
                            course_content_version_id=new_version.id,
                            parent_node_id=None,
                            node_type=node.node_type,
                            title=node.title,
                            description=node.description,
                            sequence_no=node.sequence_no,
                            source_chunk_id=node.source_chunk_id,
                            review_status=node.review_status,
                        )
                        db.add(cloned_node)
                await db.flush()

                # Second pass: child nodes
                for node in old_nodes:
                    if node.parent_node_id is not None:
                        new_node_id = uuid.uuid4()
                        old_to_new_id[node.id] = new_node_id
                        cloned_node = SyllabusNode(
                            id=new_node_id,
                            institution_id=tenant_id,
                            course_content_version_id=new_version.id,
                            parent_node_id=old_to_new_id.get(node.parent_node_id),
                            node_type=node.node_type,
                            title=node.title,
                            description=node.description,
                            sequence_no=node.sequence_no,
                            source_chunk_id=node.source_chunk_id,
                            review_status=node.review_status,
                        )
                        db.add(cloned_node)
                await db.flush()

                # Clone concept bindings
                bind_stmt = select(CourseContentConcept).where(
                    CourseContentConcept.course_content_version_id == prev_pub.id
                )
                old_bindings = (await db.execute(bind_stmt)).scalars().all()
                for b in old_bindings:
                    cloned_binding = CourseContentConcept(
                        course_content_version_id=new_version.id,
                        concept_id=b.concept_id,
                        institution_id=tenant_id,
                        primary_syllabus_node_id=old_to_new_id.get(b.primary_syllabus_node_id) if b.primary_syllabus_node_id else None,
                        importance_weight=b.importance_weight,
                    )
                    db.add(cloned_binding)

        await db.commit()
        await db.refresh(new_version)
        return new_version

    @staticmethod
    async def publish_content_version(
        db: AsyncSession,
        version_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        change_summary: Optional[str] = None,
    ) -> CourseContentVersion:
        version = await db.get(CourseContentVersion, version_id)
        if not version or version.institution_id != tenant_id:
            raise AppException(
                status_code=404,
                code="VERSION_NOT_FOUND",
                message="Course content version not found.",
            )

        if version.status not in ["draft", "in_review", "approved"]:
            raise AppException(
                status_code=400,
                code="INVALID_VERSION_STATE",
                message=f"Version in '{version.status}' state cannot be published.",
            )

        # Ensure at least 1 node exists
        node_count_stmt = select(func.count(SyllabusNode.id)).where(
            SyllabusNode.course_content_version_id == version_id
        )
        node_count = (await db.execute(node_count_stmt)).scalar() or 0
        if node_count == 0:
            raise AppException(
                status_code=400,
                code="EMPTY_SYLLABUS",
                message="Cannot publish a course content version with no syllabus nodes.",
            )

        now = datetime.now(timezone.utc)

        # Supersede any currently published version for this course offering
        prev_pub_stmt = select(CourseContentVersion).where(
            CourseContentVersion.course_offering_id == version.course_offering_id,
            CourseContentVersion.institution_id == tenant_id,
            CourseContentVersion.status == "published",
        )
        prev_pub_res = await db.execute(prev_pub_stmt)
        prev_pub = prev_pub_res.scalars().first()
        if prev_pub:
            prev_pub.status = "superseded"
            prev_pub.updated_at = now

        version.status = "published"
        version.reviewed_by_user_id = user_id
        version.approved_at = now
        version.published_at = now
        if change_summary:
            version.change_summary = change_summary
        version.updated_at = now

        await db.commit()
        await db.refresh(version)
        return version

    @staticmethod
    async def create_syllabus_node(
        db: AsyncSession,
        version_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: SyllabusNodeCreate,
    ) -> SyllabusNode:
        version = await db.get(CourseContentVersion, version_id)
        if not version or version.institution_id != tenant_id:
            raise AppException(
                status_code=404,
                code="VERSION_NOT_FOUND",
                message="Course content version not found.",
            )

        if version.status not in ["draft", "in_review"]:
            raise AppException(
                status_code=400,
                code="VERSION_NOT_EDITABLE",
                message="Cannot add nodes to a published or archived content version.",
            )

        if data.parent_node_id:
            parent = await db.get(SyllabusNode, data.parent_node_id)
            if not parent or parent.course_content_version_id != version_id:
                raise AppException(
                    status_code=400,
                    code="INVALID_PARENT_NODE",
                    message="Parent node does not exist in this content version.",
                )

        node = SyllabusNode(
            institution_id=tenant_id,
            course_content_version_id=version_id,
            parent_node_id=data.parent_node_id,
            node_type=data.node_type,
            title=data.title,
            description=data.description,
            sequence_no=data.sequence_no,
            source_chunk_id=data.source_chunk_id,
            review_status="approved",
        )
        db.add(node)
        await db.commit()
        await db.refresh(node)
        return node

    @staticmethod
    async def update_syllabus_node(
        db: AsyncSession,
        node_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: SyllabusNodeUpdate,
    ) -> SyllabusNode:
        node = await db.get(SyllabusNode, node_id)
        if not node or node.institution_id != tenant_id:
            raise AppException(
                status_code=404,
                code="NODE_NOT_FOUND",
                message="Syllabus node not found.",
            )

        version = await db.get(CourseContentVersion, node.course_content_version_id)
        if not version or version.status not in ["draft", "in_review"]:
            raise AppException(
                status_code=400,
                code="VERSION_NOT_EDITABLE",
                message="Cannot edit nodes in a published or archived version.",
            )

        if data.title is not None:
            node.title = data.title
        if data.description is not None:
            node.description = data.description
        if data.sequence_no is not None:
            node.sequence_no = data.sequence_no
        if data.parent_node_id is not None:
            if data.parent_node_id == node.id:
                raise AppException(status_code=400, code="SELF_PARENT", message="Node cannot be its own parent.")
            parent = await db.get(SyllabusNode, data.parent_node_id)
            if not parent or parent.course_content_version_id != node.course_content_version_id:
                raise AppException(status_code=400, code="INVALID_PARENT_NODE", message="Invalid parent node.")
            node.parent_node_id = data.parent_node_id
        if data.review_status is not None:
            node.review_status = data.review_status

        await db.commit()
        await db.refresh(node)
        return node

    @staticmethod
    async def approve_syllabus_node(
        db: AsyncSession,
        node_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SyllabusNode:
        node = await db.get(SyllabusNode, node_id)
        if not node or node.institution_id != tenant_id:
            raise AppException(
                status_code=404,
                code="NODE_NOT_FOUND",
                message="Syllabus node not found.",
            )

        version = await db.get(CourseContentVersion, node.course_content_version_id)
        if not version or version.status not in ["draft", "in_review"]:
            raise AppException(
                status_code=400,
                code="VERSION_NOT_EDITABLE",
                message="Cannot approve nodes in a published or archived version.",
            )

        node.review_status = "approved"
        await db.commit()
        await db.refresh(node)
        return node

    @staticmethod
    async def delete_syllabus_node(
        db: AsyncSession,
        node_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        node = await db.get(SyllabusNode, node_id)
        if not node or node.institution_id != tenant_id:
            raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Syllabus node not found.")

        version = await db.get(CourseContentVersion, node.course_content_version_id)
        if not version or version.status not in ["draft", "in_review"]:
            raise AppException(
                status_code=400,
                code="VERSION_NOT_EDITABLE",
                message="Cannot delete nodes in a published or archived version.",
            )

        await db.delete(node)
        await db.commit()

    @staticmethod
    async def create_concept(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        data: ConceptCreate,
        user_id: uuid.UUID,
    ) -> Concept:
        if data.concept_code:
            existing = await db.execute(
                select(Concept).where(
                    Concept.institution_id == tenant_id,
                    Concept.concept_code == data.concept_code,
                )
            )
            if existing.scalars().first():
                raise AppException(
                    status_code=409,
                    code="CONCEPT_CODE_EXISTS",
                    message=f"Concept code '{data.concept_code}' already exists.",
                )

        concept = Concept(
            institution_id=tenant_id,
            concept_code=data.concept_code,
            canonical_name=data.canonical_name,
            status="active",
        )
        db.add(concept)
        await db.flush()

        v1 = ConceptVersion(
            institution_id=tenant_id,
            concept_id=concept.id,
            version_number=1,
            definition=data.definition,
            explanation=data.explanation,
            review_status="teacher_approved",
            created_by_user_id=user_id,
            approved_by_user_id=user_id,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(v1)
        await db.commit()
        await db.refresh(concept)
        return concept

    @staticmethod
    async def create_concept_version(
        db: AsyncSession,
        concept_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: ConceptVersionCreate,
        user_id: uuid.UUID,
    ) -> ConceptVersion:
        concept = await db.get(Concept, concept_id)
        if not concept or concept.institution_id != tenant_id:
            raise AppException(status_code=404, code="CONCEPT_NOT_FOUND", message="Concept not found.")

        v_stmt = select(func.max(ConceptVersion.version_number)).where(
            ConceptVersion.concept_id == concept_id
        )
        v_res = await db.execute(v_stmt)
        current_max = v_res.scalar() or 0

        new_v = ConceptVersion(
            institution_id=tenant_id,
            concept_id=concept_id,
            version_number=current_max + 1,
            definition=data.definition,
            explanation=data.explanation,
            review_status="teacher_approved",
            created_by_user_id=user_id,
            approved_by_user_id=user_id,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(new_v)
        await db.commit()
        await db.refresh(new_v)
        return new_v

    @staticmethod
    async def bind_concept_to_content(
        db: AsyncSession,
        version_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: CourseContentConceptBindRequest,
    ) -> CourseContentConcept:
        version = await db.get(CourseContentVersion, version_id)
        if not version or version.institution_id != tenant_id:
            raise AppException(status_code=404, code="VERSION_NOT_FOUND", message="Content version not found.")

        if version.status not in ["draft", "in_review"]:
            raise AppException(
                status_code=400,
                code="VERSION_NOT_EDITABLE",
                message="Cannot bind concepts to a published or archived version.",
            )

        concept = await db.get(Concept, data.concept_id)
        if not concept or concept.institution_id != tenant_id:
            raise AppException(status_code=404, code="CONCEPT_NOT_FOUND", message="Concept not found.")

        if data.primary_syllabus_node_id:
            node = await db.get(SyllabusNode, data.primary_syllabus_node_id)
            if not node or node.course_content_version_id != version_id:
                raise AppException(
                    status_code=400,
                    code="INVALID_NODE",
                    message="Primary syllabus node must belong to this content version.",
                )

        stmt = select(CourseContentConcept).where(
            CourseContentConcept.course_content_version_id == version_id,
            CourseContentConcept.concept_id == data.concept_id,
        )
        res = await db.execute(stmt)
        existing = res.scalars().first()

        if existing:
            existing.primary_syllabus_node_id = data.primary_syllabus_node_id
            existing.importance_weight = data.importance_weight
            binding = existing
        else:
            binding = CourseContentConcept(
                course_content_version_id=version_id,
                concept_id=data.concept_id,
                institution_id=tenant_id,
                primary_syllabus_node_id=data.primary_syllabus_node_id,
                importance_weight=data.importance_weight,
            )
            db.add(binding)

        await db.commit()
        await db.refresh(binding)
        return binding

    @staticmethod
    async def create_learning_objective(
        db: AsyncSession,
        version_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: LearningObjectiveCreate,
    ) -> LearningObjective:
        version = await db.get(CourseContentVersion, version_id)
        if not version or version.institution_id != tenant_id:
            raise AppException(status_code=404, code="VERSION_NOT_FOUND", message="Content version not found.")

        if version.status not in ["draft", "in_review"]:
            raise AppException(status_code=400, code="VERSION_NOT_EDITABLE", message="Content version is not editable.")

        lo = LearningObjective(
            institution_id=tenant_id,
            course_content_version_id=version_id,
            syllabus_node_id=data.syllabus_node_id,
            concept_id=data.concept_id,
            objective_code=data.objective_code,
            description=data.description,
            bloom_level=data.bloom_level,
            sequence_no=data.sequence_no,
        )
        db.add(lo)
        await db.commit()
        await db.refresh(lo)
        return lo

    @staticmethod
    async def resolve_teacher_syllabus(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool = False,
    ) -> SyllabusTreeResponse:
        await KnowledgeService.verify_teacher_access(
            db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=user_id, is_admin=is_admin
        )

        # Look for draft/in_review first; then published; or create initial draft
        stmt = (
            select(CourseContentVersion)
            .where(
                CourseContentVersion.course_offering_id == offering_id,
                CourseContentVersion.institution_id == tenant_id,
                CourseContentVersion.status.in_(["draft", "in_review"]),
            )
            .order_by(CourseContentVersion.version_number.desc())
        )
        res = await db.execute(stmt)
        target_version = res.scalars().first()

        if not target_version:
            pub_stmt = (
                select(CourseContentVersion)
                .where(
                    CourseContentVersion.course_offering_id == offering_id,
                    CourseContentVersion.institution_id == tenant_id,
                    CourseContentVersion.status == "published",
                )
                .order_by(CourseContentVersion.version_number.desc())
            )
            pub_res = await db.execute(pub_stmt)
            target_version = pub_res.scalars().first()

        if not target_version:
            # Create first draft version
            target_version = await KnowledgeService.get_or_create_draft_version(
                db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=user_id
            )

        return await KnowledgeService._build_syllabus_tree_response(db, target_version)

    @staticmethod
    async def resolve_student_syllabus(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SyllabusTreeResponse:
        await KnowledgeService.verify_student_access(
            db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=user_id
        )

        pub_stmt = select(CourseContentVersion).where(
            CourseContentVersion.course_offering_id == offering_id,
            CourseContentVersion.institution_id == tenant_id,
            CourseContentVersion.status == "published",
        )
        pub_res = await db.execute(pub_stmt)
        pub_version = pub_res.scalars().first()

        if not pub_version:
            raise AppException(
                status_code=404,
                code="SYLLABUS_NOT_PUBLISHED",
                message="The syllabus for this course offering has not been published yet.",
            )

        return await KnowledgeService._build_syllabus_tree_response(db, pub_version, approved_only=True)

    @staticmethod
    async def _build_syllabus_tree_response(
        db: AsyncSession,
        version: CourseContentVersion,
        approved_only: bool = False,
    ) -> SyllabusTreeResponse:
        # Fetch all syllabus nodes
        node_stmt = (
            select(SyllabusNode)
            .where(SyllabusNode.course_content_version_id == version.id)
            .order_by(SyllabusNode.sequence_no)
        )
        if approved_only:
            node_stmt=node_stmt.where(SyllabusNode.review_status=="approved")
        nodes = (await db.execute(node_stmt)).scalars().all()
        if approved_only:
            approved_ids={n.id for n in nodes}
            nodes=[n for n in nodes if n.parent_node_id is None or n.parent_node_id in approved_ids]

        # Fetch all learning objectives
        lo_stmt = (
            select(LearningObjective)
            .where(LearningObjective.course_content_version_id == version.id)
            .order_by(LearningObjective.sequence_no)
        )
        los = (await db.execute(lo_stmt)).scalars().all()
        los_by_node: Dict[uuid.UUID, List[LearningObjectiveOut]] = {}
        for lo in los:
            if lo.syllabus_node_id:
                los_by_node.setdefault(lo.syllabus_node_id, []).append(
                    LearningObjectiveOut.model_validate(lo)
                )

        # Build tree structure
        node_tree_map: Dict[uuid.UUID, SyllabusNodeTreeOut] = {}
        for n in nodes:
            node_tree_map[n.id] = SyllabusNodeTreeOut(
                id=n.id,
                institution_id=n.institution_id,
                course_content_version_id=n.course_content_version_id,
                parent_node_id=n.parent_node_id,
                node_type=n.node_type,
                title=n.title,
                description=n.description,
                sequence_no=n.sequence_no,
                source_chunk_id=n.source_chunk_id,
                review_status=n.review_status,
                created_at=n.created_at,
                updated_at=n.updated_at,
                children=[],
                learning_objectives=los_by_node.get(n.id, []),
            )

        root_nodes: List[SyllabusNodeTreeOut] = []
        for n in nodes:
            tree_item = node_tree_map[n.id]
            if n.parent_node_id and n.parent_node_id in node_tree_map:
                node_tree_map[n.parent_node_id].children.append(tree_item)
            else:
                root_nodes.append(tree_item)

        # Fetch bound concepts
        bind_stmt = (
            select(CourseContentConcept, Concept)
            .join(Concept, CourseContentConcept.concept_id == Concept.id)
            .where(CourseContentConcept.course_content_version_id == version.id)
        )
        if approved_only:
            latest_versions=(select(ConceptVersion.concept_id.label("concept_id"),func.max(ConceptVersion.version_number).label("version_number")).group_by(ConceptVersion.concept_id).subquery())
            bind_stmt=bind_stmt.join(latest_versions,latest_versions.c.concept_id==Concept.id).join(ConceptVersion,and_(ConceptVersion.concept_id==Concept.id,ConceptVersion.version_number==latest_versions.c.version_number)).where(ConceptVersion.review_status=="teacher_approved")
        bind_res = await db.execute(bind_stmt)
        bound_concepts: List[ConceptSummaryOut] = []

        for binding, concept in bind_res.all():
            # Get latest approved version for concept
            v_stmt = (
                select(ConceptVersion)
                .where(ConceptVersion.concept_id == concept.id)
                .order_by(ConceptVersion.version_number.desc())
                .limit(1)
            )
            v_res = await db.execute(v_stmt)
            latest_v = v_res.scalars().first()
            bound_concepts.append(
                ConceptSummaryOut(
                    id=concept.id,
                    concept_code=concept.concept_code,
                    canonical_name=concept.canonical_name,
                    definition=latest_v.definition if latest_v else "",
                    importance_weight=float(binding.importance_weight),
                    primary_syllabus_node_id=binding.primary_syllabus_node_id,
                )
            )

        return SyllabusTreeResponse(
            version=CourseContentVersionOut.model_validate(version),
            nodes=root_nodes,
            concepts=bound_concepts,
        )

