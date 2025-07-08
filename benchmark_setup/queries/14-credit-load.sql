COPY credit."category" FROM 'benchmark_setup/csvs/credit/category.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY credit."charge" FROM 'benchmark_setup/csvs/credit/charge.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY credit."corporation" FROM 'benchmark_setup/csvs/credit/corporation.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY credit."member" FROM 'benchmark_setup/csvs/credit/member.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY credit."payment" FROM 'benchmark_setup/csvs/credit/payment.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY credit."provider" FROM 'benchmark_setup/csvs/credit/provider.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY credit."region" FROM 'benchmark_setup/csvs/credit/region.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY credit."statement" FROM 'benchmark_setup/csvs/credit/statement.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
