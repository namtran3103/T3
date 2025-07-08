COPY ssb.customer FROM 'benchmark_setup/csvs/ssb/customer.csv' DELIMITER '|' QUOTE '"' ESCAPE '\' NULL '' CSV HEADER;
COPY ssb.part FROM 'benchmark_setup/csvs/ssb/part.csv' DELIMITER '|' QUOTE '"' ESCAPE '\' NULL '' CSV HEADER;
COPY ssb.supplier FROM 'benchmark_setup/csvs/ssb/supplier.csv' DELIMITER '|' QUOTE '"' ESCAPE '\' NULL '' CSV HEADER;
COPY ssb.lineorder FROM 'benchmark_setup/csvs/ssb/lineorder.csv' DELIMITER '|' QUOTE '"' ESCAPE '\' NULL '' CSV HEADER;
COPY ssb.dim_date FROM 'benchmark_setup/csvs/ssb/dim_date.csv' DELIMITER '|' QUOTE '"' ESCAPE '\' NULL '' CSV HEADER;
