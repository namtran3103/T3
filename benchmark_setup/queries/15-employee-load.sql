COPY employee."departments" FROM 'benchmark_setup/csvs/employee/departments.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY employee."dept_emp" FROM 'benchmark_setup/csvs/employee/dept_emp.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY employee."dept_manager" FROM 'benchmark_setup/csvs/employee/dept_manager.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY employee."employees" FROM 'benchmark_setup/csvs/employee/employees.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY employee."salaries" FROM 'benchmark_setup/csvs/employee/salaries.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY employee."titles" FROM 'benchmark_setup/csvs/employee/titles.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
