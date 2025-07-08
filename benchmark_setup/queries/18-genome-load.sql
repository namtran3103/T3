COPY genome."ATT_CLASSES" FROM 'benchmark_setup/csvs/genome/ATT_CLASSES.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY genome."IMG_OBJ" FROM 'benchmark_setup/csvs/genome/IMG_OBJ.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY genome."IMG_OBJ_ATT" FROM 'benchmark_setup/csvs/genome/IMG_OBJ_ATT.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY genome."IMG_REL" FROM 'benchmark_setup/csvs/genome/IMG_REL.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY genome."OBJ_CLASSES" FROM 'benchmark_setup/csvs/genome/OBJ_CLASSES.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY genome."PRED_CLASSES" FROM 'benchmark_setup/csvs/genome/PRED_CLASSES.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
