COPY fhnk."pripady" FROM 'benchmark_setup/csvs/fhnk/pripady.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY fhnk."vykony" FROM 'benchmark_setup/csvs/fhnk/vykony.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY fhnk."zup" FROM 'benchmark_setup/csvs/fhnk/zup.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
