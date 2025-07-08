#!/bin/bash
SQL=benchmark_setup/sql
DB=benchmark_setup/db/all.db
SCHEMATA=benchmark_setup/schemata/
QUERIES=benchmark_setup/queries/
mkdir -p benchmark_setup/db || exit
echo "" | $SQL -createdb $DB || exit
echo 'loading tpchSf1'
$SQL $DB $SCHEMATA/01-tpchSf1-schema.sql $QUERIES/01-tpchSf1-load.sql
echo 'loading tpchSf10'
$SQL $DB $SCHEMATA/01-tpchSf10-schema.sql $QUERIES/01-tpchSf10-load.sql
echo 'loading tpchSf100'
$SQL $DB $SCHEMATA/01-tpchSf100-schema.sql $QUERIES/01-tpchSf100-load.sql
echo 'loading tpcdsSf1'
$SQL $DB $SCHEMATA/02-tpcdsSf1-schema.sql $QUERIES/02-tpcdsSf1-load.sql
echo 'loading tpcdsSf10'
$SQL $DB $SCHEMATA/02-tpcdsSf10-schema.sql $QUERIES/02-tpcdsSf10-load.sql
echo 'loading tpcdsSf100'
$SQL $DB $SCHEMATA/02-tpcdsSf100-schema.sql $QUERIES/02-tpcdsSf100-load.sql
echo 'loading job'
$SQL $DB $SCHEMATA/03-job-schema.sql $QUERIES/03-job-load.sql
echo 'loading airline'
$SQL $DB $SCHEMATA/04-airline-schema.sql $QUERIES/04-airline-load.sql
echo 'loading ssb'
$SQL $DB $SCHEMATA/05-ssb-schema.sql $QUERIES/05-ssb-load.sql
echo 'loading walmart'
$SQL $DB $SCHEMATA/06-walmart-schema.sql $QUERIES/06-walmart-load.sql
echo 'loading financial'
$SQL $DB $SCHEMATA/07-financial-schema.sql $QUERIES/07-financial-load.sql
echo 'loading basketball'
$SQL $DB $SCHEMATA/08-basketball-schema.sql $QUERIES/08-basketball-load.sql
echo 'loading accident'
$SQL $DB $SCHEMATA/09-accident-schema.sql $QUERIES/09-accident-load.sql
echo 'loading movielens'
$SQL $DB $SCHEMATA/10-movielens-schema.sql $QUERIES/10-movielens-load.sql
echo 'loading baseball'
$SQL $DB $SCHEMATA/11-baseball-schema.sql $QUERIES/11-baseball-load.sql
echo 'loading hepatitis'
$SQL $DB $SCHEMATA/12-hepatitis-schema.sql $QUERIES/12-hepatitis-load.sql
echo 'loading tournament'
$SQL $DB $SCHEMATA/13-tournament-schema.sql $QUERIES/13-tournament-load.sql
echo 'loading credit'
$SQL $DB $SCHEMATA/14-credit-schema.sql $QUERIES/14-credit-load.sql
echo 'loading employee'
$SQL $DB $SCHEMATA/15-employee-schema.sql $QUERIES/15-employee-load.sql
echo 'loading consumer'
$SQL $DB $SCHEMATA/16-consumer-schema.sql $QUERIES/16-consumer-load.sql
echo 'loading geneea'
$SQL $DB $SCHEMATA/17-geneea-schema.sql $QUERIES/17-geneea-load.sql
echo 'loading genome'
$SQL $DB $SCHEMATA/18-genome-schema.sql $QUERIES/18-genome-load.sql
echo 'loading carcinogenesis'
$SQL $DB $SCHEMATA/19-carcinogenesis-schema.sql $QUERIES/19-carcinogenesis-load.sql
echo 'loading seznam'
$SQL $DB $SCHEMATA/20-seznam-schema.sql $QUERIES/20-seznam-load.sql
echo 'loading fhnk'
$SQL $DB $SCHEMATA/21-fhnk-schema.sql $QUERIES/21-fhnk-load.sql
