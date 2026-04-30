# Reproducing my results:


Python: 3.11.7, install dependencies from requirements.txt (I used Conda)

pip install -r requirements.txt

Go to the results folder

results/fig_... are to reproduce the figures
results/models contain the pre-trained models

They can be reproduced by running the scripts in results/mdoels/0_reproduction
Then, compare results with the pre-trained results using the .txt files
However, retraining can take a very long time for all models (for me multiple hours)

src/zeroshot + src/pg_features contains my added code, the rest is taken from T3 repo