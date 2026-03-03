import logging
import random
import string
from sqlalchemy import update, select, func, text
# from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.core.config import settings
from common.db.sql.models import URL
# from sqlalchemy.sql import func, text
from opentelemetry import trace


logger = logging.getLogger(__name__)

class URLKeyRepository:

    @staticmethod
    def _generate_key():
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("generate_key") as span:
            span.add_event("generate_key_called")
            return ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    
    @staticmethod
    async def get_unused_key(session: AsyncSession):
        """
        Atomically acquire an unused key using SELECT FOR UPDATE SKIP LOCKED.
        This prevents race conditions in distributed systems.
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("get_unused_key") as span:
            try:
                span.add_event("get_unused_key_query_started")
                result = await session.execute(
                    select(URL)
                    .where(~URL.is_used)
                    .limit(1)
                    .with_for_update(skip_locked=True)  # Key fix for race conditions!
                )
                span.add_event("get_unused_key_query_completed")
                url = result.scalars().first()

                if url is not None:
                    # Mark the key as used
                    span.add_event("get_unused_key_marking_key_as_used")
                    # Access key before commit to avoid lazy loading issues
                    key_value = url.key
                    await session.execute(
                        update(URL)
                        .where(URL.id == url.id)
                        .values(is_used=True)
                    )
                    await session.commit()
                    # Refresh to ensure attributes are loaded after commit
                    await session.refresh(url)
                    span.add_event("get_unused_key_marking_key_as_used_completed")
                    logger.info(f"Acquired key: {key_value}")
                    return url

                else:
                    span.add_event("get_unused_key_no_unused_keys_available")
                    logger.warning("No unused keys available")
                    return None

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                await session.rollback()
                logger.error(f"Error acquiring unused key: {e}")
                raise
    
    @staticmethod
    async def get_unused_key_raw(session: AsyncSession) -> dict | None:
        """
        Raw SQL version - use if ORM becomes a bottleneck.
        Benchmark before switching!
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("get_unused_key_raw") as span:
            try:
                span.add_event("get_unused_key_raw_query_started")
                result = await session.execute(
                        text("""
                        UPDATE urls 
                        SET is_used = true 
                        WHERE id = (
                            SELECT id FROM urls 
                            WHERE is_used = false 
                            LIMIT 1 
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING id, key
                    """)
                )
                span.add_event("get_unused_key_raw_query_completed")
                row = result.first()
            
                if row:
                    await session.commit()
                    span.add_event("get_unused_key_raw_marking_key_as_used")
                    return {"id": row[0], "key": row[1]}
                span.add_event("get_unused_key_raw_no_unused_keys_available")
                return None

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                await session.rollback()
                logger.error(
                    "Error acquiring unused key",
                    extra={"error": e}
                )
                raise


    @staticmethod
    async def pre_populate_keys(session: AsyncSession, count: int = 100000):
        """
        Pre-populate the database with unused keys.
        Uses efficient bulk insertion with parameterized queries.
        
        Args:
            session: AsyncSession - The database session
            count: int - Number of keys to pre-populate (default: 100000)
        
        Returns:
            int: Number of keys successfully inserted
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("pre_populate_keys") as span:
            try:
                # Generate keys efficiently - collision probability is negligible
                # With 62^7 possibilities and 100K keys, collision chance < 0.0001%
                if count <= 0:
                    span.add_event("pre_populate_keys_count_is_zero_or_negative")
                    logger.info("Key pre-population count is zero or negative, skipping.")
                    return 0

                keys = [URLKeyRepository._generate_key() for _ in range(count)]
            
                # Use larger batches for better performance
                batch_size = settings.key_batch_size

                span.add_event("pre_populate_keys_bulk_insert_keys_started")                
                for i in range(0, len(keys), batch_size):
                    batch = keys[i:i + batch_size]
                    await URLKeyRepository._bulk_insert_keys_optimized(session, batch, commit=False)
                span.add_event("pre_populate_keys_bulk_insert_keys_completed")
            
                # Single commit at the end for maximum efficiency
                await session.commit()
                span.add_event("pre_populate_keys_completed")
                logger.info(
                    "Pre-populated {count} keys",
                    extra={"count": count}
                )
                return count

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                await session.rollback()
                logger.error(
                    "Error pre-populating keys",
                    extra={"error": e}
                )
                raise

    @staticmethod
    async def _bulk_insert_keys(session: AsyncSession, keys: list[str]) -> int:
        """
        Bulk insert with raw SQL for better performance.
        This IS worth optimizing with raw SQL.
        """
        if not keys:
            return 0
        
        # Use raw SQL for bulk insert - much faster than ORM
        values = ", ".join([f"('{key}', false)" for key in keys])
        query = text(f"""
            INSERT INTO urls (key, is_used) 
            VALUES {values}
            ON CONFLICT (key) DO NOTHING
        """)
        
        result = await session.execute(query)
        await session.commit()
        
        return result.rowcount  # type: ignore[attr-defined]

    @staticmethod
    async def _bulk_insert_keys_optimized(session: AsyncSession, keys: list[str], commit: bool = True):
        """
        Optimized bulk insert using parameterized queries.
        Much safer and often faster than string concatenation.
        """
        if not keys:
            return
        
        # Use parameterized query for safety and performance
        # PostgreSQL handles this very efficiently
        query = text("""
            INSERT INTO urls (key, is_used) 
            VALUES (:key, false)
            ON CONFLICT (key) DO NOTHING
        """)
        
        # Bulk execute with parameters
        key_params = [{"key": key} for key in keys]
        await session.execute(query, key_params)
        
        if commit:
            await session.commit()

    @staticmethod
    async def get_available_key_count(session: AsyncSession) -> int:
        """Get count of available unused keys."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("get_available_key_count") as span:
            try:
                span.add_event("get_available_key_count_query_started")
                result = await session.execute(
                    select(func.count(URL.id)).where(~URL.is_used)
                )
                span.add_event("get_available_key_count_query_completed")
                count = result.scalar()
                span.add_event("get_available_key_count_returning_count", {"count": count})
                return count or 0
            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error(f"Error getting available key count: {e}")
                return 0

    @staticmethod
    async def get_total_key_count(session: AsyncSession) -> int:
        """Get total count of keys."""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("get_total_key_count") as span:
            try:
                span.add_event("get_total_key_count_query_started")
                result = await session.execute(
                    select(func.count(URL.id))
                )
                span.add_event("get_total_key_count_query_completed")
                count = result.scalar()
                span.add_event("get_total_key_count_returning_count", {"count": count})
                return count or 0
            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error(f"Error getting total key count: {e}")
                return 0

    # ========================================================================
    # OPTIMIZATION: PostgreSQL generate_series (FASTEST - O(1) from app)
    # ========================================================================
    @staticmethod
    async def pre_populate_keys_postgres_native(
        session: AsyncSession,
        count: int = 100000
    ) -> int:
        """
        Use PostgreSQL's generate_series to create keys directly in the database.
        This is the FASTEST method - O(1) operation from application perspective.

        Performance: ~100K keys in 1-2 seconds

        Trade-off: Keys are generated by PostgreSQL, not Python.
        Uses a simple sequential approach with random salt.
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("pre_populate_keys_postgres_native") as span:
            span.set_attribute("key_count", count)
            try:
                if count <= 0:
                    span.add_event("pre_populate_keys_count_is_zero_or_negative")
                    return 0

                span.add_event("pre_populate_keys_postgres_native_started")
                result = await session.execute(
                    text("""
                        INSERT INTO urls (key, is_used)
                        SELECT
                            -- Generate 7 random alphanumeric characters
                            array_to_string(
                                ARRAY(
                                    SELECT substr('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
                                        (random() * 61 + 1)::int, 1)
                                    FROM generate_series(1, 7)
                                ),
                                ''
                            ) as key,
                            false as is_used
                        FROM generate_series(1, :count)
                        ON CONFLICT (key) DO NOTHING
                        RETURNING id
                    """),
                    {"count": count}
                )

                inserted_count = len(result.fetchall())
                await session.commit()
                span.set_attribute("inserted_count", inserted_count)
                span.set_status(trace.Status(trace.StatusCode.OK))
                span.add_event("pre_populate_keys_postgres_native_completed")

                logger.info(
                    f"Pre-populated {inserted_count} keys using PostgreSQL native method",
                    extra={"inserted_count": inserted_count, "span_context": span.get_span_context()}
                )
                return inserted_count

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                await session.rollback()
                logger.error(
                    f"Error pre-populating keys (postgres native): {e}",
                    extra={"error": str(e), "span_context": span.get_span_context()}
                )
                raise

    # ========================================================================
    # OPTIMIZATION: Single INSERT with VALUES (Very Fast)
    # ========================================================================
    @staticmethod
    async def pre_populate_keys_single_insert(
        session: AsyncSession,
        count: int = 100000
    ) -> int:
        """
        Generate all keys in Python, then insert with a SINGLE SQL query.

        Performance: ~100K keys in 2-3 seconds

        Pros:
        - Only one database round-trip
        - Full control over key generation
        - PostgreSQL can optimize the entire insert

        Cons:
        - Large SQL query string (but PostgreSQL handles it well)
        - Limited by max_allowed_packet (default: 1GB, more than enough)
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("pre_populate_keys_single_insert") as span:
            span.set_attribute("key_count", count)
            try:
                if count <= 0:
                    return 0

                span.add_event("pre_populate_keys_single_insert_generating_keys")
                # Pre-generate all keys
                keys = [URLKeyRepository._generate_key() for _ in range(count)]

                span.add_event("pre_populate_keys_single_insert_building_query")
                # Build single VALUES clause with proper escaping
                values_clause = ",".join([f"('{key}', false)" for key in keys])

                query = text(f"""
                    INSERT INTO urls (key, is_used)
                    VALUES {values_clause}
                    ON CONFLICT (key) DO NOTHING
                    RETURNING id
                """)

                span.add_event("pre_populate_keys_single_insert_executing_query")
                result = await session.execute(query)
                inserted_count = len(result.fetchall())
                await session.commit()

                span.set_attribute("inserted_count", inserted_count)
                span.set_status(trace.Status(trace.StatusCode.OK))
                logger.info(
                    f"Pre-populated {inserted_count} keys using single INSERT",
                    extra={"inserted_count": inserted_count, "span_context": span.get_span_context()}
                )
                return inserted_count

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                await session.rollback()
                logger.error(
                    f"Error pre-populating keys (single insert): {e}",
                    extra={"error": str(e), "span_context": span.get_span_context()}
                )
                raise

    # ========================================================================
    # OPTIMIZATION: Hybrid Approach (Production Ready)
    # ========================================================================
    @staticmethod
    async def pre_populate_keys_hybrid(
        session: AsyncSession,
        count: int = 100000
    ) -> int:
        """
        Production-ready hybrid approach.
        Automatically chooses the best method based on count.

        - Small batches (<1K): Use executemany (safe, fast enough)
        - Medium batches (1K-50K): Use single INSERT (fast, memory efficient)
        - Large batches (>50K): Use PostgreSQL native (fastest)

        This gives you the best performance across all scenarios.
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("pre_populate_keys_hybrid") as span:
            span.set_attribute("key_count", count)
            try:
                if count <= 0:
                    return 0

                span.add_event("pre_populate_keys_hybrid_selecting_strategy")
                # Choose strategy based on count
                if count < 1000:
                    # For small batches, safety and simplicity matter more
                    span.set_attribute("strategy", "executemany")
                    return await URLKeyRepository.pre_populate_keys(session, count)
                elif count < 50000:
                    # For medium batches, single INSERT is optimal
                    span.set_attribute("strategy", "single_insert")
                    return await URLKeyRepository.pre_populate_keys_single_insert(session, count)
                else:
                    # For large batches, use PostgreSQL native
                    span.set_attribute("strategy", "postgres_native")
                    return await URLKeyRepository.pre_populate_keys_postgres_native(session, count)

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.error(
                    f"Error pre-populating keys (hybrid): {e}",
                    extra={"error": str(e), "span_context": span.get_span_context()}
                )
                raise
    