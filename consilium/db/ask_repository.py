"""Repository for Q&A history persistence."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from consilium.config import Settings, get_settings
from consilium.db.connection import DatabasePool, get_pool
from consilium.ask.models import AskResult, AskResponse
from consilium.core.enums import SignalType, ConfidenceLevel


class AskRepository:
    """Repository for storing and retrieving Q&A history."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._pool: DatabasePool | None = None

    async def _ensure_pool(self) -> DatabasePool:
        """Ensure database pool is available."""
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def save_question(self, result: AskResult) -> int:
        """
        Save a Q&A session to history.

        Args:
            result: The AskResult to save

        Returns:
            The ID of the saved question
        """
        pool = await self._ensure_pool()

        # Insert question
        question_query = """
            INSERT INTO ask_questions
                (question, tickers, agents, include_market_data,
                 input_tokens, output_tokens, cost_usd, created_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    question_query,
                    (
                        result.question,
                        json.dumps(result.tickers),
                        json.dumps(result.agents_queried),
                        result.include_market_data,
                        result.total_input_tokens,
                        result.total_output_tokens,
                        float(result.total_cost_usd),
                        result.created_at,
                    ),
                )
                question_id = cursor.lastrowid

                # Insert responses
                if result.responses:
                    response_query = """
                        INSERT INTO ask_responses
                            (question_id, agent_id, agent_name,
                             signal, confidence, reasoning, key_factors, risks,
                             time_horizon, target_price, input_tokens, output_tokens,
                             created_at)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    for response in result.responses:
                        await cursor.execute(
                            response_query,
                            (
                                question_id,
                                response.agent_id,
                                response.agent_name,
                                response.signal.value,
                                response.confidence.value,
                                response.reasoning,
                                json.dumps(response.key_factors),
                                json.dumps(response.risks),
                                response.time_horizon,
                                float(response.target_price) if response.target_price else None,
                                response.input_tokens,
                                response.output_tokens,
                                result.created_at,
                            ),
                        )

                await conn.commit()
                return question_id

    async def get_question(self, question_id: int) -> AskResult | None:
        """
        Retrieve a Q&A session by ID.

        Args:
            question_id: The question ID

        Returns:
            AskResult if found, None otherwise
        """
        pool = await self._ensure_pool()

        question_query = """
            SELECT id, question, tickers, agents, include_market_data,
                   input_tokens, output_tokens, cost_usd, created_at
            FROM ask_questions
            WHERE id = %s
        """

        response_query = """
            SELECT agent_id, agent_name, signal, confidence, reasoning,
                   key_factors, risks, time_horizon, target_price,
                   input_tokens, output_tokens
            FROM ask_responses
            WHERE question_id = %s
            ORDER BY id
        """

        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(question_query, (question_id,))
                row = await cursor.fetchone()

                if not row:
                    return None

                # Get responses
                await cursor.execute(response_query, (question_id,))
                response_rows = await cursor.fetchall()

                responses = []
                for r_row in response_rows:
                    responses.append(
                        AskResponse(
                            agent_id=r_row[0],
                            agent_name=r_row[1],
                            signal=SignalType(r_row[2]),
                            confidence=ConfidenceLevel(r_row[3]),
                            reasoning=r_row[4],
                            key_factors=json.loads(r_row[5]) if r_row[5] else [],
                            risks=json.loads(r_row[6]) if r_row[6] else [],
                            time_horizon=r_row[7],
                            target_price=Decimal(str(r_row[8])) if r_row[8] else None,
                            input_tokens=r_row[9] or 0,
                            output_tokens=r_row[10] or 0,
                        )
                    )

                return AskResult(
                    id=row[0],
                    question=row[1],
                    tickers=json.loads(row[2]) if row[2] else [],
                    agents_queried=json.loads(row[3]) if row[3] else [],
                    responses=responses,
                    include_market_data=bool(row[4]),
                    total_input_tokens=row[5] or 0,
                    total_output_tokens=row[6] or 0,
                    total_cost_usd=Decimal(str(row[7])) if row[7] else Decimal("0"),
                    created_at=row[8] or datetime.now(),
                )

    async def list_questions(
        self,
        agent_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List Q&A questions with optional filtering.

        Args:
            agent_id: Filter by agent (searches in agents JSON array)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of question summaries
        """
        pool = await self._ensure_pool()

        if agent_id:
            query = """
                SELECT id, question, tickers, agents, cost_usd, created_at
                FROM ask_questions
                WHERE JSON_CONTAINS(agents, %s)
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params = (json.dumps(agent_id), limit, offset)
        else:
            query = """
                SELECT id, question, tickers, agents, cost_usd, created_at
                FROM ask_questions
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params = (limit, offset)

        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                rows = await cursor.fetchall()

                return [
                    {
                        "id": row[0],
                        "question": row[1][:100] + "..." if len(row[1]) > 100 else row[1],
                        "tickers": json.loads(row[2]) if row[2] else [],
                        "agents": json.loads(row[3]) if row[3] else [],
                        "cost_usd": Decimal(str(row[4])) if row[4] else Decimal("0"),
                        "created_at": row[5],
                    }
                    for row in rows
                ]

    async def delete_question(self, question_id: int) -> bool:
        """
        Delete a Q&A session.

        Args:
            question_id: The question ID to delete

        Returns:
            True if deleted, False if not found
        """
        pool = await self._ensure_pool()

        query = "DELETE FROM ask_questions WHERE id = %s"

        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (question_id,))
                await conn.commit()
                return cursor.rowcount > 0
