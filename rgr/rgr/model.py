import psycopg2

class Model:

    def __init__(self):
        self.conn = psycopg2.connect(
            dbname='hr',
            user='postgres',
            password='postgres',
            host='localhost',
            port=5432
        )

    def get_all_tables(self):
        try:
            c = self.conn.cursor()
            c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            return c.fetchall()
        except Exception as e:
            self.conn.rollback()
            print(e)
        return []

    def get_all_columns(self, table_name):
        try:
            c = self.conn.cursor()
            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table_name,))
            return c.fetchall()
        except Exception as e:
            self.conn.rollback()
            print(e)
        return []

    def search_group_by(self, table_name, field_name, field_value, group_by_field, limit=None):
        try:
            c = self.conn.cursor()
            query = f"""
                SELECT * 
                FROM {table_name} 
                WHERE {field_name} = %s 
                GROUP BY {group_by_field} 
                ORDER BY {group_by_field} ASC
            """
            if limit is not None:
                query += f" LIMIT {limit}"
            c.execute(query, (field_value,))
            return c.fetchall()
        except Exception as e:
            self.conn.rollback()
            print(f"Error: {e}")
        return []


    def fetch_table_data(self, table_name, offset=0, limit=10):
        try:
            c = self.conn.cursor()
            query = f"SELECT * FROM {table_name} OFFSET %s LIMIT %s;"
            c.execute(query, (offset, limit))
            result = c.fetchall()
            return result
        except psycopg2.Error as e:
            print(f"Error fetching data from {table_name}: {e}")
            return []

    def add_data(self, table_name, columns, val):
        try:
            c = self.conn.cursor()
            columns_str = ', '.join(columns)
            placeholders = ', '.join(['%s'] * len(val))

            identifier_column = f'{table_name.lower()}_id'
            identifier_index = columns.index(identifier_column)
            val[identifier_index] = int(val[identifier_index])
            c.execute(f'SELECT {identifier_column} FROM public."{table_name}"')
            existing_identifiers = [item[0] for item in c.fetchall()]
            if val[identifier_index] in existing_identifiers:
                return 2
            external_keys = [column for column in columns if column.endswith('_id') and column != identifier_column]
            for key_column in external_keys:
                referenced_table = key_column[:-3].capitalize()
                c.execute(f'SELECT {key_column} FROM public."{referenced_table}"')
                referenced_values = [item[0] for item in c.fetchall()]

                if int(val[columns.index(key_column)]) not in referenced_values:
                    return 3
            c.execute(f'INSERT INTO public."{table_name}" ({columns_str}) VALUES ({placeholders})', val)
            self.conn.commit()
            return 1
        except Exception as e:
            self.conn.rollback()
            print(e)
        return 0

    def update_data(self, table_name, column, id, new_value):
        try:
            c = self.conn.cursor()

            identifier_column = f'{table_name.lower()}_id'
            is_unique_identifier = identifier_column == column
            if is_unique_identifier:
                c.execute(f'SELECT {identifier_column} FROM public."{table_name}"')
                existing_identifiers = [item[0] for item in c.fetchall()]
                if int(new_value) in existing_identifiers:
                    return 2
            elif column.endswith('_id'):
                referenced_table = column[:-3].capitalize()
                c.execute(f'SELECT {column} FROM public."{referenced_table}"')
                referenced_values = [item[0] for item in c.fetchall()]
                if int(new_value) not in referenced_values:
                    return 3
            c.execute(f'UPDATE public."{table_name}" SET {column} = %s WHERE {identifier_column} = %s',
                    (new_value, id))
            self.conn.commit()
            print(f"Changed lines: {c.rowcount}")
            return 1
        except Exception as e:
            self.conn.rollback()
            print(e)
        return 0

    def delete_data(self, table_name, id):
        try:
            c = self.conn.cursor()
            c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            tables = [item[0] for item in c.fetchall()]

            for current_table in tables:
                if current_table == table_name:
                    continue

                c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (current_table,))
                column_names = [item[0] for item in c.fetchall()]
                for column_name in column_names:
                    if column_name == f'{table_name.lower()}_id':
                        c.execute(f'SELECT {column_name} FROM public."{current_table}"')
                        referenced_values = [item[0] for item in c.fetchall()]
                        if id in referenced_values:
                            return 0
            c.execute(f'DELETE FROM public."{table_name}" WHERE {table_name.lower()}_id = %s', (id,))
            self.conn.commit()
            return 1
        except Exception as e:
            self.conn.rollback()
            print(e)
        return 0

    def generate_data(self, table_name, count):
        try:
            c = self.conn.cursor()
            c.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s", (table_name,))
            columns_info = c.fetchall()
            id_column = f'{table_name.lower()}_id'
            for i in range(count):
                insert_query = f'INSERT INTO public."{table_name}" ('
                select_subquery = ""
                for column_info in columns_info:
                    column_name = column_info[0]
                    column_type = column_info[1]
                    if column_name == id_column:
                        c.execute(f'SELECT max("{id_column}") FROM public."{table_name}"')
                        max_id = c.fetchone()[0] or 0
                        select_subquery += f'{max_id + 1},'
                    elif column_name.endswith('_id'):
                        related_table_name = column_name[:-3]
                        c.execute(f'SELECT {related_table_name.lower()}_id FROM public."{related_table_name}" ORDER BY RANDOM() LIMIT 1')
                        related_id = c.fetchone()[0]
                        select_subquery += f'{related_id},'
                    elif column_type == 'integer':
                        select_subquery += f'trunc(random()*100)::INT,'
                    elif column_type == 'character varying':
                        select_subquery += f"'Text {column_name}',"
                    elif column_type == 'date':
                        select_subquery += "'2024-01-01',"
                    elif column_type == 'timestamp with time zone':
                        select_subquery += "'2024-01-01 08:30:00+03',"
                    else:
                        continue

                    insert_query += f'"{column_name}",'

                insert_query = insert_query.rstrip(',') + f') VALUES ({select_subquery[:-1]})'
                c.execute(insert_query)

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(e)
        return 0