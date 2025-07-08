import argparse
import os
import subprocess
import tarfile
from pathlib import Path

import lz4.frame
from lleaves import lleaves

from dp.BenchmarkDPResult import benchmark_dp_queries
from dp.dp_to_sql import convert_all_dp_results_to_sql
from src.benchmark_runner import benchmark
from src.benchmark_setup import download_csvs, create_tpc_data, download_t3_file, load_csvs_to_db
from src.evaluation import QueryEstimationCache
from src.figures.acc_comparison import comparison_plot
from src.figures.acc_comparison_zero_shot import comparison_zero_shot_plot
from src.figures.accuracy_table import write_accuracy_table
from src.figures.cardinality_degradation import make_card_degen_figure
from src.figures.clean_benchmarks import clean_benchmark_figure
from src.figures.error_by_query_type import get_error_by_query_hist
from src.figures.error_histogram import get_error_histogram
from src.figures.est_card_acc import eval_card_est
from src.figures.infra import get_figure_path, set_figure_path, set_figure_format, set_use_latex
from src.figures.latency_accuracy import latency_acc_figure
from src.figures.latency_scaling import latency_scaling_figure
from src.figures.per_database_acc import create_per_db_figure
from src.figures.per_tuple import per_tuple_prediction_figure
from src.figures.query_runtimes import get_benchmark_variance
from src.server import start_webserver_new, kill_webserver_new
from src.train import optimize_all
from src.util import rm_rec


def download_bench_data():
    if not Path("data").exists():
        download_t3_file("benchdata.tar.lz4")
        data_path = "downloaded_data/benchdata.tar"
        with open("downloaded_data/benchdata.tar.lz4", "rb") as data:
            decompressed_data = lz4.frame.decompress(data.read())
        with open(data_path, "wb") as tar:
            tar.write(decompressed_data)
        with tarfile.open(data_path, "r") as tar:
            tar.extractall("./")


def reproduce_bench_data():
    print("Starting db server")
    start_webserver_new()
    print("Benchmarking (This may take a while)")
    benchmark()
    print("Shutting down webserver")
    kill_webserver_new()


def download_join_order_data():
    download_t3_file("cardinality_oracle.tar")
    download_t3_file("webserver.lz4")
    download_t3_file("lightgbm.tar.lz4")


def create_db_files():
    download_csvs()
    create_tpc_data()
    load_csvs_to_db()


def extract_webserver():
    if not Path("webserver").exists():
        download_t3_file("webserver.lz4")
        with open("downloaded_data/webserver.lz4", "rb") as server:
            decompressed_data = lz4.frame.decompress(server.read())
        with open("webserver", "wb") as server:
            server.write(decompressed_data)
        subprocess.run(["chmod", "+x", "webserver"], cwd=os.getcwd())

def extract_lightGBM():
    if not Path("dp/LightGBM").exists():
        lgbm_path = "downloaded_data/lightgbm.tar"
        with open("downloaded_data/lightgbm.tar.lz4", "rb") as lgbm:
            decompressed_data = lz4.frame.decompress(lgbm.read())
        with open(lgbm_path, "wb") as tar:
            tar.write(decompressed_data)
        with tarfile.open(lgbm_path, "r") as tar:
            tar.extractall("dp/")
    if not Path("dp/LightGBM").exists():
        download_t3_file("lightgbm.tar.lz4")



def run_join_order_experiment(model, benchmark_results: bool):
    print("Downloading join order experiment data")
    download_join_order_data()

    print("Compiling the tree model")
    model.tree.save_model("model.txt")
    llvm_tree = lleaves.Model(model_file="model.txt")
    Path("./lleaves.o").unlink(missing_ok=True)
    llvm_tree.compile(cache="./lleaves.o")

    print("Unpacking required data")
    cardinality_oracle_path = Path("dp/")
    cardinality_oracle_path.mkdir(parents=True, exist_ok=True)
    with tarfile.open("downloaded_data/cardinality_oracle.tar", "r") as tar:
        tar.extractall(cardinality_oracle_path)

    extract_webserver()

    print("Building LightGBM (C++ version)")
    print(" extracting...")
    extract_lightGBM()
    print(" compiling...")
    subprocess.run(["bash", "dp/compile_lightgbm.sh"], cwd=os.getcwd(), stdout=subprocess.PIPE)

    print("Compiling C++ benchmark")
    subprocess.run(["bash", "dp/compile.sh"], cwd=os.getcwd(), stdout=subprocess.PIPE)

    print("Running C++ benchmark")
    subprocess.run(["dp/bin/dp_experiment"], cwd=os.getcwd())

    if benchmark_results:
        print("Generating new SQL queries")
        convert_all_dp_results_to_sql()

        print("Starting db server")
        start_webserver_new()
        print("Benchmarking generated SQL queries")
        benchmark_dp_queries()
        kill_webserver_new()


