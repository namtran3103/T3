COPY accident."nesreca" FROM 'benchmark_setup/csvs/accident/nesreca.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY accident."oseba" FROM 'benchmark_setup/csvs/accident/oseba.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY accident."upravna_enota" FROM 'benchmark_setup/csvs/accident/upravna_enota.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
