"""NEXUS Graph Engine & Relational Traversal Subsystem.

Provides CRUD for entities and relations, multi-hop recursive CTE neighborhood
extraction with cycle prevention, shortest path search, and semantic graph triple
retrieval for hybrid RAG.
"""

import re
from typing import Any

from sqlalchemy import and_, case, delete, distinct, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.models import (
    KnowledgeEdgeModel,
    KnowledgeNodeModel,
)
from packages.types.nexus_types.schemas import (
    GraphNeighborhood,
    GraphOverview,
    GraphShortestPath,
    GraphTriple,
    KnowledgeEdgeCreate,
    KnowledgeEdgeItem,
    KnowledgeNodeCreate,
    KnowledgeNodeItem,
    KnowledgeNodeUpdate,
)


class GraphEngine:
    """Core knowledge graph storage and relational traversal engine."""

    # ------------------------------------------------------------------------
    # Node CRUD
    # ------------------------------------------------------------------------

    async def create_node(
        self,
        db: AsyncSession,
        user_id: str,
        request: KnowledgeNodeCreate,
    ) -> KnowledgeNodeItem:
        """Create a new knowledge entity node."""
        node = KnowledgeNodeModel(
            user_id=user_id,
            label=request.label.strip(),
            node_type=request.node_type.value
            if hasattr(request.node_type, "value")
            else str(request.node_type),
            properties=request.properties,
            document_id=request.document_id,
            memory_id=request.memory_id,
        )
        db.add(node)
        await db.commit()
        await db.refresh(node)
        return self._node_to_item(node)

    async def get_node(
        self,
        db: AsyncSession,
        user_id: str,
        node_id: str,
    ) -> KnowledgeNodeItem | None:
        """Fetch a specific node by ID."""
        stmt = select(KnowledgeNodeModel).where(
            KnowledgeNodeModel.id == node_id,
            KnowledgeNodeModel.user_id == user_id,
        )
        node = await db.scalar(stmt)
        return self._node_to_item(node) if node else None

    async def update_node(
        self,
        db: AsyncSession,
        user_id: str,
        node_id: str,
        update: KnowledgeNodeUpdate,
    ) -> KnowledgeNodeItem | None:
        """Update a node's label, type, or properties."""
        stmt = select(KnowledgeNodeModel).where(
            KnowledgeNodeModel.id == node_id,
            KnowledgeNodeModel.user_id == user_id,
        )
        node = await db.scalar(stmt)
        if not node:
            return None

        if update.label is not None:
            node.label = update.label.strip()
        if update.node_type is not None:
            node.node_type = (
                update.node_type.value
                if hasattr(update.node_type, "value")
                else str(update.node_type)
            )
        if update.properties is not None:
            node.properties = update.properties

        await db.commit()
        await db.refresh(node)
        return self._node_to_item(node)

    async def delete_node(
        self,
        db: AsyncSession,
        user_id: str,
        node_id: str,
    ) -> bool:
        """Delete a node and cascade all incident edges."""
        stmt = delete(KnowledgeNodeModel).where(
            KnowledgeNodeModel.id == node_id,
            KnowledgeNodeModel.user_id == user_id,
        )
        result = await db.execute(stmt)
        await db.commit()
        rowcount = getattr(result, "rowcount", 0) or 0
        return rowcount > 0

    async def list_nodes(
        self,
        db: AsyncSession,
        user_id: str,
        node_type: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeNodeItem]:
        """List entity nodes with filtering and search."""
        query = select(KnowledgeNodeModel).where(KnowledgeNodeModel.user_id == user_id)
        if node_type:
            query = query.where(KnowledgeNodeModel.node_type == node_type)
        if search:
            query = query.where(KnowledgeNodeModel.label.ilike(f"%{search.strip()}%"))

        query = query.order_by(KnowledgeNodeModel.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        nodes = result.scalars().all()
        return [self._node_to_item(n) for n in nodes]

    # ------------------------------------------------------------------------
    # Edge CRUD
    # ------------------------------------------------------------------------

    async def create_edge(
        self,
        db: AsyncSession,
        user_id: str,
        request: KnowledgeEdgeCreate,
    ) -> KnowledgeEdgeItem:
        """Create a directed relation edge between two nodes."""
        # Validate that both source and target nodes belong to the user
        source_stmt = select(KnowledgeNodeModel).where(
            KnowledgeNodeModel.id == request.source_node_id,
            KnowledgeNodeModel.user_id == user_id,
        )
        target_stmt = select(KnowledgeNodeModel).where(
            KnowledgeNodeModel.id == request.target_node_id,
            KnowledgeNodeModel.user_id == user_id,
        )
        source_node = await db.scalar(source_stmt)
        target_node = await db.scalar(target_stmt)

        if not source_node or not target_node:
            raise ValueError("Source or target node not found or belongs to another user")

        edge = KnowledgeEdgeModel(
            user_id=user_id,
            source_node_id=request.source_node_id,
            target_node_id=request.target_node_id,
            relation_type=(
                request.relation_type.value
                if hasattr(request.relation_type, "value")
                else str(request.relation_type)
            ),
            weight=request.weight,
            properties=request.properties,
        )
        db.add(edge)
        await db.commit()
        await db.refresh(edge)
        return self._edge_to_item(
            edge, source_label=source_node.label, target_label=target_node.label
        )

    async def get_edge(
        self,
        db: AsyncSession,
        user_id: str,
        edge_id: str,
    ) -> KnowledgeEdgeItem | None:
        """Fetch a specific edge by ID."""
        stmt = select(KnowledgeEdgeModel).where(
            KnowledgeEdgeModel.id == edge_id,
            KnowledgeEdgeModel.user_id == user_id,
        )
        edge = await db.scalar(stmt)
        if not edge:
            return None

        # Fetch labels
        source = await db.scalar(
            select(KnowledgeNodeModel.label).where(KnowledgeNodeModel.id == edge.source_node_id)
        )
        target = await db.scalar(
            select(KnowledgeNodeModel.label).where(KnowledgeNodeModel.id == edge.target_node_id)
        )
        return self._edge_to_item(edge, source_label=source, target_label=target)

    async def delete_edge(
        self,
        db: AsyncSession,
        user_id: str,
        edge_id: str,
    ) -> bool:
        """Remove a directed edge."""
        stmt = delete(KnowledgeEdgeModel).where(
            KnowledgeEdgeModel.id == edge_id,
            KnowledgeEdgeModel.user_id == user_id,
        )
        result = await db.execute(stmt)
        await db.commit()
        rowcount = getattr(result, "rowcount", 0) or 0
        return rowcount > 0

    async def list_edges(
        self,
        db: AsyncSession,
        user_id: str,
        source_node_id: str | None = None,
        target_node_id: str | None = None,
        relation_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[KnowledgeEdgeItem]:
        """List edges matching criteria."""
        query = select(KnowledgeEdgeModel).where(KnowledgeEdgeModel.user_id == user_id)
        if source_node_id:
            query = query.where(KnowledgeEdgeModel.source_node_id == source_node_id)
        if target_node_id:
            query = query.where(KnowledgeEdgeModel.target_node_id == target_node_id)
        if relation_type:
            query = query.where(KnowledgeEdgeModel.relation_type == relation_type)

        query = query.order_by(KnowledgeEdgeModel.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        edges = result.scalars().all()
        if not edges:
            return []

        # Batch resolve node labels
        node_ids = set()
        for e in edges:
            node_ids.add(e.source_node_id)
            node_ids.add(e.target_node_id)

        labels_res = await db.execute(
            select(KnowledgeNodeModel.id, KnowledgeNodeModel.label).where(
                KnowledgeNodeModel.id.in_(node_ids)
            )
        )
        label_map: dict[str, str] = {str(row[0]): str(row[1]) for row in labels_res.all()}

        return [
            self._edge_to_item(
                e,
                source_label=label_map.get(e.source_node_id),
                target_label=label_map.get(e.target_node_id),
            )
            for e in edges
        ]

    # ------------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------------

    async def get_overview(self, db: AsyncSession, user_id: str) -> GraphOverview:
        """Aggregate summary counts of nodes and edges for the user."""
        nodes_res = await db.execute(
            select(KnowledgeNodeModel.node_type, func.count(KnowledgeNodeModel.id))
            .where(KnowledgeNodeModel.user_id == user_id)
            .group_by(KnowledgeNodeModel.node_type)
        )
        nodes_by_type: dict[str, int] = {str(row[0]): int(row[1]) for row in nodes_res.all()}
        total_nodes = sum(nodes_by_type.values())

        edges_res = await db.execute(
            select(KnowledgeEdgeModel.relation_type, func.count(KnowledgeEdgeModel.id))
            .where(KnowledgeEdgeModel.user_id == user_id)
            .group_by(KnowledgeEdgeModel.relation_type)
        )
        edges_by_relation: dict[str, int] = {str(row[0]): int(row[1]) for row in edges_res.all()}
        total_edges = sum(edges_by_relation.values())

        return GraphOverview(
            total_nodes=total_nodes,
            total_edges=total_edges,
            nodes_by_type=nodes_by_type,
            edges_by_relation=edges_by_relation,
        )

    # ------------------------------------------------------------------------
    # Recursive CTE Traversal (Neighborhood with Cycle Prevention)
    # ------------------------------------------------------------------------

    async def get_neighborhood(
        self,
        db: AsyncSession,
        user_id: str,
        node_id: str,
        depth: int = 2,
        direction: str = "all",
    ) -> GraphNeighborhood:
        """Traverse k-hop neighborhood using recursive CTE with cycle prevention.

        direction:
        - "all": Bidirectional traversal (both incoming and outgoing relations)
        - "outgoing": Forward paths only
        - "incoming": Reverse paths only
        """
        depth = max(1, min(depth, 3))  # Hard ceiling at 3 hops

        # Ensure starting node exists and belongs to user
        center_node = await self.get_node(db, user_id, node_id)
        if not center_node:
            raise ValueError(f"Center node '{node_id}' not found")

        # Define edge filter condition based on direction
        base_next_node: Any
        if direction == "outgoing":
            base_edge_cond = KnowledgeEdgeModel.source_node_id == node_id
            base_next_node = KnowledgeEdgeModel.target_node_id
        elif direction == "incoming":
            base_edge_cond = KnowledgeEdgeModel.target_node_id == node_id
            base_next_node = KnowledgeEdgeModel.source_node_id
        else:  # "all" bidirectional
            base_edge_cond = or_(
                KnowledgeEdgeModel.source_node_id == node_id,
                KnowledgeEdgeModel.target_node_id == node_id,
            )
            base_next_node = case(
                (KnowledgeEdgeModel.source_node_id == node_id, KnowledgeEdgeModel.target_node_id),
                else_=KnowledgeEdgeModel.source_node_id,
            )

        # Base case: immediate 1-hop connections
        # Path string: ,center_id,next_node_id,
        init_path = literal(",") + literal(node_id) + literal(",") + base_next_node + literal(",")

        base_q = select(
            base_next_node.label("node_id"),
            KnowledgeEdgeModel.id.label("edge_id"),
            literal(1).label("depth"),
            init_path.label("path"),
        ).where(
            KnowledgeEdgeModel.user_id == user_id,
            base_edge_cond,
        )

        cte = base_q.cte(name="neighborhood_cte", recursive=True)

        # Recursive step
        rec_next_node: Any
        if direction == "outgoing":
            rec_edge_cond = KnowledgeEdgeModel.source_node_id == cte.c.node_id
            rec_next_node = KnowledgeEdgeModel.target_node_id
        elif direction == "incoming":
            rec_edge_cond = KnowledgeEdgeModel.target_node_id == cte.c.node_id
            rec_next_node = KnowledgeEdgeModel.source_node_id
        else:
            rec_edge_cond = or_(
                KnowledgeEdgeModel.source_node_id == cte.c.node_id,
                KnowledgeEdgeModel.target_node_id == cte.c.node_id,
            )
            rec_next_node = case(
                (
                    KnowledgeEdgeModel.source_node_id == cte.c.node_id,
                    KnowledgeEdgeModel.target_node_id,
                ),
                else_=KnowledgeEdgeModel.source_node_id,
            )

        rec_q = (
            select(
                rec_next_node.label("node_id"),
                KnowledgeEdgeModel.id.label("edge_id"),
                (cte.c.depth + 1).label("depth"),
                (cte.c.path + rec_next_node + literal(",")).label("path"),
            )
            .select_from(
                cte.join(
                    KnowledgeEdgeModel,
                    and_(
                        KnowledgeEdgeModel.user_id == user_id,
                        rec_edge_cond,
                    ),
                )
            )
            .where(
                cte.c.depth < depth,
                # Cycle prevention: next node must not already exist in path string
                ~cte.c.path.like(
                    literal("%") + literal(",") + rec_next_node + literal(",") + literal("%")
                ),
            )
        )

        full_cte = cte.union_all(rec_q)
        query = select(distinct(full_cte.c.node_id), full_cte.c.edge_id)
        result = await db.execute(query)
        rows = result.all()

        traversed_node_ids = {node_id}
        traversed_edge_ids = set()
        for r_node_id, r_edge_id in rows:
            traversed_node_ids.add(r_node_id)
            if r_edge_id:
                traversed_edge_ids.add(r_edge_id)

        # Fetch complete node models
        nodes_stmt = select(KnowledgeNodeModel).where(
            KnowledgeNodeModel.id.in_(traversed_node_ids),
            KnowledgeNodeModel.user_id == user_id,
        )
        nodes_res = await db.execute(nodes_stmt)
        node_models = nodes_res.scalars().all()
        node_items = [self._node_to_item(n) for n in node_models]
        node_label_map = {n.id: n.label for n in node_models}

        # Fetch complete edge models connecting traversed nodes
        if traversed_edge_ids:
            edges_stmt = select(KnowledgeEdgeModel).where(
                KnowledgeEdgeModel.id.in_(traversed_edge_ids),
                KnowledgeEdgeModel.user_id == user_id,
            )
            edges_res = await db.execute(edges_stmt)
            edge_models = edges_res.scalars().all()
            edge_items = [
                self._edge_to_item(
                    e,
                    source_label=node_label_map.get(e.source_node_id),
                    target_label=node_label_map.get(e.target_node_id),
                )
                for e in edge_models
            ]
        else:
            edge_items = []

        return GraphNeighborhood(
            center_node_id=node_id,
            depth=depth,
            nodes=node_items,
            edges=edge_items,
        )

    # ------------------------------------------------------------------------
    # Shortest Path Traversal
    # ------------------------------------------------------------------------

    async def find_shortest_path(
        self,
        db: AsyncSession,
        user_id: str,
        source_node_id: str,
        target_node_id: str,
        max_depth: int = 5,
    ) -> GraphShortestPath:
        """Compute shortest path between source and target nodes with cycle prevention."""
        max_depth = max(1, min(max_depth, 6))

        if source_node_id == target_node_id:
            node = await self.get_node(db, user_id, source_node_id)
            if not node:
                return GraphShortestPath(
                    found=False,
                    source_node_id=source_node_id,
                    target_node_id=target_node_id,
                )
            return GraphShortestPath(
                found=True,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                length=0,
                total_weight=0.0,
                nodes=[node],
                edges=[],
            )

        # Base case
        base_next = KnowledgeEdgeModel.target_node_id
        base_path = literal(",") + literal(source_node_id) + literal(",") + base_next + literal(",")

        base_q = select(
            base_next.label("node_id"),
            literal(1).label("depth"),
            KnowledgeEdgeModel.weight.label("total_weight"),
            base_path.label("path"),
        ).where(
            KnowledgeEdgeModel.user_id == user_id,
            KnowledgeEdgeModel.source_node_id == source_node_id,
        )

        cte = base_q.cte(name="path_cte", recursive=True)

        rec_next = KnowledgeEdgeModel.target_node_id
        rec_q = (
            select(
                rec_next.label("node_id"),
                (cte.c.depth + 1).label("depth"),
                (cte.c.total_weight + KnowledgeEdgeModel.weight).label("total_weight"),
                (cte.c.path + rec_next + literal(",")).label("path"),
            )
            .select_from(
                cte.join(
                    KnowledgeEdgeModel,
                    and_(
                        KnowledgeEdgeModel.user_id == user_id,
                        KnowledgeEdgeModel.source_node_id == cte.c.node_id,
                    ),
                )
            )
            .where(
                cte.c.depth < max_depth,
                cte.c.node_id != target_node_id,  # stop expanding once destination reached
                ~cte.c.path.like(
                    literal("%") + literal(",") + rec_next + literal(",") + literal("%")
                ),
            )
        )

        full_cte = cte.union_all(rec_q)
        query = (
            select(full_cte.c.depth, full_cte.c.total_weight, full_cte.c.path)
            .where(full_cte.c.node_id == target_node_id)
            .order_by(full_cte.c.depth.asc(), full_cte.c.total_weight.asc())
            .limit(1)
        )

        result = await db.execute(query)
        match = result.first()

        if not match:
            return GraphShortestPath(
                found=False,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
            )

        depth_found, total_weight, path_str = match
        # path_str is like ,src,n1,n2,tgt,
        path_ids = [p for p in path_str.split(",") if p]

        # Fetch nodes in sequence
        nodes_stmt = select(KnowledgeNodeModel).where(
            KnowledgeNodeModel.id.in_(path_ids),
            KnowledgeNodeModel.user_id == user_id,
        )
        nodes_res = await db.execute(nodes_stmt)
        nodes_by_id = {n.id: self._node_to_item(n) for n in nodes_res.scalars().all()}
        ordered_nodes = [nodes_by_id[nid] for nid in path_ids if nid in nodes_by_id]

        # Fetch connecting edges
        edge_items: list[KnowledgeEdgeItem] = []
        for i in range(len(path_ids) - 1):
            s_id = path_ids[i]
            t_id = path_ids[i + 1]
            e_stmt = (
                select(KnowledgeEdgeModel)
                .where(
                    KnowledgeEdgeModel.user_id == user_id,
                    KnowledgeEdgeModel.source_node_id == s_id,
                    KnowledgeEdgeModel.target_node_id == t_id,
                )
                .limit(1)
            )
            e = await db.scalar(e_stmt)
            if e:
                edge_items.append(
                    self._edge_to_item(
                        e,
                        source_label=nodes_by_id[s_id].label if s_id in nodes_by_id else None,
                        target_label=nodes_by_id[t_id].label if t_id in nodes_by_id else None,
                    )
                )

        return GraphShortestPath(
            found=True,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            length=depth_found,
            total_weight=float(total_weight),
            nodes=ordered_nodes,
            edges=edge_items,
        )

    # ------------------------------------------------------------------------
    # Semantic Triple Extraction for Hybrid RAG
    # ------------------------------------------------------------------------

    async def find_relevant_triples(
        self,
        db: AsyncSession,
        user_id: str,
        query: str,
        limit: int = 15,
    ) -> list[GraphTriple]:
        """Discover knowledge graph triples relevant to a search query or context."""
        # 1. Extract potential entity tokens/terms from query (clean non-alphanumerics)
        tokens = [t.lower() for t in re.findall(r"\b[A-Za-z0-9_\-\.]{3,}\b", query)]
        if not tokens:
            return []

        # 2. Find nodes whose labels match any token or phrase
        conditions = [KnowledgeNodeModel.label.ilike(f"%{tok}%") for tok in tokens[:10]]
        nodes_stmt = (
            select(KnowledgeNodeModel)
            .where(
                KnowledgeNodeModel.user_id == user_id,
                or_(*conditions),
            )
            .limit(10)
        )
        nodes_res = await db.execute(nodes_stmt)
        matched_nodes = nodes_res.scalars().all()
        if not matched_nodes:
            return []

        matched_node_ids = [n.id for n in matched_nodes]

        # 3. Retrieve 1-hop connected edges
        edges_stmt = (
            select(
                KnowledgeEdgeModel,
                KnowledgeNodeModel.label.label("source_label"),
            )
            .join(KnowledgeNodeModel, KnowledgeNodeModel.id == KnowledgeEdgeModel.source_node_id)
            .where(
                KnowledgeEdgeModel.user_id == user_id,
                or_(
                    KnowledgeEdgeModel.source_node_id.in_(matched_node_ids),
                    KnowledgeEdgeModel.target_node_id.in_(matched_node_ids),
                ),
            )
            .order_by(KnowledgeEdgeModel.weight.desc())
            .limit(limit)
        )
        edges_res = await db.execute(edges_stmt)
        edge_rows = edges_res.all()

        if not edge_rows:
            return []

        # Collect target node IDs to fetch target labels
        target_ids = {e.KnowledgeEdgeModel.target_node_id for e in edge_rows}
        targets_res = await db.execute(
            select(KnowledgeNodeModel.id, KnowledgeNodeModel.label).where(
                KnowledgeNodeModel.id.in_(target_ids)
            )
        )
        target_label_map: dict[str, str] = {str(row[0]): str(row[1]) for row in targets_res.all()}

        triples: list[GraphTriple] = []
        for row in edge_rows:
            e: KnowledgeEdgeModel = row.KnowledgeEdgeModel
            src_label = row.source_label
            tgt_label = target_label_map.get(e.target_node_id, e.target_node_id)
            triples.append(
                GraphTriple(
                    subject=src_label,
                    relation=e.relation_type,
                    object=tgt_label,
                    weight=e.weight,
                    properties=e.properties,
                )
            )

        return triples

    # ------------------------------------------------------------------------
    # Serialization Helpers
    # ------------------------------------------------------------------------

    def _node_to_item(self, node: KnowledgeNodeModel) -> KnowledgeNodeItem:
        return KnowledgeNodeItem(
            id=node.id,
            user_id=node.user_id,
            label=node.label,
            node_type=node.node_type,
            properties=node.properties or {},
            document_id=node.document_id,
            memory_id=node.memory_id,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    def _edge_to_item(
        self,
        edge: KnowledgeEdgeModel,
        source_label: str | None = None,
        target_label: str | None = None,
    ) -> KnowledgeEdgeItem:
        return KnowledgeEdgeItem(
            id=edge.id,
            user_id=edge.user_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            relation_type=edge.relation_type,
            weight=edge.weight,
            properties=edge.properties or {},
            created_at=edge.created_at,
            source_label=source_label,
            target_label=target_label,
        )


_graph_engine: GraphEngine | None = None


def get_graph_engine() -> GraphEngine:
    global _graph_engine
    if _graph_engine is None:
        _graph_engine = GraphEngine()
    return _graph_engine
