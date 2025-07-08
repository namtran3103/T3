COPY consumer."EXPENDITURES" FROM 'benchmark_setup/csvs/consumer/EXPENDITURES.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY consumer."HOUSEHOLDS" FROM 'benchmark_setup/csvs/consumer/HOUSEHOLDS.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY consumer."HOUSEHOLD_MEMBERS" FROM 'benchmark_setup/csvs/consumer/HOUSEHOLD_MEMBERS.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
