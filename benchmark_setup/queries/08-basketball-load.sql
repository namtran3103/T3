COPY basketball."awards_coaches" FROM 'benchmark_setup/csvs/basketball/awards_coaches.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY basketball."awards_players" FROM 'benchmark_setup/csvs/basketball/awards_players.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY basketball."coaches" FROM 'benchmark_setup/csvs/basketball/coaches.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY basketball."draft" FROM 'benchmark_setup/csvs/basketball/draft.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY basketball."player_allstar" FROM 'benchmark_setup/csvs/basketball/player_allstar.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY basketball."players" FROM 'benchmark_setup/csvs/basketball/players.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY basketball."players_teams" FROM 'benchmark_setup/csvs/basketball/players_teams.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY basketball."series_post" FROM 'benchmark_setup/csvs/basketball/series_post.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;
COPY basketball."teams" FROM 'benchmark_setup/csvs/basketball/teams.csv' DELIMITER '	' QUOTE '"' ESCAPE '\' NULL 'NULL' CSV HEADER;