def reset():
    print("Cleaning intermediate files")
    for path in [
        Path("./data"),
        Path("./benchmark_setup/db/"),
        Path("./dp/bin/"),
        Path("./dp/cout_plans.txt"),
        Path("./dp/cout_plans.sql"),
        Path("./dp/model_plans.txt"),
        Path("./dp/model_plans.sql"),
        Path("./dp/query_names.txt"),
        Path("./webserver"),
        Path("./lleaves.o"),
        Path("./model.txt"),
    ]:
        rm_rec(path)


def main():
    parser = argparse.ArgumentParser(description="Master script to re-create all figures of the T3 paper.")
    parser.add_argument("--runcpp", "-c", action="store_true", help="Run C++ experiments. (This is not portable)")
    parser.add_argument(
        "--benchjob",
        "-j",
        action="store_true",
        help="Benchmark job (This is not portable and requires the download of over 20GB of data)",
    )
    parser.add_argument(
        "--runbench",
        "-b",
        action="store_true",
        help="Reproduce the benchmarks. (This is not portable, can take hours, and requires the download of over 20GB of data)",
    )
    parser.add_argument(
        "--reset",
        "-r",
        action="store_true",
        help="Reset local data. (This might be helpful when switching between dockerized and regular execution)",
    )

    args = parser.parse_args()

    run_cpp: bool = args.runcpp
    run_bench: bool = args.runbench
    benchmark_job: bool = args.benchjob
    do_reset: bool = args.reset

    if do_reset:
        reset()

    if run_bench or benchmark_job:
        print("Setup database")
        create_db_files()
        extract_webserver()
    if run_bench:
        print("Reproducing benchmark data")
        reproduce_bench_data()
    else:
        print("Downloading benchmark data")
        download_bench_data()

    print("Training models for exact and predicted cardinalities")
    exact_model = optimize_all(False)
    pred_model = optimize_all(True)
    print("Evaluating models")
    exact_exact_eval = QueryEstimationCache(exact_model, False)
    exact_pred_eval = QueryEstimationCache(exact_model, True)
    pred_pred_eval = QueryEstimationCache(pred_model, True)

    set_figure_path("./figure_output")
    set_figure_format("pdf")
    set_use_latex(False)
    Path(get_figure_path()).mkdir(parents=True, exist_ok=True)
    print(f"Storing figures in {get_figure_path().absolute()}")

    print("Creating latency accuracy overview")
    latency_acc_figure(pred_pred_eval)
    print("Creating query runtime figure")
    get_benchmark_variance()
    print("Creating accuracy table")
    write_accuracy_table(exact_exact_eval)
    print("Creating accuracy histogram")
    get_error_histogram(exact_exact_eval)
    print("Creating per query accuracy figure")
    get_error_by_query_hist(exact_exact_eval)
    print("Creating per database instance accuracy figure (requires re-training)")
    create_per_db_figure()
    print("Creating cardinality comparison figure")
    eval_card_est([exact_exact_eval, exact_pred_eval, pred_pred_eval])
    print("Creating accuracy comparison figure")
    comparison_plot(pred_pred_eval)
    print("Creating accuracy comparison to zero shot figure (requires re-training)")
    comparison_zero_shot_plot()
    print("Creating ablation study figure (requires re-training)")
    per_tuple_prediction_figure()
    print("Creating clean benchmark figure (requires re-training)")
    clean_benchmark_figure()
    print("Creating cardinality degradation figure (might take a while)")
    make_card_degen_figure()

    if run_cpp:
        print("Running join order microbenchmark")
        run_join_order_experiment(exact_model, benchmark_job)
        print("Creating latency scaling figure")
        latency_scaling_figure()


if __name__ == "__main__":
    main()
