COPY seznam."client" FROM 'benchmark_setup/csvs/seznam/client.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY seznam."dobito" FROM 'benchmark_setup/csvs/seznam/dobito.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY seznam."probehnuto" FROM 'benchmark_setup/csvs/seznam/probehnuto.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY seznam."probehnuto_mimo_penezenku" FROM 'benchmark_setup/csvs/seznam/probehnuto_mimo_penezenku.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
