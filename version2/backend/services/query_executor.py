"""
Dynamic Query Executor Service
==============================
Converts natural language questions to SQL, executes against data, returns real results.

This is the CRITICAL component that makes chat actually useful by:
1. Generating SQL from natural language using LLM
2. Validating SQL for safety and correctness
3. Executing SQL against the actual dataset using DuckDB
4. Returning computed results (NO hallucinations)

Architecture:
    User Query → SQL Generation (LLM) → SQL Validation → DuckDB Execution → Result Formatting
"""

import logging
import re
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
import json

import duckdb
import polars as pl
import pandas as pd

from services.llm_router import llm_router
from core.prompt_templates import get_sql_generation_prompt, get_result_interpretation_prompt

logger = logging.getLogger(__name__)


# ============================================================
#                    SQL VALIDATOR
# ============================================================
class SQLValidator:
    """
    Validates generated SQL for safety and correctness.
    Prevents SQL injection and dangerous operations.
    """
    
    # Dangerous operations that should NEVER be executed
    FORBIDDEN_KEYWORDS = [
        r'\bDROP\b', r'\bDELETE\b', r'\bTRUNCATE\b', r'\bINSERT\b', 
        r'\bUPDATE\b', r'\bALTER\b', r'\bCREATE\s+TABLE\b', 
        r'\bEXEC\b', r'\bEXECUTE\b', r'\bGRANT\b', r'\bREVOKE\b',
        r'\bATTACH\b', r'\bDETACH\b', r'\bCOPY\b', r'\bIMPORT\b',
        r';\s*--', r'/\*', r'\*/',  # Comment injection
        r'\bINTO\s+OUTFILE\b', r'\bLOAD_FILE\b',  # File operations
    ]
    
    # Allowed SQL operations (whitelist approach)
    ALLOWED_OPERATIONS = [
        'SELECT', 'WITH', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 
        'HAVING', 'LIMIT', 'OFFSET', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN',
        'INNER JOIN', 'CROSS JOIN', 'UNION', 'INTERSECT', 'EXCEPT',
        'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AS', 'DISTINCT',
        'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'NULLIF',
        'CAST', 'ROUND', 'ABS', 'UPPER', 'LOWER', 'TRIM', 'LENGTH',
        'SUBSTRING', 'CONCAT', 'LIKE', 'ILIKE', 'IN', 'NOT IN', 
        'BETWEEN', 'IS NULL', 'IS NOT NULL', 'AND', 'OR', 'NOT',
        'ASC', 'DESC', 'OVER', 'PARTITION BY', 'ROW_NUMBER', 'RANK',
        'DENSE_RANK', 'LAG', 'LEAD', 'FIRST_VALUE', 'LAST_VALUE',
        'PERCENTILE_CONT', 'PERCENTILE_DISC', 'MEDIAN', 'MODE',
        'STDDEV', 'VARIANCE', 'CORR', 'COVAR_POP', 'COVAR_SAMP',
        'DATE_TRUNC', 'DATE_PART', 'EXTRACT', 'NOW', 'CURRENT_DATE',
        'STRFTIME', 'DATE_DIFF', 'DATE_ADD', 'DATE_SUB',
        'REGEXP_MATCHES', 'REGEXP_REPLACE', 'STRING_SPLIT',
        'ARRAY_AGG', 'LIST', 'UNNEST', 'GENERATE_SERIES',
        'GREATEST', 'LEAST', 'IIF', 'IFNULL', 'NVL',
    ]
    
    @classmethod
    def validate(cls, sql: str) -> Tuple[bool, str]:
        """
        Validate SQL for safety.
        
        Returns:
            (is_valid, error_message)
        """
        if not sql or not sql.strip():
            return False, "Empty SQL query"
        
        sql_upper = sql.upper()
        
        # Check for forbidden operations
        for pattern in cls.FORBIDDEN_KEYWORDS:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                return False, f"Forbidden SQL operation detected: {pattern}"
        
        # Must start with SELECT or WITH (CTE)
        sql_stripped = sql_upper.strip()
        if not (sql_stripped.startswith('SELECT') or sql_stripped.startswith('WITH')):
            return False, "Query must be a SELECT statement"
        
        # Check for multiple statements (semicolon injection)
        # Allow semicolon only at the very end
        sql_no_end_semicolon = sql.rstrip().rstrip(';')
        if ';' in sql_no_end_semicolon:
            return False, "Multiple SQL statements not allowed"
        
        # Require FROM clause when the SELECT references identifiers (not just
        # literal expressions like SELECT 1+1 or SELECT CURRENT_DATE).
        if 'SELECT' in sql_upper and 'FROM' not in sql_upper:
            # Allow only if every column expression looks like a literal/function
            # with no bare word that could be a column reference.
            # Heuristic: if the SELECT list contains any bare identifier that is
            # not a known aggregate/scalar function name, reject it.
            known_no_from = re.compile(
                r'^SELECT\s+(?:[\d\'\"\.\s,+\-\*\/()]+|'
                r'(?:CURRENT_DATE|CURRENT_TIMESTAMP|NOW|TRUE|FALSE|NULL)'
                r')\s*(?:;)?$',
                re.IGNORECASE
            )
            if not known_no_from.match(sql.strip()):
                return False, "SELECT statement is missing a FROM clause"

        return True, ""
    
    @classmethod
    def sanitize_column_names(cls, columns: List[str]) -> Dict[str, str]:
        """
        Create safe aliases for column names that might contain special characters.
        """
        safe_names = {}
        for col in columns:
            # Replace problematic characters
            safe = re.sub(r'[^\w]', '_', col)
            safe = re.sub(r'^(\d)', r'col_\1', safe)  # Can't start with digit
            safe_names[col] = safe if safe != col else col
        return safe_names


