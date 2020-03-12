def main():
    from wkr_serving.server import WKRServer
    from wkr_serving.server.helper import get_run_args
    with WKRServer(get_run_args()) as server:
        server.join()


def benchmark():
    from wkr_serving.server.benchmark import run_benchmark
    from wkr_serving.server.helper import get_run_args, get_benchmark_parser
    args = get_run_args(get_benchmark_parser)
    run_benchmark(args)


def terminate():
    from wkr_serving.server import WKRServer
    from wkr_serving.server.helper import get_run_args, get_shutdown_parser
    args = get_run_args(get_shutdown_parser)
    WKRServer.shutdown(args)
