COPY movielens."actors" FROM 'benchmark_setup/csvs/movielens/actors.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY movielens."directors" FROM 'benchmark_setup/csvs/movielens/directors.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY movielens."movies" FROM 'benchmark_setup/csvs/movielens/movies.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY movielens."movies2actors" FROM 'benchmark_setup/csvs/movielens/movies2actors.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY movielens."movies2directors" FROM 'benchmark_setup/csvs/movielens/movies2directors.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY movielens."u2base" FROM 'benchmark_setup/csvs/movielens/u2base.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY movielens."users" FROM 'benchmark_setup/csvs/movielens/users.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
