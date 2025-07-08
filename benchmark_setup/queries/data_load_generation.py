import os
import re

load_args = {
    "airline": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL '' CSV HEADER",
    "ssb": "DELIMITER '|' QUOTE '\"' ESCAPE '\\' NULL '' CSV HEADER",
    "walmart": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "financial": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "basketball": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "accident": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "movielens": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "baseball": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "hepatitis": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "tournament": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "credit": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "employee": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "consumer": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "geneea": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "genome": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "carcinogenesis": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "seznam": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
    "fhnk": "DELIMITER '\t' QUOTE '\"' ESCAPE '\\' NULL 'NULL' CSV HEADER",
}


# Function to generate SQL file for copying data from CSV to table
def generate_sql(schema_file):
    create_table_statements = ["create table", "CREATE TABLE"]
    schema_name = ""
    table_names = []
    commands = []
    # Read the schema file
    with open(schema_file, "r") as schema:
        for line in schema:
            line = line.strip()
            match = re.search(r"\bcreate\s+schema\s+(\w+);", line, re.IGNORECASE)
            if match:
                schema_name = match.group(1)
            # Extract table name and CSV file path from the schema file
            for stmt in create_table_statements:
                if line.startswith(stmt):
                    line = line[len(stmt) :].strip()
                    table_name = line.split()[0]
                    table_names.append(table_name)

    for table_name in table_names:
        # Generate the SQL command
        stripped_table_name = "".join(table_name.split(".")[1:]).strip('"')
        current_load_args = " " + load_args[schema_name] if schema_name in load_args else ""
        sql_command = f"COPY {table_name} FROM 'benchmark_setups/csvs/{schema_name}/{stripped_table_name}.csv'{current_load_args};"
        commands.append(sql_command)

    return commands


def main():
    # Directory containing schema files
    schema_directory = "benchmark_setup/schemata"

    # Directory where SQL files will be saved
    sql_directory = "benchmark_setup/queries"

    # Iterate through schema files in the directory
    files = [file for file in os.listdir(schema_directory)]
    files.sort()
    # files = reversed(files)
    for schema_file in files:
        if schema_file.endswith("-schema.sql"):
            print(schema_file)
            # Generate SQL command
            commands = generate_sql(os.path.join(schema_directory, schema_file))
            print("\n".join(commands))
            print()
            # # Create an SQL file with the same name as the schema file
            # sql_file = os.path.join(sql_directory, schema_file.replace("-schema.sql", ".sql"))
            # with open(sql_file, "w") as sql:
            #     sql.write(sql_command)

            # print(f"Generated SQL file: {sql_file}")

    print("SQL file generation complete.")


if __name__ == "__main__":
    main()
