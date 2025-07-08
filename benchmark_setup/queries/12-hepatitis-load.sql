COPY hepatitis."Bio" FROM 'benchmark_setup/csvs/hepatitis/Bio.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY hepatitis."dispat" FROM 'benchmark_setup/csvs/hepatitis/dispat.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY hepatitis."indis" FROM 'benchmark_setup/csvs/hepatitis/indis.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY hepatitis."inf" FROM 'benchmark_setup/csvs/hepatitis/inf.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY hepatitis."rel11" FROM 'benchmark_setup/csvs/hepatitis/rel11.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY hepatitis."rel12" FROM 'benchmark_setup/csvs/hepatitis/rel12.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY hepatitis."rel13" FROM 'benchmark_setup/csvs/hepatitis/rel13.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
