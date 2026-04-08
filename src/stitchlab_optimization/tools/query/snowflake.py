import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
import pandas as pd
from pydantic import BaseModel
from typing import Optional, Union


class SnowflakeTablePath(BaseModel):
    database_name: str
    schema_name: str
    table_name: str

    @property
    def path(self):
        return f"{self.database_name}.{self.schema_name}.{self.table_name}"
    

class SnowflakeConnectionParams(BaseModel):
    account: str
    warehouse: str
    database: str
    user: str
    private_key_file: str
    private_key_file_pwd: str


def read_df_from_snowflake(queries: Union[str, list[str]], conn_params: SnowflakeConnectionParams) -> Union[pd.DataFrame, list[pd.DataFrame]]:
    """
    Run multiple queries and return a list of DataFrames.
    """
    
    conn, cur = None, None
    dfs = [pd.DataFrame() for _ in range(len(queries))]
    
    try:
        print("Connecting to Snowflake...")
        conn = snowflake.connector.connect(**conn_params.model_dump())
        cur = conn.cursor()

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        raise

    is_single_query = isinstance(queries, str)
    if is_single_query:
        queries = [queries]

    for i, query in enumerate(queries):
        try:
            print(f"\n===================== Running query {i} =====================\n{query}\n======================================================\n")
            dfs[i] = cur.execute(query).fetch_pandas_all()

        except Exception as e:
            print(f"❌ Query {i} failed: {e}")
            raise

    if cur is not None:
        cur.close()

    if conn is not None:
        conn.close()

    if is_single_query:
        return dfs[0]

    return dfs


def insert_df_to_snowflake(df: pd.DataFrame, conn_params: SnowflakeConnectionParams, path: SnowflakeTablePath, if_exists: str = "append", chunk_size: int = 1000):
    """
    Inserts a pandas DataFrame into a Snowflake table.

    :param df: pandas DataFrame to insert
    :param table_name: target Snowflake table name
    :param schema: (optional) schema name
    :param database: (optional) database name
    :param if_exists: "append" (default) or "replace"
    :param chunk_size: number of rows per insert (default 1000)
    """

    database = path.database_name
    schema = path.schema_name
    table_name = path.table_name

    # If DataFrame is empty, then for 'append' skip insert, for 'replace' empty the table
    if df.empty:
        if if_exists == "append":
            print("DataFrame is empty and if_exists == 'append'. Skipping insert.")
            return 0
        elif if_exists == "replace":
            print("DataFrame is empty and if_exists == 'replace'. Table will be truncated.")
            conn = None
            try:
                print("Connecting to Snowflake to truncate the table...")
                conn = snowflake.connector.connect(**conn_params.model_dump())
                cur = conn.cursor()
                fqtn = ""
                if database and schema:
                    fqtn = f'{database}.{schema}.{table_name}'
                elif schema:
                    fqtn = f'{schema}.{table_name}'
                else:
                    fqtn = table_name
                cur.execute(f"TRUNCATE TABLE {fqtn}")
                print(f"✅ Table {fqtn} truncated.")
                cur.close()
                return 0
            except Exception as e:
                print(f"❌ Truncate failed: {e}")
                raise
            finally:
                if conn is not None:
                    conn.close()


    # Ensure DataFrame has a standard RangeIndex before uploading to Snowflake
    if not isinstance(df.index, pd.RangeIndex):
        # print(f"⚠️ DataFrame index is of type {type(df.index)}. Resetting index to avoid Snowflake warning.")
        df = df.reset_index(drop=True)
    
    df = df.where(pd.notnull(df), None)

    conn = None
    try:
        print("Connecting to Snowflake for insert...")
        conn = snowflake.connector.connect(**SNOWFLAKE_ENV)
        print(f"Inserting to table: {table_name} (schema={schema}, database={database})")

        # --- Manual insert into Snowflake without write_pandas ---
        # Build fully-qualified table name
        fqtn = ""
        if database and schema:
            fqtn = f'{database}.{schema}.{table_name}'
        elif schema:
            fqtn = f'{schema}.{table_name}'
        else:
            fqtn = table_name

        # Handle if_exists = "replace" by truncating the table before inserting
        if if_exists == "replace":
            cur = conn.cursor()
            try:
                cur.execute(f"TRUNCATE TABLE {fqtn}")
                print(f"✅ Table {fqtn} truncated (replace mode).")
            finally:
                cur.close()

        # Preprocess DataFrame, get columns & rows
        columns = list(df.columns)
        nrows = len(df)
        nchunks = (nrows // chunk_size) + (1 if nrows % chunk_size != 0 else 0)

        insert_sql = "INSERT INTO {} ({}) VALUES ({})".format(
            fqtn,
            ", ".join([f'"{col}"' for col in columns]),
            ", ".join(["%s"] * len(columns))
        )

        cur = conn.cursor()
        try:
            
            for i in range(nchunks):
                chunk_df = df.iloc[i*chunk_size:(i+1)*chunk_size]
                values = [tuple(row) for row in chunk_df.values]
                if values:
                    cur.executemany(insert_sql, values)
            conn.commit()
            print(f"✅ Inserted {nrows} rows in {nchunks} chunks to {table_name}")

        except Exception as e:
            print(f"❌ Error during insert: {e}")
            conn.rollback()
            nrows = 0
            nchunks = 0

        finally:
            cur.close()

    #     success, nchunks, nrows, _ = write_pandas(
    #         conn=conn,
    #         df=df,
    #         table_name=table_name,
    #         schema=schema,
    #         database=database,
    #         chunk_size=chunk_size,
    #         overwrite=(if_exists == "replace")
    #     )

    #     if not success:
    #         raise Exception(f"❌ insert_dataframe_to_snowflake failed to insert dataframe")
    #     print(f"✅ Inserted {nrows} rows in {nchunks} chunks to {table_name}")
    #     return nrows

    except Exception as e:
        print(f"❌ Insert failed: {e}")
        raise

    finally:
        if conn is not None:
            conn.close()