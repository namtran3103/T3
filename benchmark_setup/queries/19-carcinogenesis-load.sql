COPY carcinogenesis."atom" FROM 'benchmark_setup/csvs/carcinogenesis/atom.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY carcinogenesis."canc" FROM 'benchmark_setup/csvs/carcinogenesis/canc.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY carcinogenesis."sbond_1" FROM 'benchmark_setup/csvs/carcinogenesis/sbond_1.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY carcinogenesis."sbond_2" FROM 'benchmark_setup/csvs/carcinogenesis/sbond_2.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY carcinogenesis."sbond_3" FROM 'benchmark_setup/csvs/carcinogenesis/sbond_3.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY carcinogenesis."sbond_7" FROM 'benchmark_setup/csvs/carcinogenesis/sbond_7.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
