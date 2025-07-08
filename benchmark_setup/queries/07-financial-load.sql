COPY financial."account" FROM 'benchmark_setup/csvs/financial/account.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY financial."card" FROM 'benchmark_setup/csvs/financial/card.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY financial."client" FROM 'benchmark_setup/csvs/financial/client.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY financial."disp" FROM 'benchmark_setup/csvs/financial/disp.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY financial."district" FROM 'benchmark_setup/csvs/financial/district.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY financial."loan" FROM 'benchmark_setup/csvs/financial/loan.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY financial."order" FROM 'benchmark_setup/csvs/financial/order.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY financial."trans" FROM 'benchmark_setup/csvs/financial/trans.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
