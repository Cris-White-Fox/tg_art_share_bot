import time

TIMERS = {}


def timers_view():
    return {
        func_name: {
            "count": len(timer),
            "median_time": sorted(timer)[len(timer)//2],
            "worst 10": [round(t, 3) for t in sorted(timer, reverse=True)[:10]],
        } for func_name, timer in TIMERS.items()
    }


def timeit(func):
    def inner(*args, **kwargs):
        global TIMERS
        start = time.time()

        result = func(*args, **kwargs)

        timer = time.time() - start
        TIMERS[str(func)] = [timer] + TIMERS.get(str(func), [])[:1000]
        print(timers_view())
        return result
    return inner