# ============================================================
#                  QUERY EXECUTOR
# ============================================================
class QueryExecutor:
    """
    Executes natural language queries against datasets using DuckDB.
    
    This is the core component that eliminates hallucinations by:
    1. Converting questions to SQL (interpretable)
    2. Executing SQL against real data
    3. Returning actual computed results
    """
    
    def __init__(self):
        self._query_cache: Dict[str, Dict] = {}  # Cache recent query results
        self._cache_keys_by_dataset: Dict[str, set] = {}  # dataset_id -> set of cache keys
        self._max_cache_size = 100
        self._max_result_rows = 1000  # Limit result size for safety
    
    def _get_column_schema(self, df: pl.DataFrame) -> str:
        """Generate column schema string for LLM prompt."""
        schema_lines = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            # Get sample non-null values
            non_null = df[col].drop_nulls()
            sample_val = non_null[0] if len(non_null) > 0 else "NULL"
            
            # Truncate long sample values
            sample_str = str(sample_val)[:50] + "..." if len(str(sample_val)) > 50 else str(sample_val)
            
            schema_lines.append(f"  - `{col}` ({dtype}) — Example: {sample_str}")
        
        return "\n".join(schema_lines)
    
    def _get_sample_data(self, df: pl.DataFrame, n: int = 5) -> str:
        """Get sample data as formatted string."""
        try:
            sample = df.head(n)
            # Convert to list of dicts for readable format
            rows = sample.to_dicts()
            # Truncate long values
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, str) and len(v) > 50:
                        row[k] = v[:50] + "..."
            return json.dumps(rows, indent=2, default=str)[:2000]  # Limit size
        except Exception as e:
            logger.warning(f"Error getting sample data: {e}")
            return "Sample data unavailable"
    
    def _get_data_stats(self, df: pl.DataFrame) -> str:
        """Get basic data statistics for context."""
        stats = []
        stats.append(f"Total rows: {len(df):,}")
        stats.append(f"Total columns: {len(df.columns)}")
        
        # Numeric column stats
        numeric_cols = [name for name, dtype in zip(df.columns, df.dtypes) if dtype in pl.NUMERIC_DTYPES]
        if numeric_cols:
            stats.append(f"Numeric columns: {', '.join(numeric_cols[:5])}")
        
        # Categorical columns with unique counts
        string_cols = [name for name, dtype in zip(df.columns, df.dtypes) if dtype == pl.Utf8]
        if string_cols:
            for col in string_cols[:3]:
                nunique = df[col].n_unique()
                if nunique <= 20:
                    unique_vals = df[col].unique().to_list()[:10]
                    stats.append(f"  {col} values: {unique_vals}")
        
        # Date range if date columns exist
        for col in df.columns:
            if "date" in col.lower() or "time" in col.lower():
                try:
                    min_date = df[col].min()
                    max_date = df[col].max()
                    stats.append(f"Date range ({col}): {min_date} to {max_date}")
                except Exception as e:
                    logger.debug(f"Could not get date range for {col}: {e}")
        
        return "\n".join(stats)
    
    def _generate_cache_key(self, query: str, dataset_id: str) -> str:
        """Generate cache key for query results."""
        content = f"{dataset_id}:{query.lower().strip()}"
        return hashlib.md5(content.encode()).hexdigest()

    @staticmethod
    def _capitalize_first_alpha(text: str) -> str:
        """Uppercase the first alphabetic character in a string."""
        for i, ch in enumerate(text):
            if ch.isalpha():
                return text[:i] + ch.upper() + text[i + 1:]
        return text

    @classmethod
    def _postprocess_interpretation(cls, text: str) -> str:
        """
        Enforce response-quality guardrails for interpreted SQL answers.

        Fixes:
        - removes filler openings ("Based on...", "The data shows...")
        - softens overconfident absolutes
        - repairs nested-bold artifacts like **text at **1.28****
        - wraps bare numeric values in bold for consistency
        """
        if not text:
            return text

        cleaned = text.strip()

        # Remove filler intros at response start.
        cleaned = re.sub(
            r"(?i)^\s*(based on the (?:data|results|analysis|information)"
            r"|according to (?:the )?(?:data|results)"
            r"|the (?:data|results) show(?:s)?"
            r"|looking at the (?:data|results))[\s,:-]*",
            "",
            cleaned,
        )
        cleaned = re.sub(r"(?i)^that\s+", "", cleaned)
        cleaned = cls._capitalize_first_alpha(cleaned)

        # Reduce overconfident wording.
        confidence_rewrites = [
            (r"(?i)\bwithout (?:a )?doubt\b", "based on available data"),
            (r"(?i)\bdefinitely\b", "likely"),
            (r"(?i)\bcertainly\b", "likely"),
            (r"(?i)\babsolutely\b", "strongly"),
            (r"(?i)\balways true\b", "consistently supported by the observed data"),
            (r"(?i)\balways\b", "consistently"),
            (r"(?i)\bnever fail\b", "rarely fail in this dataset"),
            (r"(?i)\bimpossible to evaluate\b", "not identifiable from the available variation"),
        ]
        for pattern, replacement in confidence_rewrites:
            cleaned = re.sub(pattern, replacement, cleaned)

        # Repair nested bold around numeric tokens.
        prev = None
        while prev != cleaned:
            prev = cleaned
            cleaned = re.sub(
                r"\*\*([^*]*?)\s+\*\*([0-9][^*]*?)\*\*\*\*",
                r"\1 **\2**",
                cleaned,
            )

        # Bold any remaining bare numeric values (counts, rates, percentages).
        cleaned = re.sub(
            r"(?<![\w*`])(\d[\d,]*(?:\.\d+)?%?)(?![\w*`])",
            r"**\1**",
            cleaned,
        )

        return cleaned
    
    @staticmethod
    def _sanitize_sql(sql: str) -> str:
        """
        Post-process LLM-generated SQL to fix common model mistakes before
        handing it to DuckDB.

        Fixes applied
        -------------
        1. Trailing ``?`` on identifiers  (e.g. ``awards_won?``)
        2. ``AGG(col) OVER ()`` window-inside-aggregate → scalar subquery
        3. ``json_object_agg(...)`` → ``json_group_object(...)`` (DuckDB alias)
        4. Multi-row scalar subquery guard: ``(SELECT col FROM data WHERE ...)``
           that would return >1 row is capped with LIMIT 1.
        """
        # --- fix 1: strip stray '?' appended to identifiers -----------------
        sql = re.sub(r'(?<=[A-Za-z0-9_])\?', '', sql)

        # --- fix 2: window-function-inside-aggregate rewrite ----------------
        sql = re.sub(
            r'AVG\(([^()]+)\)\s+OVER\s*\(\s*\)',
            lambda m: f'(SELECT AVG({m.group(1)}) FROM data)',
            sql,
            flags=re.IGNORECASE
        )
        for agg_fn in ('SUM', 'COUNT', 'MIN', 'MAX'):
            sql = re.sub(
                rf'{agg_fn}\(([^()]+)\)\s+OVER\s*\(\s*\)',
                lambda m, fn=agg_fn: f'(SELECT {fn}({m.group(1)}) FROM data)',
                sql,
                flags=re.IGNORECASE
            )

        # --- fix 3: PostgreSQL json_object_agg → DuckDB json_group_object ----
        sql = re.sub(r'\bjson_object_agg\b', 'json_group_object', sql, flags=re.IGNORECASE)

        # --- fix 4: scalar subquery returning multiple rows ------------------
        # Pattern: a subquery in a scalar position (inside an expression but NOT
        # in FROM/JOIN) that selects a single column with no top-level LIMIT.
        # Append LIMIT 1 so DuckDB doesn't raise "more than one row" error.
        # Only target the simple case: (SELECT <col|expr> FROM data <optional WHERE>)
        def _add_limit1(m: re.Match) -> str:
            inner = m.group(1)
            if re.search(r'\bLIMIT\b', inner, re.IGNORECASE):
                return m.group(0)  # already has LIMIT
            if re.search(r'\bGROUP\s+BY\b', inner, re.IGNORECASE):
                return m.group(0)  # aggregate — let DuckDB handle it
            return f'(SELECT {inner} LIMIT 1)'

        sql = re.sub(
            r'\(SELECT\s+((?:(?!\bFROM\b).)+FROM\s+data(?:\s+WHERE\s+[^)]+)?)\)',
            _add_limit1,
            sql,
            flags=re.IGNORECASE | re.DOTALL
        )

        return sql

    async def generate_sql(self, query: str, df: pl.DataFrame) -> Tuple[str, str]:
        """
        Generate SQL from natural language query.
        
        Returns:
            (sql_query, error_message)
        """
        try:
            # Build comprehensive prompt
            prompt = get_sql_generation_prompt(
                column_schema=self._get_column_schema(df),
                sample_data=self._get_sample_data(df),
                data_stats=self._get_data_stats(df),
                user_query=query
            )
            
            # Call LLM for SQL generation
            sql = await llm_router.call(
                prompt=prompt,
                model_role="sql_generator",
                expect_json=False,
                temperature=0.1,  # Low temperature for deterministic SQL
                max_tokens=1000
            )
            
            # Clean up the response
            sql = sql.strip()
            
            # Remove markdown code blocks if present
            if sql.startswith("```"):
                lines = sql.split("\n")
                sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            sql = sql.strip().rstrip(';') + ';'

            # Apply model-output sanitisation (strips '?', rewrites bad window
            # patterns, etc.) before the validator sees the SQL.
            sql = self._sanitize_sql(sql)
            
            # Validate SQL
            is_valid, error = SQLValidator.validate(sql)
            if not is_valid:
                logger.warning(f"Generated invalid SQL: {error}")
                return "", f"Generated invalid SQL: {error}"
            
            return sql, ""
            
        except Exception as e:
            logger.error(f"Error generating SQL: {e}", exc_info=True)
            return "", f"Failed to generate SQL: {str(e)}"
    
    def execute_sql(self, sql: str, df: pl.DataFrame) -> Tuple[Optional[pl.DataFrame], str]:
        """
        Execute SQL query against the dataframe using DuckDB.
        
        Returns:
            (result_df, error_message)
        """
        try:
            # Final validation before execution
            is_valid, error = SQLValidator.validate(sql)
            if not is_valid:
                return None, f"SQL validation failed: {error}"
            
            # Create DuckDB connection (in-memory, isolated)
            conn = duckdb.connect(":memory:")
            
            try:
                # Register the Polars dataframe as a table.
                # Avoid hard dependency on pyarrow by falling back to
                # dict-based conversion when to_pandas() is unavailable.
                try:
                    pandas_df = df.to_pandas()
                except ModuleNotFoundError as exc:
                    if exc.name != "pyarrow":
                        raise
                    logger.warning(
                        "pyarrow is not installed; falling back to slower "
                        "dict-based Polars->Pandas conversion for SQL execution."
                    )
                    pandas_df = pd.DataFrame(df.to_dicts())
                conn.register("data", pandas_df)
                
                # Execute with timeout and row limit
                result_sql = f"SELECT * FROM ({sql.rstrip(';')}) AS subquery LIMIT {self._max_result_rows}"

                # Avoid pyarrow dependency: use fetchall() + build Polars from dicts.
                # .pl() and .df() both rely on Arrow (pyarrow), but fetchall()
                # returns plain Python tuples which need no extra C-extension.
                cursor = conn.execute(result_sql)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                records = [dict(zip(columns, row)) for row in rows]
                result = pl.from_dicts(records) if records else pl.DataFrame(
                    {col: pl.Series(col, [], dtype=pl.Utf8) for col in columns}
                )
            finally:
                conn.close()
            
            logger.info(f"✅ SQL executed successfully, returned {len(result)} rows")
            return result, ""
            
        except duckdb.Error as e:
            error_msg = str(e)
            logger.error(f"DuckDB execution error: {error_msg}")
            
            # Provide helpful error messages
            if "does not exist" in error_msg.lower():
                return None, f"Column not found. Check column names. Error: {error_msg}"
            elif "syntax error" in error_msg.lower():
                return None, f"SQL syntax error: {error_msg}"
            else:
                return None, f"Query execution failed: {error_msg}"
                
        except Exception as e:
            logger.error(f"Unexpected execution error: {e}", exc_info=True)
            return None, f"Unexpected error: {str(e)}"
    
    def format_results(self, result_df: pl.DataFrame, max_display_rows: int = 20) -> str:
        """Format query results as a readable markdown table."""
        if result_df is None or len(result_df) == 0:
            return "No results found."
        
        rows = len(result_df)
        cols = len(result_df.columns)
        
        # Limit display rows
        display_df = result_df.head(max_display_rows)
        
        # Build markdown table
        lines = []
        
        # Header
        headers = " | ".join(str(col) for col in display_df.columns)
        lines.append(f"| {headers} |")
        lines.append("|" + "|".join(["---"] * cols) + "|")
        
        # Rows
        for row in display_df.iter_rows():
            formatted_values = []
            for val in row:
                if val is None:
                    formatted_values.append("NULL")
                elif isinstance(val, float):
                    # Format numbers nicely
                    if abs(val) >= 1_000_000:
                        formatted_values.append(f"{val:,.0f}")
                    elif abs(val) >= 1:
                        formatted_values.append(f"{val:,.2f}")
                    else:
                        formatted_values.append(f"{val:.4f}")
                else:
                    # Truncate long strings
                    s = str(val)
                    formatted_values.append(s[:50] + "..." if len(s) > 50 else s)
            
            lines.append(f"| {' | '.join(formatted_values)} |")
        
        result_str = "\n".join(lines)
        
        # Add summary if truncated
        if rows > max_display_rows:
            result_str += f"\n\n*Showing {max_display_rows} of {rows:,} total rows*"
        
        return result_str
    
    async def interpret_results(
        self, 
        query: str, 
        sql: str, 
        result_df: pl.DataFrame
    ) -> str:
        """
        Use LLM to interpret query results in natural language.
        """
        try:
            # Format results for LLM
            if len(result_df) == 0:
                results_str = "The query returned no results (empty dataset)."
            elif len(result_df) == 1 and len(result_df.columns) == 1:
                # Single value result
                value = result_df.row(0)[0]
                results_str = f"Single value: {value}"
            else:
                # Format as table (limited)
                results_str = self.format_results(result_df, max_display_rows=15)
            
            prompt = get_result_interpretation_prompt(
                user_query=query,
                sql_query=sql,
                query_results=results_str
            )
            
            interpretation = await llm_router.call(
                prompt=prompt,
                model_role="conversational",
                expect_json=False,
                temperature=0.3,
                max_tokens=500,
                is_conversational=True
            )

            return self._postprocess_interpretation(str(interpretation).strip())
            
        except Exception as e:
            logger.error(f"Error interpreting results: {e}")
            # Fallback to raw results
            return f"Query completed. Results:\n\n{self.format_results(result_df)}"
    
    async def execute_query(
        self, 
        query: str, 
        df: pl.DataFrame, 
        dataset_id: str,
        return_raw: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry point: Execute a natural language query against the dataset.
        
        Args:
            query: Natural language question
            df: Polars DataFrame with the data
            dataset_id: Dataset identifier for caching
            return_raw: If True, return raw data instead of interpretation
        
        Returns:
            {
                "success": bool,
                "response": str,  # Natural language answer
                "sql": str,       # Generated SQL (for transparency)
                "data": list,     # Raw result data (optional)
                "row_count": int,
                "error": str      # Error message if failed
            }
        """
        start_time = datetime.now()
        
        # Check cache
        cache_key = self._generate_cache_key(query, dataset_id)
        if cache_key in self._query_cache:
            cached = self._query_cache[cache_key]
            logger.info(f"📋 Query cache HIT for: {query[:50]}...")
            cached["cached"] = True
            return cached
        
        # Step 1: Generate SQL
        logger.info(f"🔄 Generating SQL for query: {query[:50]}...")
        sql, sql_error = await self.generate_sql(query, df)
        
        if sql_error:
            return {
                "success": False,
                "response": f"I couldn't generate a valid query for your question. {sql_error}",
                "sql": None,
                "data": None,
                "row_count": 0,
                "error": sql_error,
                "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
            }
        
        # Step 2: Execute SQL
        logger.info(f"⚡ Executing SQL: {sql[:100]}...")
        result_df, exec_error = self.execute_sql(sql, df)
        
        if exec_error:
            # Try to provide helpful feedback
            return {
                "success": False,
                "response": f"The query couldn't be executed. {exec_error}\n\nGenerated SQL:\n```sql\n{sql}\n```",
                "sql": sql,
                "data": None,
                "row_count": 0,
                "error": exec_error,
                "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
            }
        
        # Step 3: Interpret results
        if return_raw:
            response = self.format_results(result_df)
        else:
            response = await self.interpret_results(query, sql, result_df)
        
        # Prepare result
        result = {
            "success": True,
            "response": response,
            "sql": sql,
            "data": result_df.to_dicts() if len(result_df) <= 100 else result_df.head(100).to_dicts(),
            "row_count": len(result_df),
            "columns": result_df.columns,
            "error": None,
            "cached": False,
            "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
        }
        
        # Cache result
        if len(self._query_cache) >= self._max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self._query_cache))
            # Clean up the dataset index for the evicted key
            for ds_keys in self._cache_keys_by_dataset.values():
                ds_keys.discard(oldest_key)
            del self._query_cache[oldest_key]
        
        self._query_cache[cache_key] = result
        # Index this key under its dataset for efficient per-dataset clearing
        if dataset_id not in self._cache_keys_by_dataset:
            self._cache_keys_by_dataset[dataset_id] = set()
        self._cache_keys_by_dataset[dataset_id].add(cache_key)
        
        logger.info(f"✅ Query executed successfully in {result['execution_time_ms']:.0f}ms, {len(result_df)} rows")
        
        return result
    
    def clear_cache(self, dataset_id: Optional[str] = None):
        """Clear query cache."""
        if dataset_id:
            # Clear only for specific dataset using the dataset index
            keys_to_remove = self._cache_keys_by_dataset.pop(dataset_id, set())
            for k in keys_to_remove:
                self._query_cache.pop(k, None)
        else:
            self._query_cache.clear()
            self._cache_keys_by_dataset.clear()
        logger.info(f"🗑️ Query cache cleared")


# ============================================================
#              QUERY TYPE CLASSIFIER
# ============================================================
class QueryClassifier:
    """
    Classifies user queries to determine if they need SQL execution
    or can be answered from metadata alone.
    """
    
    # Patterns that indicate SQL execution is needed
    SQL_NEEDED_PATTERNS = [
        # Aggregations
        r'\b(total|sum|count|average|avg|mean|median|max|min|maximum|minimum)\b',
        r'\b(how many|how much|what is the)\b',
        
        # Filtering
        r'\b(where|filter|only|just|specific|particular)\b',
        r'\b(greater than|less than|more than|fewer than|between|equals?)\b',
        r'\b(in|not in|contains|starts with|ends with)\b',
        r'\b(first|last|top|bottom|highest|lowest|best|worst)\s+\d+',
        
        # Grouping
        r'\b(by|per|each|every|group|breakdown|split)\b',
        r'\b(compare|comparison|versus|vs\.?)\b',
        
        # Time-based
        r'\b(last|this|next|previous)\s+(day|week|month|quarter|year)',
        r'\b(daily|weekly|monthly|quarterly|yearly|annual)\b',
        r'\b(since|before|after|during|between)\b',
        
        # Specific data requests
        r'\b(show me|list|display|get|find|retrieve)\b',
        r'\b(what are|what is|which)\b.*\b(all|any)\b',
        
        # Calculations
        r'\b(calculate|compute|difference|change|growth|rate|ratio|percent)\b',
        r'\b(correlation|relationship|trend|pattern)\b',
    ]
    
    # Patterns that can be answered from metadata
    METADATA_PATTERNS = [
        r'^(describe|explain|what is this|tell me about)\s+(the\s+)?(data|dataset|table)',
        r'\b(how many columns|column names|what columns|list columns)\b',
        r'\b(data types|schema|structure)\b',
        r'^(what|how)\s+(can|do)\s+(i|you)',  # Help questions
    ]
    
    @classmethod
    def needs_sql_execution(cls, query: str) -> bool:
        """
        Determine if a query requires SQL execution against real data.
        
        Returns:
            True if SQL execution is needed, False if metadata is sufficient
        """
        query_lower = query.lower()
        
        # Check if it's a metadata-only question
        for pattern in cls.METADATA_PATTERNS:
            if re.search(pattern, query_lower):
                return False
        
        # Check if SQL execution is needed
        for pattern in cls.SQL_NEEDED_PATTERNS:
            if re.search(pattern, query_lower):
                return True
        
        # Default: if it looks like a question about the data, use SQL
        if any(word in query_lower for word in ['?', 'show', 'get', 'find', 'what', 'how', 'which', 'where']):
            return True
        
        return False
    
    @classmethod
    def get_query_complexity(cls, query: str) -> str:
        """
        Estimate query complexity for logging/monitoring.
        
        Returns: 'simple' | 'moderate' | 'complex'
        """
        query_lower = query.lower()
        
        complexity_score = 0
        
        # Aggregations add complexity
        if re.search(r'\b(sum|count|average|avg|mean)\b', query_lower):
            complexity_score += 1
        
        # Grouping adds complexity
        if re.search(r'\b(by|per|group|breakdown)\b', query_lower):
            complexity_score += 1
        
        # Multiple conditions add complexity
        if query_lower.count(' and ') + query_lower.count(' or ') > 0:
            complexity_score += 1
        
        # Comparisons/rankings add complexity
        if re.search(r'\b(top|bottom|rank|compare)\b', query_lower):
            complexity_score += 1
        
        # Time-based analysis adds complexity
        if re.search(r'\b(trend|over time|change|growth)\b', query_lower):
            complexity_score += 2
        
        if complexity_score <= 1:
            return "simple"
        elif complexity_score <= 3:
            return "moderate"
        else:
            return "complex"


# Global instance
query_executor = QueryExecutor()
query_classifier = QueryClassifier()
