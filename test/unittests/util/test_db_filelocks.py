import cProfile
import os
import pstats
import random
import shutil
import string
import tempfile
import time
from multiprocessing.pool import ThreadPool
from pstats import SortKey

from conan.api.model import RecipeReference, PkgReference
from conan.internal.cache.db.cache_database import CacheDatabase
from conan.internal.errors import ConanReferenceDoesNotExistInDB

tmpf = os.path.join(tempfile.gettempdir(), "conan_test", "dbfilelocks")
datafile = os.path.join(tmpf, "data.sqlite")


def _mydbproc(db):
    letters = string.ascii_lowercase
    pkg_name = ''.join(random.choice(letters) for i in range(15))
    for i in range(10):
        # db.list_references()
        ref = RecipeReference.loads(f"{pkg_name}/0.{i}#rev1%1")
        path = f"/random/path/{pkg_name}/{i}/folder"
        db.create_recipe(path, ref)

        pref = PkgReference(ref, "1234", "rev2", 123)
        path = f"/random/path/{pkg_name}/binary/{i}/folder"
        build_id = "12345"
        db.create_package(path, pref, build_id)
        # time.sleep(0.001)


def test_simple_mutex():
    shutil.rmtree(tmpf, ignore_errors=True)
    os.makedirs(os.path.dirname(datafile), exist_ok=True)

    pr = cProfile.Profile()
    pr.enable()
    db = CacheDatabase(datafile)
    num_threads = 10
    thread_pool = ThreadPool(num_threads)
    thread_pool.map(_mydbproc, [db] * num_threads)
    thread_pool.close()
    thread_pool.join()

    pr.disable()

    sortby = SortKey.CUMULATIVE
    ps = pstats.Stats(pr).sort_stats(sortby)
    ps.print_stats()


"""
ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      103    0.000    0.000 1402.859   13.620 C:\ws\Python\Python312\Lib\threading.py:1117(join)
20829/522    0.772    0.000 1402.858    2.687 {method 'acquire' of '_thread.lock' objects}
      203    0.000    0.000 1402.856    6.911 C:\ws\Python\Python312\Lib\threading.py:1155(_wait_for_tstate_lock)
        1    0.000    0.000  350.750  350.750 C:\ws\Python\Python312\Lib\multiprocessing\pool.py:659(join)
    103/1    0.000    0.000  350.741  350.741 C:\ws\Python\Python312\Lib\threading.py:1018(_bootstrap)
    103/1    0.000    0.000  350.741  350.741 C:\ws\Python\Python312\Lib\threading.py:1058(_bootstrap_inner)

ncalls  tottime  percall  cumtime  percall filename:lineno(function)
       13    0.000    0.000    9.196    0.707 C:\ws\Python\Python312\Lib\threading.py:1117(join)
   309/72    0.006    0.000    9.192    0.128 {method 'acquire' of '_thread.lock' objects}
       23    0.000    0.000    9.192    0.400 C:\ws\Python\Python312\Lib\threading.py:1155(_wait_for_tstate_lock)
    100/3    0.001    0.000    4.543    1.514 C:\Users\Diego\conanws\conan\conan\internal\cache\db\cache_database.py:83(create_recipe)
    100/3    0.003    0.000    4.543    1.514 C:\Users\Diego\conanws\conan\conan\internal\cache\db\recipes_table.py:39(create)
        1    0.000    0.000    2.305    2.305 C:\ws\Python\Python312\Lib\multiprocessing\pool.py:659(join)
"""
