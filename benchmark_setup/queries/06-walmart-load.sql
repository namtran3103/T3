COPY walmart."key" FROM 'benchmark_setup/csvs/walmart/key.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY walmart."station" FROM 'benchmark_setup/csvs/walmart/station.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY walmart."train" FROM 'benchmark_setup/csvs/walmart/train.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
